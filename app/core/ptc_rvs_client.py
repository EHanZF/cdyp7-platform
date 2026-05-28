import asyncio
import os
from typing import Any
from urllib.parse import quote

import httpx

PTC_RVS_BASE_URL = os.getenv(
    "PTC_RVS_BASE_URL",
    "https://skobde-mks-im.kobde.trw.com:7001",
).rstrip("/")

PTC_RVS_PROJECTS_PATH = os.getenv("PTC_RVS_PROJECTS_PATH", "/im/projects")
PTC_RVS_ISSUES_PATH = os.getenv("PTC_RVS_ISSUES_PATH", "/im/issues")

PTC_RVS_ITEM_LOOKUP_PATH = os.getenv(
    "PTC_RVS_ITEM_LOOKUP_PATH",
    "/im/issues/{item_number}",
)

PTC_RVS_QUERY_PARAM = os.getenv("PTC_RVS_QUERY_PARAM", "query")
PTC_RVS_LIMIT_PARAM = os.getenv("PTC_RVS_LIMIT_PARAM", "limit")
PTC_RVS_ITEM_NUMBER_PARAM = os.getenv("PTC_RVS_ITEM_NUMBER_PARAM", "itemNumber")

PTC_RVS_MAX_RESPONSE_BYTES = int(os.getenv("PTC_RVS_MAX_RESPONSE_BYTES", "2000000"))

ALLOWED_RVS_HOSTS = {
    "skobde-mks-im.kobde.trw.com",
}


def validate_fixed_base_url(base_url: str = PTC_RVS_BASE_URL) -> None:
    parsed = httpx.URL(base_url)

    if parsed.host not in ALLOWED_RVS_HOSTS:
        raise RuntimeError(f"PTC_RVS_BASE_URL host is not allowed: {parsed.host}")

    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(f"PTC_RVS_BASE_URL scheme is not allowed: {parsed.scheme}")


class PtcRvsClient:
    """
    Read-only RV&S / approved gateway client.

    Boundary rule:
      Do not add write/mutation methods to this class.
    """

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def get_projects(self) -> list[dict[str, Any]]:
        return await self._get_list(PTC_RVS_PROJECTS_PATH)

    async def get_items(self, query: str, limit: int) -> list[dict[str, Any]]:
        return await self._get_list(
            PTC_RVS_ISSUES_PATH,
            params={
                PTC_RVS_QUERY_PARAM: query,
                PTC_RVS_LIMIT_PARAM: limit,
            },
        )

    async def get_item_by_number(self, item_number: str) -> dict[str, Any]:
        """
        Read-only lookup for linked ALM item.

        Supports two endpoint styles:

        1. Path-template style:
             /api/items/by-number/{item_number}

        2. Query-param style:
             /api/items
             ?itemNumber=<item_number>

        Configure with:
          PTC_RVS_ITEM_LOOKUP_PATH
          PTC_RVS_ITEM_NUMBER_PARAM
        """
        safe_number = quote(str(item_number), safe="")

        if "{item_number}" in PTC_RVS_ITEM_LOOKUP_PATH:
            path = PTC_RVS_ITEM_LOOKUP_PATH.replace("{item_number}", safe_number)
            return await self._get_object(path)

        return await self._get_object(
            PTC_RVS_ITEM_LOOKUP_PATH,
            params={PTC_RVS_ITEM_NUMBER_PARAM: item_number},
        )

    async def _get_list(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        response = await self._request_with_retries(
            "GET",
            path,
            params=params,
        )

        data = self._json_or_raise(response=response, path=path)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("items", "data", "results", "projects", "issues"):
                if isinstance(data.get(key), list):
                    return data[key]

        raise RuntimeError(
            "Unexpected RV&S JSON response shape. "
            f"path={path!r}, "
            "expected list or object containing one of: "
            "items, data, results, projects, issues."
        )

    async def _get_object(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self._request_with_retries(
            "GET",
            path,
            params=params,
        )

        data = self._json_or_raise(response=response, path=path)

        if isinstance(data, dict):
            # Common wrapped object shapes.
            for key in ("item", "data", "result"):
                if isinstance(data.get(key), dict):
                    return data[key]

            return data

        if isinstance(data, list):
            if len(data) == 1 and isinstance(data[0], dict):
                return data[0]

            raise RuntimeError(
                "RV&S item lookup returned a list but not exactly one item. "
                f"path={path!r}, "
                f"count={len(data)}"
            )

        raise RuntimeError(
            "Unexpected RV&S item lookup JSON response shape. "
            f"path={path!r}, "
            "expected object or single-item list."
        )

    def _json_or_raise(self, response: httpx.Response, path: str) -> Any:
        content_type = response.headers.get("content-type", "")

        if "application/json" not in content_type.lower():
            preview = response.text[:1000].replace("\r", "\\r").replace("\n", "\\n")

            raise RuntimeError(
                "RV&S returned non-JSON response. "
                f"method=GET, "
                f"path={path!r}, "
                f"request_url={str(response.request.url)!r}, "
                f"status_code={response.status_code}, "
                f"content_type={content_type!r}, "
                f"content_length_header={response.headers.get('content-length')!r}, "
                f"actual_bytes={len(response.content)}, "
                f"headers={dict(response.headers)!r}, "
                f"preview={preview!r}. "
                "This usually means the configured endpoint is the RV&S web UI, "
                "a login/session page, a timezone bootstrap page, or not the "
                "approved REST/JSON API endpoint."
            )

        try:
            return response.json()
        except ValueError as exc:
            preview = response.text[:1000].replace("\r", "\\r").replace("\n", "\\n")
            raise RuntimeError(
                "RV&S response declared JSON but could not be decoded. "
                f"path={path!r}, "
                f"content_type={content_type!r}, "
                f"status_code={response.status_code}, "
                f"preview={preview!r}"
            ) from exc

    async def _request_with_retries(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        max_attempts = 3
        base_delay_seconds = 0.4

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.client.request(
                    method,
                    path,
                    params=params,
                )

                content_length = int(response.headers.get("content-length", "0") or "0")

                if content_length and content_length > PTC_RVS_MAX_RESPONSE_BYTES:
                    raise RuntimeError(
                        "RV&S response too large by content-length. "
                        f"path={path!r}, "
                        f"content_length={content_length}, "
                        f"max_bytes={PTC_RVS_MAX_RESPONSE_BYTES}"
                    )

                response.raise_for_status()

                if len(response.content) > PTC_RVS_MAX_RESPONSE_BYTES:
                    raise RuntimeError(
                        "RV&S response exceeded byte cap after download. "
                        f"path={path!r}, "
                        f"actual_bytes={len(response.content)}, "
                        f"max_bytes={PTC_RVS_MAX_RESPONSE_BYTES}"
                    )

                return response

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code

                if status not in (429, 503, 504) or attempt == max_attempts:
                    raise RuntimeError(
                        "RV&S HTTP error. "
                        f"method={method}, "
                        f"path={path!r}, "
                        f"status_code={status}, "
                        f"response_preview={exc.response.text[:1000]!r}"
                    ) from exc

            except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                if attempt == max_attempts:
                    raise RuntimeError(
                        "RV&S request timed out. "
                        f"method={method}, "
                        f"path={path!r}, "
                        f"attempts={max_attempts}"
                    ) from exc

            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "RV&S connection failed. "
                    f"method={method}, "
                    f"path={path!r}, "
                    "Check VPN, DNS, firewall, scheme, host, and port."
                ) from exc

            except httpx.RemoteProtocolError as exc:
                raise RuntimeError(
                    "RV&S protocol error. "
                    f"method={method}, "
                    f"path={path!r}, "
                    "This can happen when using HTTP against HTTPS, or when "
                    "the configured port is not a normal HTTP/1.1 REST endpoint."
                ) from exc

            await asyncio.sleep(base_delay_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("RV&S request failed after retries")
