@echo off
cd /d "%~dp0"

set MCP_TRANSPORT=streamable-http

.\.venv312\Scripts\python.exe .\app\mcp\ptc_rvs_mcp_server.py
pause