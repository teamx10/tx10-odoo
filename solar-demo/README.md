# Solar EPC демостенд — Odoo 19 Community + OCA

Изолированный **демонстрационный** стенд базового контура:
объекты/станции → оборудование → проекты → сервисные работы → закупки/склад →
гарантии → плановое ТО → ремонт → учёт времени → подпись документа.

> Это не готовая Solar EPC-платформа. Специализированных EPC-процессов, цифрового паспорта,
> AI, SCADA, EMS, VPP и карты здесь **нет**. 20 из 23 OCA-модулей имеют статус Beta.

| Параметр | Значение |
|---|---|
| URL | http://localhost:8069/odoo (только 127.0.0.1; см. «Tailscale» ниже) |
| БД / filestore | `solar_epc_demo19` / `.odoo-data/filestore/solar_epc_demo19` |
| Код Odoo | `tx10-odoo`, ветка `19.0` @ `29cf86bd012` (без изменений) |
| OCA | `solar-demo/oca/*` @ коммиты из `config/repos.lock` |
| Конфиг | `tx10-odoo/odoo19.conf` ← собирается из `config/odoo19.conf.example` |
| Секреты | `solar-demo/.secrets` (права 600, вне git, в документы не попадают) |
| Почта | заблокирована: SMTP → 127.0.0.1:2 (закрытый порт), письма остаются в `exception` |

## Структура

```
solar-demo/
├── README.md                 ← этот файл: развёртывание с нуля
├── config/  odoo19.conf.example · repos.lock · python-deps.txt
├── oca/     field-service · maintenance · rma · sign · geospatial   (git clone 19.0)
├── loader/  _lib.py + 10…60_*.py   — демоданные через ORM, идемпотентно (xmlid demo_solar.*)
├── verify/  _check.py + s*.py      — проверки сценариев под обычными пользователями
├── scripts/ install-group · verify-group · load-demo · verify · backup · restore ·
│            render-conf · start · stop · ui-session · ui-login-js · gen-inventory
├── docs/    VISION.md · REPORT.md · RESULTS.md · MODULES.md · DEMO-WALKTHROUGH.md · BACKUP-RESTORE.md · screens/
├── logs/    журналы установки групп и загрузки
├── backups/ дампы БД + filestore
└── .secrets, .private/  (600/700, не публикуются)
```

## Повторное развёртывание с нуля

Требования: macOS/Linux, PostgreSQL 17 (роль `odoo` с CREATEDB), `uv`, git.

```bash
cd ~/dev/tx10/tx10-odoo
git checkout 19.0 && git reset --hard 29cf86bd012     # только если рабочая копия чистая!
uv venv -p 3.12 .venv19 && uv pip install -p .venv19 -r requirements.txt

# 1. OCA по закреплённым коммитам
mkdir -p solar-demo/oca && cd solar-demo/oca
while read name url branch sha; do [ "$name" = odoo ] && continue
  git clone -q -b "$branch" "$url" "$name" && git -C "$name" checkout -q "$sha"; done < ../config/repos.lock
cd ../..

# 2. Секреты (генерируются локально, никуда не отправляются)
( umask 077; { echo "MASTER_PASSWD=$(openssl rand -base64 18 | tr -d '/+=')"
  for u in admin pm tech svcmgr; do echo "PW_$u=$(openssl rand -base64 12 | tr -d '/+=')"; done
} > solar-demo/.secrets )
solar-demo/scripts/render-conf.sh                       # → odoo19.conf

# 3. Установка модулей группами (каждая проверяется: состояние, лог, HTTP)
S=solar-demo/scripts
$S/install-group.sh 01-core contacts,project,purchase,stock,maintenance,repair,hr_timesheet,base_automation,base_geolocalize
$S/install-group.sh 02-fsm-core base_territory,fieldservice
$S/install-group.sh 03-fsm-ext1 fieldservice_project,fieldservice_stock,fieldservice_timesheet,fieldservice_stage_validation,fieldservice_stage_server_action
$S/install-group.sh 04-fsm-ext2 product_warranty,fieldservice_equipment_stock,fieldservice_equipment_warranty,fieldservice_purchase,fieldservice_recurring,fieldservice_repair
$S/install-group.sh 05-maintenance base_maintenance,maintenance_plan,maintenance_equipment_category_hierarchy,maintenance_equipment_certification,maintenance_equipment_tags,maintenance_project,maintenance_request_purchase,maintenance_request_repair
$S/install-group.sh 06-sign sign_oca,fieldservice_sign
# после каждой: $S/verify-group.sh <группа> <модули>

# 4. Демоданные и проверки
$S/load-demo.sh            # все шаги loader/10…60, повторный запуск не создаёт дублей
$S/start.sh
$S/verify.sh               # → docs/results-latest.txt
# Подпись (сценарий 11) ставится в браузере — см. docs/DEMO-WALKTHROUGH.md, затем verify.sh s11b_signed.py
```

Карта (`base_google_map`, `web_view_google_map`, `fieldservice_google_map`) **не устанавливается**:
нужен ключ Google Maps JavaScript API с billing-аккаунтом. Если ключ будет разрешён:
`$S/install-group.sh 07-map base_google_map,web_view_google_map,fieldservice_google_map`,
затем ключ — в *Settings → Google Maps* (не в git/документы).

## Управление

```bash
solar-demo/scripts/start.sh  |  solar-demo/scripts/stop.sh   # обёртки над .odoo-data/*-demo19.sh
tail -f .odoo-data/odoo19.log
```

## Публичное демо (Tailscale Funnel)

Вне демо: `tailscale serve` публикует 8069 **только внутри tailnet** на `:8443`; в интернет стенд не открыт.
`:443` (`localhost:3013`) всегда остаётся tailnet-only.

| Шаг | Команда / действие |
|---|---|
| 1. Перед показом | `solar-demo/scripts/demo-up.sh` — старт Odoo 19 → проверка, что на 8069 именно `odoo19.conf` и менеджер БД закрыт → Funnel на `:8443` |
| 2. Ссылка для зрителей | `https://mac-madfish-m1.tail331ad2.ts.net:8443/odoo` (без Tailscale; первые ~30 с после включения ingress может не отвечать) |
| 3. Логины зрителям | только `pm` / `tech` (пароли — `solar-demo/.secrets`), **никогда** `admin` *(Q2 — подтвердить; после показа сменить пароли, если их видели посторонние)* |
| 4. Администратор | заходить через публичную ссылку, иначе ссылки в письмах/документах ведут на `localhost:8069` |
| 5. После показа | `solar-demo/scripts/demo-down.sh` — `:8443` обратно tailnet-only, стоп Odoo |
| Проверить в любой момент | `tailscale funnel status` — публичный порт помечен `(Funnel on)` |

Защита: пока `:8443` публичен, `.odoo-data/start-demo.sh` (Odoo 20, `admin/admin`, открытый менеджер БД)
отказывается стартовать. `demo-up.sh` безопасно запускать повторно.
