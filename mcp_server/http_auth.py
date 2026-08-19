"""Статический Bearer для HTTP MCP. Не путать с Power BI Service Principal."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings


class StaticBearerVerifier:
    def __init__(self, token: str) -> None:
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not hmac.compare_digest(token, self._token):
            return None
        return AccessToken(
            token=token,
            client_id="ask-pbi",
            scopes=["mcp"],
            subject="marketer",
        )


def build_http_auth() -> tuple[Optional[AuthSettings], Optional[StaticBearerVerifier]]:
    token = os.environ.get("ASKPBI_MCP_TOKEN", "").strip()
    if not token:
        return None, None
    public = os.environ.get("ASKPBI_PUBLIC_URL", "https://n8n.hemonc.ru/mcp").rstrip("/")
    issuer = public.rsplit("/mcp", 1)[0] or public
    auth = AuthSettings(
        issuer_url=issuer,
        resource_server_url=public,
        required_scopes=["mcp"],
    )
    return auth, StaticBearerVerifier(token)
