#!/bin/bash

# Zoom H2n USB Connection Manager for Raspberry Pi Zero W
# Usage: ./usb_mic_connect.sh [options]

# # Initial setup
# chmod +x ./usb_mic_connect.sh
# ./usb_mic_connect.sh --setup
# 
# # Detect and configure H2n
# ./usb_mic_connect.sh --detect
#
# # Test the device
# ./usb_mic_connect.sh --test
#
# # Show current configuration
# ./usb_mic_connect.sh --config

# Default settings
CONFIG_FILE="$HOME/.h2n_config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== Zoom H2n Connection Manager ===${NC}"
    echo
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -s, --setup             Setup system for H2n recording"
    echo "  -d, --detect            Detect and configure H2n device"
    echo "  -l, --list              List available audio devices"
    echo "  -t, --test [DEVICE]     Test specified device (or auto-detected)"
    echo "  -c, --config            Show current configuration"
    echo "  -r, --reset             Reset configuration"
    echo "  -h, --help              Show this help message"
    echo
    echo "Examples:"
    echo "  $0 --setup              # Initial system setup"
    echo "  $0 --detect             # Detect and configure H2n"
    echo "  $0 --test hw:1,0        # Test specific device"
    echo "  $0 --config             # Show current config"
}

# Function to save configuration
save_config() {
    local device="$1"
    local card_num=$(echo $device | cut -d: -f2 | cut -d, -f1)
    
    cat > "$CONFIG_FILE" << EOF
# H2n Configuration
H2N_DEVICE=$device
H2N_CARD=$card_num
LAST_DETECTED=$(date)
EOF
    
    print_status "Configuration saved to $CONFIG_FILE"
}

# Function to load configuration
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
        return 0
    fi
    return 1
}

# Function to show current configuration
show_config() {
    if load_config; then
        print_status "Current H2n Configuration:"
        echo "  Device: $H2N_DEVICE"
        echo "  Card: $H2N_CARD"
        echo "  Last Detected: $LAST_DETECTED"
        echo
        
        # Test if device is still available
        if arecord -l 2>/dev/null | grep "card $H2N_CARD" > /dev/null; then
            print_status "Device is currently available"
        else
            print_warning "Configured device not currently available"
        fi
    else
        print_warning "No configuration found. Run --setup and --detect first."
    fi
}

# Function to setup system
setup_system() {
    print_status "Setting up system for H2n recording..."
    
    # Check if running as root for apt commands
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root. This is not recommended for regular use."
    fi
    
    # Install required packages
    print_status "Installing required packages..."
    sudo apt update || { print_error "Failed to update package list"; return 1; }
    sudo apt install -y alsa-utils sox || { print_error "Failed to install packages"; return 1; }
    
    # Load audio modules
    print_status "Loading audio modules..."
    sudo modprobe snd-usb-audio
    
    # Add user to audio group
    print_status "Adding user to audio group..."
    sudo usermod -a -G audio $USER
    
    print_status "System setup complete!"
    print_warning "You may need to log out and back in for group changes to take effect."
}

# Function to detect H2n device
detect_h2n() {
    print_status "Scanning for Zoom H2n..."
    
    # Check USB devices first
    local usb_info=$(lsusb | grep -i "zoom\|h2n")
    if [ ! -z "$usb_info" ]; then
        print_status "Zoom device found in USB:"
        echo "  $usb_info"
    else
        print_warning "No Zoom device found in USB devices."
        print_status "Checking for generic USB audio devices..."
    fi
    
    # Get all audio capture devices
    local devices=$(arecord -l 2>/dev/null)
    
    if [ -z "$devices" ]; then
        print_error "No audio capture devices found"
        print_status "Troubleshooting steps:"
        echo "  1. Ensure H2n is connected to powered USB hub"
        echo "  2. Check that H2n is in USB mode (not SD card mode)"
        echo "  3. Try a different USB cable"
        echo "  4. Check dmesg output: dmesg | tail -20"
        return 1
    fi
    
    print_status "Available audio devices:"
    echo "$devices"
    echo
    
    # Try to auto-detect H2n by looking for USB audio devices
    local h2n_candidates=(
        $(arecord -l 2>/dev/null | grep -E "(USB|H2n|Zoom)" | sed -n 's/card \([0-9]\+\).*device \([0-9]\+\).*/hw:\1,\2/p')
    )
    
    # If no USB-specific matches, try generic detection
    if [ ${#h2n_candidates[@]} -eq 0 ]; then
        h2n_candidates=(
            $(arecord -l 2>/dev/null | grep "card" | sed -n 's/card \([0-9]\+\).*device \([0-9]\+\).*/hw:\1,\2/p')
        )
    fi
    
    if [ ${#h2n_candidates[@]} -gt 0 ]; then
        local selected_device="${h2n_candidates[0]}"
        
        if [ ${#h2n_candidates[@]} -gt 1 ]; then
            print_warning "Multiple audio devices found:"
            for i in "${!h2n_candidates[@]}"; do
                echo "  [$i] ${h2n_candidates[$i]}"
            done
            echo
            print_status "Using first device: $selected_device"
            print_status "Use --test <device> to test specific devices"
        else
            print_status "Detected device: $selected_device"
        fi
        
        # Test the device
        if test_device "$selected_device"; then
            save_config "$selected_device"
            create_alsa_config "$selected_device"
            print_status "H2n detection and configuration complete!"
            return 0
        else
            print_error "Device test failed for $selected_device"
            return 1
        fi
    else
        print_error "No suitable audio devices found"
        return 1
    fi
}

# Function to test audio device
test_device() {
    local device="$1"
    
    if [ -z "$device" ]; then
        if load_config; then
            device="$H2N_DEVICE"
        else
            print_error "No device specified and no configuration found"
            return 1
        fi
    fi
    
    print_status "Testing device: $device"
    
    # Check if device exists in ALSA
    if ! arecord -l 2>/dev/null | grep "${device#hw:}" > /dev/null; then
        print_error "Device $device not found in audio device list"
        return 1
    fi
    
    # Test recording for 2 seconds
    local test_file="/tmp/h2n_test_$(date +%s).wav"
    
    print_status "Recording 2-second test sample..."
    
    if timeout 5 arecord -D "$device" -r 44100 -f S16_LE -c 2 -d 2 "$test_file" 2>/dev/null; then
        if [ -f "$test_file" ] && [ -s "$test_file" ]; then
            local size=$(stat -c%s "$test_file" 2>/dev/null || echo "0")
            print_status "Test successful! Recorded ${size} bytes"
            
            # Show audio info if sox is available
            if command -v soxi > /dev/null 2>&1; then
                print_status "Audio file details:"
                soxi "$test_file" 2>/dev/null | grep -E "(Sample Rate|Channels|Duration)"
            fi
            
            rm -f "$test_file"
            return 0
        else
            print_error "Test file was not created or is empty"
            rm -f "$test_file"
            return 1
        fi
    else
        print_error "Recording test failed"
        rm -f "$test_file"
        return 1
    fi
}

# Function to create ALSA configuration
create_alsa_config() {
    local device="$1"
    local card_num=$(echo $device | cut -d: -f2 | cut -d, -f1)
    
    print_status "Creating ALSA configuration..."
    
    # Backup existing config
    if [ -f "$HOME/.asoundrc" ]; then
        cp "$HOME/.asoundrc" "$HOME/.asoundrc.backup.$(date +%s)"
        print_status "Backed up existing .asoundrc"
    fi
    
    # Create new configuration
    cat > "$HOME/.asoundrc" << EOF
# ALSA configuration for Zoom H2n
# Generated by h2n_connect.sh on $(date)

pcm.h2n {
    type hw
    card $card_num
    device 0
}

ctl.h2n {
    type hw
    card $card_num
}

# Set H2n as default capture device
pcm.!default {
    type asym
    playback.pcm "dmix"
    capture.pcm "h2n"
}

ctl.!default {
    type hw
    card $card_num
}
EOF
    
    print_status "ALSA configuration created at $HOME/.asoundrc"
}

# Function to list audio devices
list_devices() {
    print_status "USB Devices:"
    lsusb | grep -E "(Audio|Zoom|H2n)" || echo "  No audio/Zoom devices found in USB"
    echo
    
    print_status "ALSA Audio Capture Devices:"
    local devices=$(arecord -l 2>/dev/null)
    if [ ! -z "$devices" ]; then
        echo "$devices"
    else
        echo "  No audio capture devices found"
    fi
    echo
    
    print_status "Audio Cards in /proc:"
    if [ -f /proc/asound/cards ]; then
        cat /proc/asound/cards
    else
        echo "  /proc/asound/cards not found"
    fi
}

# Function to reset configuration
reset_config() {
    print_status "Resetting H2n configuration..."
    
    if [ -f "$CONFIG_FILE" ]; then
        rm "$CONFIG_FILE"
        print_status "Removed configuration file"
    fi
    
    if [ -f "$HOME/.asoundrc" ]; then
        if [ -f "$HOME/.asoundrc.backup"* ]; then
            print_status "ALSA config backup exists. Remove manually if needed."
        fi
        rm "$HOME/.asoundrc"
        print_status "Removed ALSA configuration"
    fi
    
    print_status "Configuration reset complete"
}

# Parse command line arguments
case "${1:-}" in
    -s|--setup)
        print_header
        setup_system
        ;;
    -d|--detect)
        print_header
        detect_h2n
        ;;
    -l|--list)
        print_header
        list_devices
        ;;
    -t|--test)
        print_header
        test_device "$2"
        ;;
    -c|--config)
        print_header
        show_config
        ;;
    -r|--reset)
        print_header
        reset_config
        ;;
    -h|--help|"")
        print_header
        show_usage
        ;;
    *)
        print_error "Unknown option: $1"
        show_usage
        exit 1
        ;;
esac