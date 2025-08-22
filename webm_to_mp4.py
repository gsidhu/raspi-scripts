import os
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
# Set the root folder where you want to start searching for .webm files.
# The script will search this folder and all subfolders recursively.
ROOT_FOLDER = Path.home() / "Documents/GitHub/music-dl/TV"

# Set the number of files to convert simultaneously.
# The user requested 3.
MAX_WORKERS = 3

# --- CONVERSION FUNCTION ---
def convert_file(webm_file: Path):
    """
    Converts a single .webm file to .mp4 using ffmpeg.
    
    Args:
        webm_file (Path): The Path object of the input .webm file.
    """
    # Create the output filename.
    # We replace the .webm extension with .mp4.
    mp4_file = webm_file.with_suffix(".mp4")

    # The ffmpeg command. We use `-i` for the input and specify the output file.
    # `-c:v copy` and `-c:a copy` tell ffmpeg to copy the video and audio streams
    # without re-encoding, which is much faster and retains quality.
    # This works if the codecs (VP9/Opus for WebM) are compatible with the MP4 container,
    # which is often the case. If not, you can remove these flags to re-encode.
    command = [
        "ffmpeg",
        "-i", str(webm_file),
        "-c:v", "copy",
        "-c:a", "copy",
        str(mp4_file)
    ]
    
    print(f"Starting conversion for: {webm_file.name}")
    
    try:
        # Use subprocess.run to execute the command. `capture_output=True` is useful for debugging.
        # `text=True` ensures output is a string. `check=True` raises an error if the command fails.
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Successfully converted {webm_file.name} to {mp4_file.name}")
        
    except subprocess.CalledProcessError as e:
        print(f"Error converting {webm_file.name}:")
        print(f"  Command failed with exit code {e.returncode}")
        print(f"  Stdout: {e.stdout}")
        print(f"  Stderr: {e.stderr}")
    except FileNotFoundError:
        print("Error: `ffmpeg` not found. Please ensure it is installed and in your system's PATH.")

# --- MAIN LOGIC ---
def main():
    """
    Main function to find all .webm files and process them in parallel.
    """
    print("Searching for .webm files in subfolders...")
    
    # Use pathlib's rglob() to find all files with a .webm extension
    # in the ROOT_FOLDER and all its subdirectories (recursively).
    webm_files = list(ROOT_FOLDER.rglob('*.webm'))
    
    if not webm_files:
        print("No .webm files found. Exiting.")
        return

    print(f"Found {len(webm_files)} .webm files. Converting with {MAX_WORKERS} workers.")

    # Use ThreadPoolExecutor for parallel execution.
    # It creates a pool of worker threads to execute jobs.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # The executor.map() function applies the convert_file function
        # to each item in the webm_files list. It's a simple way to
        # submit all tasks and get the results as they finish.
        executor.map(convert_file, webm_files)
        
    print("\nAll conversions finished.")

if __name__ == "__main__":
    main()
