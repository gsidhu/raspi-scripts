#!/bin/bash

# Bluetooth Speaker Setup Script for Raspberry Pi Zero W
# This script sets up and connects a Bluetooth speaker to Pi Zero W in headless mode
# Usage: ./bluetooth_speaker_setup.sh [MAC_ADDRESS]
# If no MAC address is provided, the script will help you discover devices

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

# Check if running as root for system operations
check_sudo() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root. This is okay for system setup."
    fi
}

# Install required packages
install_packages() {
    print_status "Installing required Bluetooth packages..."
    sudo apt update -qq
    sudo apt install -y bluetooth bluez bluez-tools pulseaudio pulseaudio-module-bluetooth alsa-utils
    print_success "Packages installed successfully"
}

# Enable and start Bluetooth services
setup_services() {
    print_status "Setting up Bluetooth services..."
    
    # Enable and start Bluetooth service
    sudo systemctl enable bluetooth
    sudo systemctl start bluetooth
    
    # Check if Bluetooth service is running
    if sudo systemctl is-active --quiet bluetooth; then
        print_success "Bluetooth service is running"
    else
        print_error "Failed to start Bluetooth service"
        exit 1
    fi
    
    # Start PulseAudio if not running
    if ! pgrep -x "pulseaudio" > /dev/null; then
        print_status "Starting PulseAudio..."
        pulseaudio --start --log-target=syslog
        sleep 2
    fi
    
    print_success "Services configured successfully"
}

# Check Bluetooth adapter status
check_bluetooth() {
    print_status "Checking Bluetooth adapter..."
    
    if command -v hciconfig > /dev/null; then
        if hciconfig hci0 | grep -q "UP RUNNING"; then
            print_success "Bluetooth adapter is active"
        else
            print_status "Bringing up Bluetooth adapter..."
            sudo hciconfig hci0 up
        fi
    else
        print_warning "hciconfig not available, using bluetoothctl to check"
    fi
}

# Discover Bluetooth devices
discover_devices() {
    print_status "Scanning for Bluetooth devices..."
    print_warning "Make sure your Bluetooth speaker is in pairing mode!"
    echo
    
    # Use bluetoothctl to scan for devices
    timeout 30 bluetoothctl <<EOF
power on
agent on
default-agent
discoverable on
scan on
EOF
    
    print_status "Scan completed. Available devices:"
    bluetoothctl devices
    echo
}

# Connect to a specific Bluetooth device
connect_device() {
    local mac_address="$1"
    
    if [[ -z "$mac_address" ]]; then
        print_error "No MAC address provided"
        return 1
    fi
    
    # Validate MAC address format
    if [[ ! "$mac_address" =~ ^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$ ]]; then
        print_error "Invalid MAC address format. Expected format: XX:XX:XX:XX:XX:XX"
        return 1
    fi
    
    print_status "Connecting to device: $mac_address"
    
    # Connect using bluetoothctl
    bluetoothctl <<EOF
power on
agent on
default-agent
pair $mac_address
trust $mac_address
connect $mac_address
exit
EOF
    
    # Wait a moment for connection to establish
    sleep 3
    
    # Verify connection
    if bluetoothctl info "$mac_address" | grep -q "Connected: yes"; then
        print_success "Successfully connected to $mac_address"
        return 0
    else
        print_error "Failed to connect to $mac_address"
        return 1
    fi
}

# Configure audio output to use Bluetooth speaker
setup_audio() {
    local mac_address="$1"
    
    print_status "Configuring audio output..."
    
    # Wait for PulseAudio to detect the Bluetooth sink
    sleep 5
    
    # Convert MAC address format for PulseAudio (replace : with _)
    local pa_mac=$(echo "$mac_address" | tr ':' '_')
    local sink_name="bluez_sink.${pa_mac}.a2dp_sink"
    
    # List available sinks
    print_status "Available audio sinks:"
    pactl list short sinks
    echo
    
    # Try to set the Bluetooth speaker as default sink
    if pactl list short sinks | grep -q "$sink_name"; then
        pactl set-default-sink "$sink_name"
        print_success "Set Bluetooth speaker as default audio output"
    else
        print_warning "Bluetooth audio sink not found. You may need to manually configure audio."
        print_status "Available sinks listed above. Use: pactl set-default-sink SINK_NAME"
    fi
}

# Test audio output
test_audio() {
    print_status "Testing audio output..."
    print_warning "You should hear a test sound. Press Ctrl+C to stop if needed."
    
    # Test with speaker-test for 5 seconds
    timeout 5 speaker-test -t wav -c 2 2>/dev/null || true
    
    print_status "Audio test completed"
}

# Setup auto-reconnect on boot
setup_autoconnect() {
    local mac_address="$1"
    
    print_status "Setting up auto-reconnect on boot..."
    
    # Create a systemd service for auto-reconnect
    sudo tee /etc/systemd/system/bluetooth-speaker.service > /dev/null <<EOF
[Unit]
Description=Connect Bluetooth Speaker
After=bluetooth.service
Requires=bluetooth.service

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 10
ExecStart=/usr/bin/bluetoothctl connect $mac_address
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    # Enable the service
    sudo systemctl daemon-reload
    sudo systemctl enable bluetooth-speaker.service
    
    print_success "Auto-reconnect service created and enabled"
}

# Main function
main() {
    local mac_address="$1"
    
    echo "=================================="
    echo "Bluetooth Speaker Setup for Pi Zero W"
    echo "=================================="
    echo
    
    check_sudo
    install_packages
    setup_services
    check_bluetooth
    
    # If no MAC address provided, help user discover devices
    if [[ -z "$mac_address" ]]; then
        discover_devices
        echo
        print_warning "Please run the script again with your speaker's MAC address:"
        print_warning "Example: $0 XX:XX:XX:XX:XX:XX"
        exit 0
    fi
    
    # Connect to the specified device
    if connect_device "$mac_address"; then
        setup_audio "$mac_address"
        
        # Ask user if they want to test audio
        echo
        read -p "Do you want to test audio output? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            test_audio
        fi
        
        # Ask user if they want auto-reconnect
        echo
        read -p "Do you want to setup auto-reconnect on boot? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            setup_autoconnect "$mac_address"
        fi
        
        echo
        print_success "Bluetooth speaker setup completed!"
        print_status "Your speaker should now be connected and ready to use."
        echo
        print_status "Useful commands:"
        echo "  - Reconnect: bluetoothctl connect $mac_address"
        echo "  - Disconnect: bluetoothctl disconnect $mac_address"
        echo "  - Check status: bluetoothctl info $mac_address"
        echo "  - List audio sinks: pactl list short sinks"
        echo "  - Set audio output: pactl set-default-sink SINK_NAME"
        
    else
        print_error "Setup failed. Please check your speaker is in pairing mode and try again."
        exit 1
    fi
}

# Script usage information
show_usage() {
    echo "Usage: $0 [MAC_ADDRESS]"
    echo
    echo "If no MAC address is provided, the script will scan for available devices."
    echo "Example: $0 XX:XX:XX:XX:XX:XX"
    echo
    echo "Make sure your Bluetooth speaker is in pairing mode before running this script."
}

# Handle command line arguments
case "${1:-}" in
    -h|--help)
        show_usage
        exit 0
        ;;
    *)
        main "$1"
        ;;
esac