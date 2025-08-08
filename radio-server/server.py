import asyncio
import json
import os
import re
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv
load_dotenv(".env")
from scrobble import find_track_details_and_scrobble
from typing import Optional, Tuple

# --- Configuration ---
# !!! IMPORTANT: Replace this with your speaker's MAC address !!!
BLUETOOTH_DEVICE_MAC = os.getenv("JBL_GO_MAC_ADDRESS")
STATIONS_FILE = os.getenv("STATIONS_FILE", "fm_stations.json")
BLUETOOTH_SCRIPT_PATH = os.getenv("BLUETOOTH_SCRIPT_PATH", "./bluetooth_speaker_setup.sh")

# --- Global State ---
# We use global state to keep track of the music player process.
# This is simple and fine for a single-user Pi Zero application.
playback_process = None
current_station_info = { "name": None, "link": None }
scrobbling_task = None
current_track_info = {"title": None, "artist": None, "album": None}

# --- Helper Functions ---
def load_stations():
    """Loads station data from the JSON file."""
    try:
        with open(STATIONS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {STATIONS_FILE} not found.")
        return {}

stations_data = load_stations()

def extract_icy_meta(icy_meta_line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract title and artist from ICY-META line.
    
    Example input: 
        ICY-META: StreamTitle='Barry Can't Swim - The Person You’d Like To Be';StreamUrl='http://img.radioparadise.com/covers/l/24109.jpg';
    
    Args:
        icy_meta_line: Line containing ICY-META information
        
    Returns:
        Tuple of (title, artist) or (None, None) if extraction fails
    """
    try:
        # Extract StreamTitle value using a non-greedy regex to handle internal quotes
        stream_title_match = re.search(r"StreamTitle='(.*?)';", icy_meta_line)
        if not stream_title_match:
            return None, None
            
        stream_title = stream_title_match.group(1).strip().replace("'", "")
        
        # Common patterns for artist - title separation
        separators = [' - ', ' – ', ' — ', ' | ', ': ']
        
        for separator in separators:
            if separator in stream_title:
                parts = stream_title.split(separator, 1)
                if len(parts) == 2:
                    artist = parts[0].strip()
                    title = parts[1].strip()
                    return title, artist
        
        # If no separator found, return the whole string as title and None for artist
        return stream_title.strip(), None
    except Exception as e:
        print(f"Error extracting ICY meta: {e}")
        return None, None

async def monitor_mpg123_stdout_and_stderr() -> None:
    """
    Monitor mpg123 stdout and stderr for ICY-META information and update current track info.
    """
    global playback_process, current_track_info
    
    if not playback_process:
        return
        
    print("Starting mpg123 output monitoring...")
    
    async def read_stream(stream, stream_name):
        """Read from a stream and look for ICY-META lines"""
        global playback_process, current_track_info
        try:
            while playback_process and playback_process.returncode is None:
                line = await stream.readline()
                if not line:
                    break
                    
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                # Print all output for debugging
                if line_str:
                    print(f"[{stream_name}] {line_str}")
                
                # Look for ICY-META lines
                if line_str.startswith('ICY-META:') and 'StreamTitle=' in line_str:
                    print(f"Found ICY-META in {stream_name}: {line_str}")
                    
                    title, artist = extract_icy_meta(line_str)
                    if title or artist:
                        # Update global track info
                        current_track_info = {
                            "title": title,
                            "artist": artist, 
                            "album": None  # ICY-META typically doesn't include album info
                        }
                        print(f"Updated track info - Artist: {artist}, Title: {title}")
                        
        except asyncio.CancelledError:
            print(f"mpg123 {stream_name} monitoring cancelled")
            raise
        except Exception as e:
            print(f"Error monitoring mpg123 {stream_name}: {e}")
    
    try:
        # Monitor both stdout and stderr concurrently
        tasks = []
        if playback_process.stdout:
            tasks.append(asyncio.create_task(read_stream(playback_process.stdout, "stdout")))
        if playback_process.stderr:
            tasks.append(asyncio.create_task(read_stream(playback_process.stderr, "stderr")))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            print("No stdout or stderr available from mpg123 process")
            
    except asyncio.CancelledError:
        print("mpg123 output monitoring cancelled")
        raise
    except Exception as e:
        print(f"Error in mpg123 output monitoring: {e}")

async def scrobbling_worker(station_name) -> None:
    """
    Worker function that runs the scrobbling process every 60 seconds.
    """
    print(f"Starting scrobbling worker for station: {station_name}")
    
    try:
        while True:
            try:
                # Get current track info
                title = current_track_info.get("title")
                artist = current_track_info.get("artist") 
                album = current_track_info.get("album")
                
                # Call the scrobbling function if track details available
                if title is not None and artist is not None:
                    # Note: If find_track_details_and_scrobble is synchronous, we run it in a thread pool
                    await asyncio.get_event_loop().run_in_executor(
                        None, find_track_details_and_scrobble, station_name, title, artist, album
                    )
                    print(f"Scrobbling track for station: {station_name} - {artist} - {title}")
            except Exception as e:
                print(f"Error during scrobbling: {e}")
            
            # Wait 30 seconds before next scrobble attempt
            await asyncio.sleep(30)
            
    except asyncio.CancelledError:
        print(f"Scrobbling worker cancelled for station: {station_name}")
        raise

async def stop_playback_logic() -> None:
    """Stops the mpg123 process and scrobbling task if they're running."""
    global playback_process, current_station_info, scrobbling_task, current_track_info
    
    # Stop the scrobbling task first
    if scrobbling_task and not scrobbling_task.done():
        print("Stopping scrobbling task...")
        scrobbling_task.cancel()
        try:
            await scrobbling_task
        except asyncio.CancelledError:
            print("Scrobbling task cancelled successfully.")
        scrobbling_task = None
    
    # Stop the playback process
    if playback_process and playback_process.returncode is None:
        print("Stopping current playback...")
        playback_process.terminate()
        await playback_process.wait()
        print("Playback stopped.")
    
    playback_process = None
    current_station_info = {"name": None, "link": None}
    current_track_info = {"title": None, "artist": None, "album": None}

async def get_status(request):
    """Checks Bluetooth and playback status using the management script."""
    is_connected = False
    bluetooth_error = None

    try:
        # Construct the command to call the bash script with the --status argument
        # This matches the script's usage: ./bluetooth_speaker_setup.sh --status [MAC_ADDRESS]
        cmd = f'{BLUETOOTH_SCRIPT_PATH} --status {BLUETOOTH_DEVICE_MAC}'
        
        # Use asyncio.create_subprocess_shell for asynchronous execution
        # Capture stdout and stderr for parsing the status
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for the process to complete and capture its output
        stdout, stderr = await proc.communicate()

        stdout_decoded = stdout.decode().strip()
        stderr_decoded = stderr.decode().strip()

        # Log script output for debugging
        print(f"Bluetooth status script stdout:\n{stdout_decoded}")
        if stderr_decoded:
            print(f"Bluetooth status script stderr:\n{stderr_decoded}")

        # Check the return code of the script first
        if proc.returncode == 0:
            # Parse the output to determine connection status
            # ASSUMPTION: The script outputs "Connected: yes" or "Connected: no"
            if "Connected: yes" in stdout_decoded:
                is_connected = True
            elif "Connected: no" in stdout_decoded:
                is_connected = False
            else:
                # If the output doesn't match expected, assume not connected or an issue
                print(f"WARNING: Bluetooth status script output unrecognized: '{stdout_decoded}'")
                is_connected = False
                bluetooth_error = "Unrecognized status output from script."
        else:
            # If the script itself failed (non-zero exit code)
            bluetooth_error = f"Bluetooth script failed with return code {proc.returncode}. Stderr: {stderr_decoded}"
            print(f"ERROR: {bluetooth_error}")

    except FileNotFoundError:
        bluetooth_error = f"Bluetooth management script not found at {BLUETOOTH_SCRIPT_PATH}."
        print(f"CRITICAL ERROR: {bluetooth_error}")
    except Exception as e:
        bluetooth_error = f"An unexpected error occurred while checking Bluetooth status: {str(e)}"
        print(f"ERROR: {bluetooth_error}")

    is_playing = playback_process is not None and playback_process.returncode is None
    
    status = {
        "bluetooth_mac": BLUETOOTH_DEVICE_MAC,
        "bluetooth_connected": is_connected,
        "is_playing": is_playing,
        "station": current_station_info
    }
    
    if bluetooth_error:
        status["bluetooth_status_error"] = bluetooth_error

    return JSONResponse(status)

async def get_stations(request):
    """Returns the list of radio stations."""
    # Assuming stations_data is loaded globally
    return JSONResponse(stations_data)

async def connect_bluetooth(request):
    """Attempts to connect to the Bluetooth device using the management script."""
    print(f"Attempting to connect to {BLUETOOTH_DEVICE_MAC} using script: {BLUETOOTH_SCRIPT_PATH}")
    try:
        # Construct the command to call the bash script with the --connect argument
        # This matches the script's usage: ./bluetooth_speaker_setup.sh --connect MAC_ADDRESS
        cmd = f'{BLUETOOTH_SCRIPT_PATH} --connect {BLUETOOTH_DEVICE_MAC}'
        
        # Use asyncio.create_subprocess_shell for asynchronous execution
        # Capture stdout and stderr for better debugging and logging of the script's output
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for the process to complete and capture its output
        stdout, stderr = await proc.communicate()

        # Decode output for logging/display
        stdout_decoded = stdout.decode().strip()
        stderr_decoded = stderr.decode().strip()

        print(f"Bluetooth connect script stdout:\n{stdout_decoded}")
        if stderr_decoded:
            print(f"Bluetooth connect script stderr:\n{stderr_decoded}")
        
        # Check the return code of the script
        if proc.returncode == 0:
            print("Bluetooth connect command sent successfully via script.")
            return JSONResponse({"status": "success", "message": "Connection attempt sent via script."})
        else:
            # If the script returns a non-zero exit code, it indicates an error
            message = f"Bluetooth script failed with return code {proc.returncode}. Stderr: {stderr_decoded}"
            print(f"ERROR: {message}")
            return JSONResponse({"status": "error", "message": message}, status_code=500)

    except FileNotFoundError:
        # Handle cases where the script itself is not found at the specified path
        message = f"Bluetooth management script not found at {BLUETOOTH_SCRIPT_PATH}. Ensure the path is correct and the script exists and is executable."
        print(f"CRITICAL ERROR: {message}")
        return JSONResponse({"status": "error", "message": message}, status_code=500)
    except Exception as e:
        # Catch any other unexpected errors during subprocess creation or execution
        message = f"An unexpected error occurred while running the Bluetooth script: {str(e)}"
        print(f"ERROR: {message}")
        return JSONResponse({"status": "error", "message": message}, status_code=500)

async def play_station(request) -> JSONResponse:
    """Plays a selected station."""
    global playback_process, current_station_info, scrobbling_task
    
    # Stop any currently playing music first
    await stop_playback_logic()
    
    data = await request.json()
    station_name = data.get("name")
    station_link = data.get("link")

    if not station_link:
        return JSONResponse({"status": "error", "message": "Station link not provided."}, status_code=400)

    print(f"Starting playback for: {station_name}")
    
    # mpg123 -q (quiet) is essential to avoid verbose output
    if "mp3" in station_link:
        # Don't use -q flag for MP3 streams so we can capture ICY-META
        command = ["mpg123", "-o", "pulse", station_link]
    else:
        command = ["ffplay", "-nodisp", "-autoexit", station_link]
    
    print(f"Executing play command: {' '.join(command)}")
    
    try:
        # For mpg123 streams, we need to capture stdout and stderr
        if "mp3" in station_link:
            playback_process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # Start monitoring stdout/stderr for ICY-META
            asyncio.create_task(monitor_mpg123_stdout_and_stderr())
        else:
            # Use standard subprocess for other stations
            # Use asyncio.create_subprocess_exec for non-blocking command execution
            playback_process = await asyncio.create_subprocess_exec(*command)
        current_station_info = { "name": station_name, "link": station_link }
        
        # Start the scrobbling task
        scrobbling_task = asyncio.create_task(scrobbling_worker(station_name))
        print(f"Started scrobbling task for: {station_name}")
        return JSONResponse({"status": "success", "message": f"Playing {station_name}"})
    except Exception as e:
        print(f"Error starting playback: {e}")
        return JSONResponse({"status": "error", "message": f"Failed to start playback: {str(e)}"}, status_code=500)

async def stop_playback(request):
    """Stops the music."""
    await stop_playback_logic()
    return JSONResponse({"status": "success", "message": "Playback stopped."})

async def set_volume(request):
    """Sets the volume using amixer."""
    try:
        # Extract volume from path parameters
        volume = int(request.path_params["volume"])
        
        # Validate volume range
        if volume < 0 or volume > 100:
            return JSONResponse({"error": "Volume must be between 0 and 100", "status": "error"}, status_code=400)
        
        # Use amixer to set the volume
        cmd = ["amixer", "-D", "pulse", "sset", "Master", f"{volume}%"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print(f"Volume set to {volume}%")
            return JSONResponse({"status": "success", "message": f"Volume set to {volume}%", "volume": volume})
        else:
            error_msg = stderr.decode().strip()
            print(f"Failed to set volume: return code {process.returncode}, stderr: {error_msg}")
            return JSONResponse({"error": f"Failed to set volume: {error_msg}", "status": "error"}, status_code=500)
            
    except KeyError:
        return JSONResponse({"error": "Volume parameter missing from URL", "status": "error"}, status_code=400)
    except ValueError:
        return JSONResponse({"error": "Invalid volume value - must be an integer", "status": "error"}, status_code=400)
    except FileNotFoundError:
        print("amixer command not found")
        return JSONResponse({"error": "amixer not found", "status": "error"}, status_code=500)
    except Exception as e:
        print(f"Error setting volume: {str(e)}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)

async def current_volume(request):
    """Gets the current volume level using amixer."""
    try:
        cmd = ["amixer", "-D", "pulse", "get", "Master"]
        process = await asyncio.create_subprocess_exec(
            *cmd, 
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE  # Add stderr capture
        )
        stdout, stderr = await process.communicate()
        
        # Check if the command was successful
        if process.returncode != 0:
            print(f"amixer command failed with return code {process.returncode}")
            print(f"stderr: {stderr.decode().strip()}")
            return JSONResponse({"error": "Failed to get volume", "volume": None}, status_code=500)
        
        output = stdout.decode().strip()
        print(f"amixer output: {output}")  # Debug logging
        
        # Parse the output to find the volume level
        for line in output.splitlines():
            if "Mono:" in line or "Front Left:" in line:
                # Look for percentage in brackets like [50%]
                import re
                match = re.search(r'\[(\d+)%\]', line)
                if match:
                    volume = int(match.group(1))
                    return JSONResponse({"volume": volume})
                
                # Fallback: try the old parsing method
                parts = line.split()
                for part in parts:
                    if part.endswith('%'):
                        try:
                            volume = int(part[:-1])
                            return JSONResponse({"volume": volume})
                        except ValueError:
                            continue
        
        # If we couldn't parse the volume, return an error
        print(f"Could not parse volume from amixer output: {output}")
        return JSONResponse({"error": "Could not parse volume", "volume": None}, status_code=500)
        
    except FileNotFoundError:
        print("amixer command not found")
        return JSONResponse({"error": "amixer not found", "volume": None}, status_code=500)
    except Exception as e:
        print(f"Error getting current volume: {str(e)}")
        return JSONResponse({"error": str(e), "volume": None}, status_code=500)

async def homepage(request):
    """Serves the main HTML page."""
    try:
        with open("index.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(html_content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: index.html not found</h1>", status_code=500)

# --- App Setup ---
routes = [
    Route("/", endpoint=homepage),
    Route("/api/status", endpoint=get_status),
    Route("/api/stations", endpoint=get_stations),
    Route("/api/bluetooth/connect", endpoint=connect_bluetooth, methods=["POST"]),
    Route("/api/play", endpoint=play_station, methods=["POST"]),
    Route("/api/stop", endpoint=stop_playback, methods=["POST"]),
    Route("/api/volume/{volume:int}", endpoint=set_volume, methods=["POST"]),
    Route("/api/current_volume", endpoint=current_volume, methods=["GET"]),
]

app = Starlette(debug=False, routes=routes)
# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    # Check for placeholder MAC address
    if "XX:XX:XX:XX:XX:XX" in BLUETOOTH_DEVICE_MAC:
        print("\n" + "="*60)
        print("!!! WARNING: You have not set your Bluetooth MAC address. !!!")
        print(f"Please edit server.py and change the BLUETOOTH_DEVICE_MAC variable.")
        print("="*60 + "\n")
        
    # Host '0.0.0.0' makes it accessible on your local network
    uvicorn.run(app, host="0.0.0.0", port=8000)
