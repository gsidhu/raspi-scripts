import asyncio
import json
import os
import subprocess
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
# !!! IMPORTANT: Replace this with your speaker's MAC address !!!
BLUETOOTH_DEVICE_MAC = os.getenv("JBL_GO_MAC_ADDRESS")
STATIONS_FILE = "fm_stations.json"

# --- Global State ---
# We use global state to keep track of the music player process.
# This is simple and fine for a single-user Pi Zero application.
playback_process = None
current_station_info = { "name": None, "link": None }

# --- Helper Functions ---
BLUETOOTH_SCRIPT_PATH = "./bluetooth_speaker_setup.sh" 

def load_stations():
    """Loads station data from the JSON file."""
    try:
        with open(STATIONS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {STATIONS_FILE} not found.")
        return {}

stations_data = load_stations()

async def stop_playback_logic():
    """Stops the mpg123 process if it's running."""
    global playback_process, current_station_info
    if playback_process and playback_process.returncode is None:
        print("Stopping current playback...")
        playback_process.terminate()
        await playback_process.wait()
        print("Playback stopped.")
    playback_process = None
    current_station_info = { "name": None, "link": None }

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

async def play_station(request):
    """Plays a selected station."""
    global playback_process, current_station_info
    
    # Stop any currently playing music first
    await stop_playback_logic()
    
    data = await request.json()
    station_name = data.get("name")
    station_link = data.get("link")

    if not station_link:
        return JSONResponse({"status": "error", "message": "Station link not provided."}, status_code=400)

    print(f"Starting playback for: {station_name}")
    
    # mpg123 -q (quiet) is essential to avoid verbose output
    command = ["mpg123", "-q", "-o", "pulse", station_link]
    
    print(f"Executing play command: {' '.join(command)}")
    
    # Use asyncio.create_subprocess_exec for non-blocking command execution
    playback_process = await asyncio.create_subprocess_exec(*command)
    current_station_info = { "name": station_name, "link": station_link }
    
    return JSONResponse({"status": "success", "message": f"Playing {station_name}"})

async def stop_playback(request):
    """Stops the music."""
    await stop_playback_logic()
    return JSONResponse({"status": "success", "message": "Playback stopped."})

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