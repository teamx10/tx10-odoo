# Прохождение демосценариев (≈20 минут)

Вход: http://localhost:8069/odoo. Пароли — локально в `solar-demo/.secrets`.

| Роль | Логин | Штатные группы |
|---|---|---|
| Администратор | `admin` | Settings / Administrator |
| PM | `demo-pm` | Project Admin, FSM Dispatcher, Purchase User, Inventory User, Sign User: All |
| Исполнитель сервиса | `demo-tech` | FSM User, Project User, Timesheets own, Inventory User, Sign own |
| Руководитель сервиса | `demo-svcmgr` | FSM Manager, Maintenance Equipment Manager, Inventory/Purchase User, Timesheets all, Sign User: All |

Все демозаписи начинаются с `DEMO-SOLAR`; все данные синтетические.

## 1. Объект → оборудование (`demo-tech`)
Field Service → Master Data → Locations → **DEMO-SOLAR-ST01** → кнопка **4 Equipment** →
инвертор `DEMO-SOLAR-SN-INV-0001`: серийный номер, гарантия до 2031, складская локация.

## 2. Сервисная работа через этапы (`demo-svcmgr`, затем `demo-tech`)
Operations → Orders → New: Location ST02, Team «DEMO-SOLAR Service Team», Assigned To — техник.
Этапы: **Новая → Запланирована → В работе** (статус-бар) → заполнить *Resolution* → кнопка
**Complete** (= «Выполнена») → **Закрыта**. Когда заказ входит в «В работе», серверное действие создаёт
To-Do активность для руководителя сервиса (видна в его Discuss/Activities).
Готовый пример: заказ FO009 (уже закрыт).

## 3. Блокировка перехода (`demo-tech`)
FO003 → кнопка **Complete**, *Resolution* пустой → «Validation Error: Cannot move to stage
Выполнена until the resolution field is set». Если перевести в «Запланирована» без исполнителя,
получится аналогичная ошибка по `person_id`.
Важно: «Выполнена» через статус-бар запрещена ядром FSM («Cannot move to completed from Kanban»),
завершать заказ нужно кнопкой Complete.

## 4. Проект ↔ сервис (`demo-pm`)
Project → **DEMO-SOLAR-PRJ-001** → 5 задач; задача *Installation* → FO001. В заказе FO001 видны
поля Project / Project Task, а в карточке станции ST01 — кнопка **1 Projects**.

## 5. Закупка
- из сервиса: FO003 → вкладка/кнопка *Purchases* → P00002 (DC-предохранители);
- из ТО: Maintenance → Requests → **DEMO-SOLAR-MR-001** → Purchase Orders → P00003.

## 6. Склад ↔ оборудование ↔ серийный номер
Purchase P00001 → приёмка WH/IN/00001 с 7 серийниками; оборудование создано **автоматически**.
Inventory → Lots/Serial Numbers → `DEMO-SOLAR-SN-PV-0001` (передан заказчику по WH/OUT/00001,
связанной с FO001).

## 7. Гарантии
Колонки Warranty Start/End в Field Service → Equipments; срок гарантии берётся из товара
(вкладка Warranty/Purchase у `DEMO-SOLAR-INV-100K`: 5 лет, возврат поставщику).

## 8. Плановые работы
- FSM: Operations → Recurring Orders → **RFO001** (ежемесячно, создал FO004–FO006);
- Maintenance: оборудование *DEMO-SOLAR-ST01 Inverter #1* → Maintenance Plans → квартальный план,
  2 профилактические заявки (создаёт штатный cron).

## 9. Ремонт
FO002 (тип *Repair*) → **Repair Orders** (создан автоматически, lot INV-0002).
Заявка MR-001 → поле *Repair Order* = WH/RO/00001. Ремонт: Confirm → Start → End.

## 10. Учёт времени (`demo-tech`)
FO001 → вкладка Timesheets → добавить строку (проект/задача подставляются) → итог в проекте
(Project → PRJ-001 → Timesheets).

## 11. Подпись документа
1. `demo-pm`: в любом незакрытом заказе → **Request Signature** (шаблон «Commissioning Acceptance Act»).
   Подписант — синтетический заказчик; письмо НЕ уходит (SMTP заблокирован).
2. Ссылку подписанта выведите локально: `solar-demo/scripts/sign-link.sh` → откройте её в
   приватном окне → Click to start → имя → подпись → *Adopt & Sign* → *Validate & Send document*.
3. Результат: заказ → **Sign Requests** → статус Signed, скачать подписанный PDF.
   Пример уже подписан: FO001, копия — `docs/signed-acceptance-act-FO001.pdf`.

## 12. Карта
Не установлена: нет разрешённого Google Maps API-ключа (см. README).

## 13. Перезапуск
`solar-demo/scripts/stop.sh && solar-demo/scripts/start.sh` → повторить шаги 1, 4, 11.3.

## Чего здесь нет (не демонстрировать как готовое)
- синхронизации FSM-оборудования (`fsm.equipment`) с оборудованием ТО (`maintenance.equipment`):
  это разные модели, связь только по серийному номеру в тексте карточки;
- EPC-специфики (этапы стройки, исполнительная документация, цифровой паспорт), SCADA/EMS/VPP, AI, карты.
