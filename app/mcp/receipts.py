"""
Receipt persistence helpers.
"""

import json
from pathlib import Path


def write_receipt(data: dict):
    """
    Persist receipt to disk.
    """

    Path("data/receipts").mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        "data/receipts/latest.json",
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(data, handle, indent=2)
