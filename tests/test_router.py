from app.mcp.router import route_tool_call


def test_unknown_tool_raises():
    try:
        route_tool_call("invalid.tool", {})
    except Exception:
        assert True
        return

    assert False
