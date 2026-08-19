# Вопросы к дашбордам через Claude

Claude на компьютере отвечает на вопросы по цифрам из Power BI обычным языком:
лиды, KPI, конверсия, посетители сайта. Отчёты руками открывать не нужно.

Claude **только читает** данные. Он не меняет отчёты и не придумывает DAX —
запросы идут через заранее проверенные шаблоны на сервере компании.

---

## Как пользоваться

Нужны: подписка Claude (Pro или Team), токен из 1Password, доступ к отчётам
в [app.powerbi.com](https://app.powerbi.com) глазами. Python, git и pip
на компьютере **не нужны**. Отдельный вход в Power BI через Claude тоже не нужен.

### Один раз: поставить Claude Code

**Mac / Linux** — приложение «Терминал»:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Закройте окно терминала полностью и откройте новое. Проверка: `claude --version`.

Если пишет `command not found: claude` (часто на Mac):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
claude --version
```

**Windows** — PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Новое окно PowerShell, затем `claude --version`.

Первый запуск `claude` откроет браузер — войдите рабочим email.

### Один раз: подключить дашборды

Токен — из 1Password, целиком, без пробелов по краям.

```bash
claude mcp add --transport http --scope user ask-pbi https://n8n.hemonc.ru/mcp \
  --header "Authorization: Bearer <токен из 1Password>"
```

Проверка: `claude mcp list` — у `ask-pbi` должно быть **Connected**.

Адрес пока `n8n.hemonc.ru` (временный поддомен). Когда сменим — придёт новая
команда, токен тот же.

### Каждый день

В любой папке запустите `claude` и спросите, как коллегу:

- «Сколько всего свежих контактов сейчас?»
- «Сколько свежих контактов было в июне?»
- «Как изменилась конверсия свежих контактов в мае по сравнению с апрелем?»

Можно без слов «Power BI» и «дашборд».

Что умеем сегодня: свежие контакты, конверсия свежих контактов, конверсия
записи в приём, посетители и просмотры сайта. Каталог растёт.

**Ограничение:** конверсия свежих контактов считается только за **один
календарный месяц** за раз. Квартал или «за лето» по этой мере Claude честно
откажет — спрашивайте месяц к месяцу. Остальные метрики из списка складываются
по любому периоду.

На вашей машине ничего обновлять не нужно: новые метрики появляются на сервере.

| Что видите | Что сделать |
|---|---|
| `command not found: claude` | Новый терминал или блок с `PATH` выше |
| `ask-pbi` нет в `claude mcp list` | Повторите команду с токеном |
| Failed / 401 | Токен неверный — возьмите свежий в 1Password |
| Нет отчёта в app.powerbi.com | Это отдельно от Claude — доступ у админа |
| Нужна новая мера в отчёте | Напишите разработчику, не через Claude |

---

## Как развернуть

Прод: каталог `/opt/ask-pbi` на сервере DWH. Маркетологи ходят на
`https://n8n.hemonc.ru/mcp`. Python крутится только там, не на ноутбуках.
Пакеты **не** ставить в `/opt/clinic-dwh/venv`.

Секреты только в `/opt/ask-pbi/.env` (`chmod 600`), не в git. Шаблон:
`.env.example`.

```
PBI_AUTH_MODE=service_principal
PBI_TENANT_ID / PBI_CLIENT_ID / PBI_CLIENT_SECRET   # приложение Entra
ASKPBI_TRANSPORT=http
ASKPBI_MCP_TOKEN                                    # Bearer для Claude
ASKPBI_PUBLIC_URL=https://n8n.hemonc.ru/mcp
```

### Первый раз на сервере

```bash
# с ноутбука
rsync -az --exclude '.git/' --exclude 'venv/' --exclude '.env' --exclude 'var/' \
  ./ root@DWH:/opt/ask-pbi/
ssh root@DWH 'chmod 600 /opt/ask-pbi/.env; cd /opt/ask-pbi && ./deploy/install_linux.sh'
```

Скрипт ставит venv, systemd `ask-pbi` (127.0.0.1:8100) и nginx: `/mcp` → MCP,
остальное на этом хосте по-прежнему n8n.

Проверка на сервере:

```bash
curl -sS http://127.0.0.1:8100/health
cd /opt/ask-pbi && set -a && source .env && set +a && ./venv/bin/python -m mcp_server.smoke_test
```

Снаружи без токена `/mcp` должен отвечать 401, с Bearer — подключаться.

### Обновить код

```bash
rsync -az --exclude '.git/' --exclude 'venv/' --exclude '.env' --exclude 'var/' \
  ./ root@DWH:/opt/ask-pbi/
ssh root@DWH 'cd /opt/ask-pbi && ./venv/bin/pip install -q -r requirements.txt && systemctl restart ask-pbi'
```

Nginx трогать не нужно, если не меняли `deploy/nginx-n8n.hemonc.ru.conf`.
После правки nginx: `./deploy/install_linux.sh`.

Токен маркетологам не перевыпускается при обычном обновлении метрик.

Подробности (реестр мер, allowlist, Service Principal): [`references/FOR_DEVELOPERS.md`](references/FOR_DEVELOPERS.md).
