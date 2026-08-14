# Установка (подробная версия)

Краткая инструкция для маркетологов — в **[README.md](../README.md)** в корне репозитория.

Ниже — те же шаги с полными командами для отладки.

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

«Сколько свежих контактов за последний месяц в leads_marketing?»

## Ошибки

| Симптом | Действие |
|---|---|
| `invalid_grant` | Повтор §4 |
| Нет workspace | Доступ в app.powerbi.com |
| `executeQueries` 403 | Tenant setting — dev (см. PBI_ADMIN_CHECKLIST в pbi-patch-factory) |
