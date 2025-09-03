#!/usr/bin/env python3
"""
Enhanced Spotify Downloader for iPod (SpotDL 5+ compatible)
- Downloads albums, tracks, playlists (public or private)
- Converts tracks to AAC (M4A) with proper iPod tagging
- Embeds metadata and album artwork
- Logs downloads with retries and fallbacks
"""

import subprocess
import json
import re
import requests
import uuid
import time
from pathlib import Path
from datetime import datetime
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, urlparse, parse_qs

# ----------------------------------------
# Configuration
# ----------------------------------------
BASE_DIR = Path.home() / "SpotifyDownloads"
LOG_FILE = BASE_DIR / "download_log.txt"

PREFERRED_FORMAT = "flac"
FALLBACK_FORMAT = "mp3"
MP3_BITRATE = "320k"

# Spotify API credentials (replace with your values)
SPOTIFY_CLIENT_ID = "ENTER_CLIENT_ID"
SPOTIFY_CLIENT_SECRET = "ENTER_CLIENT_SECRET"
REDIRECT_URI = "http://localhost:8888/callback"

# Scopes needed for private playlists + liked songs
SPOTIFY_SCOPES = "playlist-read-private user-library-read"

# ----------------------------------------
# Spotify Auth
# ----------------------------------------
def get_spotify_token(client_only: bool = True) -> str:
    """
    Get a Spotify access token.
    client_only=True -> Client credentials flow (public data only)
    client_only=False -> Authorization code flow (private data)
    """
    if client_only:
        url = "https://accounts.spotify.com/api/token"
        data = {"grant_type": "client_credentials"}
        resp = requests.post(url, data=data, auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET))
        resp.raise_for_status()
        return resp.json()["access_token"]
    else:
        print("\n🔐 Private data requires user login...")
        params = {
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SPOTIFY_SCOPES
        }
        auth_url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
        print(f"👉 Open this URL in your browser and login:\n{auth_url}")
        code = input("\nPaste the 'code' param from redirect URL: ").strip()

        resp = requests.post("https://accounts.spotify.com/api/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        })
        resp.raise_for_status()
        tokens = resp.json()
        return tokens["access_token"]

# ----------------------------------------
# Spotify Metadata Fetchers
# ----------------------------------------
def extract_spotify_id_and_type(url: str):
    if "liked-songs" in url:  # special case
        return "liked", "liked"
    pattern = r'https?://open\.spotify\.com/(album|playlist|track)/([a-zA-Z0-9]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(2), match.group(1)
    return None, None

def get_album_metadata(spotify_id: str, token: str) -> dict:
    url = f"https://api.spotify.com/v1/albums/{spotify_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    tracks = [{
        "number": t["track_number"],
        "title": t["name"],
        "artists": ", ".join(a["name"] for a in t["artists"]),
        "album": data["name"]
    } for t in data["tracks"]["items"]]

    return {
        "artist": ", ".join([a["name"] for a in data["artists"]]),
        "album": data["name"],
        "tracks": tracks,
        "image_url": data["images"][0]["url"] if data.get("images") else None
    }

def get_track_metadata(spotify_id: str, token: str) -> dict:
    url = f"https://api.spotify.com/v1/tracks/{spotify_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    return {
        "artist": ", ".join([a["name"] for a in data["artists"]]),
        "album": data["album"]["name"],
        "tracks": [{
            "number": 1,
            "title": data["name"],
            "artists": ", ".join([a["name"] for a in data["artists"]]),
            "album": data["album"]["name"]
        }],
        "image_url": data["album"]["images"][0]["url"] if data["album"].get("images") else None
    }

def get_playlist_metadata(spotify_id: str, token: str) -> dict:
    url = f"https://api.spotify.com/v1/playlists/{spotify_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    tracks = []
    for idx, item in enumerate(data["tracks"]["items"], start=1):
        track = item["track"]
        if track:
            tracks.append({
                "number": idx,
                "title": track["name"],
                "artists": ", ".join([a["name"] for a in track["artists"]]),
                "album": data["name"]
            })

    return {
        "artist": data["owner"]["display_name"],
        "album": data["name"],
        "tracks": tracks,
        "image_url": data["images"][0]["url"] if data.get("images") else None
    }

def get_liked_songs_metadata(token: str) -> dict:
    url = "https://api.spotify.com/v1/me/tracks?limit=50"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    tracks = []
    for idx, item in enumerate(data["items"], start=1):
        t = item["track"]
        tracks.append({
            "number": idx,
            "title": t["name"],
            "artists": ", ".join([a["name"] for a in t["artists"]]),
            "album": t["album"]["name"]
        })

    return {
        "artist": "Liked Songs",
        "album": "Spotify Liked Songs",
        "tracks": tracks,
        "image_url": None
    }

def get_metadata_from_url(url: str) -> dict:
    spotify_id, content_type = extract_spotify_id_and_type(url)
    if not spotify_id:
        return {}

    client_only = (content_type in ["album", "track"])  # public
    token = get_spotify_token(client_only=client_only)

    if content_type == "album":
        return get_album_metadata(spotify_id, token)
    elif content_type == "track":
        return get_track_metadata(spotify_id, token)
    elif content_type == "playlist":
        return get_playlist_metadata(spotify_id, token)
    elif content_type == "liked":
        return get_liked_songs_metadata(token)
    return {}

# ----------------------------------------
# Utilities
# ----------------------------------------
def sanitize_filename(filename: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip('. ')[:200]

def check_spotdl_installed():
    try:
        result = subprocess.run(["spotdl", "--version"], capture_output=True, text=True, check=True)
        print(f"✅ SpotDL found: {result.stdout.strip()}")
        return True
    except:
        print("❌ SpotDL not found. Install with: pip install spotdl")
        return False

def download_album_art(url: str) -> Path | None:
    if not url:
        return None
    response = requests.get(url)
    if response.status_code == 200:
        tmp_file = Path(tempfile.gettempdir()) / f"album_art_{uuid.uuid4().hex}.jpg"
        with open(tmp_file, "wb") as f:
            f.write(response.content)
        return tmp_file
    return None

def log_download(artist: str, album: str, num_songs: int, fmt: str = "AAC M4A", status: str = "SUCCESS"):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {status} | {artist} - {album} | {num_songs} songs | {fmt}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(entry)

# ----------------------------------------
# Conversion & Metadata
# ----------------------------------------
def get_ffmpeg_aac_codec():
    try:
        result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
        if "aac_at" in result.stdout:
            return "aac_at"
    except:
        pass
    return "aac"

def embed_metadata(file_path: Path, track_info: dict, album_art: Path = None, pad_digits: int = 2):
    codec = get_ffmpeg_aac_codec()
    track_number_str = str(track_info['number']).zfill(pad_digits)
    safe_title = sanitize_filename(track_info['title'])
    output_file = file_path.parent / f"{track_number_str} - {safe_title}.m4a"

    cmd = ["ffmpeg", "-y", "-i", str(file_path)]
    if album_art and album_art.exists():
        cmd += ["-i", str(album_art), "-map", "0:a", "-map", "1:v",
                "-c:v", "copy", "-disposition:v:0", "attached_pic"]
    else:
        cmd += ["-map", "0:a"]

    cmd += [
        "-c:a", codec,
        "-b:a", "256k",
        "-movflags", "+faststart",
        "-metadata", f"artist={track_info['artists']}",
        "-metadata", f"album={track_info['album']}",
        "-metadata", f"title={track_info['title']}",
        "-metadata", f"track={track_info['number']}",
        str(output_file)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        file_path.unlink(missing_ok=True)
        return output_file
    else:
        print(f"❌ Conversion failed for {file_path.name}:\n{result.stderr}")
        return None

def convert_to_aac_parallel(folder: Path, track_list: list, album_art_url: str = None, max_workers: int = 4) -> int:
    files = sorted([f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in {'.mp3', '.flac', '.wav', '.ogg'}])
    album_art_path = download_album_art(album_art_url) if album_art_url else None
    pad_digits = len(str(len(track_list)))

    # safer matching by title
    matched = []
    for track in track_list:
        for f in files:
            if track["title"].lower() in f.stem.lower():
                matched.append((f, track, album_art_path, pad_digits))
                break

    converted = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for output_file in executor.map(lambda args: embed_metadata(*args), matched):
            if output_file:
                converted += 1
                print(f"✅ Converted → {output_file.name}")
    print(f"🎧 Converted {converted}/{len(track_list)} tracks to AAC (M4A)")
    return converted

# ----------------------------------------
# SpotDL Download
# ----------------------------------------
def run_spotdl_download_with_fallback(url: str, artist: str, album: str):
    folder = run_spotdl_download(url, artist, album, PREFERRED_FORMAT)
    if folder:
        return folder, PREFERRED_FORMAT
    print(f"⚠️ Preferred {PREFERRED_FORMAT} failed. Falling back to {FALLBACK_FORMAT}...")
    folder = run_spotdl_download(url, artist, album, FALLBACK_FORMAT, bitrate=MP3_BITRATE)
    return folder, FALLBACK_FORMAT

def run_spotdl_download(url: str, artist: str, album: str, fmt: str, bitrate: str = None, retries: int = 2):
    folder_name = sanitize_filename(f"{artist} - {album}")
    target_folder = BASE_DIR / folder_name
    target_folder.mkdir(parents=True, exist_ok=True)
    output_template = str(target_folder / "{artists} - {title}.{output-ext}")

    for attempt in range(1, retries + 2):
        print(f"🔄 SpotDL attempt {attempt} ({fmt})")
        cmd = ["spotdl", "download", url, "--output", output_template, "--format", fmt, "--threads", "8"]
        if fmt == "mp3" and bitrate:
            cmd += ["--bitrate", bitrate]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return target_folder
        print(f"❌ Attempt {attempt} failed:\n{result.stderr}")
        time.sleep(2 ** attempt)  # backoff
    return None

# ----------------------------------------
# Main
# ----------------------------------------
def download_spotify_url(url: str):
    metadata = get_metadata_from_url(url)
    if not metadata:
        print("❌ Could not fetch metadata")
        return

    artist = metadata.get("artist", "Unknown Artist")
    album = metadata.get("album", "Unknown Album")
    track_list = metadata.get("tracks", [])
    album_art_url = metadata.get("image_url")

    print(f"🎤 Artist: {artist}\n💿 Album/Playlist: {album}\n🎵 Tracks: {len(track_list)}")

    folder, fmt = run_spotdl_download_with_fallback(url, artist, album)
    if folder and folder.exists():
        num = convert_to_aac_parallel(folder, track_list, album_art_url, max_workers=8)
        if num > 0:
            log_download(artist, album, num, fmt=f"AAC M4A (from {fmt})")
            print(f"✅ Finished: {artist} - {album} ({num} tracks in AAC M4A)")
        else:
            print("⚠️ Conversion failed")
    else:
        print("❌ SpotDL download failed")

def main():
    print("=" * 60)
    print("🎵 Enhanced Spotify Downloader for iPod")
    print("=" * 60)
    if not check_spotdl_installed():
        sys.exit(1)

    while True:
        try:
            url = input("\n👉 Enter Spotify URL (or 'exit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if url.lower() in ["exit", "quit"]:
            break
        elif url.lower() == "history":
            if LOG_FILE.exists():
                print(LOG_FILE.read_text())
            continue
        download_spotify_url(url)

    print("\n✅ Exiting. Downloads saved to:", BASE_DIR)

if __name__ == "__main__":
    main()
