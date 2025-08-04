#!/bin/bash

# === Enhanced Mac Backup Script ===
# Author: Gurjot
# Description: Flexible rsync-based backup script for Mac
# Usage: See show_help() function

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# === Configuration File Support ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/backup_config.conf"

# Default configuration
DEST_BASE="/Volumes/BackupDrive/Backup"
LOG_RETENTION_DAYS=30
BACKUP_SOURCES=(
  "Music:/Users/thatgurjot/Music"
  "Pictures:/Users/thatgurjot/Pictures"
)
RSYNC_EXCLUDES=(
  ".DS_Store"
  ".Spotlight-V100"
  ".Trashes"
  ".TemporaryItems"
  ".fseventsd"
  "*.tmp"
  ".localized"
  "Thumbs.db"
)

# Load custom configuration if it exists
if [[ -f "$CONFIG_FILE" ]]; then
  source "$CONFIG_FILE"
fi

# === Derived Configuration ===
LOG_DIR="$DEST_BASE/logs"
DATESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOG_DIR/backup_$DATESTAMP.log"

# === Color Output ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# === Utility Functions ===

print_color() {
  local color=$1
  shift
  echo -e "${color}$*${NC}"
}

log() {
  local message="[$(date +"%Y-%m-%d %H:%M:%S")] $1"
  echo -e "$message" | tee -a "$LOG_FILE"
}

log_error() {
  local message="[$(date +"%Y-%m-%d %H:%M:%S")] ERROR: $1"
  print_color "$RED" "$message" | tee -a "$LOG_FILE"
}

log_success() {
  local message="[$(date +"%Y-%m-%d %H:%M:%S")] SUCCESS: $1"
  print_color "$GREEN" "$message" | tee -a "$LOG_FILE"
}

log_warning() {
  local message="[$(date +"%Y-%m-%d %H:%M:%S")] WARNING: $1"
  print_color "$YELLOW" "$message" | tee -a "$LOG_FILE"
}

# === Validation Functions ===

check_dependencies() {
  if ! command -v rsync >/dev/null 2>&1; then
    log_error "rsync is not installed. Please install it first."
    exit 1
  fi
}

check_drive_space() {
  local required_space_gb=${1:-1}  # Default 1GB minimum
  local available_space=$(df -g "$DEST_BASE" 2>/dev/null | awk 'NR==2 {print $4}')
  
  if [[ -z "$available_space" ]] || [[ "$available_space" -lt "$required_space_gb" ]]; then
    log_error "Insufficient disk space. Need at least ${required_space_gb}GB"
    return 1
  fi
  log "Available space: ${available_space}GB"
}

validate_source_path() {
  local source_path="$1"
  if [[ ! -d "$source_path" ]]; then
    log_warning "Source path does not exist: $source_path"
    return 1
  fi
  return 0
}

# === Setup Functions ===

setup_environment() {
  # Ensure log directory exists
  mkdir -p "$LOG_DIR"
  
  # Check if external drive is mounted
  if [[ ! -d "$DEST_BASE" ]]; then
    log_error "External drive not found at $DEST_BASE"
    log_error "Is the drive mounted?"
    exit 1
  fi
  
  # Create backup directories
  for source_info in "${BACKUP_SOURCES[@]}"; do
    local name="${source_info%%:*}"
    mkdir -p "$DEST_BASE/$name"
  done
}

cleanup_old_logs() {
  log "Cleaning up logs older than $LOG_RETENTION_DAYS days..."
  find "$LOG_DIR" -name "*.log" -type f -mtime +$LOG_RETENTION_DAYS -exec rm {} \; 2>/dev/null || true
}

# === Backup Functions ===

build_rsync_excludes() {
  local exclude_args=()
  for exclude in "${RSYNC_EXCLUDES[@]}"; do
    exclude_args+=("--exclude=$exclude")
  done
  echo "${exclude_args[@]}"
}

backup_source() {
  local name="$1"
  local source_path="$2"
  local dest_path="$DEST_BASE/$name"
  
  if ! validate_source_path "$source_path"; then
    return 1
  fi
  
  log "Backing up $name from $source_path..."
  
  # Build rsync command with excludes
  local rsync_excludes
  rsync_excludes=$(build_rsync_excludes)
  
  # Perform backup with error handling
  local rsync_exit_code=0
  eval "rsync -avh --progress $rsync_excludes \"$source_path/\" \"$dest_path/\"" >> "$LOG_FILE" 2>&1 || rsync_exit_code=$?
  
  if [[ $rsync_exit_code -eq 0 ]]; then
    log_success "$name backup completed"
    return 0
  else
    log_error "$name backup failed with exit code $rsync_exit_code"
    return 1
  fi
}

# === Main Backup Logic ===

get_available_sources() {
  local available=()
  for source_info in "${BACKUP_SOURCES[@]}"; do
    local name="${source_info%%:*}"
    available+=("$name")
  done
  echo "${available[@]}"
}

backup_by_name() {
  local target_name="$1"
  
  for source_info in "${BACKUP_SOURCES[@]}"; do
    local name="${source_info%%:*}"
    local path="${source_info##*:}"
    
    if [[ "$name" == "$target_name" ]]; then
      backup_source "$name" "$path"
      return $?
    fi
  done
  
  log_error "Unknown backup source: $target_name"
  return 1
}

backup_all() {
  local failed_backups=()
  
  for source_info in "${BACKUP_SOURCES[@]}"; do
    local name="${source_info%%:*}"
    local path="${source_info##*:}"
    
    if ! backup_source "$name" "$path"; then
      failed_backups+=("$name")
    fi
  done
  
  if [[ ${#failed_backups[@]} -gt 0 ]]; then
    log_error "Some backups failed: ${failed_backups[*]}"
    return 1
  fi
  
  return 0
}

# === Configuration Management ===

create_config_template() {
  if [[ -f "$CONFIG_FILE" ]]; then
    log_warning "Configuration file already exists at $CONFIG_FILE"
    return 1
  fi
  
  cat > "$CONFIG_FILE" << 'EOF'
# Backup Configuration File
# Customize these settings for your environment

# External drive base path
DEST_BASE="/Volumes/BackupDrive/Backup"

# Log retention in days
LOG_RETENTION_DAYS=30

# Backup sources (format: "name:path")
BACKUP_SOURCES=(
  "Documents:$HOME/Documents"
  "Pictures:$HOME/Pictures"
  "Desktop:$HOME/Desktop"
  "Downloads:$HOME/Downloads"
  "Music:$HOME/Music"
)

# Files and patterns to exclude from backup
RSYNC_EXCLUDES=(
  ".DS_Store"
  ".Spotlight-V100"
  ".Trashes"
  ".TemporaryItems"
  ".fseventsd"
  "*.tmp"
  ".localized"
  "Thumbs.db"
)
EOF

  log_success "Configuration template created at $CONFIG_FILE"
  print_color "$BLUE" "Edit this file to customize your backup settings."
}

# === Help and Usage ===

show_help() {
  cat << EOF
Enhanced Mac Backup Script

Usage: $0 [OPTIONS] [TARGETS...]

TARGETS:
  all                    Back up all configured sources
  $(get_available_sources | tr ' ' '\n' | sed 's/^/  /')

OPTIONS:
  -h, --help            Show this help message
  -c, --config          Create configuration template
  -l, --list            List available backup sources
  -v, --version         Show version information
  --dry-run             Show what would be backed up (not implemented)

EXAMPLES:
  $0 all                           # Back up everything
  $0 Documents Pictures            # Back up selected folders
  $0 --config                      # Create config template
  $0 --list                        # Show available sources

CONFIGURATION:
  Edit $CONFIG_FILE to customize settings.
  Run '$0 --config' to create a template.

LOGS:
  Backup logs are stored in: $LOG_DIR
EOF
}

show_version() {
  echo "Enhanced Mac Backup Script v2.0"
  echo "https://github.com/yourusername/mac-backup-script"
}

list_sources() {
  echo "Available backup sources:"
  for source_info in "${BACKUP_SOURCES[@]}"; do
    local name="${source_info%%:*}"
    local path="${source_info##*:}"
    printf "  %-12s -> %s\n" "$name" "$path"
  done
}

# === Main Execution ===

main() {
  # Parse options
  while [[ $# -gt 0 ]]; do
    case $1 in
      -h|--help)
        show_help
        exit 0
        ;;
      -c|--config)
        create_config_template
        exit $?
        ;;
      -l|--list)
        list_sources
        exit 0
        ;;
      -v|--version)
        show_version
        exit 0
        ;;
      --dry-run)
        log_warning "Dry run mode not yet implemented"
        exit 1
        ;;
      -*)
        log_error "Unknown option: $1"
        show_help
        exit 1
        ;;
      *)
        break
        ;;
    esac
    shift
  done
  
  # Show help if no arguments
  if [[ $# -eq 0 ]]; then
    show_help
    exit 1
  fi
  
  # Initialize
  check_dependencies
  setup_environment
  cleanup_old_logs
  check_drive_space 2  # Require at least 2GB free
  
  log "=== Backup started ==="
  log "Configuration: $(basename "$CONFIG_FILE")"
  log "Destination: $DEST_BASE"
  
  # Process targets
  local overall_success=true
  
  for target in "$@"; do
    case "$target" in
      all)
        if ! backup_all; then
          overall_success=false
        fi
        ;;
      *)
        if ! backup_by_name "$target"; then
          overall_success=false
        fi
        ;;
    esac
  done
  
  # Final status
  if $overall_success; then
    log_success "All backups completed successfully"
    exit 0
  else
    log_error "Some backups failed - check log for details"
    exit 1
  fi
}

# Run main function with all arguments
main "$@"