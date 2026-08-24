"""HTTP-auth для MCP: OAuth для Claude Desktop + статический Bearer для Claude Code."""

from __future__ import annotations

import os
from typing import Optional

from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)

from mcp_server.oauth_provider import (
    AskPbiOAuthProvider,
    MCP_SCOPE,
    _issuer_and_resource,
    build_oauth_provider,
)


def build_http_auth() -> tuple[Optional[AuthSettings], Optional[AskPbiOAuthProvider]]:
    token = os.environ.get("ASKPBI_MCP_TOKEN", "").strip()
    if not token:
        return None, None
    issuer, resource = _issuer_and_resource()
    auth = AuthSettings(
        issuer_url=issuer,
        resource_server_url=resource,
        required_scopes=[MCP_SCOPE],
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[MCP_SCOPE],
            default_scopes=[MCP_SCOPE],
        ),
        revocation_options=RevocationOptions(enabled=True),
    )
    return auth, build_oauth_provider()
