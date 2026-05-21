import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from app.mcp.codebeamer_dashboard import build_dashboard


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2))


def main():
    payload = json.loads(sys.argv[1])

    tool = payload.get("tool")
    input_data = payload.get("input", {})

    if tool == "cdyp7.cb.dashboard.refresh":
        query = input_data.get("query", "type = 'Requirement'")
        result = build_dashboard(query)

        receipt = {
            "receipt_id": f"rcpt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "tool": tool,
            "source": "codebeamer",
            "authority": "non_authoritative",
            "receipt_backed": True,
            "semantic_verification_required": False,
            "human_approved": False,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "input": input_data
        }

        write_json("output.json", result)
        write_json("receipt.json", receipt)
        return

    raise Exception(f"Unsupported MCP tool: {tool}")


if __name__ == "__main__":
    main()
