"""Проверка OAuth-провайдера без Power BI и без HTTP.

Запуск: `python3 -m mcp_server.oauth_selftest`
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path

from pydantic import AnyUrl

from mcp.server.auth.provider import AuthorizationParams, RegistrationError
from mcp.shared.auth import OAuthClientInformationFull

from mcp_server.oauth_provider import AskPbiOAuthProvider, redirect_uri_allowed


def _fail(msg: str) -> None:
    raise SystemExit(f"FAIL: {msg}")


def _ok(msg: str) -> None:
    print(f"ok: {msg}")


def test_redirect_allowlist() -> None:
    assert redirect_uri_allowed("https://claude.ai/api/mcp/auth_callback")
    assert redirect_uri_allowed("https://claude.com/api/mcp/auth_callback")
    assert redirect_uri_allowed("http://127.0.0.1:8756/callback")
    assert not redirect_uri_allowed("https://evil.example/callback")
    assert not redirect_uri_allowed("https://claude.ai.evil.com/api/mcp/auth_callback")
    _ok("redirect allowlist")


async def test_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "oauth-store.json"
        provider = AskPbiOAuthProvider(
            issuer_url="https://pbi.hemonc.ru",
            login_url="https://pbi.hemonc.ru/login",
            password="test-pass",
            static_bearer="static-token-value",
            store_path=store,
        )
        client = OAuthClientInformationFull.model_validate(
            {
                "client_id": "claude-test",
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "scope": "mcp",
            }
        )
        await provider.register_client(client)

        evil = OAuthClientInformationFull.model_validate(
            {
                "client_id": "evil",
                "redirect_uris": ["https://evil.example/cb"],
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            }
        )
        try:
            await provider.register_client(evil)
            _fail("evil redirect должен быть отклонён")
        except RegistrationError:
            _ok("DCR reject evil redirect")

        verifier = "a" * 43
        challenge = (
            __import__("base64")
            .urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        login_url = await provider.authorize(
            client,
            AuthorizationParams(
                state="client-state",
                scopes=["mcp"],
                code_challenge=challenge,
                redirect_uri=AnyUrl("https://claude.ai/api/mcp/auth_callback"),
                redirect_uri_provided_explicitly=True,
                resource="https://pbi.hemonc.ru/mcp",
            ),
        )
        if "state=" not in login_url:
            _fail(f"login url without state: {login_url}")
        state = login_url.rsplit("state=", 1)[-1]

        page = provider.login_page(state)
        if page.status_code != 200 or "Пароль" not in page.body.decode():
            _fail("login page")
        _ok("login page")

        from urllib.parse import parse_qs, urlparse

        redirect_to = provider._issue_code(state)  # noqa: SLF001
        parsed = urlparse(redirect_to)
        qs = parse_qs(parsed.query)
        code = qs["code"][0]
        if qs.get("state") != ["client-state"]:
            _fail(f"state not echoed: {qs}")
        _ok("authorization code issued")

        loaded = await provider.load_authorization_code(client, code)
        if loaded is None:
            _fail("load_authorization_code")
        tokens = await provider.exchange_authorization_code(client, loaded)
        access = await provider.load_access_token(tokens.access_token)
        if access is None or "mcp" not in access.scopes:
            _fail("access token")
        _ok("code → access token")

        if not tokens.refresh_token:
            _fail("no refresh token")
        rt = await provider.load_refresh_token(client, tokens.refresh_token)
        if rt is None:
            _fail("load_refresh_token")
        rotated = await provider.exchange_refresh_token(client, rt, ["mcp"])
        if rotated.access_token == tokens.access_token:
            _fail("refresh did not rotate")
        _ok("refresh rotation")

        static = await provider.load_access_token("static-token-value")
        if static is None or static.client_id != "ask-pbi-static":
            _fail("static bearer")
        _ok("static bearer still valid")

        # persist + reload
        provider2 = AskPbiOAuthProvider(
            issuer_url="https://pbi.hemonc.ru",
            login_url="https://pbi.hemonc.ru/login",
            password="test-pass",
            static_bearer="static-token-value",
            store_path=store,
        )
        if await provider2.get_client("claude-test") is None:
            _fail("client not persisted")
        if await provider2.load_access_token(rotated.access_token) is None:
            _fail("token not persisted")
        _ok("store persist")


def main() -> None:
    test_redirect_allowlist()
    asyncio.run(test_flow())
    print("oauth_selftest: all passed")


if __name__ == "__main__":
    main()
