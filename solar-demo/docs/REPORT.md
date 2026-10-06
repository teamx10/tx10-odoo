# Отчёт: Solar EPC демостенд на Odoo 19 Community — 2026-10-05

**Статус: базовый демоконтур развёрнут и проверен. 13 из 13 применимых сценариев PASS, карта
пропущена (сценарий 12).** Это демонстрационный стенд на Beta-модулях, а не готовая Solar EPC-платформа.

## Стенд
| | |
|---|---|
| Адрес | http://localhost:8069/odoo (127.0.0.1; внутри tailnet также :8443 через существующий `tailscale serve`) |
| Демобаза | `solar_epc_demo19`, filestore `.odoo-data/filestore/solar_epc_demo19` |
| Развёртывание | существующее: `.venv19` + `odoo-bin` + `odoo19.conf` + `.odoo-data/start|stop-demo19.sh` (Docker нет) |
| Код | Odoo 19.0 @ `29cf86bd012` без изменений; OCA 19.0 по коммитам из `config/repos.lock` |
| Прежний стенд | `tx10_demo19` заменён по вашему решению; БД **не удалена**, бэкап в `backups/tx10_demo19-20261005-1745/` |

## Установлено и настроено
- **126 модулей**: 23 OCA + 103 Odoo Community (целевые и транзитивные, в том числе account, sale_management, hr).
  Enterprise и платных модулей нет. Манифесты не менялись, ACL и record rules не отключались.
- Odoo: contacts, project, purchase, stock, maintenance, repair, hr_timesheet, base_automation, base_geolocalize.
- OCA field-service (13): base_territory, fieldservice, _project, _stock, _equipment_stock,
  _equipment_warranty, _purchase, _recurring, _repair, _stage_validation, _stage_server_action, _timesheet, _sign.
- OCA rma: product_warranty. OCA maintenance (8): base_maintenance, maintenance_plan, _equipment_category_hierarchy,
  _equipment_certification, _equipment_tags, maintenance_project, maintenance_request_purchase, _request_repair.
- OCA sign: sign_oca.
- **Конфигурация**: компания DEMO-SOLAR; 4 роли на штатных группах; этапы Новая → Запланирована →
  В работе → Выполнена → Закрыта (+ Cancelled); stage_validation (исполнитель для «Запланирована», итог работ для
  «Выполнена»); stage_server_action («В работе» → внутренняя To-Do активность руководителю, без отправки наружу);
  серийный учёт; авто-создание FSM-оборудования при приёмке; подпись документов в FSM.
- **Демоданные** (синтетические, xmlid `demo_solar.*`, повторная загрузка без дублей): 2 станции с координатами,
  заказчик и поставщик, категории «панели/инверторы/счётчики» (иерархия), 3 тега, 4 товара с гарантией,
  7 серийных номеров → 7 единиц FSM-оборудования, EPC-проект с 5 задачами, сервисные заказы FO001–FO006 и FO009,
  3 закупки, приёмка и отгрузка, повторяющийся заказ, план ТО с 2 заявками, корректирующая заявка с ремонтом
  и закупкой, 2 ремонта, 4 записи времени, сертификат, шаблон и подписанный акт.
- **Почта** изолирована: SMTP направлен на закрытый порт 127.0.0.1:2; все 16 писем в `exception`, отправлено 0.
  Cron «Update Notification» (отправляет данные на odoo.com) отключён.

## Установлено, но не настроено / проверено частично
- Сценарии 2, 5, 8, 9, 10 проверены через ORM под обычными пользователями. В браузере для них проверено
  только открытие разделов без ошибок, полный клик-проход не выполнялся.
- `sign_oca`: подпись проверена через портал. Виджет Odoo в режиме «Auto» сам рисует подпись из имени.
  Позиции полей шаблона подобраны вручную. JS-запрос бандла `sign_oca.sign_assets` даёт ERR_TOO_MANY_REDIRECTS
  (в бандле только CSS); на подпись это не влияет.
- Территории (base_territory), ценовые листы исполнителей (fieldservice_purchase), уведомления об истечении
  сертификатов, `maintenance_project` (кроме привязки проекта) не настраивались.

## Пропущено и почему
| Компонент | Причина |
|---|---|
| base_google_map, web_view_google_map, fieldservice_google_map | нужен ключ Google Maps JS API с billing; разрешённого ключа нет, интеграция отключена (сценарий 12 не проверялся) |
| solar_project_management, mcp_server, mn_mcp_server, ai_oca_* , ai_document_extraction, ai_tool_server_action, ai_connection_ollama | исключены ТЗ |
| Синхронизация FSM ↔ Maintenance | штатной связи нет: в 19.0 нет модуля `fieldservice_maintenance` (в настройках FSM есть только переключатель). `fsm.equipment` и `maintenance.equipment` — разные записи, общее у них только серийный номер в тексте |

## Beta-компоненты (20 из 23 OCA)
Production/Stable: base_territory, fieldservice, product_warranty. Все остальные — **Beta**: 10 модулей FSM и
base_maintenance помечены так явно, а fieldservice_equipment_warranty, sign_oca и 7 модулей maintenance —
по README-бейджу, потому что `development_status` в манифесте не задан. Полный список: `docs/MODULES.md`.

## Ограничения и решения по ролям
- Исполнителю нужна **FSM User** (не «own»): кнопка Complete видна только этой группе. Нужна и
  **Inventory/User**: без неё не открываются серийные номера оборудования.
- Подписант: роль `sign.oca` с политикой `default` (один синтетический заказчик). Если заказчиков несколько,
  выражение `{{object.location_id.owner_id.id}}` сработает только у пользователей с группой Mail Template Editor
  (whitelist `mail_allowed_qweb_expressions`). Права шире я не выдавал.
- Переход в «Выполнена» через статус-бар запрещён ядром FSM; завершать нужно кнопкой Complete.
- После смены групп у пользователя нужен рестарт сервера (ormcache), а пользователю — повторный вход
  или очистка данных сайта (RPC-кеш IndexedDB).
- PDF-отчёты Odoo (wkhtmltopdf) на этом Mac не проверялись. Подпись работает на reportlab/PyPDF2.

## Что нужно от вас
1. Решить, удалять ли старую БД `tx10_demo19` (команда в `docs/BACKUP-RESTORE.md`).
2. Решить про публикацию в tailnet (`tailscale serve --https=8443 off`, если она не нужна).
3. Если нужна карта, получить разрешённый ключ Google Maps и ввести его в Settings (не в чат и не в git).
4. Пароли лежат в `solar-demo/.secrets`. Перед показом сторонним людям смените их в интерфейсе.

## Артефакты
`README.md` (развёртывание с нуля), `config/` (конфиг без секретов, repos.lock, python-deps.txt),
`docs/MODULES.md`, `docs/BACKUP-RESTORE.md`, `docs/DEMO-WALKTHROUGH.md`, `docs/RESULTS.md`, `loader/`, `verify/`, `scripts/`.
