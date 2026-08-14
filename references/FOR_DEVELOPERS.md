# Техническая документация (dev)

Репозиторий [`ask-pbi`](https://github.com/hemonc-team/ask-pbi) — marketing-контур. Dev (патч `.pbix`, publish, SP) — [`pbi-patch-factory`](https://github.com/hemonc-team/pbi-patch-factory).

## Структура

| Путь | Назначение |
|---|---|
| `SKILL.md` | Полные инструкции для Claude (обновляются через git pull) |
| `SKILL.bootstrap.md` | Loader для одноразового upload в Claude |
| `scripts/pbi_run.sh` | Read-only REST; compact output; `resolve-dataset`; schema cache в `~/.pbi/schema-cache/` |
| `references/workspaces.md` | Workspace ID + синонимы (dataset ID — через resolve) |
| `references/measures-cheatsheet.md` | Меры + готовый DAX |
| `references/TROUBLESHOOTING.md` | Ошибки Cowork/Chat/токен/кэш |

## Сборка zip для маркетологов

```bash
bash scripts/package.sh
# → dist/pbi-marketing-qa-bootstrap.zip (upload once)
# → dist/pbi-marketing-qa.zip (fallback без git)
```

## Auth

- Маркетолог: delegated OAuth, Device Code → `~/.pbi/tokens.json`
- Tenant/client: `config/pbi_config.example.json`
- Admin checklist: в `pbi-patch-factory` → `docs/guides/PBI_ADMIN_CHECKLIST.md`

## Детальный онбординг (с командами)

См. [`SETUP_MARKETER.md`](SETUP_MARKETER.md) — расширенная версия для отладки.
