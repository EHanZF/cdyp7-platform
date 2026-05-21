"""
Codebeamer MCP adapter.
"""

import os

import requests

CB_URL = os.getenv("CB_URL", "")
CB_TOKEN = os.getenv("CB_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {CB_TOKEN}",
    "Content-Type": "application/json",
}

REQUEST_TIMEOUT = 30


def create_requirement(data: dict):
    """Create a Codebeamer requirement."""

    response = requests.post(
        f"{CB_URL}/api/v3/items",
        json=data,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    return response.json()


def read_requirement(item_id: str):
    """Read a Codebeamer requirement."""

    response = requests.get(
        f"{CB_URL}/api/v3/items/{item_id}",
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    return response.json()


def update_requirement(item_id: str, data: dict):
    """Update a Codebeamer requirement."""

    response = requests.put(
        f"{CB_URL}/api/v3/items/{item_id}",
        json=data,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    return response.json()


def delete_requirement(item_id: str):
    """Delete a Codebeamer requirement."""

    response = requests.delete(
        f"{CB_URL}/api/v3/items/{item_id}",
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    return response.status_code
