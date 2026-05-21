"""
Receipt hashing utilities.
"""

import hashlib


def hash_receipt(data: str) -> str:
    """
    Generate SHA-256 hash for receipt payloads.
    """

    return hashlib.sha256(data.encode()).hexdigest()
