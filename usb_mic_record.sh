#!/bin/bash

# Zoom H2n USB Recording Manager for Raspberry Pi Zero W
# Usage: ./usb_mic_record.sh [options]

# # Setup
# chmod +x ./usb_mic_record.sh
#
# # Basic recording
# ./usb_mic_record.sh
#
# # Named recording with duration
# ./usb_mic_record.sh -f meeting -d 30m
#
# # High quality recording
# ./usb_mic_record.sh -f concert -q dat -d 2h
#
# # Show status
# ./usb_mic_record.sh status
#
# # List recordings
# ./usb_mic_record.sh list

# Default settings
CONFIG_FILE="$HOME/.h2n_config"
OUTPUT_DIR="$HOME/recordings"
SAMPLE_RATE=44100
FORMAT="S16_LE"
CHANNELS=2
DEVICE=""
FILENAME=""
DURATION=""
QUALITY="cd"

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
    echo -e "${BLUE}=== Zoom H2n Recording Manager ===${NC}"
    echo
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [ACTION]"
    echo
    echo "Actions:"
    echo "  record                  Start recording (default action)"
    echo "  status                  Show recording status and device info"
    echo "  list                    List previous recordings"
    echo "  info FILE               Show information about a recording"
    echo
    echo "Recording Options:"
    echo "  -f, --filename NAME     Output filename (without extension)"
    echo "  -d, --duration TIME     Recording duration (e.g., 10s, 5m, 1h)"
    echo "  -o, --output DIR        Output directory (default: ~/recordings)"
    echo "  -q, --quality PRESET    Quality preset: cd, dat, phone, voice"
    echo "  -r, --rate RATE         Sample rate (default: 44100)"
    echo "  -c, --channels NUM      Number of channels (default: 2)"
    echo "  --device DEVICE         Override configured device"
    echo
    echo "Other Options:"
    echo "  -v, --verbose           Verbose output"
    echo "  -h, --help              Show this help message"
    echo
    echo "Quality Presets:"
    echo "  cd      44100 Hz, 16-bit, stereo (default)"
    echo "  dat     48000 Hz, 16-bit, stereo"
    echo "  phone   8000 Hz, 8-bit, mono"
    echo "  voice   22050 Hz, 16-bit, mono"
    echo
    echo "Examples:"
    echo "  $0                              # Start recording with defaults"
    echo "  $0 -f meeting -d 30m            # Record meeting for 30 minutes"
    echo "  $0 -f concert -q dat -d 2h      # High quality 2-hour recording"
    echo "  $0 status                       # Show current status"
    echo "  $0 list                         # List all recordings"
    echo "  $0 info recording_20240101.wav  # Show file information"
}

# Function to load H2n configuration
load_h2n_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
        if [ ! -z "$H2N_DEVICE" ]; then
            DEVICE="$H2N_DEVICE"
            return 0
        fi
    fi
    
    print_error "No H2n configuration found."
    print_status "Run: ./h2n_connect.sh --setup && ./h2n_connect.sh --detect"
    return 1
}

# Function to apply quality presets
apply_quality_preset() {
    case "$QUALITY" in
        cd)
            SAMPLE_RATE=44100
            FORMAT="S16_LE"
            CHANNELS=2
            ;;
        dat)
            SAMPLE_RATE=48000
            FORMAT="S16_LE"
            CHANNELS=2
            ;;
        phone)
            SAMPLE_RATE=8000
            FORMAT="U8"
            CHANNELS=1
            ;;
        voice)
            SAMPLE_RATE=22050
            FORMAT="S16_LE"
            CHANNELS=1
            ;;
        *)
            print_warning "Unknown quality preset: $QUALITY. Using defaults."
            ;;
    esac
}

# Function to check device status
check_device_status() {
    if [ -z "$DEVICE" ]; then
        print_error "No device configured"
        return 1
    fi
    
    # Check if device exists
    if ! arecord -l 2>/dev/null | grep "${DEVICE#hw:}" > /dev/null; then
        print_error "Configured device $DEVICE not found"
        print_status "Available devices:"
        arecord -l 2>/dev/null || echo "  No devices found"
        return 1
    fi
    
    return 0
}

# Function to generate filename
generate_filename() {
    if [ -z "$FILENAME" ]; then
        FILENAME="recording_$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Ensure output directory exists
    mkdir -p "$OUTPUT_DIR"
    
    echo "${OUTPUT_DIR}/${FILENAME}.wav"
}

# Function to convert duration to seconds
duration_to_seconds() {
    local duration="$1"
    case "$duration" in
        *s) echo ${duration%s} ;;
        *m) echo $((${duration%m} * 60)) ;;
        *h) echo $((${duration%h} * 3600)) ;;
        *) echo $duration ;;
    esac
}

# Function to format duration for display
format_duration() {
    local seconds="$1"
    local hours=$((seconds / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))
    
    if [ $hours -gt 0 ]; then
        printf "%dh %dm %ds" $hours $minutes $secs
    elif [ $minutes -gt 0 ]; then
        printf "%dm %ds" $minutes $secs
    else
        printf "%ds" $secs
    fi
}

# Function to show recording status
show_status() {
    print_status "H2n Recording Status"
    echo
    
    # Load and show configuration
    if load_h2n_config; then
        print_status "Device Configuration:"
        echo "  Device: $DEVICE"
        echo "  Card: $H2N_CARD"
        echo "  Last Detected: $LAST_DETECTED"
        echo
        
        # Check current device status
        if check_device_status; then
            print_status "Device Status: Available"
            
            # Show current mixer levels if possible
            if command -v amixer > /dev/null 2>&1; then
                print_status "Current Levels:"
                amixer -c ${H2N_CARD} sget Mic 2>/dev/null | grep -E "(Left|Right|Mono):" || echo "  Unable to read levels"
            fi
        else
            print_warning "Device Status: Not Available"
        fi
        echo
        
        # Show recording settings
        apply_quality_preset
        print_status "Recording Settings:"
        echo "  Sample Rate: $SAMPLE_RATE Hz"
        echo "  Format: $FORMAT"
        echo "  Channels: $CHANNELS"
        echo "  Output Directory: $OUTPUT_DIR"
        echo
        
        # Show disk space
        print_status "Storage:"
        df -h "$OUTPUT_DIR" | tail -1 | awk '{print "  Available Space: " $4 " (" $5 " used)"}'
    fi
}

# Function to list recordings
list_recordings() {
    print_status "Recordings in $OUTPUT_DIR:"
    echo
    
    if [ ! -d "$OUTPUT_DIR" ]; then
        print_warning "Recordings directory does not exist: $OUTPUT_DIR"
        return
    fi
    
    local recordings=($(find "$OUTPUT_DIR" -name "*.wav" -type f | sort -r))
    
    if [ ${#recordings[@]} -eq 0 ]; then
        print_status "No recordings found"
        return
    fi
    
    echo "Recent recordings:"
    for i in "${!recordings[@]}"; do
        local file="${recordings[$i]}"
        local basename=$(basename "$file")
        local size=$(ls -lh "$file" | awk '{print $5}')
        local date=$(ls -l --time-style="+%Y-%m-%d %H:%M" "$file" | awk '{print $6, $7}')
        
        printf "  [%2d] %-30s %8s  %s\n" $((i+1)) "$basename" "$size" "$date"
        
        # Show only first 10 by default
        if [ $i -ge 9 ]; then
            local remaining=$((${#recordings[@]} - 10))
            if [ $remaining -gt 0 ]; then
                echo "  ... and $remaining more recordings"
            fi
            break
        fi
    done
}

# Function to show file information
show_file_info() {
    local filename="$1"
    
    # If filename doesn't include path, assume it's in OUTPUT_DIR
    if [[ "$filename" != /* ]]; then
        filename="$OUTPUT_DIR/$filename"
    fi
    
    if [ ! -f "$filename" ]; then
        print_error "File not found: $filename"
        return 1
    fi
    
    print_status "File Information: $(basename "$filename")"
    echo
    
    # Basic file info
    local size=$(ls -lh "$filename" | awk '{print $5}')
    local date=$(ls -l --time-style="+%Y-%m-%d %H:%M:%S" "$filename" | awk '{print $6, $7}')
    
    echo "  File Size: $size"
    echo "  Created: $date"
    echo "  Full Path: $filename"
    echo
    
    # Audio information using soxi if available
    if command -v soxi > /dev/null 2>&1; then
        print_status "Audio Information:"
        soxi "$filename" 2>/dev/null | sed 's/^/  /'
    else
        # Basic audio info using file command
        file "$filename" | sed 's/^.*: /  /'
    fi
}

# Function to start recording
start_recording() {
    local output_file=$(generate_filename)
    
    # Check device status
    if ! check_device_status; then
        return 1
    fi
    
    # Apply quality settings
    apply_quality_preset
    
    print_status "Starting recording..."
    echo
    print_status "Recording Configuration:"
    echo "  Device: $DEVICE"
    echo "  Sample Rate: $SAMPLE_RATE Hz"
    echo "  Format: $FORMAT"
    echo "  Channels: $CHANNELS"
    echo "  Output File: $output_file"
    
    if [ ! -z "$DURATION" ]; then
        local duration_seconds=$(duration_to_seconds "$DURATION")
        local duration_formatted=$(format_duration $duration_seconds)
        echo "  Duration: $duration_formatted"
    else
        echo "  Duration: Until stopped (Ctrl+C)"
    fi
    
    echo
    
    # Check available disk space
    local available_kb=$(df "$OUTPUT_DIR" | tail -1 | awk '{print $4}')
    local available_mb=$((available_kb / 1024))
    
    if [ $available_mb -lt 100 ]; then
        print_warning "Low disk space: ${available_mb}MB available"
    fi
    
    # Build arecord command
    local cmd="arecord -D $DEVICE -r $SAMPLE_RATE -f $FORMAT -c $CHANNELS"
    
    if [ ! -z "$DURATION" ]; then
        local seconds=$(duration_to_seconds "$DURATION")
        cmd="$cmd -d $seconds"
    fi
    
    cmd="$cmd \"$output_file\""
    
    # Start recording with progress indication
    print_status "Recording... Press Ctrl+C to stop"
    echo
    
    # Set up signal handler for clean exit
    trap 'echo; print_status "Recording stopped by user"' INT
    
    # Execute recording command
    if eval $cmd; then
        echo
        print_status "Recording completed successfully!"
        
        # Show file information
        if [ -f "$output_file" ]; then
            local size=$(ls -lh "$output_file" | awk '{print $5}')
            print_status "Output file: $output_file ($size)"
            
            # Show audio information if available
            if command -v soxi > /dev/null 2>&1; then
                echo
                print_status "Recording details:"
                soxi "$output_file" | grep -E "(Sample Rate|Channels|Duration)" | sed 's/^/  /'
            fi
        fi
    else
        echo
        print_error "Recording failed!"
        
        # Clean up failed recording file
        if [ -f "$output_file" ] && [ ! -s "$output_file" ]; then
            rm -f "$output_file"
            print_status "Cleaned up empty recording file"
        fi
        
        return 1
    fi
    
    trap - INT
}

# Initialize
VERBOSE=false
ACTION="record"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        record|status|list|info)
            ACTION="$1"
            shift
            ;;
        -f|--filename)
            FILENAME="$2"
            shift 2
            ;;
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -q|--quality)
            QUALITY="$2"
            shift 2
            ;;
        -r|--rate)
            SAMPLE_RATE="$2"
            shift 2
            ;;
        -c|--channels)
            CHANNELS="$2"
            shift 2
            ;;
        --device)
            DEVICE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            print_header
            show_usage
            exit 0
            ;;
        *)
            # Check if it's a filename for 'info' action
            if [ "$ACTION" = "info" ] && [ -z "$INFO_FILE" ]; then
                INFO_FILE="$1"
                shift
            else
                print_error "Unknown option: $1"
                show_usage
                exit 1
            fi
            ;;
    esac
done

# Main execution
print_header

# Execute action
case "$ACTION" in
    record)
        if ! load_h2n_config; then
            exit 1
        fi
        start_recording
        ;;
    status)
        show_status
        ;;
    list)
        list_recordings
        ;;
    info)
        if [ -z "$INFO_FILE" ]; then
            print_error "No filename specified for info command"
            exit 1
        fi
        show_file_info "$INFO_FILE"
        ;;
    *)
        print_error "Unknown action: $ACTION"
        show_usage
        exit 1
        ;;
esac