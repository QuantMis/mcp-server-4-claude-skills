"""Bearer-token authentication as pure ASGI middleware.

Every request must carry ``Authorization: Bearer <token>`` matching the
configured secret. Comparison uses :func:`hmac.compare_digest` to avoid timing
side-channels. Failures return a JSON 401 and never echo the supplied token.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from starlette.types import ASGIApp, Receive, Scope, Send

_BEARER_PREFIX = "bearer "


def _extract_token(headers: list[tuple[bytes, bytes]]) -> str | None:
    for key, value in headers:
        if key.lower() == b"authorization":
            decoded = value.decode("latin-1")
            if decoded.lower().startswith(_BEARER_PREFIX):
                return decoded[len(_BEARER_PREFIX):].strip()
            return None
    return None


async def _reject(send: Send, message: str) -> None:
    body = b'{"error":"%s"}' % message.encode("ascii")
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BearerAuthMiddleware:
    """ASGI middleware that enforces a single shared bearer token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        if not token:
            raise ValueError("BearerAuthMiddleware requires a non-empty token")
        self._app = app
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Pass through lifespan/websocket events untouched.
            await self._app(scope, receive, send)
            return

        supplied = _extract_token(scope.get("headers", []))
        if supplied is None:
            await _reject(send, "missing or malformed bearer token")
            return
        if not hmac.compare_digest(supplied, self._token):
            await _reject(send, "invalid bearer token")
            return

        await self._app(scope, receive, send)


AuthFactory = Callable[[ASGIApp], Awaitable[None]]
