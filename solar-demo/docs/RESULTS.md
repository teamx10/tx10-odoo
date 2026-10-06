# Результаты проверок — 2026-10-05

Стенд: http://localhost:8069 · БД `solar_epc_demo19` · Odoo 19.0 @ `29cf86bd012` · OCA — `config/repos.lock`.

## Метод
- **ORM под пользователем** — `scripts/verify.sh`: `env(user=demo-*)` применяет ACL и record rules так же,
  как веб-клиент. Изменяющие проверки выполняются в savepoint и откатываются, кроме постоянных
  демозаписей (FO009, запрос подписи FO001).
- **UI** — Playwright, свежий браузерный контекст, сессия обычного пользователя (не admin).

## Сводка

| # | Сценарий | ORM (пользователь) | UI | Итог |
|---|---|---|---|---|
| 1 | Объект → оборудование | ✓ demo-tech | ✓ demo-tech: ST01 → 4 Equipment → форма инвертора без ошибок | PASS |
| 2 | Работа: создать → назначить → этапы | ✓ svcmgr → tech, Новая→…→Закрыта + активность | — | PASS (ORM) |
| 3 | Блокировка stage_validation | ✓ demo-tech (person_id, resolution) | ✓ demo-tech: Complete → Validation Error, этап не сменился | PASS |
| 4 | Проект ↔ сервисная работа | ✓ demo-pm | ✓ кнопка «1 Projects» у ST01, проект в списке PM | PASS |
| 5 | Закупка из FSM и из ТО | ✓ demo-pm создал PO из FO003; MR-001 → P00003 | список PO открывается | PASS (ORM) |
| 6 | Оборудование ↔ серийный номер ↔ склад | ✓ авто-создание при приёмке, lot⇄equipment, отгрузка | форма оборудования (серийник, локация) | PASS |
| 7 | Гарантии | ✓ даты из срока гарантии товара, supplierinfo | колонки Warranty в списке оборудования | PASS |
| 8 | Плановые/повторяющиеся | ✓ RFO001 → 3 заказа, план ТО → 2 заявки, cron без дублей | — | PASS (ORM) |
| 9 | Ремонт ↔ FSM / ТО | ✓ FO002→repair (авто), MR-001→RO; Confirm→Start→End | список Repairs открывается | PASS (ORM) |
| 10 | Учёт времени | ✓ demo-tech +0.5 ч на FO001, итог проекта | список Timesheets открывается | PASS (ORM) |
| 11 | Демоподпись и чтение результата | ✓ PM запросил; результат: 2_signed, хеш PDF, журнал create→validate→view→sign | ✓ подпись через портальную ссылку заказчика | PASS |
| 12 | Карта | — | — | **ПРОПУЩЕН**: нет разрешённого API-ключа |
| 13 | Перезапуск и повторное открытие | ✓ verify 14/14 после рестарта | ✓ demo-pm: 9 разделов без ошибок | PASS |
| — | Изоляция почты | ✓ 16 писем в `exception` («Connection refused»), sent = 0 | — | PASS |

Лог сервера после всех проверок: 0 ERROR / 0 Traceback; WARNING только ожидаемые
(2 × «Cannot move to completed from Kanban», 1 × stage validation, 1 × выход сессии старой БД).

## Найдено и исправлено в ходе проверок
| Находка | Причина | Решение |
|---|---|---|
| Техник не видит серийные номера | `stock.lot` доступен только Inventory/User | роли «исполнитель» добавлена штатная группа Inventory/User |
| У техника нет кнопки Complete в UI | кнопка с `groups="fieldservice.group_fsm_user"`, а у роли было «User (own)» | роль переведена на FSM User |
| PM не может запросить подпись | выражение роли подписанта вне whitelist `mail_allowed_qweb_expressions` | роль подписанта: политика `default` (фиксированный синтетический заказчик) |
| Старое представление в браузере после смены групп | ormcache сервера + RPC-кеш IndexedDB клиента | рестарт сервера; новый вход / очистка данных сайта |
| Пароли сбрасывались при повторной загрузке | загрузчик ставил пароль на каждом прогоне | пароль задаётся только при создании |

## Скриншоты
`docs/screens/ui-01-tech-equipment.png`, `ui-03-tech-stage-validation.png`, `ui-13-pm-fo001-after-restart.png`.
Подписанный документ: `docs/signed-acceptance-act-FO001.pdf`.

## Вывод scripts/verify.sh (последний прогон)

```
PASS | 01 объект → оборудование | demo-tech
     ✓ location DEMO-SOLAR-ST01 Solar Park North (5 MWp)
     ✓ 4 equipment: DEMO-SOLAR-SN-INV-0001, DEMO-SOLAR-SN-PV-0001, DEMO-SOLAR-SN-PV-0002, DEMO-SOLAR-SN-MTR-0001
     ✓ coords 50.61, 30.91
PASS | 02 работа: создать → назначить → этапы | demo-svcmgr → demo-tech
     ✓ server action → activity for svcmgr: ['Работа начата — проверить ход выполнения']
     ✓ FO024: Новая → Запланирована → В работе → Выполнена → Закрыта
PASS | 03 stage_validation блокирует переход | demo-tech
     ✓ без исполнителя: ValidationError: Cannot move to stage Запланирована until the person_id field is set.
     ✓ без итога работ: ValidationError: Cannot move to stage Выполнена until the resolution field is set.
PASS | 04 проект ↔ сервисная работа | demo-pm
     ✓ project orders: ['FO001', 'FO003']
     ✓ task «DEMO-SOLAR-PRJ-001.3 Installation» → ['FO001']
     ✓ project FSM location: DEMO-SOLAR-ST01
PASS | 05 закупка из FSM и из заявки ТО | demo-pm / demo-svcmgr
     ✓ FO003: POs ['P00002/purchase']
     ✓ PM создал P00008 из заказа FO003 (draft, удаляется)
     ✓ DEMO-SOLAR-MR-001 Inverter #1 cooling fan noise: POs ['P00003']
PASS | 06 оборудование ↔ серийный номер ↔ склад | demo-svcmgr
     ✓ DEMO-SOLAR-SN-INV-0001 ⇄ equipment #1 (обратная ссылка lot)
     ✓ INV-0001 stock: WH/Stock
     ✓ PV-0001 after delivery: Customers
     ✓ receipt WH/IN/00001 done → equipment auto-created
PASS | 07 гарантии | demo-tech
     ✓ DEMO-SOLAR-SN-INV-0001: 5 year → 2026-10-05..2031-10-05
     ✓ DEMO-SOLAR-SN-PV-0001: 25 year → 2026-10-05..2051-10-05
     ✓ DEMO-SOLAR-SN-MTR-0001: 24 month → 2026-10-05..2028-10-05
     ✓ supplier warranty (product_warranty): 5.0, return → supplier
PASS | 08 повторяющиеся работы и план ТО | cron + demo-svcmgr
     ✓ RFO001: 3 заказов ['2026-10-12', '2026-11-12', '2026-12-12'], cron без дублей
     ✓ план ТО: 2 заявок, повторный cron без дублей
     ✓ svcmgr создал RFO005: 3 заказа(ов)
PASS | 09 ремонт ↔ FSM / ТО | demo-svcmgr
     ✓ FO002 (type Repair) → FO002 - DEMO-SOLAR String Inverter 100 kW (synthetic) (DEMO-SOLAR-SN-INV-0002), lot DEMO-SOLAR-SN-INV-0002
     ✓ DEMO-SOLAR-MR-001 Inverter #1 cooling fan noise → WH/RO/00001
     ✓ FO002 - DEMO-SOLAR String Inverter 100 kW (synthetic) (DEMO-SOLAR-SN-INV-0002): confirmed → under_repair → done (откат после проверки)
PASS | 10 учёт времени | demo-tech
     ✓ FO001: 8.5 ч → 9.0 ч (запись техника, откат)
     ✓ проект: всего 14.0 ч
PASS | 11a запрос подписи из FSM-заказа | demo-pm
     ✓ DEMO-SOLAR Commissioning Acceptance Act: signer DEMO-SOLAR Customer Energy LLC, state 2_signed
PASS | mail изоляция исходящей почты | system
     ✓ mail.mail: 27 всего, sent=0, exception=27
     ✓ причины: {'61\nConnection refused'}
PASS | 11b результат демоподписи | demo-pm (чтение)
     ✓ DEMO-SOLAR Commissioning Acceptance Act: state=2_signed, signed 2026-10-05 15:05:18 by DEMO-SOLAR Customer Energy LLC
     ✓ PDF изменён подписью, current_hash совпадает (aa3eeab87786…), 70143 байт
     ✓ значения полей: имя + PNG подписи ['DEMO-SOLAR Customer Energy LLC', 'data:image/png;base64,iVBORw0K']
     ✓ журнал действий: ['create', 'validate', 'view', 'sign']
     ✓ FO001.sign_request_state = 2_signed
PASS | 12 карта — ПРОПУЩЕН, проверено отсутствие | —
     ✓ НЕ УСТАНОВЛЕНА намеренно: нет разрешённого API-ключа Google (billing) — base_google_map=uninstalled, fieldservice_google_map=uninstalled, web_view_google_map=uninstalled

TOTAL: 14/14 PASS
```
