# Pi Music Server

A web-app to stream internet radio stations.

Designed to run on a Raspberry Pi. Includes Bluetooth speaker integration for wireless audio output.

## Features

*   **Internet Radio Streaming**: Stream a curated list of internet radio stations.
*   **Web Interface**: Control playback, view station lists, and manage Bluetooth connections via a user-friendly web UI.
*   **Bluetooth Speaker Support**: Connect to and play audio through a Bluetooth speaker.
*   **Volume Control**: Adjust the system volume directly from the web interface.
*   **Systemd Service**: Runs as a background service for continuous operation.

## Setup Instructions

This guide assumes you have a Raspberry Pi with Raspberry Pi OS (or a similar Debian-based distribution) installed and configured with network access. Give it a [static IP address](../static_ip_address.md) if you want to access it reliably.

### 1. Prerequisites

**PulseAudio**

For audio output. Install and set it up with:
```bash
sudo apt update
sudo apt install pulseaudio pulseaudio-module-bluetooth pavucontrol bluez -y
pulseaudio --start
echo autospawn = yes >> ~/.config/pulse/client.conf # Creates the config file if it doesn't exist
sudo reboot # Important! Reboot to apply changes
```

**Bluetooth**

> [!NOTE]
> You have to connect your Bluetooth speaker to the Raspberry Pi manually the first time. After that, the server will handle reconnections automatically.

Make sure your speaker is in pairing mode, then run the following commands to connect it to your Pi:
```bash
bluetoothctl
# Inside bluetoothctl, run the following commands:
power on
agent on
default-agent
scan on
# Wait until your speaker shows up, then:
pair XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
# (Replace XX:XX:XX:XX:XX:XX with your speaker’s MAC address.)
```
You should see “Connection successful”. Your speaker should likely give a confirmation sound as well.
Type `exit` to leave bluetoothctl.

**`mpg123`**

A command-line MP3 player. Install it using:
```bash
sudo apt update
sudo apt install mpg123
```

**`ffmpeg`**

`mpg123` can only handle MP3 streams. For AAC, DASH or other modern formats, you need `ffmpeg`. Install it with:
```bash
sudo apt update
sudo apt install ffmpeg
```

**User Groups**

Ensure your user is part of the `audio` and `bluetooth` groups to access audio devices and Bluetooth functionality:
```bash
sudo usermod -aG audio,bluetooth thatgurjot # Replace 'thatgurjot' with your actual username
# Verify the groups with:
groups thatgurjot
```

**Linger User Sessions**

Tell systemd to keep the user's session active even if the user is not logged in:
```bash
sudo loginctl enable-linger thatgurjot
```
# Verify linger status:
```bash
loginctl show-user thatgurjot | grep Linger
```
# Reboot the device:
```bash
sudo reboot
```

### 2. Clone the Repository

For this guide, we'll assume it's cloned into `/home/thatgurjot/radio-server/`.

SSH into your Pi and run –

```bash
git clone https://github.com/gsidhu/raspi-scripts.git
mv raspi-scripts/radio-server /home/thatgurjot/radio-server # Move the radio-server directory to the expected location
cd /home/thatgurjot/radio-server
```

### 3. Set Up Python Environment and Install Dependencies

It's recommended to use a Python virtual environment.

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install required Python packages
# Based on server.py, dependencies are: starlette, python-dotenv, uvicorn
pip install starlette python-dotenv uvicorn
```

### 4. Configure Bluetooth MAC Address

You need to provide your Bluetooth speaker's MAC address to the server.

1.  **Find your speaker's MAC address**:
    *   Put your Bluetooth speaker in pairing mode.
    *   On your Raspberry Pi, run `bluetoothctl`.
    *   Inside `bluetoothctl`, type `scan on`.
    *   Wait for your speaker to appear in the list. Note its MAC address (e.g., `XX:XX:XX:XX:XX:XX`).
    *   Type `scan off` and `exit` to leave `bluetoothctl`.

2.  **Edit `server.py`**:
    Open `server.py` in a text editor (e.g., `nano server.py`).
    Find the line:
    ```python
    BLUETOOTH_DEVICE_MAC = os.getenv("JBL_GO_MAC_ADDRESS")
    ```
    And change it to directly include your speaker's MAC address, or set it as an environment variable. For simplicity, you can hardcode it:
    ```python
    # !!! IMPORTANT: Replace this with your speaker's MAC address !!!
    BLUETOOTH_DEVICE_MAC = "YOUR_SPEAKER_MAC_ADDRESS" # e.g., "A1:B2:C3:D4:E5:F6"
    ```
    Alternatively, you can create a `.env` file in the `radio-server/` directory with the line:
    ```
    JBL_GO_MAC_ADDRESS=YOUR_SPEAKER_MAC_ADDRESS
    ```
    The script will automatically pick it up if `python-dotenv` is installed.

### 5. Configure Systemd Service

The `pi-radio-server.service` file is provided to run the server as a background service.

1.  **Copy the service file**:
    ```bash
    sudo cp /home/thatgurjot/radio-server/pi-radio-server.service ~/.config/systemd/user/pi-radio-server.service
    ```
    *Note: If you are not running as the `thatgurjot` user, adjust the `WorkingDirectory` and `ExecStart` paths in the `.service` file accordingly.*

2.  **Enable Lingering for the User**:
    To ensure the service runs even when you are not logged in, enable lingering for your user.
    ```bash
    sudo loginctl enable-linger thatgurjot
    ```
    *(Replace `thatgurjot` with your actual username if different.)*

### 6. Enable and Start the Service

```bash
# Reload systemd to recognize the new service
systemctl --user daemon-reload

# Enable the service to start on boot
systemctl --user enable pi-radio-server.service

# Start the service immediately
systemctl --user start pi-radio-server.service

# Check the status of the service
systemctl --user status pi-radio-server.service
```

### 7. Access the Web Interface

Once the service is running, you can access the web interface from any device on the same network as your Raspberry Pi.

Open a web browser and go to:
`http://<YOUR_RASPBERRY_PI_IP_ADDRESS>:8000`

You can find your Raspberry Pi's IP address using `hostname -I` on the Pi.

## Usage

*   **Connect Bluetooth Speaker**: Click the "Connect Speaker" button.
*   **Play Station**: Click the "Play" button next to your desired FM station.
*   **Stop Playback**: Click the "STOP" button.
*   **Adjust Volume**: Use the "+" and "-" buttons to control the volume.

## Troubleshooting

* **No Audio**: Ensure your Bluetooth speaker is connected and selected as the default audio output. Check PulseAudio configuration if necessary.
* **Bluetooth Connection Issues**: Verify the MAC address in `server.py` is correct. Ensure your speaker is in pairing mode when attempting to connect. Check `bluetoothctl` for errors.
* **Web Interface Not Loading**: Make sure the `uvicorn` server is running (`systemctl --user status pi-radio-server.service`). Check the Raspberry Pi's IP address and ensure your client device is on the same network.
* **`amixer` errors**: Ensure `pulseaudio-utils` is installed.
* **Permissions issues or `(code=exited, status=203/EXEC)` errors**: 
    * Ensure the service file has the correct paths and permissions. The `ExecStart` path should point to the Python interpreter in your virtual environment, and the working directory should be set correctly.
    * Make sure the `start-server.sh` script is executable (`chmod +x start-server.sh`).
    * Make sure the user running the service has permission to access the audio devices. You can check this by running `groups thatgurjot` and ensuring `audio` and `bluetooth` are listed.
    * Make sure `linger` is enabled for your user. You can check this with `loginctl show-user thatgurjot` and looking for `Linger=yes`.

View logs for more details:
```bash
journalctl --user-unit pi-radio-server.service
```

For everything else: Ask your friendly local LLM!