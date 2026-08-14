# Если что-то сломалось

## Claude не видит ~/ask-pbi

Режим **Chat** — не подходит. **Cowork** → **Project or folder** → папка `ask-pbi`. **Clear active** для чужих проектов.

## Нет интернета / cloud / device_bash

Новый Cowork-чат, папка `ask-pbi` на компьютере. Не выдумывать цифры.

## Нет tokens.json / invalid_grant

```bash
~/ask-pbi/scripts/pbi_run.sh login
```

## executeQueries 403

Tenant setting *Semantic Model Execute Queries REST API* — просить разработчика (не маркетолог).

## Нет доступа к workspace

app.powerbi.com — если отчёта нет и там, нужен доступ у админа.

## resolve-dataset не находит модель

```bash
~/ask-pbi/scripts/pbi_run.sh list-workspaces
~/ask-pbi/scripts/pbi_run.sh list-datasets --group <group_id>
```

Имя датасета = имя semantic model в Service.

## Устаревший кэш мер

```bash
~/ask-pbi/scripts/pbi_run.sh discover-schema --group <id> --dataset <id> --refresh-cache
```

Кэш живёт 7 дней в `~/.pbi/schema-cache/`, обновляется сам при истечении.
