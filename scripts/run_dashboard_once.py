import asyncio
import os
import sys

sys.path.insert(0, ".")

from app.mcp.ptc_codebeamer_mcp_server import cdyp7_cb_dashboard


async def main():
    result = await cdyp7_cb_dashboard(
        query=os.getenv("CB_QUERY", "status != 'Closed'"),
        page_size=100,
        max_pages=25,
        persist=True,
    )

    print("Dashboard generated.")
    print("Items:", result.get("totals", {}).get("items"))
    print("Open items:", result.get("totals", {}).get("openItems"))
    print("Deliveries:", len(result.get("deliveries", [])))
    print("Receipt:", result.get("receiptId"))


if __name__ == "__main__":
    asyncio.run(main())