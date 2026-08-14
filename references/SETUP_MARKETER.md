# Установка pbi-marketing-qa (маркетолог)

~20 минут, один раз. Нужны: Mac, Claude Desktop (Free или Pro), Power BI Pro на вашем рабочем email.

## 1. Claude Desktop

1. Скачайте [claude.com/download](https://claude.com/download).
2. Войдите **своим** аккаунтом.
3. В Settings включите **code execution**, если спросит.

## 2. Git + skill из репозитория

Разработчик выдаст read-only доступ к репозиторию:

```bash
git clone https://github.com/hemonc-team/ask-pbi.git ~/ask-pbi
bash ~/ask-pbi/install.sh
```

Или обновление существующего клона:

```bash
git -C ~/ask-pbi pull
```

## 3. Python

```bash
pip3 install requests --user
# или: pip3 install requests --break-system-packages
```

## 4. Power BI — вход один раз (Device Code)

```bash
SKILL=~/ask-pbi
cp "$SKILL/config/pbi_config.example.json" "$SKILL/config/pbi_config.json"
# при необходимости поправьте tokens_path в pbi_config.json

"$SKILL/scripts/pbi_run.sh" device-code-start
# откройте ссылку, войдите СВОИМ рабочим email (тот, у кого Pro)
"$SKILL/scripts/pbi_run.sh" device-code-poll --device-code <код из ~/.pbi/device.json>
"$SKILL/scripts/pbi_run.sh" list-workspaces
```

## 5. Bootstrap skill в Claude (один раз)

1. Customize → Skills → Upload.
2. Заархивируйте zip из `dist/pbi-marketing-qa-bootstrap.zip` (даёт разработчик после `bash scripts/package.sh`).
3. Либо вручную: zip с одним файлом `SKILL.md` = содержимое `SKILL.bootstrap.md` (имя папки в zip: `pbi-marketing-qa`).

## 6. Проверка

Спросите Claude: «Сколько свежих контактов за последний месяц в leads_marketing?»

## Обновления

Напишите Claude: **«обнови скилл»** — он выполнит `git pull` в `~/ask-pbi`.

## Если сломалось

| Симптом | Действие |
|---|---|
| `invalid_grant` | Повторите §4 (Device Code) |
| Нет workspace в списке | Попросите доступ в app.powerbi.com |
| `executeQueries` 403 | Разработчик включает tenant setting (не вы) |

Правки моделей/мер — не через skill, а через разработчика ([`pbi-patch-factory`](https://github.com/hemonc-team/pbi-patch-factory)).
