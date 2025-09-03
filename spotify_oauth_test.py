#!/usr/bin/env python3
"""
Minimal Spotify OAuth Test
- Opens browser for login
- Handles redirect on http://127.0.0.1:8888/callback
- Saves access + refresh tokens
- Fetches user profile to confirm access
"""

import json
import requests
import webbrowser
from urllib.parse import urlencode
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==== CONFIG (replace with your values) ====
CLIENT_ID = "ENTER _CLIENT_ID
CLIENT_SECRET = "ENTER_CLIENT_SECRET"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "playlist-read-private playlist-read-collaborative user-library-read"

TOKENS_FILE = "tokens.json"


# ==== Simple HTTP server to capture redirect ====
class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if "/callback" in self.path:
            query = self.path.split("?", 1)[1]
            params = dict(qc.split("=") for qc in query.split("&"))
            self.server.auth_code = params.get("code")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = "<h1>Login successful! 🎶 You can close this window.</h1>"
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


def load_tokens():
    try:
        with open(TOKENS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def get_tokens(auth_code):
    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()


def refresh_tokens(refresh_token):
    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()


def get_profile(access_token):
    r = requests.get("https://api.spotify.com/v1/me",
                     headers={"Authorization": f"Bearer {access_token}"})
    r.raise_for_status()
    return r.json()


def main():
    tokens = load_tokens()

    if not tokens:
        # Step 1: Open login URL
        params = {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        }
        auth_url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
        print("🌐 Opening browser for login:", auth_url)
        webbrowser.open(auth_url)

        # Step 2: Start temporary local server to catch redirect
        server = HTTPServer(("127.0.0.1", 8888), OAuthHandler)
        server.handle_request()
        auth_code = server.auth_code

        # Step 3: Exchange auth code for tokens
        tokens = get_tokens(auth_code)
        save_tokens(tokens)
        print("✅ Tokens saved to", TOKENS_FILE)

    # Step 4: Check if access token works
    try:
        profile = get_profile(tokens["access_token"])
    except requests.HTTPError:
        # Token expired → refresh
        print("♻️ Refreshing token...")
        tokens = refresh_tokens(tokens["refresh_token"])
        save_tokens(tokens)
        profile = get_profile(tokens["access_token"])

    print("\n👤 Logged in as:", profile["display_name"], f"({profile['id']})")


if __name__ == "__main__":
    main()
