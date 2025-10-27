# 🎶 PodSpot — Spotify → iPod Downloader

PodSpot lets you easily download Spotify music (albums, playlists, tracks, and your Liked Songs) and convert them into **iPod-ready AAC (M4A)** files with embedded metadata and album art.  

Supports **private playlists** and **Liked Songs** via OAuth login.  
Perfect for syncing your Spotify library to old iPods or Apple devices.  

---

## ✨ Features
- ✅ Download **albums, playlists, tracks, Liked Songs**
- ✅ Works with **private playlists**
- ✅ Converts to **AAC (M4A)** for iPod compatibility
- ✅ Keeps **track order and numbering**
- ✅ Embeds **artist, album, title, track number, album art**
- ✅ Cleans up originals (keeps only `.m4a`)
- ✅ Maintains a **download log**

---

## 🚀 Installation

1. Clone this repo:
   
      git clone https://github.com/Prajee7/podspot.git
      cd podspot

2. Install requirements:

     pip install spotdl requests
     brew install ffmpeg   # macOS
     sudo apt install ffmpeg   # Linux

3. Create a Spotify Developer App:

     Go to Spotify Developer Dashboard.
     Create an app → copy Client ID and Client Secret.
     Add http://127.0.0.1:8888/callback as a Redirect URI.
     Paste the credentials into podspot.py.

---

## 🎵 Usage

   Run PodSpot: python3 podspot.py


The first time, you’ll log in via browser.
After that, just enter a Spotify link or one of these keywords:

  https://open.spotify.com/album/... → downloads album
  
  https://open.spotify.com/playlist/... → downloads playlist
  
  https://open.spotify.com/track/... → downloads single track

  liked → downloads your Liked Songs

  history → shows last 10 downloads

  exit → quits the program

---

## 📂 Output

Downloads are saved in:

  ~/PodSpotDownloads/Artist - Album/
  
  01 - Song Title.m4a
  
  02 - Another Track.m4a
  



---
## 👨‍💻 Author : @_altamate_


---
## ⚖️ Disclaimer

This tool is for personal use only. Respect Spotify’s terms of service.
