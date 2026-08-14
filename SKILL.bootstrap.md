---
name: pbi-marketing-qa
description: >-
  Bootstrap: читай ~/ask-pbi/SKILL.md для PBI метрик. «Обнови скилл» → git pull.
  Триггер: leads_marketing, KPI, лиды, дашборд.
---

# pbi-marketing-qa (bootstrap)

Тонкий loader. Полные инструкции — в git-клоне на диске пользователя.

## Перед любым вопросом про Power BI / дашборд / метрики / лиды

1. Прочитай файл:
   `~/ask-pbi/SKILL.md`
2. При необходимости — `references/` в той же папке.
3. Скрипты запускай только через:
   `~/ask-pbi/scripts/pbi_run.sh`
4. Команды — **только на компьютере пользователя**, не в cloud/`device_bash` (нет интернета до Power BI). Если сети нет — попроси новый чат «на этом компьютере» / On your computer.

Если папки нет — попроси пользователя выполнить `install.sh` (см. `references/SETUP_MARKETER.md` в репо или у разработчика).

## Обновление

Если пользователь просит **обновить skill** / **обнови скилл**:

```bash
git -C ~/ask-pbi pull
```

Затем перечитай `SKILL.md` из обновлённого пути.

## Ограничение

Этот bootstrap меняется редко. Не дублируй сюда бизнес-логику — она только в git `SKILL.md`.
