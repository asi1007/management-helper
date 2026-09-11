from __future__ import annotations

from amazon_api import shared_spapi_client


def get_auth_token() -> str:
    return shared_spapi_client().access_token()
