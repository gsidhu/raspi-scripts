import requests
import datetime
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from typing import List, Optional
from dotenv import load_dotenv
import os
import json
import sqlite3
from sqlite3 import Connection
load_dotenv(".scrobble-env")

cookies = {
  'PHPSESSID': os.getenv("PHPSESSID"),
}

headers = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'en-GB,en-US;q=0.7,en;q=0.3',
  'Content-Type': 'application/x-www-form-urlencoded',
  'Referer': 'https://openscrobbler.com/scrobble/song',
  'OWS-Version': '2.11.0',
  'Origin': 'https://openscrobbler.com',
  'DNT': '1',
  'Sec-Fetch-Dest': 'empty',
  'Sec-Fetch-Mode': 'cors',
  'Sec-Fetch-Site': 'same-origin',
  'Authorization': os.getenv("OPEN_SCROBBLER_JWT"),
  'Connection': 'keep-alive',
  'Alt-Used': 'openscrobbler.com',
  'Sec-GPC': '1',
}

db_path = "scrobble_history.db"
STATIONS_FILE = os.getenv("STATIONS_FILE", "fm_stations.json")

def load_stations():
    """Loads station data from the JSON file."""
    try:
        with open(STATIONS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {STATIONS_FILE} not found.")
        return {}

def create_track_data_string(track_title: str, artist: str, album: str) -> str:
    """
    Creates a URL-encoded string for a track, artist, album, and a current timestamp.

    The format is:
    'artist%5B%5D=...&track%5B%5D=...&album%5B%5D=...&timestamp%5B%5D=...'

    Args:
        artist (str): The name of the artist.
        track_title (str): The title of the track.
        album (str): The name of the album.

    Returns:
        str: The fully URL-encoded string.
    """
    # Get the current UTC timestamp and format it as an ISO 8601 string.
    # The 'Z' at the end indicates Zulu time (UTC).
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # URL-encode each of the string values.
    # quote_plus handles spaces as '+' which is often preferred for query strings.
    encoded_artist = quote_plus(artist)
    encoded_track = quote_plus(track_title)
    encoded_album = quote_plus(album)
    encoded_timestamp = quote_plus(timestamp)

    # Manually construct the final string, ensuring the '[]' parts of the keys
    # are correctly encoded as '%5B%5D'.
    result = (
        f"artist%5B%5D={encoded_artist}&"
        f"track%5B%5D={encoded_track}&"
        f"album%5B%5D={encoded_album}&"
        f"timestamp%5B%5D={encoded_timestamp}"
    )

    return result

def load_url_and_find_text(station_url: str, title_selector: str, artist_selector: str, album_selector: str, remove_string: str = "") -> Optional[List[str]]:
    """
    Loads content from a URL, parses it, and finds the innerText of the elements
    using their CSS selector.

    Args:
        station_url (str): The URL to fetch.
        title_selector (str): The CSS selector for the title element.
        artist_selector (str): The CSS selector for the artist element.
        album_selector (str): The CSS selector for the album element.
        remove_string (str): A string to remove from the extracted text.

    Returns:
        Optional[List[str]]: A list containing the title, artist, and album text,
                             or None if an error occurs.
    """
    try:
        # Fetch the content of the URL
        response = requests.get(station_url)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the elements using the provided CSS selectors
        title_elem = soup.select_one(title_selector) if title_selector else None
        artist_elem = soup.select_one(artist_selector) if artist_selector else None
        album_elem = soup.select_one(album_selector) if album_selector else None

        # Extract text, handle None case, and strip whitespace
        title = title_elem.get_text(strip=True) if title_elem else ''
        artist = artist_elem.get_text(strip=True) if artist_elem else ''
        album = album_elem.get_text(strip=True) if album_elem else ''

        # Remove specified string if provided
        if remove_string:
            title = title.replace(remove_string, '')
            artist = artist.replace(remove_string, '')
            album = album.replace(remove_string, '')

        return [title, artist, album]

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def scrobble_request(data, cookies=cookies, headers=headers) -> int:
  response = requests.post('https://openscrobbler.com/api/v2/scrobble.php', cookies=cookies, headers=headers, data=data)
  return response.status_code

def setup_db(conn: Connection):
  cursor = conn.cursor()
  # Create shazam table if it doesn't exist
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS scrobble_history (
          title TEXT,
          artist TEXT,
          album TEXT,
          station TEXT,
          timestamp TEXT
      )
  """)
  conn.commit()
  print("Scrobbling History database set up successfully.")

def add_play_to_db(title: str, artist: str, album: str, station: str, conn: Connection):
  cursor = conn.cursor()
  # Create shazam table if it doesn't exist
  timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
  cursor.execute("""
            INSERT INTO scrobble_history (title, artist, album, station, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (title, artist,album, station, timestamp))
  conn.commit()

def get_last_scrobbled_track_in_db(conn: Connection):
  """
  Retrieves the last scrobbled track from the 'scrobble_history' table.

  Args:
    conn: An active SQLite database connection object.

  Returns:
    A tuple containing the title, artist, and album of the last scrobbled
    track, or None if the table is empty.
  """
  cursor = conn.cursor()
  cursor.execute("""
    SELECT title, artist, album FROM scrobble_history ORDER BY ROWID DESC LIMIT 1;
    """)
  
  # Fetch the single result.
  last_track = cursor.fetchone()
  
  return last_track

def check_and_make_scrobble_request(title: str, artist: str, album: str|None, station_name: str, conn: Connection):
  # Check against last track
  last_scrobbled_track = get_last_scrobbled_track_in_db(conn)
  # print(last_scrobbled_track)
  if last_scrobbled_track is not None and title == last_scrobbled_track[0] and artist == last_scrobbled_track[1]:
    print("Same track as before. Skipping.")
    return False
  elif title == "":
    print("Couldn't find the track name. Skipping.")
    return False
  elif title == station_name or artist == station_name:
    print("Not a valid Artist or Title. Skipping.")
  else:
    # Scrobble
    if album is None:
      album = ""
    data = create_track_data_string(track_title=title, artist=artist, album=album)
    # print(data)
    response = scrobble_request(data)
    # Log to DB
    if response == 200:
      add_play_to_db(title, artist, album, station_name, conn)
      print("Response 200. Scrobbled successfully. Added to DB.")
      return True
    else:
      print(f"Response {response}. Failed to scrobble.")

def find_track_details_and_scrobble(station_name: str, title:Optional[str], artist:Optional[str], album: Optional[str]):
  if cookies['PHPSESSID'] is None or headers['Authorization'] is None:
    print("Environment variables not loaded correctly. Skipping.")
    return
  elif title is None and artist is None:
    # Get station details
    stations_json = load_stations()
    station_details = stations_json.get(station_name)
    station_web_link = ""
    css_selectors = {}
    if station_details:
      station_web_link = station_details["Web"]
      css_selectors = station_details["CSS"]
    else:
      print("Couldn't find station details in JSON. Skipping.")
      return
    # Get now playing details
    title_selector = css_selectors["title"] if "title" in css_selectors.keys() else ""
    artist_selector = css_selectors["artist"] if "artist" in css_selectors.keys() else ""
    album_selector = css_selectors["album"] if "album" in css_selectors.keys() else ""
    remove_string = css_selectors["remove"] if "remove" in css_selectors.keys() else ""
    result = load_url_and_find_text(station_web_link, title_selector, artist_selector, album_selector, remove_string)
    if result:
      title = result[0]
      artist = result[1]
      album = result[2]
  
  # Make scrobble request
  if title and artist:
    # Set up DB connection
    conn = sqlite3.connect(db_path)
    response = check_and_make_scrobble_request(title, artist, album, station_name, conn)  
    conn.close()
    
# Set up DB (Runs automatically when script is loaded)
conn = sqlite3.connect(db_path)
setup_db(conn)
conn.close()

## TEST
# if __name__ == '__main__':
#   station = "Radio Swiss Pop"
#   find_track_details_and_scrobble(station)