#!/usr/bin/env python3
"""
Interactive Google OAuth 2.0 Token Generator for AutoShorts.
Generates `youtube_credentials.json` for headless/server deployment.
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow
from app.config import settings
from app.services.youtube.oauth_manager import YOUTUBE_SCOPES


def main():
    print("=" * 65)
    print("AutoShorts YouTube Data API OAuth 2.0 Setup")
    print("=" * 65)

    client_secrets = settings.YOUTUBE_CLIENT_SECRETS_FILE
    credentials_target = settings.YOUTUBE_CREDENTIALS_FILE

    if not client_secrets.exists():
        print(f"\n[!] Missing client secrets file at: {client_secrets}")
        print("Please download your OAuth 2.0 Client ID JSON from Google Cloud Console:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth Client ID (Application type: Desktop or Web application)")
        print(f"3. Save the downloaded JSON file as: {client_secrets.resolve()}\n")
        return

    print(f"\n[✓] Found client secrets at: {client_secrets}")
    print(f"[i] Target credentials output: {credentials_target}\n")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets),
        scopes=YOUTUBE_SCOPES
    )

    try:
        # Try local web server if browser is available
        print("Attempting to open browser for authorization...")
        creds = flow.run_local_server(port=8080, open_browser=True)
    except Exception as e:
        print(f"Local browser flow unavailable ({e}). Using console flow...")
        creds = flow.run_console()

    # Save credentials JSON
    credentials_target.parent.mkdir(parents=True, exist_ok=True)
    with open(credentials_target, "w") as f:
        f.write(creds.to_json())

    print("\n" + "=" * 65)
    print("SUCCESS: YouTube OAuth 2.0 credentials saved successfully!")
    print(f"Location: {credentials_target.resolve()}")
    print("AutoShorts can now publish shorts and query analytics autonomously.")
    print("=" * 65)


if __name__ == "__main__":
    main()

