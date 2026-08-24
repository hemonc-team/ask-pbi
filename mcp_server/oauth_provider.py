"""OAuth 2.1 authorization server для Claude custom connector.

MCP Python SDK монтирует /authorize, /token, /register и well-known.
Здесь — логин, PKCE-коды, токены и общий пароль маркетолога.

Статический ASKPBI_MCP_TOKEN по-прежнему принимается как Bearer
(Claude Code). Не путать с Power BI Service Principal.
"""

from __future__ import annotations

import hashlib
import html
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from pydantic import AnyUrl
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

MCP_SCOPE = "mcp"
ACCESS_TTL_SEC = 8 * 3600
REFRESH_TTL_SEC = 30 * 24 * 3600
AUTH_CODE_TTL_SEC = 300

# Только callback Claude (и localhost для своих тестов).
# Иначе открытый DCR + auto-approve = любой в интернете получает доступ.
_CLAUDE_HOSTS = frozenset({"claude.ai", "claude.com"})
_CLAUDE_PATH_PREFIXES = ("/api/mcp/auth_callback", "/oauth/")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def redirect_uri_allowed(uri: str) -> bool:
    parsed = urlparse(uri)
    host = (parsed.hostname or "").lower()
    if host in _LOOPBACK_HOSTS and parsed.scheme in ("http", "https"):
        return True
    if parsed.scheme != "https" or host not in _CLAUDE_HOSTS:
        return False
    path = parsed.path or ""
    return any(path == p or path.startswith(p) for p in _CLAUDE_PATH_PREFIXES)


def _passwords_match(given: str, expected: str) -> bool:
    """compare_digest по SHA-256 — одинаковая длина, без утечки длины пароля."""
    left = hashlib.sha256(given.encode()).digest()
    right = hashlib.sha256(expected.encode()).digest()
    return hmac.compare_digest(left, right)


def _issuer_and_resource() -> tuple[str, str]:
    public = os.environ.get("ASKPBI_PUBLIC_URL", "https://pbi.hemonc.ru/mcp").rstrip("/")
    issuer = public.rsplit("/mcp", 1)[0] or public
    return issuer.rstrip("/"), public


class AskPbiOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    def __init__(
        self,
        *,
        issuer_url: str,
        login_url: str,
        password: str,
        static_bearer: str,
        store_path: Path,
    ) -> None:
        self.issuer_url = issuer_url.rstrip("/")
        self.login_url = login_url
        self._password = password
        self._static_bearer = static_bearer
        self._store_path = store_path
        self._lock = threading.Lock()
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.state_mapping: dict[str, dict[str, str | None]] = {}
        self._load()

    # --- persist ---

    def _load(self) -> None:
        if not self._store_path.exists():
            return
        try:
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        now = time.time()
        for cid, data in (raw.get("clients") or {}).items():
            try:
                self.clients[cid] = OAuthClientInformationFull.model_validate(data)
            except Exception:
                continue
        for tok, data in (raw.get("tokens") or {}).items():
            try:
                item = AccessToken.model_validate(data)
            except Exception:
                continue
            if item.expires_at and item.expires_at < now:
                continue
            self.tokens[tok] = item
        for tok, data in (raw.get("refresh_tokens") or {}).items():
            try:
                item = RefreshToken.model_validate(data)
            except Exception:
                continue
            if item.expires_at and item.expires_at < now:
                continue
            self.refresh_tokens[tok] = item

    def _save_unlocked(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "clients": {k: v.model_dump(mode="json") for k, v in self.clients.items()},
            "tokens": {k: v.model_dump(mode="json") for k, v in self.tokens.items()},
            "refresh_tokens": {
                k: v.model_dump(mode="json") for k, v in self.refresh_tokens.items()
            },
        }
        tmp = self._store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._store_path)
        try:
            os.chmod(self._store_path, 0o600)
        except OSError:
            pass

    # --- clients ---

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise RegistrationError(
                error="invalid_client_metadata",
                error_description="client_id is required",
            )
        uris = [str(u) for u in (client_info.redirect_uris or [])]
        if not uris:
            raise RegistrationError(
                error="invalid_redirect_uri",
                error_description="redirect_uris is required",
            )
        bad = [u for u in uris if not redirect_uri_allowed(u)]
        if bad:
            raise RegistrationError(
                error="invalid_redirect_uri",
                error_description=(
                    "redirect_uri не из allowlist Claude "
                    f"({', '.join(bad[:3])})"
                ),
            )
        with self._lock:
            self.clients[client_info.client_id] = client_info
            self._save_unlocked()

    # --- authorize / login ---

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        state = params.state or secrets.token_urlsafe(16)
        self.state_mapping[state] = {
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "redirect_uri_provided_explicitly": str(
                params.redirect_uri_provided_explicitly
            ),
            "client_id": client.client_id,
            "resource": params.resource,
            "oauth_state": params.state,
        }
        sep = "&" if "?" in self.login_url else "?"
        return f"{self.login_url}{sep}state={state}"

    def login_page(self, state: str, error: str | None = None) -> HTMLResponse:
        if not state or state not in self.state_mapping:
            raise HTTPException(400, "Недействительная сессия входа. Начните Connect заново.")
        err_html = (
            f'<p class="err">{html.escape(error)}</p>' if error else ""
        )
        password_field = ""
        if self._password:
            password_field = """
            <label for="password">Пароль от Михаила</label>
            <input id="password" name="password" type="password" required
                   autocomplete="current-password" autofocus>
            """
        body = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Подключить дашборды</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 28rem; margin: 12vh auto; padding: 0 1.25rem; color: #1a1a1a; }}
    h1 {{ font-size: 1.35rem; }}
    p {{ line-height: 1.45; color: #333; }}
    label {{ display: block; margin: 1rem 0 0.35rem; font-weight: 600; }}
    input {{ width: 100%; box-sizing: border-box; padding: 0.6rem 0.7rem;
             font-size: 1rem; border: 1px solid #ccc; border-radius: 8px; }}
    button {{ margin-top: 1.25rem; width: 100%; padding: 0.75rem;
              font-size: 1rem; border: 0; border-radius: 8px;
              background: #1f6feb; color: #fff; cursor: pointer; }}
    .err {{ color: #b42318; }}
    .hint {{ font-size: 0.9rem; color: #666; }}
  </style>
</head>
<body>
  <h1>Дашборды клиники</h1>
  <p>Claude получит <strong>только чтение</strong> цифр из Power BI.
     Отчёты не меняются.</p>
  {err_html}
  <form method="post" action="/login/callback">
    <input type="hidden" name="state" value="{html.escape(state)}">
    {password_field}
    <button type="submit">Разрешить доступ</button>
  </form>
  <p class="hint">Если пароля нет — напишите Михаилу.</p>
</body>
</html>
"""
        return HTMLResponse(content=body, headers={"Cache-Control": "no-store"})

    async def handle_login_callback(self, request: Request) -> Response:
        form = await request.form()
        state = form.get("state")
        password = form.get("password") or ""
        if not isinstance(state, str) or not state:
            raise HTTPException(400, "Нет state")
        if not isinstance(password, str):
            password = ""
        if self._password and not _passwords_match(password, self._password):
            return self.login_page(state, "Неверный пароль.")
        try:
            redirect_to = self._issue_code(state)
        except HTTPException as exc:
            if exc.status_code == 400:
                return self.login_page(state, str(exc.detail))
            raise
        return RedirectResponse(url=redirect_to, status_code=302)

    def _issue_code(self, state: str) -> str:
        data = self.state_mapping.get(state)
        if not data:
            raise HTTPException(400, "Сессия входа истекла. Начните Connect заново.")
        redirect_uri = data["redirect_uri"]
        code_challenge = data["code_challenge"]
        client_id = data["client_id"]
        resource = data.get("resource")
        oauth_state = data.get("oauth_state")
        if not redirect_uri or not code_challenge or not client_id:
            raise HTTPException(400, "Повреждённая сессия входа")
        if not redirect_uri_allowed(redirect_uri):
            raise HTTPException(400, "redirect_uri не разрешён")

        code = secrets.token_urlsafe(24)
        auth_code = AuthorizationCode(
            code=code,
            client_id=client_id,
            redirect_uri=AnyUrl(redirect_uri),
            redirect_uri_provided_explicitly=data.get(
                "redirect_uri_provided_explicitly"
            )
            == "True",
            expires_at=time.time() + AUTH_CODE_TTL_SEC,
            scopes=[MCP_SCOPE],
            code_challenge=code_challenge,
            resource=resource,
            subject="marketer",
        )
        self.auth_codes[code] = auth_code
        del self.state_mapping[state]
        kwargs: dict[str, str | None] = {"code": code, "iss": self.issuer_url}
        if oauth_state:
            kwargs["state"] = oauth_state
        return construct_redirect_uri(redirect_uri, **kwargs)

    # --- tokens ---

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        return self.auth_codes.get(authorization_code)

    def _mint_tokens(
        self, *, client_id: str, scopes: list[str], resource: str | None, subject: str | None
    ) -> OAuthToken:
        now = int(time.time())
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        self.tokens[access] = AccessToken(
            token=access,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + ACCESS_TTL_SEC,
            resource=resource,
            subject=subject,
        )
        self.refresh_tokens[refresh] = RefreshToken(
            token=refresh,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + REFRESH_TTL_SEC,
            subject=subject,
        )
        self._save_unlocked()
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL_SEC,
            refresh_token=refresh,
            scope=" ".join(scopes),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        with self._lock:
            stored = self.auth_codes.get(authorization_code.code)
            if stored is None:
                raise TokenError(
                    error="invalid_grant",
                    error_description="authorization code does not exist",
                )
            del self.auth_codes[authorization_code.code]
            if not client.client_id:
                raise TokenError(
                    error="invalid_client", error_description="No client_id"
                )
            return self._mint_tokens(
                client_id=client.client_id,
                scopes=authorization_code.scopes or [MCP_SCOPE],
                resource=authorization_code.resource,
                subject=authorization_code.subject,
            )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        item = self.refresh_tokens.get(refresh_token)
        if item is None:
            return None
        if item.expires_at and item.expires_at < time.time():
            with self._lock:
                self.refresh_tokens.pop(refresh_token, None)
                self._save_unlocked()
            return None
        return item

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        with self._lock:
            stored = self.refresh_tokens.get(refresh_token.token)
            if stored is None or stored.client_id != client.client_id:
                raise TokenError(
                    error="invalid_grant",
                    error_description="refresh token does not exist",
                )
            del self.refresh_tokens[refresh_token.token]
            granted = scopes or stored.scopes or [MCP_SCOPE]
            return self._mint_tokens(
                client_id=client.client_id,
                scopes=granted,
                resource=None,
                subject=stored.subject,
            )

    async def load_access_token(self, token: str) -> AccessToken | None:
        if self._static_bearer and _passwords_match(token, self._static_bearer):
            return AccessToken(
                token=token,
                client_id="ask-pbi-static",
                scopes=[MCP_SCOPE],
                expires_at=None,
                subject="marketer",
            )
        item = self.tokens.get(token)
        if item is None:
            return None
        if item.expires_at and item.expires_at < time.time():
            with self._lock:
                self.tokens.pop(token, None)
                self._save_unlocked()
            return None
        return item

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        with self._lock:
            if isinstance(token, RefreshToken):
                self.refresh_tokens.pop(token.token, None)
            else:
                self.tokens.pop(token.token, None)
            self._save_unlocked()


def build_oauth_provider() -> AskPbiOAuthProvider:
    issuer, _resource = _issuer_and_resource()
    repo = Path(__file__).resolve().parent.parent
    default_store = repo / "var" / "oauth-store.json"
    store = Path(
        os.environ.get("ASKPBI_OAUTH_STORE", str(default_store))
    ).expanduser()
    return AskPbiOAuthProvider(
        issuer_url=issuer,
        login_url=f"{issuer}/login",
        password=os.environ.get("ASKPBI_OAUTH_PASSWORD", "").strip(),
        static_bearer=os.environ.get("ASKPBI_MCP_TOKEN", "").strip(),
        store_path=store,
    )
