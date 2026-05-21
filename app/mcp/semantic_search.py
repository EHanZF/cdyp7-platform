"""
Semantic search adapter.
"""


def semantic_search(_payload: dict):
    """
    Execute semantic search.
    """

    return {
        "matches": [
            {
                "requirement_id": "REQ-001",
                "score": 0.98,
                "content": "Brake timing requirement",
            }
        ]
    }
