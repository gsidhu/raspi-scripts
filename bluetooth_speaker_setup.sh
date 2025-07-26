#!/bin/bash

# Bluetooth Speaker Manager Script for Raspberry Pi Zero W
# This script manages Bluetooth speaker connections in headless mode
# Usage: 
#   ./bluetooth_speaker_setup.sh --setup                    # Install packages and setup services
#   ./bluetooth_speaker_setup.sh --connect MAC_ADDRESS      # Connect to device
#   ./bluetooth_speaker_setup.sh --disconnect MAC_ADDRESS   # Disconnect from device
#   ./bluetooth_speaker_setup.sh --status [MAC_ADDRESS]     # Show status of device(s)
#   ./bluetooth_speaker_setup.sh --scan                     # Scan for available devices

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate MAC address format
validate_mac() {
    local mac_address="$1"
    if [[ ! "$mac_address" =~ ^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$ ]]; then
        print_error "Invalid MAC address format. Expected format: XX:XX:XX:XX:XX:XX"
        exit 1
    fi
}

# Install required packages and setup services
setup_system() {
    print_status "Setting up Bluetooth system..."
    
    # Check if running with appropriate permissions
    if [[ $EUID -ne 0 ]]; then
        print_error "Setup requires root privileges. Please run with sudo."
        exit 1
    fi
    
    print_status "Installing required Bluetooth packages..."
    apt update -qq
    apt install -y bluetooth bluez bluez-tools pulseaudio pulseaudio-module-bluetooth alsa-utils
    print_success "Packages installed successfully"
    
    print_status "Setting up Bluetooth services..."
    
    # Enable and start Bluetooth service
    systemctl enable bluetooth
    systemctl start bluetooth
    
    # Check if Bluetooth service is running
    if systemctl is-active --quiet bluetooth; then
        print_success "Bluetooth service is running"
    else
        print_error "Failed to start Bluetooth service"
        exit 1
    fi
    
    # Bring up Bluetooth adapter
    if command -v hciconfig > /dev/null; then
        hciconfig hci0 up 2>/dev/null || true
    fi
    
    print_success "Bluetooth system setup completed"
}

# Scan for available Bluetooth devices
scan_devices() {
    print_status "Scanning for Bluetooth devices..."
    print_warning "Make sure your Bluetooth speaker is in pairing mode!"
    
    # Ensure Bluetooth is powered on and start scanning
    timeout 30 bluetoothctl <<EOF 2>/dev/null || true
power on
agent on
default-agent
discoverable on
scan on
EOF
    
    sleep 2
    
    print_status "Available devices:"
    bluetoothctl devices
}

# Connect to a Bluetooth device
connect_device() {
    local mac_address="$1"
    
    validate_mac "$mac_address"
    
    print_status "Connecting to device: $mac_address"
    
    # Start PulseAudio if not running
    if ! pgrep -x "pulseaudio" > /dev/null; then
        print_status "Starting PulseAudio..."
        pulseaudio --start --log-target=syslog 2>/dev/null || true
        sleep 2
    fi
    
    # Connect using bluetoothctl
    bluetoothctl <<EOF 2>/dev/null
power on
agent on
default-agent
pair $mac_address
trust $mac_address
connect $mac_address
exit
EOF
    
    # Wait for connection to establish
    sleep 3
    
    # Verify connection
    if bluetoothctl info "$mac_address" 2>/dev/null | grep -q "Connected: yes"; then
        print_success "Successfully connected to $mac_address"
        
        # Configure audio output
        setup_audio "$mac_address"
        
        exit 0
    else
        print_error "Failed to connect to $mac_address"
        exit 1
    fi
}

# Disconnect from a Bluetooth device
disconnect_device() {
    local mac_address="$1"
    
    validate_mac "$mac_address"
    
    print_status "Disconnecting from device: $mac_address"
    
    bluetoothctl <<EOF 2>/dev/null
disconnect $mac_address
exit
EOF
    
    # Wait a moment and verify disconnection
    sleep 2
    
    if bluetoothctl info "$mac_address" 2>/dev/null | grep -q "Connected: no"; then
        print_success "Successfully disconnected from $mac_address"
        exit 0
    else
        print_warning "Device may still be connected or connection status unclear"
        exit 1
    fi
}

# Configure audio output to use Bluetooth speaker
setup_audio() {
    local mac_address="$1"
    
    print_status "Configuring audio output..."
    
    # Wait for PulseAudio to detect the Bluetooth sink
    sleep 3
    
    # Convert MAC address format for PulseAudio (replace : with _)
    local pa_mac=$(echo "$mac_address" | tr ':' '_')
    local sink_name="bluez_sink.${pa_mac}.a2dp_sink"
    
    # Try to set the Bluetooth speaker as default sink
    if pactl list short sinks 2>/dev/null | grep -q "$sink_name"; then
        pactl set-default-sink "$sink_name" 2>/dev/null || true
        print_success "Set Bluetooth speaker as default audio output"
    else
        print_warning "Bluetooth audio sink not immediately available"
        print_status "Audio may need a moment to initialize"
    fi
}

# Show status of Bluetooth device(s)
show_status() {
    local mac_address="$1"
    
    if [[ -n "$mac_address" ]]; then
        validate_mac "$mac_address"
        print_status "Status for device: $mac_address"
        
        # Try to get device info
        local device_info=$(bluetoothctl info "$mac_address" 2>/dev/null)
        if [[ -n "$device_info" ]] && echo "$device_info" | grep -q "Device"; then
            echo "----------------------------------------"
            echo "$device_info"
            echo "----------------------------------------"
        else
            print_error "Device $mac_address not found or not paired"
            exit 1
        fi
    else
        print_status "All Bluetooth devices:"
        echo "----------------------------------------"
        
        # Get all devices using the universal 'devices' command
        local all_devices=$(bluetoothctl devices 2>/dev/null)
        if [[ -n "$all_devices" ]]; then
            echo "$all_devices"
            echo
            
            # Check connection status for each device
            print_status "Connection status:"
            echo "$all_devices" | while read -r line; do
                if [[ -n "$line" ]]; then
                    local mac=$(echo "$line" | awk '{print $2}')
                    local name=$(echo "$line" | cut -d' ' -f3-)
                    
                    if [[ -n "$mac" ]] && [[ "$mac" =~ ^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$ ]]; then
                        local info=$(bluetoothctl info "$mac" 2>/dev/null)
                        if echo "$info" | grep -q "Connected: yes"; then
                            echo "  ✓ $mac ($name) - CONNECTED"
                        elif echo "$info" | grep -q "Paired: yes"; then
                            echo "  ○ $mac ($name) - PAIRED"
                        else
                            echo "  - $mac ($name) - DISCOVERED"
                        fi
                    fi
                fi
            done
        else
            echo "No devices found"
        fi
        echo "----------------------------------------"
    fi
    
    # Show audio sinks if PulseAudio is available
    if command -v pactl > /dev/null && pgrep -x "pulseaudio" > /dev/null; then
        print_status "Available audio sinks:"
        echo "----------------------------------------"
        pactl list short sinks 2>/dev/null || print_warning "Could not list audio sinks"
        echo "----------------------------------------"
        
        # Show current default sink
        local default_sink=$(pactl info 2>/dev/null | grep "Default Sink:" | cut -d' ' -f3-)
        if [[ -n "$default_sink" ]]; then
            print_status "Current default audio output: $default_sink"
        fi
    fi
}

# Show usage information
show_usage() {
    echo "Bluetooth Speaker Manager for Raspberry Pi Zero W"
    echo
    echo "Usage:"
    echo "  $0 --setup                        Install packages and setup services (requires sudo)"
    echo "  $0 --connect MAC_ADDRESS          Connect to a Bluetooth device"
    echo "  $0 --disconnect MAC_ADDRESS       Disconnect from a Bluetooth device"
    echo "  $0 --status [MAC_ADDRESS]         Show status of device(s)"
    echo "  $0 --scan                         Scan for available Bluetooth devices"
    echo "  $0 --help                         Show this help message"
    echo
    echo "Examples:"
    echo "  $0 --setup"
    echo "  $0 --scan"
    echo "  $0 --connect AA:BB:CC:DD:EE:FF"
    echo "  $0 --status AA:BB:CC:DD:EE:FF"
    echo "  $0 --disconnect AA:BB:CC:DD:EE:FF"
    echo
    echo "Note: Make sure your Bluetooth speaker is in pairing mode before connecting."
}

# Main script logic
case "${1:-}" in
    --setup)
        setup_system
        ;;
    --connect)
        if [[ -z "$2" ]]; then
            print_error "MAC address required for --connect"
            echo
            show_usage
            exit 1
        fi
        connect_device "$2"
        ;;
    --disconnect)
        if [[ -z "$2" ]]; then
            print_error "MAC address required for --disconnect"
            echo
            show_usage
            exit 1
        fi
        disconnect_device "$2"
        ;;
    --status)
        show_status "$2"
        ;;
    --scan)
        scan_devices
        ;;
    --help|-h)
        show_usage
        ;;
    "")
        print_error "No command specified"
        echo
        show_usage
        exit 1
        ;;
    *)
        print_error "Unknown command: $1"
        echo
        show_usage
        exit 1
        ;;
esac