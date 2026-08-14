# Меры и готовый DAX

Сначала `resolve-dataset`, подставь `<group_id>` и `<dataset_id>`.

## leads_marketing

| Мера | Тема |
|---|---|
| `Количество свежих контактов` | свежие лиды |
| `Fresh_Contact_Conversion_Rate_%` | конверсия fresh contact |
| `Количество лидов` | лиды Calltouch/CRM |

Таблица дат в модели: **`Date_dim[Date]`** (если не сработало — `discover-schema`, scope measures).

### Свежие контакты — последние 30 дней от max даты в модели

```dax
EVALUATE
VAR MaxD = CALCULATE(MAX('Date_dim'[Date]), ALL('Date_dim'))
VAR FromD = MaxD - 30
RETURN ROW(
  "Период", FORMAT(FromD, "dd.mm.yyyy") & " – " & FORMAT(MaxD, "dd.mm.yyyy"),
  "Свежие контакты", CALCULATE(
    [Количество свежих контактов],
    'Date_dim'[Date] > FromD && 'Date_dim'[Date] <= MaxD
  )
)
```

### Свежие контакты — полный прошлый календарный месяц

```dax
EVALUATE
VAR MaxD = CALCULATE(MAX('Date_dim'[Date]), ALL('Date_dim'))
VAR EndPrev = EOMONTH(MaxD, -1)
VAR StartPrev = EOMONTH(EndPrev, -1) + 1
RETURN ROW(
  "Период", FORMAT(StartPrev, "mmmm yyyy", "ru-RU"),
  "Свежие контакты", CALCULATE(
    [Количество свежих контактов],
    'Date_dim'[Date] >= StartPrev && 'Date_dim'[Date] <= EndPrev
  )
)
```

### Лиды — текущий месяц с начала

```dax
EVALUATE
VAR MaxD = CALCULATE(MAX('Date_dim'[Date]), ALL('Date_dim'))
VAR StartM = EOMONTH(MaxD, -1) + 1
RETURN ROW(
  "Период", "с " & FORMAT(StartM, "dd.mm.yyyy"),
  "Лиды", CALCULATE(
    [Количество лидов],
    'Date_dim'[Date] >= StartM && 'Date_dim'[Date] <= MaxD
  )
)
```

## KPI marketing view

| Мера | Тема |
|---|---|
| меры с «Посетител» | трафик Метрики |
| `Количество лидов` | лиды DWH |

Таблица дат: уточни через `discover-schema` (часто `Date_dim` или таблица с `event_date`).

### Посетители — последние 30 дней (подставь таблицу дат после discover)

```dax
EVALUATE
VAR MaxD = CALCULATE(MAX('Date_dim'[Date]), ALL('Date_dim'))
RETURN ROW(
  "Посетители 30д",
  CALCULATE([Посетители], 'Date_dim'[Date] > MaxD - 30 && 'Date_dim'[Date] <= MaxD)
)
```

Имя меры «Посетители» может отличаться — смотри вывод `discover-schema`.
