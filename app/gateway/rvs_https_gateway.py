#!/usr/bin/env python3
"""
CDYP7 RV&S HTTPS Gateway

Purpose
-------
Internal HTTPS gateway that connects a static frontend dashboard to the
RV&S / Integrity backend adapter without exposing RV&S credentials to the browser.

Recommended runtime:
- Internal Windows host or self-hosted runner with PTC RV&S client installed
- VPN / office Wi-Fi only
- HTTPS only
- Short-lived HttpOnly Secure session cookie

Endpoints
---------
GET  /health
GET  /auth/me
POST /auth/login
POST /auth/logout
GET  /api/rvs/dashboard
GET  /api/rvs/receipt/latest
GET  / or /static/...    optional static dashboard serving from frontend/static
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import secrets
import subprocess
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

APP_NAME = "CDYP7 RV&S HTTPS Gateway"
SESSION_COOKIE = os.getenv("CDYP7_SESSION_COOKIE", "cdyp7_rvs_session")
SESSION_TTL_SECONDS = int(os.getenv("CDYP7_SESSION_TTL_SECONDS", "3600"))
CACHE_TTL_SECONDS = int(os.getenv("CDYP7_DASHBOARD_CACHE_SECONDS", "60"))

CLOSED_STATES = {
    "closed", "done", "accepted", "resolved", "verified", "complete", "completed",
    "alm_closed", "alm_completed", "alm_cancelled", "alm_rejected", "alm_tested", "cancelled",
}
HIGH_PRIORITIES = {"high", "critical", "blocker", "urgent", "mandatory"}

DEFAULT_ALLOWED_QUERIES = [
    "Find Liv Projects All My Work",
    "Find Liv Future Deliveries",
    "Find Liv Tasks Requiring Attention",
    "Find Liv Builds Requiring Attention",
    "Find Liv Items Requiring Attention",
]

DEFAULT_FIELDS = [
    "ID",
    "Summary",
    "State",
    "ALM_Owners",
    "Type",
    "Priority",
    "ALM_Delivery",
    "ALM_Target Date",
    "ALM_Remaining Effort",
    "ALM_Planned Completion Date",
    "Project",
]

SESSIONS: Dict[str, Dict[str, Any]] = {}
DASHBOARD_CACHE: Dict[str, Dict[str, Any]] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def csv_env(name: str, default: List[str]) -> List[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [x.strip() for x in value.split(",") if x.strip()]


def lower(value: Any) -> str:
    return str(value or "").strip().lower()


def is_closed(state: str) -> bool:
    return lower(state) in CLOSED_STATES


def is_high(priority: str) -> bool:
    return lower(priority) in HIGH_PRIORITIES


def number(value: Any, fallback: float = 1) -> float:
    try:
        if value in (None, ""):
            return fallback
        return float(value)
    except Exception:
        return fallback


def slug(value: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-") or "unassigned"


def split_owners(value: str) -> List[str]:
    if not value:
        return ["Unassigned"]
    for sep in [",", ";"]:
        if sep in value:
            parts = [p.strip() for p in value.split(sep) if p.strip()]
            return parts or ["Unassigned"]
    return [value.strip()] if value.strip() else ["Unassigned"]


def redact_args(args: Iterable[str]) -> List[str]:
    safe = []
    for arg in args:
        if str(arg).startswith("--password="):
            safe.append("--password=***REDACTED***")
        else:
            safe.append(str(arg))
    return safe


@dataclass
class RVSConfig:
    host: str = os.getenv("RVS_HOST", "skobde-mks-im.kobde.trw.com")
    port: str = os.getenv("RVS_PORT", "7001")
    im_exe: str = os.getenv("RVS_IM_EXE", "C:\\app\\tools\\ptc\\RVS\\bin\\im.exe")
    fields: List[str] = None
    allowed_queries: List[str] = None
    delivery_field: str = os.getenv("RVS_DELIVERY_FIELD", "ALM_Delivery")
    delivery_date_field: str = os.getenv("RVS_DELIVERY_DATE_FIELD", "ALM_Target Date")
    owner_field: str = os.getenv("RVS_OWNER_FIELD", "ALM_Owners")
    state_field: str = os.getenv("RVS_STATE_FIELD", "State")
    summary_field: str = os.getenv("RVS_SUMMARY_FIELD", "Summary")
    type_field: str = os.getenv("RVS_TYPE_FIELD", "Type")
    priority_field: str = os.getenv("RVS_PRIORITY_FIELD", "Priority")
    remaining_field: str = os.getenv("RVS_REMAINING_FIELD", "ALM_Remaining Effort")
    timeout: int = int(os.getenv("RVS_TIMEOUT", "120"))
    output_path: Path = Path(os.getenv("CDYP7_OUTPUT", "data/results/latest.json"))
    receipt_path: Path = Path(os.getenv("CDYP7_RECEIPT", "data/receipts/latest.json"))

    def __post_init__(self) -> None:
        if self.fields is None:
            self.fields = csv_env("RVS_FIELDS", DEFAULT_FIELDS)
        if self.allowed_queries is None:
            self.allowed_queries = csv_env("RVS_ALLOWED_QUERIES", DEFAULT_ALLOWED_QUERIES)

    def validate(self) -> None:
        path = Path(self.im_exe)
        if self.im_exe != "im" and not path.exists():
            raise RuntimeError(f"RVS_IM_EXE not found: {self.im_exe}")


CFG = RVSConfig()


def build_base_args(username: str, password: str) -> List[str]:
    return [
        CFG.im_exe,
        "issues",
        f"--hostname={CFG.host}",
        f"--port={CFG.port}",
        "--batch",
        "--noapplyDisplayPattern",
        f"--user={username}",
        f"--password={password}",
    ]


def run_im_connect(username: str, password: str) -> Dict[str, Any]:
    CFG.validate()
    args = [
        CFG.im_exe,
        "connect",
        f"--hostname={CFG.host}",
        f"--port={CFG.port}",
        f"--user={username}",
        f"--password={password}",
        "--batch",
    ]
    completed = subprocess.run(args, capture_output=True, text=True, timeout=CFG.timeout, shell=False)
    return {
        "ok": completed.returncode == 0,
        "exitCode": completed.returncode,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
        "safeCommand": " ".join(redact_args(args)),
    }


def run_im_issues(username: str, password: str, query: str) -> str:
    if query not in CFG.allowed_queries:
        raise HTTPException(status_code=400, detail=f"Query is not allowlisted: {query}")

    fields = ",".join(CFG.fields)
    args = build_base_args(username, password) + [
        f"--fields={fields}",
        "--fieldsDelim=\t",
        f"--query={query}",
    ]

    completed = subprocess.run(args, capture_output=True, text=True, timeout=CFG.timeout, shell=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "RV&S im issues failed\n"
            f"command: {' '.join(redact_args(args))}\n"
            f"exit: {completed.returncode}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )
    return completed.stdout


def parse_tabular_im_output(text: str) -> List[Dict[str, str]]:
    lines = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    rows = list(csv.reader(lines, delimiter="\t"))
    if not rows:
        return []

    first = [c.strip() for c in rows[0]]
    expected_lower = {f.lower() for f in CFG.fields}
    first_lower = {c.lower() for c in first}

    if len(first_lower & expected_lower) >= 2:
        headers = first
        data_rows = rows[1:]
    else:
        headers = CFG.fields
        data_rows = rows

    parsed = []
    for row in data_rows:
        item = {header: row[idx].strip() if idx < len(row) else "" for idx, header in enumerate(headers)}
        if any(item.values()):
            parsed.append(item)
    return parsed


def normalize_rvs_item(row: Dict[str, str]) -> Dict[str, Any]:
    item_id = row.get("ID") or row.get("Id") or row.get("Issue ID") or ""
    summary = row.get(CFG.summary_field) or row.get("Summary") or f"Item {item_id}"
    state = row.get(CFG.state_field) or row.get("State") or "Unknown"
    priority = row.get(CFG.priority_field) or row.get("Priority") or "Unspecified"
    delivery = row.get(CFG.delivery_field) or "Unassigned"
    target_date = row.get(CFG.delivery_date_field) or row.get("Target Date") or ""
    owners = split_owners(row.get(CFG.owner_field) or row.get("Assigned User") or "")
    tracker = row.get(CFG.type_field) or row.get("Type") or "RV&S Item"
    remaining = number(row.get(CFG.remaining_field), 1)

    return {
        "id": item_id,
        "title": summary,
        "deliveryId": slug(delivery),
        "deliveryName": delivery,
        "deliveryDate": target_date,
        "status": state,
        "priority": priority,
        "owners": owners,
        "owner": ", ".join(owners),
        "tracker": tracker,
        "type": tracker,
        "dueDate": target_date,
        "remaining": remaining,
        "blocked": "block" in lower(state) or lower(priority) == "blocker",
        "modifiedAt": row.get("Modified Date") or row.get("Modified") or "",
        "createdAt": row.get("Created Date") or row.get("Created") or "",
        "url": "",
        "rawFields": row,
    }


def build_deliveries(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in items:
        key = item["deliveryId"]
        d = grouped.setdefault(key, {
            "id": key,
            "name": item.get("deliveryName") or "Unassigned",
            "deliveryDate": item.get("deliveryDate") or "",
            "totalItems": 0,
            "completedItems": 0,
            "remainingItems": 0,
        })
        d["totalItems"] += 1
        if is_closed(item.get("status", "")):
            d["completedItems"] += 1
        else:
            d["remainingItems"] += 1
        if not d.get("deliveryDate") and item.get("deliveryDate"):
            d["deliveryDate"] = item.get("deliveryDate")
    return sorted(grouped.values(), key=lambda d: d.get("deliveryDate") or "9999-12-31")


def build_receipt(username: str, query: str, item_count: int, delivery_count: int, elapsed_ms: int) -> Dict[str, Any]:
    return {
        "receipt_id": f"gateway_rvs_rcpt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "tool": "cdyp7.gateway.rvs.dashboard",
        "source": "ptc-rvs",
        "authority": "non_authoritative",
        "receipt_backed": True,
        "semantic_verification_required": False,
        "human_approved": False,
        "generatedAt": utc_now(),
        "elapsedMs": elapsed_ms,
        "input": {
            "user": username,
            "query": query,
            "server": f"{CFG.host}:{CFG.port}",
            "fields": CFG.fields,
        },
        "output": {
            "items": item_count,
            "deliveries": delivery_count,
        },
    }


def build_dashboard(username: str, query: str) -> Dict[str, Any]:
    session = get_session_by_user(username)
    if not session:
        raise HTTPException(status_code=401, detail="No active session")

    cache_key = f"{username}:{query}"
    cached = DASHBOARD_CACHE.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL_SECONDS:
        return cached["dashboard"]

    start = time.time()
    raw = run_im_issues(username, session["password"], query)
    rows = parse_tabular_im_output(raw)
    items = [normalize_rvs_item(row) for row in rows]
    deliveries = build_deliveries(items)
    open_items = [i for i in items if not is_closed(i.get("status", ""))]
    by_status = Counter(i["status"] for i in items)
    by_priority = Counter(i["priority"] for i in items)
    by_tracker = Counter(i["tracker"] for i in items)
    by_owner: Dict[str, int] = defaultdict(int)
    for item in items:
        for owner in item.get("owners") or ["Unassigned"]:
            by_owner[owner] += 1

    elapsed_ms = int((time.time() - start) * 1000)
    rcpt = build_receipt(username, query, len(items), len(deliveries), elapsed_ms)

    dashboard = {
        "generatedAt": utc_now(),
        "source": "ptc-rvs",
        "authority": "non_authoritative",
        "receiptBacked": True,
        "receiptId": rcpt["receipt_id"],
        "query": query,
        "server": f"{CFG.host}:{CFG.port}",
        "user": username,
        "deliveries": deliveries,
        "totals": {
            "items": len(items),
            "openItems": len(open_items),
            "remaining": sum(number(i.get("remaining"), 1) for i in open_items),
            "atRisk": sum(1 for i in open_items if i.get("blocked") or is_high(i.get("priority", ""))),
        },
        "breakdowns": {
            "status": dict(by_status),
            "priority": dict(by_priority),
            "tracker": dict(by_tracker),
            "owner": dict(sorted(by_owner.items(), key=lambda kv: kv[1], reverse=True)),
        },
        "items": items,
    }

    write_json(CFG.output_path, dashboard)
    write_json(CFG.receipt_path, rcpt)
    DASHBOARD_CACHE[cache_key] = {"ts": time.time(), "dashboard": dashboard}
    return dashboard


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cleanup_sessions() -> None:
    now = time.time()
    expired = [sid for sid, session in SESSIONS.items() if session["expires_at"] < now]
    for sid in expired:
        SESSIONS.pop(sid, None)


def get_session(request: Request) -> Optional[Dict[str, Any]]:
    cleanup_sessions()
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return None
    session = SESSIONS.get(sid)
    if not session:
        return None
    if session["expires_at"] < time.time():
        SESSIONS.pop(sid, None)
        return None
    return session


def get_session_by_user(username: str) -> Optional[Dict[str, Any]]:
    cleanup_sessions()
    for session in SESSIONS.values():
        if session["username"] == username:
            return session
    return None


def require_session(request: Request) -> Dict[str, Any]:
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME)

    allowed_origins = csv_env("CDYP7_CORS_ORIGINS", ["https://localhost", "https://127.0.0.1", "http://localhost", "http://127.0.0.1"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    static_dir = Path(os.getenv("CDYP7_STATIC_DIR", "frontend/static"))
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {
            "ok": True,
            "service": APP_NAME,
            "server": f"{CFG.host}:{CFG.port}",
            "imExeExists": Path(CFG.im_exe).exists() if CFG.im_exe != "im" else True,
            "allowedQueries": CFG.allowed_queries,
        }

    @app.get("/")
    def index() -> Response:
        index_file = static_dir / "cdyp7-rvs-integrity-dashboard.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse("<h1>CDYP7 RV&S Gateway</h1><p>Static dashboard file not found.</p>")

    @app.get("/auth/login")
    def login_page() -> HTMLResponse:
        return HTMLResponse("""
<!doctype html><html><head><meta charset='utf-8'><title>CDYP7 RV&S Login</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;background:#f6f8fc;margin:0;display:grid;place-items:center;min-height:100vh}.card{background:white;border:1px solid #e5e7eb;border-radius:18px;box-shadow:0 10px 30px rgba(15,23,42,.08);padding:24px;width:min(420px,92vw)}input,button{width:100%;min-height:42px;border-radius:10px;margin-top:8px;font:inherit}input{border:1px solid #d1d5db;padding:8px 10px}button{border:0;background:#2563eb;color:white;font-weight:700}label{font-size:12px;text-transform:uppercase;color:#475467;font-weight:700}.muted{color:#667085;font-size:13px;line-height:1.4}</style></head>
<body><form class='card' method='post' action='/auth/login'><h1>RV&amp;S Login</h1><p class='muted'>Use your Z-ID. This gateway requires VPN or office Wi-Fi and stores credentials only in a short-lived server-side session.</p><label>Z-ID</label><input name='username' autocomplete='username' required><label>Password</label><input name='password' type='password' autocomplete='current-password' required><button type='submit'>Login</button></form></body></html>
""")

    @app.post("/auth/login")
    async def login(request: Request) -> Response:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", ""))
        else:
            form = await request.form()
            username = str(form.get("username", "")).strip()
            password = str(form.get("password", ""))

        if not username or not password:
            raise HTTPException(status_code=400, detail="username and password are required")

        result = run_im_connect(username, password)
        if not result["ok"]:
            raise HTTPException(status_code=401, detail={"message": "RV&S authentication failed", "stderr": result["stderr"]})

        sid = secrets.token_urlsafe(32)
        SESSIONS[sid] = {
            "username": username,
            "password": password,
            "created_at": time.time(),
            "expires_at": time.time() + SESSION_TTL_SECONDS,
        }

        wants_json = "application/json" in request.headers.get("accept", "") or "application/json" in content_type
        response: Response
        if wants_json:
            response = JSONResponse({"ok": True, "user": username, "expiresInSeconds": SESSION_TTL_SECONDS})
        else:
            response = RedirectResponse("/", status_code=303)

        response.set_cookie(
            SESSION_COOKIE,
            sid,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=os.getenv("CDYP7_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"},
            samesite=os.getenv("CDYP7_COOKIE_SAMESITE", "lax"),
        )
        return response

    @app.get("/auth/me")
    def me(request: Request) -> Dict[str, Any]:
        session = require_session(request)
        return {
            "authenticated": True,
            "user": session["username"],
            "expiresAt": datetime.fromtimestamp(session["expires_at"], tz=timezone.utc).isoformat(),
        }

    @app.post("/auth/logout")
    def logout(request: Request) -> Response:
        sid = request.cookies.get(SESSION_COOKIE)
        if sid:
            SESSIONS.pop(sid, None)
        response = JSONResponse({"ok": True})
        response.delete_cookie(SESSION_COOKIE)
        return response

    @app.get("/api/rvs/dashboard")
    def rvs_dashboard(request: Request, query: str = "Find Liv Projects All My Work") -> Dict[str, Any]:
        session = require_session(request)
        try:
            return build_dashboard(session["username"], query)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/rvs/receipt/latest")
    def latest_receipt(request: Request) -> Dict[str, Any]:
        require_session(request)
        if not CFG.receipt_path.exists():
            raise HTTPException(status_code=404, detail="No receipt generated yet")
        return json.loads(CFG.receipt_path.read_text(encoding="utf-8"))

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--host", default=os.getenv("CDYP7_GATEWAY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CDYP7_GATEWAY_PORT", "8443")))
    parser.add_argument("--certfile", default=os.getenv("CDYP7_TLS_CERT", ""))
    parser.add_argument("--keyfile", default=os.getenv("CDYP7_TLS_KEY", ""))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    ssl_kwargs = {}
    if args.certfile and args.keyfile:
        ssl_kwargs = {"ssl_certfile": args.certfile, "ssl_keyfile": args.keyfile}
        print(f"Starting HTTPS gateway on https://{args.host}:{args.port}")
    else:
        print("WARNING: TLS cert/key not provided. Starting HTTP. Use HTTPS for real credentials.")
        print(f"Starting HTTP gateway on http://{args.host}:{args.port}")

    uvicorn.run(app, host=args.host, port=args.port, reload=False, **ssl_kwargs)


if __name__ == "__main__":
    main()
