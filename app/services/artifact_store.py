"""
Artifact persistence utilities.
"""

from pathlib import Path


def save_artifact(name: str, content: str):
    """
    Save generated artifacts.
    """

    Path("data/results").mkdir(
        parents=True,
        exist_ok=True,
    )

    Path(f"data/results/{name}.json").write_text(
        content,
        encoding="utf-8",
    )
