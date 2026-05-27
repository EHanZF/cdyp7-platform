import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cdyp7.ptc_rvs")


def audit_event(event_name: str, **fields: Any) -> None:
    """Emit structured audit logs for context bootstrap lifecycle events."""
    logger.info(
        json.dumps(
            {
                "event": event_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **fields,
            },
            default=str,
            sort_keys=True,
        )
    )
