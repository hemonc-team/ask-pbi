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

## Открытые проблемы (не готово к раздаче маркетологам)

Найдено 2026-08-18 живыми запросами через уже развёрнутый skill, см.
`references/known-fields.md` за эту дату для полных деталей:

1. **`discover-schema` (INFO.TABLES/INFO.MEASURES) не работает ни на одном
   датасете KPI Team** — `AnalysisServicesErrorCode 3239575574`, HTTP 400.
   Обычный `execute-dax` по known измерению работает. Похоже, аккаунту
   маркетолога не хватает Build permission на эти датасеты (отдельно от
   Read/Execute Queries). Без этого Claude не может сам находить меры/таблицы
   под нестандартный вопрос — только то, что руками занесено в
   `measures-cheatsheet.md`. **Это блокер #1** — почини первым.
2. **`[Количество свежих контактов]` не реагирует на фильтр по дате** ни в
   одном из трёх allowed-датасетов (`KPI marketing view`, `KPI team admin
   view`, `KPI medicine view`) — возвращает одно и то же число на любой
   период. Похоже на `ALL(...)` внутри самой меры или отключённую связь с
   календарём. Из-за этого пока нет ни одной подтверждённой периодной меры
   про лиды/контакты для маркетолога.
3. Таблица дат `Date_dim` есть только в `KPI marketing view` (2017‑01‑01 …
   2026‑11‑30). В `KPI team admin view` / `KPI medicine view` календарь
   называется иначе — неизвестно как, пока не работает (1).
4. После (1)–(3) переписать `measures-cheatsheet.md`/`known-fields.md` на
   подтверждённые discover-schema данные вместо ручных проверок в этой сессии.
5. Ни разу не пройден onboarding «с нуля» (пустой `~/.pbi/tokens.json`,
   свежий `~/ask-pbi`) в этой сессии — OAuth device-code login не
   протестирован живьём на реальном новом пользователе, только код-путь.
6. После правок — пересобрать zip (`bash scripts/package.sh`) и закоммитить/
   запушить, иначе `git pull`/«обнови скилл» ничего не подтянет.
