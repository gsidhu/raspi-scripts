import os
from collections import defaultdict
from pathlib import Path

def format_size(size_bytes):
    """Converts a size in bytes to a human-readable string (KB, MB, GB)."""
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    # Keep dividing by 1024 until the number is small enough
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024.0
        i += 1
    # Format to 2 decimal places and add the unit
    return f"{size_bytes:.2f} {size_name[i]}"

def get_dir_stats(directory_path):
    """
    Recursively calculates the total size and number of items (files and folders)
    in a given directory.
    Returns: (total_size_in_bytes, total_item_count)
    """
    total_size = 0
    total_count = 0
    
    try:
        for dirpath, dirnames, filenames in os.walk(directory_path):
            # Count every file and subdirectory
            total_count += len(dirnames) + len(filenames)
            
            # Add up the size of each file
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # Skip if it's a symlink or other non-file type
                if not os.path.islink(fp):
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        # File might be inaccessible or gone
                        pass
    except OSError as e:
        print(f"  ❌ Could not calculate stats for {os.path.basename(directory_path)}: {e}")
        return 0, 0
        
    return total_size, total_count

def find_takeout_folders(directory):
    """Find all folders in the given directory that start with 'Takeout'."""
    takeout_folders = []
    try:
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path) and item.startswith('Takeout'):
                takeout_folders.append(item_path)
    except FileNotFoundError:
        print(f"❌ Error: The directory '{directory}' does not exist.")
        return []
    except PermissionError:
        print(f"❌ Error: Permission denied to read the directory '{directory}'.")
        return []
        
    return sorted(takeout_folders, key=lambda p: Path(p).name)

def find_duplicate_takeout_folders(directory='.'):
    """
    Scans a directory for 'Takeout-*' folders and finds duplicates based on the
    contents of their 'Google Photos' subfolder, reporting size and item count.
    """
    abs_directory = os.path.abspath(directory)
    print(f"🔍 Searching for Takeout folders in: {abs_directory}")
    print("="*80)

    takeout_paths = find_takeout_folders(directory)

    if not takeout_paths:
        print("❌ No Takeout folders found in the specified directory.")
        return

    print(f"Found {len(takeout_paths)} Takeout folders to analyze.")
    
    # Dictionary to map a content signature to the list of Takeout folders
    content_signatures = defaultdict(list)
    # Dictionary to store stats for each Takeout folder to avoid recalculating
    folder_stats = {}

    print("\n🔬 Scanning 'Google Photos' contents in each Takeout folder...")
    
    for takeout_path in takeout_paths:
        takeout_name = os.path.basename(takeout_path)
        google_photos_path = os.path.join(takeout_path, 'Google Photos')

        if not os.path.isdir(google_photos_path):
            print(f"⚠️  Skipping {takeout_name}: No 'Google Photos' folder found.")
            continue

        try:
            # --- The core logic for identifying duplicates ---
            # Get the list of all files/folders directly inside 'Google Photos'
            contents = os.listdir(google_photos_path)
            # Create the signature: a sorted, hashable tuple of the contents
            signature = tuple(sorted(contents))
            content_signatures[signature].append(takeout_name)
            
            # --- New logic for calculating and reporting stats ---
            total_size, item_count = get_dir_stats(google_photos_path)
            formatted_size = format_size(total_size)
            
            # Store stats for later use in the summary
            folder_stats[takeout_name] = (formatted_size, item_count)
            
            print(f"  ✅ Scanned {takeout_name} - {formatted_size} for {item_count} items")

        except (OSError, PermissionError) as e:
            print(f"❌ Error accessing contents of {google_photos_path}: {e}")

    print("\n" + "="*80)
    print("📊 DUPLICATE ANALYSIS")
    print("="*80)

    duplicate_groups = {sig: folders for sig, folders in content_signatures.items() if len(folders) > 1}

    if not duplicate_groups:
        print("✅ No duplicate Takeout folders found based on 'Google Photos' contents.")
    else:
        print(f"Found {len(duplicate_groups)} set(s) of duplicate folders.\n")
        
        sorted_groups = sorted(duplicate_groups.values(), key=lambda folders: folders[0])
        
        for i, group in enumerate(sorted_groups, 1):
            print(f"--- Group {i} ---")
            print("The following Takeout folders have identical 'Google Photos' contents:")
            for takeout_name in sorted(group):
                print(f"  📁 {takeout_name}")
            
            # Display the stats for this group using the first folder as an example
            example_folder = group[0]
            if example_folder in folder_stats:
                f_size, i_count = folder_stats[example_folder]
                print(f"   (Contents: {f_size}, {i_count} items)")
            
            print()

    print(f"\n✅ Scan complete. Processed {len(takeout_paths)} Takeout folders.")

if __name__ == "__main__":
    # IMPORTANT: Replace this path with the actual path to the directory
    # containing all your 'Takeout-*' folders.
    target_directory = "/Volumes/Expansion/Media/Photos/Google Photos Backup - Gurjot"
    find_duplicate_takeout_folders(target_directory)