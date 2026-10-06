# Резервное копирование и восстановление

## Solar EPC демобаза (`solar_epc_demo19`)

```bash
solar-demo/scripts/backup.sh
# → solar-demo/backups/solar_epc_demo19-<YYYYMMDD-HHMMSS>/
#     solar_epc_demo19.dump (pg_dump -Fc) · filestore-solar_epc_demo19.tgz · repos.lock
# скрипт сразу проверяет читаемость дампа (pg_restore -l) и архива (tar -t)
```

Восстановление — **всегда в новую БД**, существующие не удаляются и не перезаписываются:

```bash
solar-demo/scripts/restore.sh solar-demo/backups/solar_epc_demo19-<дата> [имя_новой_БД]
# по умолчанию → solar_epc_demo19_restored + .odoo-data/filestore/solar_epc_demo19_restored
```

Переключить стенд на восстановленную БД:
1. `solar-demo/scripts/stop.sh`
2. в `config/odoo19.conf.example` заменить `db_name` и `dbfilter` → `solar-demo/scripts/render-conf.sh`
3. `solar-demo/scripts/start.sh`

Проверено 2026-10-05: восстановление в `solar_restore_test` дало ту же картину, что и исходная БД
(7 fsm_order, 126 модулей, 584 вложения, 480 файлов filestore); тестовая копия затем удалена.

Важно: дамп совместим только с кодом из `config/repos.lock` (Odoo 19.0 + те же коммиты OCA).

## Предыдущий стенд `tx10_demo19` (заменён, НЕ удалён)

БД `tx10_demo19` осталась в PostgreSQL и скрыта `dbfilter`. Бэкап до изменений:
`solar-demo/backups/tx10_demo19-20261005-1745/`
(`tx10_demo19.dump`, `filestore-tx10_demo19.tgz`, `odoo19.conf.orig`, старые `start/stop-demo19.sh`, `odoo19.log.old`).

Вернуть старый стенд:
```bash
solar-demo/scripts/stop.sh
cp solar-demo/backups/tx10_demo19-20261005-1745/odoo19.conf.orig odoo19.conf
.odoo-data/start-demo19.sh
# если БД tx10_demo19 к тому моменту удалена:
#   createdb -h 127.0.0.1 -U odoo tx10_demo19
#   pg_restore -h 127.0.0.1 -U odoo -d tx10_demo19 --no-owner .../tx10_demo19.dump
#   tar -C .odoo-data/filestore -xzf .../filestore-tx10_demo19.tgz
```

Удалить старую БД окончательно (только по вашему решению):
`dropdb -h 127.0.0.1 -U odoo tx10_demo19 && rm -rf .odoo-data/filestore/tx10_demo19`
