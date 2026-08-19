# Установка (подробная версия)

Краткая инструкция для маркетологов — в **[README.md](../README.md)** в корне
репозитория: там маркетолог пишет Claude одну фразу «разверни скилл» + ссылка
на репо, и Claude сам проходит шаги 2–4 ниже (клон/pull, install.sh, login,
list-workspaces) — см. алгоритм в `SKILL.bootstrap.md`.

Ниже — те же шаги с полными командами, на случай если нужно прогнать их
руками для отладки (например, Claude застрял, или проверяете вручную перед
раздачей маркетологам).

## 1. Claude Desktop

1. [claude.com/download](https://claude.com/download)
2. Свой аккаунт, code execution включён.

## 2. Клон репозитория

```bash
git clone https://github.com/hemonc-team/ask-pbi.git ~/ask-pbi
bash ~/ask-pbi/install.sh
```

## 3. Python (если install.sh не поставил)

```bash
pip3 install requests --user
```

## 4. Power BI — Device Code (один раз)

```bash
SKILL=~/ask-pbi
cp "$SKILL/config/pbi_config.example.json" "$SKILL/config/pbi_config.json"

"$SKILL/scripts/pbi_run.sh" login
# ссылка в браузере → рабочий email; команда сама дождётся входа
"$SKILL/scripts/pbi_run.sh" list-workspaces
```

## 5. Bootstrap в Claude

Upload `dist/pbi-marketing-qa-bootstrap.zip` (собирает разработчик: `bash scripts/package.sh`).

## 6. Smoke

«Сколько всего свежих контактов сейчас в KPI marketing view?»

## Ошибки

| Симптом | Действие |
|---|---|
| `invalid_grant` | Повтор §4 |
| Нет workspace | Доступ в app.powerbi.com |
| `executeQueries` 403 | Tenant setting — dev (см. PBI_ADMIN_CHECKLIST в pbi-patch-factory) |
| `executeQueries` 400 + `AnalysisServicesErrorCode 3239575574` только на `discover-schema` (INFO.TABLES/INFO.MEASURES), обычный `execute-dax` при этом работает | Нужен Build permission на датасете для аккаунта маркетолога — см. `FOR_DEVELOPERS.md` |
