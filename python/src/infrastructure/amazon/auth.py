from __future__ import annotations

import httpx


def get_auth_token(api_key: str, api_secret: str, refresh_token: str) -> str:
    url = "https://api.amazon.com/auth/o2/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": api_key,
        "client_secret": api_secret,
    }
    response = httpx.post(url, data=payload)
    response.raise_for_status()
    return response.json()["access_token"]
