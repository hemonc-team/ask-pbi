#!/usr/bin/env python3
"""
Read-only REST-клиент Power BI Service для marketing skill.

Два режима входа (PBI_AUTH_MODE):
- delegated — Device Code под личным Pro-аккаунтом, токен в tokens_path.
- service_principal — client_credentials (PBI_CLIENT_SECRET), для HTTP MCP на DWH.

Только чтение: list/resolve, discover-schema (INFO.*), execute-dax.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
PBI_APP_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
MARKETING_SCOPES = (
    "https://analysis.windows.net/powerbi/api/Dataset.Read.All "
    "https://analysis.windows.net/powerbi/api/Report.Read.All "
    "https://analysis.windows.net/powerbi/api/Workspace.Read.All "
    "offline_access"
)
SCHEMA_CACHE_TTL_S = 7 * 86400

# Датасеты вне периметра этого skill независимо от workspace/dataset_id
# (id меняется при publish, имя — нет). Сверяется по нормализованному имени.
RESTRICTED_DATASET_NAMES = {
    "leadsmarketing",
    "clinicops",
    # "leads and bookings managers view no cash clean online (1)" — исключён
    # 2026-08-18: модель гендиректора, маркетологам видеть не должна.
    "leadsandbookingsmanagersviewnocashcleanonline1",
    # "KPI team_embed" — исключён 2026-08-19: служебная модель для встраиваемых
    # отчётов, не входит в разрешённый периметр (только marketing/admin/medicine
    # view из workspace KPI Team).
    "kpiteamembed",
}


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name, default)


def _normalize_auth_mode(raw: Optional[str]) -> str:
    mode = (raw or "delegated").strip().lower()
    if mode in ("sp", "service_principal", "client_credentials"):
        return "service_principal"
    return "delegated"


@dataclass
class Config:
    tenant_id: str
    client_id: str
    tokens_path: Path
    auth_mode: str = "delegated"
    client_secret: Optional[str] = None

    @classmethod
    def load(cls) -> "Config":
        tenant_id = _env("PBI_TENANT_ID")
        client_id = _env("PBI_CLIENT_ID")
        if not tenant_id or not client_id:
            sys.stderr.write("ERROR: нужны PBI_TENANT_ID и PBI_CLIENT_ID\n")
            sys.exit(2)
        auth_mode = _normalize_auth_mode(_env("PBI_AUTH_MODE"))
        client_secret = _env("PBI_CLIENT_SECRET")
        if auth_mode == "service_principal" and not client_secret:
            sys.stderr.write(
                "ERROR: PBI_AUTH_MODE=service_principal требует PBI_CLIENT_SECRET\n"
            )
            sys.exit(2)
        tokens_path = Path(
            _env("PBI_TOKENS_PATH", str(Path.home() / ".pbi" / "tokens.json"))
        ).expanduser()
        return cls(
            tenant_id=tenant_id,
            client_id=client_id,
            tokens_path=tokens_path,
            auth_mode=auth_mode,
            client_secret=client_secret,
        )

    @property
    def schema_cache_dir(self) -> Path:
        return self.tokens_path.parent / "schema-cache"


class AuthError(RuntimeError):
    pass


def _load_tokens(cfg: Config) -> dict[str, Any]:
    if not cfg.tokens_path.exists():
        raise AuthError(
            f"Нет {cfg.tokens_path}. Для локальной разработки: scripts/pbi_run.sh login. "
            "На проде нужен PBI_AUTH_MODE=service_principal."
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


def device_code_wait(cfg: Config, start: dict[str, Any]) -> dict[str, Any]:
    device_code = start["device_code"]
    interval = max(int(start.get("interval") or 5), 5)
    deadline = time.time() + int(start.get("expires_in") or 900)
    while time.time() < deadline:
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
        if r.status_code == 200 and "access_token" in payload:
            _save_tokens(cfg, payload)
            return payload
        err = payload.get("error")
        if err == "authorization_pending":
            time.sleep(interval)
            continue
        if err == "slow_down":
            interval += 5
            time.sleep(interval)
            continue
        raise AuthError(f"Device code flow не завершён: {payload}")
    raise AuthError("Код входа истёк. Запусти login ещё раз.")


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
            "scope": f"{PBI_APP_SCOPE} offline_access",
        },
        timeout=30,
    )
    payload = r.json()
    if r.status_code != 200 or "access_token" not in payload:
        raise AuthError(
            f"Refresh не удался: {payload.get('error')}. При invalid_grant — повтори login."
        )
    _save_tokens(cfg, payload)
    return payload


def acquire_sp_token(cfg: Config) -> dict[str, Any]:
    if not cfg.client_secret:
        raise AuthError("Нет PBI_CLIENT_SECRET для service_principal.")
    r = requests.post(
        f"{AUTHORITY}/{cfg.tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "grant_type": "client_credentials",
            "scope": PBI_APP_SCOPE,
        },
        timeout=30,
    )
    payload = r.json()
    if r.status_code != 200 or "access_token" not in payload:
        err = payload.get("error")
        desc = str(payload.get("error_description") or "")[:180]
        raise AuthError(f"SP token не получен: {err} {desc}".strip())
    _save_tokens(cfg, payload)
    return payload


def _cached_access_token(cfg: Config, margin_s: int) -> Optional[str]:
    if not cfg.tokens_path.exists():
        return None
    tokens = json.loads(cfg.tokens_path.read_text())
    saved_at = tokens.get("_saved_at", 0)
    expires_in = tokens.get("expires_in", 0)
    access = tokens.get("access_token")
    if (
        access
        and saved_at
        and expires_in
        and (time.time() - saved_at) < (expires_in - margin_s)
    ):
        return access
    return None


def get_valid_token(cfg: Config, margin_s: int = 120) -> str:
    cached = _cached_access_token(cfg, margin_s)
    if cached:
        return cached
    if cfg.auth_mode == "service_principal":
        return acquire_sp_token(cfg)["access_token"]
    return refresh_access_token(cfg)["access_token"]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.casefold())


def _row_get(row: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in row:
            return row[k]
        bracket = f"[{k}]"
        if bracket in row:
            return row[bracket]
    return None


def _dax_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])


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

    def _list_datasets_raw(self, group_id: str) -> list[dict]:
        """Неотфильтрованный список — только для внутренних проверок доступа.
        Не отдавать наружу (используй list_datasets)."""
        return self._get(f"/groups/{group_id}/datasets").get("value", [])

    def list_datasets(self, group_id: str) -> list[dict]:
        items = self._list_datasets_raw(group_id)
        return [d for d in items if _norm(d.get("name", "")) not in RESTRICTED_DATASET_NAMES]

    def list_reports(self, group_id: str) -> list[dict]:
        return self._get(f"/groups/{group_id}/reports").get("value", [])

    def _dataset_name_for(self, group_id: str, dataset_id: str) -> Optional[str]:
        for ds in self._list_datasets_raw(group_id):
            if ds.get("id") == dataset_id:
                return ds.get("name", "")
        return None

    def _assert_dataset_allowed(self, group_id: str, dataset_id: str) -> None:
        name = self._dataset_name_for(group_id, dataset_id)
        if name and _norm(name) in RESTRICTED_DATASET_NAMES:
            raise RuntimeError(
                f"Датасет «{name}» вне периметра этого skill "
                "(см. references/workspaces.md)."
            )

    def execute_dax(self, group_id: str, dataset_id: str, query: str) -> dict:
        self._assert_dataset_allowed(group_id, dataset_id)
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

    def resolve_dataset(
        self, dataset_name: str, workspace_hint: Optional[str] = None
    ) -> dict[str, str]:
        target = _norm(dataset_name)
        if target in RESTRICTED_DATASET_NAMES:
            raise RuntimeError(
                f"Датасет «{dataset_name}» вне периметра этого skill "
                "(см. references/workspaces.md)."
            )
        workspaces = self.list_workspaces()
        if workspace_hint:
            wh = _norm(workspace_hint)
            workspaces = [
                w
                for w in workspaces
                if wh in _norm(w.get("name", "")) or _norm(w.get("name", "")) in wh
            ] or workspaces
        for ws in workspaces:
            gid = ws["id"]
            for ds in self.list_datasets(gid):
                if _norm(ds.get("name", "")) == target:
                    return {
                        "workspace": ws.get("name", ""),
                        "group_id": gid,
                        "dataset": ds.get("name", ""),
                        "dataset_id": ds["id"],
                    }
        raise RuntimeError(
            f"Датасет «{dataset_name}» не найден"
            + (f" в workspace «{workspace_hint}»" if workspace_hint else "")
            + ". Проверь доступ в app.powerbi.com."
        )

    def _schema_cache_path(self, group_id: str, dataset_id: str) -> Path:
        return self.cfg.schema_cache_dir / f"{group_id}_{dataset_id}.json"

    def _load_schema_cache(self, group_id: str, dataset_id: str) -> Optional[dict]:
        path = self._schema_cache_path(group_id, dataset_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        if time.time() - data.get("_cached_at", 0) > SCHEMA_CACHE_TTL_S:
            return None
        return data

    def _save_schema_cache(
        self, group_id: str, dataset_id: str, schema: dict[str, Any]
    ) -> None:
        self.cfg.schema_cache_dir.mkdir(parents=True, exist_ok=True)
        payload = dict(schema)
        payload["_cached_at"] = int(time.time())
        path = self._schema_cache_path(group_id, dataset_id)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    def discover_schema(
        self,
        group_id: str,
        dataset_id: str,
        *,
        scope: str = "measures",
        use_cache: bool = True,
        write_cache: bool = True,
    ) -> dict[str, Any]:
        self._assert_dataset_allowed(group_id, dataset_id)
        if use_cache:
            cached = self._load_schema_cache(group_id, dataset_id)
            if cached is not None:
                return cached
        # Классические INFO.TABLES()/INFO.MEASURES()/... падают с
        # AnalysisServicesErrorCode 3239575574 (HTTP 400) через REST executeQueries
        # даже при выданном Build permission — подтверждено живым тестом 2026-08-19.
        # Рабочая замена — INFO.VIEW.* (тот же справочник, другой DAX-синтаксис).
        queries: tuple[tuple[str, str], ...]
        if scope == "full":
            queries = (
                ("tables", "EVALUATE INFO.VIEW.TABLES()"),
                ("measures", "EVALUATE INFO.VIEW.MEASURES()"),
                ("columns", "EVALUATE INFO.VIEW.COLUMNS()"),
                ("relationships", "EVALUATE INFO.VIEW.RELATIONSHIPS()"),
            )
        else:
            queries = (
                ("tables", "EVALUATE INFO.VIEW.TABLES()"),
                ("measures", "EVALUATE INFO.VIEW.MEASURES()"),
            )
        out: dict[str, Any] = {"scope": scope}
        for name, query in queries:
            result = self.execute_dax(group_id, dataset_id, query)
            out[name] = _dax_rows(result)
        if write_cache:
            self._save_schema_cache(group_id, dataset_id, out)
        return out


def _print_workspaces(items: list[dict]) -> None:
    for w in items:
        print(f"{w.get('name', '?')}\t{w.get('id', '')}")


def _print_datasets(items: list[dict]) -> None:
    for d in items:
        print(f"{d.get('name', '?')}\t{d.get('id', '')}")


def _print_reports(items: list[dict]) -> None:
    for r in items:
        ds = r.get("datasetId", "")
        print(f"{r.get('name', '?')}\t{r.get('id', '')}\tdataset={ds}")


def _print_resolve(res: dict[str, str]) -> None:
    print(
        f"workspace={res['workspace']}\n"
        f"group_id={res['group_id']}\n"
        f"dataset={res['dataset']}\n"
        f"dataset_id={res['dataset_id']}"
    )


def _print_dax_result(result: dict[str, Any]) -> None:
    rows = _dax_rows(result)
    if not rows:
        print("(пусто)")
        return
    if len(rows) == 1 and len(rows[0]) <= 4:
        for k, v in rows[0].items():
            print(f"{k}\t{v}")
        return
    cols: list[str] = []
    for row in rows:
        for k in row:
            if k not in cols:
                cols.append(k)
    print("\t".join(cols))
    for row in rows:
        print("\t".join(str(row.get(c, "")) for c in cols))


def _print_schema(schema: dict[str, Any]) -> None:
    cached = schema.get("_cached_at")
    if cached:
        age_h = int((time.time() - cached) / 3600)
        print(f"# cache age {age_h}h scope={schema.get('scope', '?')}")
    measures = schema.get("measures") or []
    print(f"# measures: {len(measures)}")
    for row in measures:
        table = _row_get(row, "Table", "TableName", "TABLE_NAME") or "?"
        name = _row_get(row, "Name", "MEASURE_NAME", "MeasureName") or "?"
        print(f"{table}\t{name}")
    tables = schema.get("tables") or []
    if tables:
        print(f"# tables: {len(tables)}")
        for row in tables[:40]:
            name = _row_get(row, "Name", "TABLE_NAME") or "?"
            print(f"table\t{name}")
        if len(tables) > 40:
            print(f"# … ещё {len(tables) - 40} таблиц")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="Один шаг: ссылка в браузере + ожидание входа")
    sub.add_parser("device-code-start")
    sp = sub.add_parser("device-code-poll")
    sp.add_argument("--device-code", default=None)
    sub.add_parser("token")
    sub.add_parser("list-workspaces")
    sp = sub.add_parser("list-datasets")
    sp.add_argument("--group", required=True)
    sp = sub.add_parser("list-reports")
    sp.add_argument("--group", required=True)
    sp = sub.add_parser("resolve-dataset")
    sp.add_argument("--dataset", required=True, help="Имя semantic model, напр. leads_marketing")
    sp.add_argument("--workspace", default=None, help="Подсказка: Входящий трафик / KPI Team")
    sp = sub.add_parser("discover-schema")
    sp.add_argument("--group", required=True)
    sp.add_argument("--dataset", required=True)
    sp.add_argument(
        "--scope",
        choices=("measures", "full"),
        default="measures",
        help="measures = таблицы+меры (по умолчанию); full = + колонки+связи",
    )
    sp.add_argument("--no-cache", action="store_true", help="Не читать локальный кэш")
    sp.add_argument("--refresh-cache", action="store_true", help="Перезаписать кэш")
    sp = sub.add_parser("execute-dax")
    sp.add_argument("--group", required=True)
    sp.add_argument("--dataset", required=True)
    sp.add_argument("--query", required=True)

    args = p.parse_args()
    cfg = Config.load()

    if args.cmd == "login":
        start = device_code_start(cfg)
        print(start.get("message", "Открой ссылку и войди рабочим email."))
        print("Жду вход в браузере… не закрывай это окно.")
        device_code_wait(cfg, start)
        print("OK, вход сохранён.")
        return
    if args.cmd == "device-code-start":
        print(device_code_start(cfg).get("message", "OK"))
        return
    if args.cmd == "device-code-poll":
        code = args.device_code
        if not code:
            device_file = cfg.tokens_path.with_name("device.json")
            if not device_file.exists():
                raise AuthError("Нет device.json — сначала login.")
            code = json.loads(device_file.read_text())["device_code"]
        device_code_poll(cfg, code)
        print("OK, токен сохранён в", cfg.tokens_path)
        return

    client = PBIClient(cfg)
    if args.cmd == "token":
        print(get_valid_token(cfg))
    elif args.cmd == "list-workspaces":
        _print_workspaces(client.list_workspaces())
    elif args.cmd == "list-datasets":
        _print_datasets(client.list_datasets(args.group))
    elif args.cmd == "list-reports":
        _print_reports(client.list_reports(args.group))
    elif args.cmd == "resolve-dataset":
        _print_resolve(client.resolve_dataset(args.dataset, args.workspace))
    elif args.cmd == "discover-schema":
        schema = client.discover_schema(
            args.group,
            args.dataset,
            scope=args.scope,
            use_cache=not args.no_cache and not args.refresh_cache,
            write_cache=True,
        )
        _print_schema(schema)
    elif args.cmd == "execute-dax":
        _print_dax_result(client.execute_dax(args.group, args.dataset, args.query))


if __name__ == "__main__":
    try:
        main()
    except (AuthError, RuntimeError) as e:
        sys.stderr.write(f"ERROR: {e}\n")
        sys.exit(1)
