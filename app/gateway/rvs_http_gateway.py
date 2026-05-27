from __future__ import annotations

import csv
import json
import os
import secrets
import subprocess
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


APP_NAME = "CDYP7 RV&S Gateway"

SESSION_COOKIE = os.getenv("CDYP7_SESSION_COOKIE", "cdyp7_rvs_session")
SESSION_TTL_SECONDS = int(os.getenv("CDYP7_SESSION_TTL_SECONDS", "3600"))
CACHE_TTL_SECONDS = int(os.getenv("CDYP7_DASHBOARD_CACHE_SECONDS", "60"))

RVS_HOST = os.getenv("RVS_HOST", "skobde-mks-im.kobde.trw.com")
RVS_PORT = os.getenv("RVS_PORT", "7001")
RVS_IM_EXE = os.getenv("RVS_IM_EXE", r"C:\app\tools\ptc\RVS\bin\im.exe")
RVS_TIMEOUT = int(os.getenv("RVS_TIMEOUT", "120"))

STATIC_DIR = Path(os.getenv("CDYP7_STATIC_DIR", "frontend/public/static"))

DEFAULT_QUERY = "Find Liv Projects All My Work"

ALLOWED_QUERIES = [
    q.strip()
    for q in os.getenv(
        "RVS_ALLOWED_QUERIES",
        "Find Liv Projects All My Work,Find Liv Future Deliveries,Find Liv Tasks Requiring Attention,Find Liv Builds Requiring Attention,Find Liv Items Requiring Attention",
    ).split(",")
    if q.strip()
]

FIELDS = [
    f.strip()
    for f in os.getenv(
        "RVS_FIELDS",
        "ID,Summary,State,ALM_Owners,Type,Priority,ALM_Delivery,ALM_Target Date,ALM_Remaining Effort,ALM_Planned Completion Date,Project",
    ).split(",")
    if f.strip()
]

DETAIL_FIELDS = [
    f.strip()
    for f in os.getenv(
        "RVS_DETAIL_FIELDS",
        "ID,Summary,State,Type,Priority,Project,ALM_Team,ALM_Owners,ALM_Analysers,ALM_Classification,ALM_Target Date,ALM_Analysis Target Date,ALM_Planned Completion Date,ALM_Remaining Effort,Created By,Created Date,Modified By,Modified Date,ALM_Description",
    ).split(",")
    if f.strip()
]

DELIVERY_FIELD = os.getenv("RVS_DELIVERY_FIELD", "ALM_Delivery")
DELIVERY_DATE_FIELD = os.getenv("RVS_DELIVERY_DATE_FIELD", "ALM_Target Date")
OWNER_FIELD = os.getenv("RVS_OWNER_FIELD", "ALM_Owners")
REMAINING_FIELD = os.getenv("RVS_REMAINING_FIELD", "ALM_Remaining Effort")

CLOSED_STATES = {
    "closed",
    "done",
    "accepted",
    "resolved",
    "verified",
    "complete",
    "completed",
    "alm_closed",
    "alm_completed",
    "alm_cancelled",
    "alm_rejected",
    "alm_tested",
    "cancelled",
}

HIGH_PRIORITIES = {"high", "critical", "blocker", "urgent", "mandatory"}

SESSIONS: Dict[str, Dict[str, Any]] = {}
DASHBOARD_CACHE: Dict[str, Dict[str, Any]] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    return re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-") or "unassigned"


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
        arg = str(arg)
        if arg.startswith("--password="):
            safe.append("--password=***REDACTED***")
        else:
            safe.append(arg)
    return safe


def validate_im() -> None:
    if RVS_IM_EXE != "im" and not Path(RVS_IM_EXE).exists():
        raise RuntimeError(f"RVS_IM_EXE not found: {RVS_IM_EXE}")


def run_im_connect(username: str, password: str) -> Dict[str, Any]:
    validate_im()

    args = [
        RVS_IM_EXE,
        "connect",
        f"--hostname={RVS_HOST}",
        f"--port={RVS_PORT}",
        f"--user={username}",
        f"--password={password}",
        "--batch",
    ]

    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=RVS_TIMEOUT,
        shell=False,
    )

    return {
        "ok": completed.returncode == 0,
        "exitCode": completed.returncode,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
        "safeCommand": " ".join(redact_args(args)),
    }


def run_im_issues(username: str, password: str, query: str) -> str:
    if query not in ALLOWED_QUERIES:
        raise HTTPException(status_code=400, detail=f"Query is not allowlisted: {query}")

    args = [
        RVS_IM_EXE,
        "issues",
        f"--hostname={RVS_HOST}",
        f"--port={RVS_PORT}",
        "--batch",
        "--noapplyDisplayPattern",
        f"--user={username}",
        f"--password={password}",
        f"--fields={','.join(FIELDS)}",
        "--fieldsDelim=\t",
        f"--query={query}",
    ]

    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=RVS_TIMEOUT,
        shell=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "RV&S im issues failed\n"
            f"command: {' '.join(redact_args(args))}\n"
            f"exit: {completed.returncode}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )

    return completed.stdout


def run_im_item_details(username: str, password: str, item_id: str) -> Dict[str, Any]:
    if not str(item_id).isdigit():
        raise HTTPException(status_code=400, detail="Invalid RV&S item id")

    fields_to_try = list(DETAIL_FIELDS)
    completed = None

    for _ in range(10):
        args = [
            RVS_IM_EXE,
            "issues",
            f"--hostname={RVS_HOST}",
            f"--port={RVS_PORT}",
            "--batch",
            "--noapplyDisplayPattern",
            f"--user={username}",
            f"--password={password}",
            f"--fields={','.join(fields_to_try)}",
            "--fieldsDelim=\t",
            f'--queryDefinition=(field["ID"] = {item_id})',
        ]

        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=RVS_TIMEOUT,
            shell=False,
        )

        if completed.returncode == 0:
            rows = parse_tabular_im_output(completed.stdout, fields_to_try)

            if not rows:
                raise HTTPException(status_code=404, detail=f"RV&S item {item_id} not found")

            row = rows[0]

            return {
                "source": "ptc-rvs",
                "server": f"{RVS_HOST}:{RVS_PORT}",
                "generatedAt": utc_now(),
                "itemId": item_id,
                "item": normalize_rvs_item(row),
                "fields": row,
                "fieldsUsed": fields_to_try,
            }

        # RV&S usually reports invalid fields like:
        # Field "Description" does not exist.
        import re

        error_text = f"{completed.stdout}\n{completed.stderr}"
        match = re.search(r'Field\s+"([^"]+)"\s+does not exist', error_text)

        if match:
            bad_field = match.group(1)

            if bad_field in fields_to_try:
                fields_to_try.remove(bad_field)
                continue

        break

    raise RuntimeError(
        "RV&S item detail query failed\n"
        f"fields attempted: {fields_to_try}\n"
        f"exit: {completed.returncode if completed else 'not-run'}\n"
        f"stdout: {completed.stdout if completed else ''}\n"
        f"stderr: {completed.stderr if completed else ''}"
    )

    args = [
        RVS_IM_EXE,
        "issues",
        f"--hostname={RVS_HOST}",
        f"--port={RVS_PORT}",
        "--batch",
        "--noapplyDisplayPattern",
        f"--user={username}",
        f"--password={password}",
        f"--fields={','.join(DETAIL_FIELDS)}",
        "--fieldsDelim=\t",
        f'--queryDefinition=(field["ID"] = {item_id})',
    ]

    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=RVS_TIMEOUT,
        shell=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "RV&S item detail query failed\n"
            f"command: {' '.join(redact_args(args))}\n"
            f"exit: {completed.returncode}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )

    rows = parse_tabular_im_output(completed.stdout, DETAIL_FIELDS)

    if not rows:
        raise HTTPException(status_code=404, detail=f"RV&S item {item_id} not found")

    row = rows[0]

    return {
        "source": "ptc-rvs",
        "server": f"{RVS_HOST}:{RVS_PORT}",
        "generatedAt": utc_now(),
        "itemId": item_id,
        "item": normalize_rvs_item(row),
        "fields": row,
    }


def parse_tabular_im_output(text: str, fields: List[str]) -> List[Dict[str, str]]:
    lines = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    rows = list(csv.reader(lines, delimiter="\t"))
    if not rows:
        return []

    first = [c.strip() for c in rows[0]]
    expected_lower = {f.lower() for f in fields}
    first_lower = {c.lower() for c in first}

    if len(first_lower & expected_lower) >= 2:
        headers = first
        data_rows = rows[1:]
    else:
        headers = fields
        data_rows = rows

    parsed = []
    for row in data_rows:
        item = {
            header: row[idx].strip() if idx < len(row) else ""
            for idx, header in enumerate(headers)
        }
        if any(item.values()):
            parsed.append(item)

    return parsed


def normalize_rvs_item(row: Dict[str, str]) -> Dict[str, Any]:
    item_id = row.get("ID") or row.get("Id") or row.get("Issue ID") or ""
    summary = row.get("Summary") or f"Item {item_id}"
    state = row.get("State") or "Unknown"
    priority = row.get("Priority") or "Unspecified"
    delivery = row.get(DELIVERY_FIELD) or "Unassigned"
    target_date = row.get(DELIVERY_DATE_FIELD) or row.get("Target Date") or ""
    owners = split_owners(row.get(OWNER_FIELD) or row.get("Assigned User") or "")
    tracker = row.get("Type") or "RV&S Item"
    remaining = number(row.get(REMAINING_FIELD), 1)

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
        key = item.get("deliveryId") or "unassigned"

        delivery = grouped.setdefault(
            key,
            {
                "id": key,
                "name": item.get("deliveryName") or "Unassigned",
                "deliveryDate": item.get("deliveryDate") or "",
                "totalItems": 0,
                "completedItems": 0,
                "remainingItems": 0,
            },
        )

        delivery["totalItems"] += 1

        if is_closed(item.get("status", "")):
            delivery["completedItems"] += 1
        else:
            delivery["remainingItems"] += 1

        if not delivery.get("deliveryDate") and item.get("deliveryDate"):
            delivery["deliveryDate"] = item.get("deliveryDate")

    return sorted(grouped.values(), key=lambda d: d.get("deliveryDate") or "9999-12-31")


def cleanup_sessions() -> None:
    now = time.time()
    expired = [
        sid
        for sid, session in SESSIONS.items()
        if session["expires_at"] < now
    ]

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


def require_session(request: Request) -> Dict[str, Any]:
    session = get_session(request)

    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return session


def build_dashboard(username: str, password: str, query: str) -> Dict[str, Any]:
    cache_key = f"{username}:{query}"

    cached = DASHBOARD_CACHE.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL_SECONDS:
        return cached["dashboard"]

    start = time.time()

    raw = run_im_issues(username, password, query)
    rows = parse_tabular_im_output(raw, FIELDS)
    items = [normalize_rvs_item(row) for row in rows]

    deliveries = build_deliveries(items)
    open_items = [item for item in items if not is_closed(item.get("status", ""))]

    by_status = Counter(item["status"] for item in items)
    by_priority = Counter(item["priority"] for item in items)
    by_tracker = Counter(item["tracker"] for item in items)

    by_owner: Dict[str, int] = defaultdict(int)
    for item in items:
        for owner in item.get("owners") or ["Unassigned"]:
            by_owner[owner] += 1

    dashboard = {
        "generatedAt": utc_now(),
        "source": "ptc-rvs",
        "authority": "non_authoritative",
        "receiptBacked": True,
        "receiptId": f"gateway_rvs_rcpt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "query": query,
        "server": f"{RVS_HOST}:{RVS_PORT}",
        "user": username,
        "elapsedMs": int((time.time() - start) * 1000),
        "deliveries": deliveries,
        "totals": {
            "items": len(items),
            "openItems": len(open_items),
            "remaining": sum(number(item.get("remaining"), 1) for item in open_items),
            "atRisk": sum(
                1
                for item in open_items
                if item.get("blocked") or is_high(item.get("priority", ""))
            ),
        },
        "breakdowns": {
            "status": dict(by_status),
            "priority": dict(by_priority),
            "tracker": dict(by_tracker),
            "owner": dict(sorted(by_owner.items(), key=lambda kv: kv[1], reverse=True)),
        },
        "items": items,
    }

    DASHBOARD_CACHE[cache_key] = {
        "ts": time.time(),
        "dashboard": dashboard,
    }

    return dashboard


app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "https://localhost",
        "https://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index(request: Request) -> Response:
    session = get_session(request)

    if not session:
        return RedirectResponse("/auth/login", status_code=303)

    preferred = STATIC_DIR / "cdyp7-rvs-integrity-dashboard.html"
    if preferred.exists():
        return FileResponse(str(preferred))

    fallback = STATIC_DIR / "index.html"
    if fallback.exists():
        return FileResponse(str(fallback))

    return HTMLResponse(
        "<h1>CDYP7 RV&S Gateway</h1>"
        "<p>Static dashboard file not found.</p>"
        f"<p>Checked: {preferred}</p>"
        f"<p>Checked: {fallback}</p>"
    )


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": APP_NAME,
        "server": f"{RVS_HOST}:{RVS_PORT}",
        "imExeExists": Path(RVS_IM_EXE).exists() if RVS_IM_EXE != "im" else True,
        "allowedQueries": ALLOWED_QUERIES,
        "staticDir": str(STATIC_DIR),
        "staticDirExists": STATIC_DIR.exists(),
    }


@app.get("/auth/login")
def login_page() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>CDYP7 RV&S Login</title>
  <style>
    body {
      font-family: Segoe UI, Arial, sans-serif;
      background: #f6f8fc;
      margin: 0;
      display: grid;
      place-items: center;
      min-height: 100vh;
    }
    .card {
      background: white;
      border: 1px solid #e5e7eb;
      border-radius: 18px;
      box-shadow: 0 10px 30px rgba(15,23,42,.08);
      padding: 24px;
      width: min(420px, 92vw);
    }
    input, button {
      width: 100%;
      min-height: 42px;
      border-radius: 10px;
      margin-top: 8px;
      font: inherit;
    }
    input {
      border: 1px solid #d1d5db;
      padding: 8px 10px;
    }
    button {
      border: 0;
      background: #2563eb;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    label {
      display: block;
      font-size: 12px;
      text-transform: uppercase;
      color: #475467;
      font-weight: 700;
      margin-top: 12px;
    }
    .muted {
      color: #667085;
      font-size: 13px;
      line-height: 1.4;
    }
  </style>
</head>
<body>
  <form class="card" method="post" action="/auth/login">
    <h1>RV&amp;S Login</h1>
    <p class="muted">
      Use your Z-ID. This gateway requires VPN or office Wi-Fi and stores
      credentials only in a short-lived server-side session.
    </p>

    <label>Z-ID</label>
    <input name="username" autocomplete="username" required>

    <label>Password</label>
    <input name="password" type="password" autocomplete="current-password" required>

    <button type="submit">Login</button>
  </form>
</body>
</html>
        """
    )


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
        raise HTTPException(
            status_code=401,
            detail={
                "message": "RV&S authentication failed",
                "stderr": result["stderr"],
            },
        )

    sid = secrets.token_urlsafe(32)

    SESSIONS[sid] = {
        "username": username,
        "password": password,
        "created_at": time.time(),
        "expires_at": time.time() + SESSION_TTL_SECONDS,
    }

    response = RedirectResponse("/", status_code=303)

    response.set_cookie(
        SESSION_COOKIE,
        sid,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=os.getenv("CDYP7_COOKIE_SECURE", "false").lower() not in {"0", "false", "no"},
        samesite=os.getenv("CDYP7_COOKIE_SAMESITE", "lax"),
    )

    return response


@app.get("/auth/me")
def me(request: Request) -> Dict[str, Any]:
    session = require_session(request)

    return {
        "authenticated": True,
        "user": session["username"],
        "expiresAt": datetime.fromtimestamp(
            session["expires_at"],
            tz=timezone.utc,
        ).isoformat(),
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
def rvs_dashboard(
    request: Request,
    query: str = DEFAULT_QUERY,
) -> Dict[str, Any]:
    session = require_session(request)

    try:
        return build_dashboard(
            session["username"],
            session["password"],
            query,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/rvs/item/{item_id}")
def rvs_item_detail(request: Request, item_id: str) -> Dict[str, Any]:
    session = require_session(request)

    try:
        return run_im_item_details(
            session["username"],
            session["password"],
            item_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
