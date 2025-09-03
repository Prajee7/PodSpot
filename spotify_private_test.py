#!/usr/bin/env python3
"""
Spotify Private Data Test
- Loads saved tokens from tokens.json
- Fetches private playlists and liked songs
"""

import json
import requests

TOKENS_FILE = "tokens.json"

def load_tokens():
    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_private_playlists(access_token):
    url = "https://api.spotify.com/v1/me/playlists"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def get_liked_songs(access_token, limit=10):
    url = f"https://api.spotify.com/v1/me/tracks?limit={limit}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def main():
    tokens = load_tokens()
    access_token = tokens["access_token"]

    print("🎶 Fetching private playlists...")
    playlists = get_private_playlists(access_token)
    for idx, pl in enumerate(playlists.get("items", []), start=1):
        print(f"{idx}. {pl['name']} (Tracks: {pl['tracks']['total']})")

    print("\n❤️ Fetching liked songs (first 10)...")
    liked = get_liked_songs(access_token)
    for idx, item in enumerate(liked.get("items", []), start=1):
        track = item["track"]
        print(f"{idx}. {track['name']} - {', '.join(a['name'] for a in track['artists'])}")

if __name__ == "__main__":
    main()
