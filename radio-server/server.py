import asyncio
import json
import os
import re
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple, Any, Union
from asyncio.subprocess import Process

load_dotenv(".env")
from scrobble import find_track_details_and_scrobble

# Type aliases for better readability
StationInfo = Dict[str, Optional[str]]
TrackInfo = Dict[str, Optional[str]]
StatusResponse = Dict[str, Union[str, bool, StationInfo, TrackInfo]]

# --- Configuration ---
# !!! IMPORTANT: Replace this with your speaker's MAC address !!!
BLUETOOTH_DEVICE_MAC: Optional[str] = os.getenv("JBL_GO_MAC_ADDRESS")
STATIONS_FILE: str = os.getenv("STATIONS_FILE", "fm_stations.json")
BLUETOOTH_SCRIPT_PATH: str = os.getenv("BLUETOOTH_SCRIPT_PATH", "./bluetooth_speaker_setup.sh")

# --- Global State ---
# We use global state to keep track of the music player process.
# This is simple and fine for a single-user Pi Zero application.
playback_process: Optional[Process] = None
current_station_info: StationInfo = {"name": None, "link": None}
scrobbling_task: Optional[asyncio.Task] = None
current_track_info: TrackInfo = {"title": None, "artist": None, "album": None}

# --- Helper Functions ---
def load_stations() -> Dict[str, Any]:
    """
    Load radio station data from the JSON configuration file.
    
    Returns:
        Dict containing station names and their streaming URLs.
        Returns empty dict if file not found.
    
    Raises:
        json.JSONDecodeError: If the JSON file is malformed.
    """
    try:
        with open(STATIONS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {STATIONS_FILE} not found.")
        return {}

stations_data: Dict[str, Any] = load_stations()

def extract_icy_meta(icy_meta_line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract track title and artist from ICY-META stream information.
    
    ICY-META is a protocol used by internet radio streams to transmit 
    currently playing track information within the audio stream.
    
    Args:
        icy_meta_line: Raw ICY-META line from mpg123 output containing StreamTitle
        
    Returns:
        Tuple of (title, artist). Returns (None, None) if extraction fails.
        If no separator is found, returns (full_string, None).
    
    Example:
        >>> extract_icy_meta("ICY-META: StreamTitle='Artist Name - Song Title';")
        ('Song Title', 'Artist Name')
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
    Monitor mpg123 process output streams for ICY-META track information.
    
    This function continuously reads stdout and stderr from the mpg123 process
    to capture real-time track information from internet radio streams.
    Updates the global current_track_info when new track data is found.
    
    Raises:
        asyncio.CancelledError: When the monitoring task is cancelled.
    """
    global playback_process, current_track_info
    
    if not playback_process:
        return
        
    print("Starting mpg123 output monitoring...")
    
    async def read_stream(stream: asyncio.StreamReader, stream_name: str) -> None:
        """
        Read from a specific stream (stdout/stderr) and parse ICY-META lines.
        
        Args:
            stream: The asyncio StreamReader to monitor.
            stream_name: Human-readable name for logging ('stdout' or 'stderr').
        """
        global playback_process, current_track_info
        try:
            while playback_process and playback_process.returncode is None:
                line = await stream.readline()
                if not line:
                    break
                    
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                # Print all output for debugging
                # if line_str:
                #     print(f"[{stream_name}] {line_str}")
                
                # Look for ICY-META lines
                if line_str.startswith('ICY-META:') and 'StreamTitle=' in line_str:
                    print(f"Found ICY-META in {stream_name}: {line_str}")
                    
                    title, artist = extract_icy_meta(line_str)
                    
                    if (title or artist) and (title != stream_name or artist != stream_name):
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
        tasks: List[asyncio.Task] = []
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

async def scrobbling_worker(station_name: str) -> None:
    """
    Background worker that scrobbles currently playing tracks to Last.fm.
    
    Runs continuously, checking for track changes every 60 seconds and
    calling the scrobbling function when valid track information is available.
    
    Args:
        station_name: Name of the radio station for context in scrobbling.
        
    Raises:
        asyncio.CancelledError: When the scrobbling task is cancelled.
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
                if title is not None and artist is not None and artist != station_name and title != station_name:
                    # Note: If find_track_details_and_scrobble is synchronous, we run it in a thread pool
                    await asyncio.get_event_loop().run_in_executor(
                        None, find_track_details_and_scrobble, station_name, title, artist, album
                    )
                    print(f"Scrobbling track for station: {station_name} - {artist} - {title}")
            except Exception as e:
                print(f"Error during scrobbling: {e}")
            
            # Wait 60 seconds before next scrobble attempt
            await asyncio.sleep(60)
            
    except asyncio.CancelledError:
        print(f"Scrobbling worker cancelled for station: {station_name}")
        raise

async def stop_playback_logic() -> None:
    """
    Stop all playback-related processes and clean up global state.
    
    This function handles:
    - Cancelling the background scrobbling task
    - Terminating the mpg123/ffplay process
    - Resetting global state variables
    """
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

async def get_status(request: Request) -> JSONResponse:
    """
    Get comprehensive system status including Bluetooth, audio, and playback state.
    
    Checks:
    - Audio device connectivity via pactl
    - Bluetooth speaker connection status via external script
    - Current playback state and station information
    
    Args:
        request: Starlette Request object (unused but required for route handler).
        
    Returns:
        JSONResponse containing system status information.
    """
    audio_device_connected = False
    is_connected = False
    bluetooth_error: Optional[str] = None

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
        # print(f"Bluetooth status script stdout:\n{stdout_decoded}")
        # if stderr_decoded:
        #     print(f"Bluetooth status script stderr:\n{stderr_decoded}")

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

    # Check playback status
    is_playing = playback_process is not None and playback_process.returncode is None

    # Check audio device status
    audio_device_connected = await is_audio_device_connected()
    
    status: StatusResponse = {
        "audio_device_connected": audio_device_connected,
        "bluetooth_mac": str(BLUETOOTH_DEVICE_MAC),
        "bluetooth_connected": is_connected,
        "is_playing": is_playing,
        "station": current_station_info,
        "current_track_info": current_track_info
    }
    
    if bluetooth_error:
        status["bluetooth_status_error"] = bluetooth_error

    return JSONResponse(status)

async def is_audio_device_connected(device_name: Optional[str] = None) -> bool:
    """
    Check if an audio device is connected using PulseAudio's pactl command.
    
    Uses `pactl list sinks` to enumerate available audio output devices.
    Can check for a specific device by name or just verify any sink exists.
    
    Excludes dummy output devices (auto_null, "Dummy Output").
    
    Args:
        device_name: Optional device name/description pattern to search for.
                    If None, checks if any audio sink is available.
    
    Returns:
        True if the specified device is found or any sink exists, False otherwise.
    """
    try:
        # Run pactl list sinks command
        cmd = 'pactl list sinks'
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for the process to complete and capture its output
        stdout, stderr = await proc.communicate()
        stdout_decoded = stdout.decode().strip()
        stderr_decoded = stderr.decode().strip()
        
        # Split output into individual sink blocks
        sink_blocks = re.split(r'Sink #\d+', stdout_decoded)[1:]  # Skip empty first element
        
        non_dummy_sinks = []
        
        for sink in sink_blocks:
            # Check if this sink is a dummy output
            is_dummy = (re.search(r'Name:\s*auto_null', sink, re.IGNORECASE) or
                       re.search(r'Description:\s*Dummy Output', sink, re.IGNORECASE))
            
            if not is_dummy:
                non_dummy_sinks.append(sink)
                
        # If no specific device name provided, check if any non-dummy sinks exist
        if device_name is None:
            return len(non_dummy_sinks) > 0
        
        # Check if the specified device name appears in non-dummy sinks
        pattern = re.compile(re.escape(device_name), re.IGNORECASE)
        for sink in non_dummy_sinks:
            if pattern.search(sink):
                return True
        
        return False
    except FileNotFoundError:
        # pactl not found on system
        return False
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while checking connected audio devices: {str(e)}")
        return False

async def get_stations(request: Request) -> JSONResponse:
    """
    Return the list of available radio stations from the JSON configuration.
    
    Args:
        request: Starlette Request object (unused but required for route handler).
        
    Returns:
        JSONResponse containing the stations data loaded from the config file.
    """
    # Assuming stations_data is loaded globally
    return JSONResponse(stations_data)

async def connect_bluetooth(request: Request) -> JSONResponse:
    """
    Attempt to connect to the configured Bluetooth audio device.
    
    Uses an external bash script to handle Bluetooth connection logic.
    The script should support the --connect flag with a MAC address parameter.
    
    Args:
        request: Starlette Request object (unused but required for route handler).
        
    Returns:
        JSONResponse indicating success/failure of the connection attempt.
    """
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

async def play_station(request: Request) -> JSONResponse:
    """
    Start playback of a selected radio station.
    
    Stops any currently playing audio, then starts a new mpg123 or ffplay process
    for the requested station. Also starts background scrobbling for MP3 streams.
    
    Args:
        request: Starlette Request containing JSON data with 'name' and 'link' fields.
        
    Returns:
        JSONResponse indicating success/failure of playback initiation.
    """
    global playback_process, current_station_info, scrobbling_task
    
    # Stop any currently playing music first
    await stop_playback_logic()
    
    data = await request.json()
    station_name: Optional[str] = data.get("name")
    station_link: Optional[str] = data.get("link")

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
        current_station_info = {"name": station_name, "link": station_link}
        
        # Start the scrobbling task
        scrobbling_task = asyncio.create_task(scrobbling_worker(station_name or "Unknown Station"))
        print(f"Started scrobbling task for: {station_name}")
        return JSONResponse({"status": "success", "message": f"Playing {station_name}"})
    except Exception as e:
        print(f"Error starting playback: {e}")
        return JSONResponse({"status": "error", "message": f"Failed to start playback: {str(e)}"}, status_code=500)

async def stop_playback(request: Request) -> JSONResponse:
    """
    Stop all audio playback and related background tasks.
    
    Args:
        request: Starlette Request object (unused but required for route handler).
        
    Returns:
        JSONResponse confirming playback has been stopped.
    """
    await stop_playback_logic()
    return JSONResponse({"status": "success", "message": "Playback stopped."})

async def set_volume(request: Request) -> JSONResponse:
    """
    Set the system audio volume using amixer.
    
    Args:
        request: Starlette Request with volume level as a path parameter.
        
    Returns:
        JSONResponse indicating success/failure of volume adjustment.
    """
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

async def current_volume(request: Request) -> JSONResponse:
    """
    Get the current system audio volume level using amixer.
    
    Args:
        request: Starlette Request object (unused but required for route handler).
        
    Returns:
        JSONResponse containing the current volume percentage (0-100).
    """
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
        # print(f"amixer output: {output}")  # Debug logging
        
        # Parse the output to find the volume level
        for line in output.splitlines():
            if "Mono:" in line or "Front Left:" in line:
                # Look for percentage in brackets like [50%]
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

async def homepage(request: Request) -> HTMLResponse:
    """
    Serve the main HTML interface page.
    
    Args:
        request: Starlette Request object (unused but required for route handler).
        
    Returns:
        HTMLResponse containing the radio station interface HTML.
    """
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
    # Check for placeholder MAC address
    if BLUETOOTH_DEVICE_MAC and "XX:XX:XX:XX:XX:XX" in BLUETOOTH_DEVICE_MAC:
        print("\n" + "="*60)
        print("!!! WARNING: You have not set your Bluetooth MAC address. !!!")
        print(f"Please edit server.py and change the BLUETOOTH_DEVICE_MAC variable.")
        print("="*60 + "\n")
        
    # Host '0.0.0.0' makes it accessible on your local network
    uvicorn.run(app, host="0.0.0.0", port=8000)