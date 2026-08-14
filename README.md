# ask-pbi

Claude Desktop skill для маркетологов: read-only вопросы к Power BI Service (лиды, KPI, конверсия) через DAX.

Dev-контур (патч `.pbix`, Service Principal, публикация) — отдельный репозиторий [`pbi-patch-factory`](https://github.com/hemonc-team/pbi-patch-factory).

## Быстрый старт (маркетолог)

```bash
git clone https://github.com/hemonc-team/ask-pbi.git ~/ask-pbi
bash ~/ask-pbi/install.sh
```

Подробно: [`references/SETUP_MARKETER.md`](references/SETUP_MARKETER.md).

## Структура

| Путь | Назначение |
|---|---|
| `SKILL.md` | Полные инструкции для Claude (в git, обновляются через pull) |
| `SKILL.bootstrap.md` | Тонкий loader для одноразового upload в Claude |
| `scripts/pbi_run.sh` | Обёртка read-only REST-клиента |
| `references/` | Воркспейсы, шпаргалка мер, онбординг |

## Сборка zip для Claude

```bash
bash scripts/package.sh
# → dist/pbi-marketing-qa-bootstrap.zip (upload once)
# → dist/pbi-marketing-qa.zip (fallback без git)
```

## Обновление у маркетологов

«Обнови скилл» в Claude → `git -C ~/ask-pbi pull`.
