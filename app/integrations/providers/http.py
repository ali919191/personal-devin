"""Deterministic HTTP provider with explicit transport controls."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib import error, parse, request

from app.integrations.base import BaseIntegration
from app.integrations.exceptions import IntegrationExecutionError
from app.integrations.models import IntegrationRequest, IntegrationResponse


class HTTPIntegration(BaseIntegration):
    """Perform explicit HTTP requests with no hidden retries."""

    name = "http"

    def execute(self, request_model: IntegrationRequest) -> IntegrationResponse:
        method = request_model.payload.get("method", "GET")
        url = request_model.payload.get("url")
        headers = dict(request_model.payload.get("headers", {}))
        params = request_model.payload.get("params", {})
        body = request_model.payload.get("body")
        timeout = request_model.payload.get("timeout_seconds", 10)

        if not isinstance(method, str) or not method.strip():
            raise IntegrationExecutionError("payload.method must be a non-empty string")
        if not isinstance(url, str) or not url.strip():
            raise IntegrationExecutionError("payload.url must be a non-empty string")
        if not isinstance(headers, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in headers.items()
        ):
            raise IntegrationExecutionError("payload.headers must be a string-to-string mapping")
        if not isinstance(params, dict):
            raise IntegrationExecutionError("payload.params must be a dictionary")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise IntegrationExecutionError("payload.timeout_seconds must be a positive number")
        if request_model.payload.get("retry") not in (None, False, 0):
            raise IntegrationExecutionError("HTTPIntegration does not perform retries")

        encoded_url = self._build_url(url, params)
        request_body = self._encode_body(body, headers)
        started_at = datetime.now(UTC)

        http_request = request.Request(
            url=encoded_url,
            data=request_body,
            headers=headers,
            method=method.upper(),
        )

        try:
            with request.urlopen(http_request, timeout=float(timeout)) as response:
                raw_body = response.read()
                response_headers = dict(response.headers.items())
                status_code = response.getcode()
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise IntegrationExecutionError(
                f"HTTP request failed with status {exc.code}: {error_body}"
            ) from exc
        except error.URLError as exc:
            raise IntegrationExecutionError(f"HTTP request failed: {exc.reason}") from exc

        finished_at = datetime.now(UTC)
        decoded_body = raw_body.decode("utf-8", errors="replace")

        return IntegrationResponse(
            id=request_model.id,
            integration=self.name,
            payload={
                "method": method.upper(),
                "url": encoded_url,
                "status_code": status_code,
                "headers": response_headers,
                "body": self._decode_response_body(decoded_body, response_headers),
                "text": decoded_body,
            },
            metadata={
                **request_model.metadata,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": (finished_at - started_at).total_seconds(),
                "retry_attempts": 0,
            },
            timestamp=finished_at,
        )

    def _build_url(self, url: str, params: dict[str, Any]) -> str:
        if not params:
            return url
        query = parse.urlencode(sorted(params.items()), doseq=True)
        separator = "&" if parse.urlparse(url).query else "?"
        return f"{url}{separator}{query}"

    def _encode_body(self, body: Any, headers: dict[str, str]) -> bytes | None:
        if body is None:
            return None
        if isinstance(body, (dict, list)):
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
            return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if isinstance(body, str):
            return body.encode("utf-8")
        raise IntegrationExecutionError("payload.body must be a dict, list, string, or null")

    def _decode_response_body(self, body: str, headers: dict[str, str]) -> Any:
        content_type = headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                return json.loads(body)
            except json.JSONDecodeError as exc:
                raise IntegrationExecutionError("response body is not valid JSON") from exc
        return body
