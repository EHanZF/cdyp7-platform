"""
RAG evidence pipeline.
"""


def build_rag_evidence(payload: dict):
    """
    Build retrieval-augmented evidence package.
    """

    return {
        "evidence": payload,
        "verified": False,
    }
