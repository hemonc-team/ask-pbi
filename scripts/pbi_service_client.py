#!/usr/bin/env python3
"""
Read-only REST-клиент Power BI Service для marketing skill.

Delegated OAuth (Device Code) под личным Pro-аккаунтом маркетолога.
Только чтение: list workspaces/datasets/reports, discover-schema (INFO.*), execute-dax.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import requests
except ImportError:
    sys.stderr.write("ERROR: pip install requests\n")
    sys.exit(1)

AUTHORITY = "https://login.microsoftonline.com"
PBI_API = "https://api.powerbi.com/v1.0/myorg"
MARKETING_SCOPES = (
    "https://analysis.windows.net/powerbi/api/Dataset.Read.All "
    "https://analysis.windows.net/powerbi/api/Report.Read.All "
    "https://analysis.windows.net/powerbi/api/Workspace.Read.All "
    "offline_access"
)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name, default)


@dataclass
class Config:
    tenant_id: str
    client_id: str
    tokens_path: Path

    @classmethod
    def load(cls) -> "Config":
        tenant_id = _env("PBI_TENANT_ID")
        client_id = _env("PBI_CLIENT_ID")
        if not tenant_id or not client_id:
            sys.stderr.write("ERROR: нужны PBI_TENANT_ID и PBI_CLIENT_ID\n")
            sys.exit(2)
        tokens_path = Path(
            _env("PBI_TOKENS_PATH", str(Path.home() / ".pbi" / "tokens.json"))
        ).expanduser()
        return cls(tenant_id=tenant_id, client_id=client_id, tokens_path=tokens_path)


class AuthError(RuntimeError):
    pass


def _load_tokens(cfg: Config) -> dict[str, Any]:
    if not cfg.tokens_path.exists():
        raise AuthError(
            f"Нет {cfg.tokens_path}. Пройди device-code-start + device-code-poll "
            "под своим PBI email (см. references/SETUP_MARKETER.md)."
        )
    return json.loads(cfg.tokens_path.read_text())


def _save_tokens(cfg: Config, data: dict[str, Any]) -> None:
    cfg.tokens_path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["_saved_at"] = int(time.time())
    cfg.tokens_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    try:
        cfg.tokens_path.chmod(0o600)
    except OSError:
        pass


def device_code_start(cfg: Config) -> dict[str, Any]:
    r = requests.post(
        f"{AUTHORITY}/{cfg.tenant_id}/oauth2/v2.0/devicecode",
        data={"client_id": cfg.client_id, "scope": MARKETING_SCOPES},
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()
    cfg.tokens_path.parent.mkdir(parents=True, exist_ok=True)
    device_file = cfg.tokens_path.with_name("device.json")
    device_file.write_text(json.dumps(payload, indent=2))
    return payload


def device_code_poll(cfg: Config, device_code: str) -> dict[str, Any]:
    r = requests.post(
        f"{AUTHORITY}/{cfg.tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": cfg.client_id,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
        },
        timeout=30,
    )
    payload = r.json()
    if r.status_code != 200 or "access_token" not in payload:
        raise AuthError(f"Device code flow не завершён: {payload}")
    _save_tokens(cfg, payload)
    return payload


def refresh_access_token(cfg: Config) -> dict[str, Any]:
    tokens = _load_tokens(cfg)
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise AuthError("Нет refresh_token — нужен новый Device Code Flow.")
    r = requests.post(
        f"{AUTHORITY}/{cfg.tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": cfg.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "https://analysis.windows.net/powerbi/api/.default offline_access",
        },
        timeout=30,
    )
    payload = r.json()
    if r.status_code != 200 or "access_token" not in payload:
        raise AuthError(
            f"Refresh не удался: {payload}. При invalid_grant — повтори Device Code Flow."
        )
    _save_tokens(cfg, payload)
    return payload


def get_valid_token(cfg: Config, margin_s: int = 120) -> str:
    tokens = _load_tokens(cfg)
    saved_at = tokens.get("_saved_at", 0)
    expires_in = tokens.get("expires_in", 0)
    if saved_at and expires_in and (time.time() - saved_at) < (expires_in - margin_s):
        return tokens["access_token"]
    return refresh_access_token(cfg)["access_token"]


class PBIClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {get_valid_token(self.cfg)}"}

    def _get(self, path: str, **kw) -> Any:
        r = requests.get(f"{PBI_API}{path}", headers=self._headers(), timeout=60, **kw)
        r.raise_for_status()
        return r.json() if r.content else None

    def _post(self, path: str, json_body: Any) -> requests.Response:
        return requests.post(
            f"{PBI_API}{path}", headers=self._headers(), json=json_body, timeout=120
        )

    def list_workspaces(self) -> list[dict]:
        return self._get("/groups").get("value", [])

    def list_datasets(self, group_id: str) -> list[dict]:
        return self._get(f"/groups/{group_id}/datasets").get("value", [])

    def list_reports(self, group_id: str) -> list[dict]:
        return self._get(f"/groups/{group_id}/reports").get("value", [])

    def execute_dax(self, group_id: str, dataset_id: str, query: str) -> dict:
        body = {
            "queries": [{"query": query}],
            "serializerSettings": {"includeNulls": True},
        }
        r = self._post(f"/groups/{group_id}/datasets/{dataset_id}/executeQueries", body)
        if r.status_code != 200:
            raise RuntimeError(
                f"executeQueries HTTP {r.status_code}: {r.text}\n"
                "Проверь tenant setting Semantic Model Execute Queries REST API "
                "и доступ Pro к датасету."
            )
        return r.json()

    def discover_schema(self, group_id: str, dataset_id: str) -> dict[str, list[dict]]:
        out = {}
        for name, query in (
            ("tables", "EVALUATE INFO.TABLES()"),
            ("measures", "EVALUATE INFO.MEASURES()"),
            ("columns", "EVALUATE INFO.COLUMNS()"),
            ("relationships", "EVALUATE INFO.RELATIONSHIPS()"),
        ):
            result = self.execute_dax(group_id, dataset_id, query)
            out[name] = result["results"][0]["tables"][0]["rows"]
        return out


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("device-code-start")
    sp = sub.add_parser("device-code-poll")
    sp.add_argument("--device-code", required=True)
    sub.add_parser("token")
    sub.add_parser("list-workspaces")
    sp = sub.add_parser("list-datasets")
    sp.add_argument("--group", required=True)
    sp = sub.add_parser("list-reports")
    sp.add_argument("--group", required=True)
    sp = sub.add_parser("discover-schema")
    sp.add_argument("--group", required=True)
    sp.add_argument("--dataset", required=True)
    sp = sub.add_parser("execute-dax")
    sp.add_argument("--group", required=True)
    sp.add_argument("--dataset", required=True)
    sp.add_argument("--query", required=True)

    args = p.parse_args()
    cfg = Config.load()

    if args.cmd == "device-code-start":
        print(device_code_start(cfg).get("message", "OK"))
        return
    if args.cmd == "device-code-poll":
        device_code_poll(cfg, args.device_code)
        print("OK, токен сохранён в", cfg.tokens_path)
        return

    client = PBIClient(cfg)
    if args.cmd == "token":
        print(get_valid_token(cfg))
    elif args.cmd == "list-workspaces":
        _print(client.list_workspaces())
    elif args.cmd == "list-datasets":
        _print(client.list_datasets(args.group))
    elif args.cmd == "list-reports":
        _print(client.list_reports(args.group))
    elif args.cmd == "discover-schema":
        _print(client.discover_schema(args.group, args.dataset))
    elif args.cmd == "execute-dax":
        _print(client.execute_dax(args.group, args.dataset, args.query))


if __name__ == "__main__":
    try:
        main()
    except (AuthError, RuntimeError) as e:
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)
