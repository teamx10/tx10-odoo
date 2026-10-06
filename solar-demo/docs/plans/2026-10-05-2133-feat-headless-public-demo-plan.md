---
title: On-Demand Public Solar Demo - Plan
type: feat
date: 2026-10-05
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# On-Demand Public Solar Demo - Plan

**Target:** демостенд Odoo 19 в `tx10-odoo`. Все пути — относительно корня `tx10-odoo`. Код Odoo не меняется; новые файлы живут в `solar-demo/` (исключён из git через `.git/info/exclude`).

---

## Goal Capsule

- **Objective:** на время демо пользователь одной командой открывает стенд Solar EPC по прямой ссылке `https://mac-madfish-m1.tail331ad2.ts.net:8443/odoo` для людей без Tailscale, а после демо так же закрывает его.
- **Means:** скрипты `demo-up`/`demo-down` поверх существующих `start.sh`/`stop.sh` и Tailscale Funnel на `:8443` (KTD1–KTD4).
- **Authority:** Requirements > KTD > Approach в юнитах. Settled-решения не пересматриваются без новых фактов.
- **Stop conditions:** остановиться и спросить, если (а) Funnel не работает на текущем Tailscale Standalone; (б) снаружи открывается менеджер БД или стенд Odoo 20.
- **Execution profile:** небольшие shell-скрипты и одна проверка снаружи (телефон в мобильной сети). Unit-тестов нет; проверка — smoke-сценарии.
- **Who finishes:** пользователь проводит проверку с телефона и подтверждает, что ссылка открывается.

---

## Product Contract

### Summary

Добавить две команды: «поднять демо» и «опустить демо». Первая запускает Odoo 19, проверяет, что на порту именно стенд Solar EPC, и включает Funnel. Вторая выключает Funnel и останавливает Odoo. Автозапуска нет: всё работает, пока пользователь вошёл в macOS.

### Problem Frame

Стенд сейчас доступен только из tailnet, поэтому показать его клиенту без Tailscale нельзя. Постоянно открытый в интернет сервис на рабочем MacBook — лишний риск, поэтому публичный доступ нужен только на время показа.

### Requirements

**Доступ**
- R1. Во время демо стенд открывается по `https://mac-madfish-m1.tail331ad2.ts.net:8443/odoo` из интернета без клиента Tailscale.
- R2. Вне демо стенд снаружи недоступен. Serve на `:443` (`localhost:3013`) всегда остаётся только в tailnet.
- R3. Публично может открыться только Odoo 19 со стендом `solar_epc_demo19`; менеджер БД закрыт (`list_db = False`).

**Эксплуатация**
- R4. Поднять и опустить демо — по одной команде каждое.
- R5. Если публичный доступ забыли выключить, это видно: `demo-up` и `demo-down` печатают состояние Funnel, а `tailscale funnel status` показывает его в любой момент.

### Key Decisions

- **Публичный доступ через Funnel** (session-settled: user-directed — chosen over tailnet-only, доступ для отдельных людей и свой домен: нужна прямая ссылка для любого). Governs R1, R3.
- **Без автозапуска; Odoo и Funnel включаются вручную только на время демо** (session-settled: user-directed — chosen over автозапуска без входа с LaunchDaemons и отдельного служебного пользователя: проще, и окно атаки открыто только во время показа). Governs R2, R4.
- **Odoo работает от `temich`** (session-settled: user-directed — chosen over отдельного служебного пользователя: риск принят, потому что публичный доступ кратковременный). Governs R3.

### Scope Boundaries

- Автозапуск после ребута, работа без входа в GUI, FileVault, LaunchDaemons — вне рамки (отменено пользователем).
- Свой домен, перенос на другую машину, стенд Odoo 20 — вне рамки.
- 2FA, rate limit, отдельный пользователь ОС — рассмотрено, не делаем: доступ открыт только на время показа. Пересмотреть, если стенд станет публичным постоянно.
- Авто-выключение Funnel по таймеру, фоновый сторож и периодическое напоминание — рассмотрено, не делаем. Опасный случай (публичный Odoo 20) закрыт KTD4; забытый Funnel на стенде Odoo 19 — это тот же стенд, что на демо, и риск принят вместе с ручным режимом. Таймер может оборвать идущий показ. Пересмотреть, если Funnel окажется забытым хотя бы раз.

### Open Questions

- Q2. Какие учётные записи получают зрители (рекомендация: только `pm`/`tech`, никогда `admin`) и меняются ли пароли после показа? Не блокирует U1–U3; ответ попадает в runbook (U3).

---

## Planning Contract

### Key Technical Decisions

- KTD1. **`demo-up` проверяет стенд перед включением Funnel.** Две проверки, обе обязательны:
  1. Процесс: единственный PID на `127.0.0.1:8069` (`workers = 0`) запущен с `-c …/odoo19.conf`. Код возврата `start.sh` не годится: `start-demo19.sh` выходит с 0 и сообщением «Odoo уже работает», если на 8069 отвечает любой Odoo, включая 20.
  2. Менеджер БД: тело `/web/database/manager` содержит «database manager has been disabled» и не содержит формы `/web/database/create`. Код ответа не годится: при `list_db = False` страница всё равно отдаёт 200 с баннером.

  Иначе Funnel не включается. Причина: на том же порту в dev бывает Odoo 20 с `admin/admin` и открытым менеджером БД, а Funnel привязан к порту, а не к процессу (R3).
- KTD2. **Funnel на `:8443` поверх существующего tailnet-serve на том же порту.** `demo-up` включает `funnel --bg --https=8443 http://127.0.0.1:8069`. `demo-down` возвращает tailnet-only командой `serve --bg --https=8443 http://127.0.0.1:8069`, а не `funnel … off`: форма `off` удаляет обработчик порта целиком, и `:8443` пропал бы и для tailnet. Ссылка для tailnet и для зрителей одна и та же. Порт `:443` не трогается (R2).
- KTD4. **Odoo 20 не стартует, пока `:8443` публичный.** `.odoo-data/start-demo.sh` в самом начале проверяет `tailscale funnel status` и отказывается запускаться с понятным сообщением, если `:8443` в режиме Funnel. Проверка KTD1 срабатывает один раз, при `demo-up`; без KTD4 забытый Funnel сделал бы публичным следующий запуск Odoo 20 (R3).
- KTD3. **Скрипты — тонкие обёртки над существующими.** Odoo запускается и останавливается через `solar-demo/scripts/start.sh` / `stop.sh` (они уже ждут HTTP 200 и освобождения порта). Новых механизмов запуска нет.

### Assumptions

- Funnel работает на текущем Tailscale Standalone (1.102.2): у ноды есть capability `funnel` для портов 443/8443/10000, serve на `:8443` уже работает. KB Tailscale (macOS variants) помечает Funnel для Standalone как неподдерживаемый — это проверяется первым шагом U1 (stop condition (а)). Если не работает — переход на `tailscaled` из Homebrew (`sudo tailscaled install-system-daemon`) отдельной задачей.
- Пользователь вошёл в macOS во время демо; Mac не спит (`sleep 0` уже в настройках `pmset`).
- `proxy_mode = True` и заголовки Tailscale дают Odoo схему `https`, как уже работает в tailnet.

### Risks & Dependencies

| Риск | Мера |
|---|---|
| Funnel не поддерживается на Standalone | Проверка первым шагом U1; запасной путь в Assumptions |
| Funnel забыли выключить после показа | `demo-down` и статус показывают состояние (R5) |
| Ссылки в письмах и подписях указывают на `localhost:8069` | Odoo берёт `web.base.url` из запроса администратора; заходить администратором через публичную ссылку или задать `web.base.url` на время демо (U3) |
| `odoo19.conf` читается всеми локальными пользователями (`644`), в нём `admin_passwd` и пароль БД | `chmod 600` в U2 |

---

## Implementation Units

### U1. Проверка Funnel и скрипты `demo-up` / `demo-down`

- **Goal:** одна команда открывает стенд публично, другая закрывает (R1, R2, R4, R5).
- **Requirements:** R1–R5. KTD1, KTD2, KTD3, KTD4.
- **Dependencies:** нет.
- **Files:** создать `solar-demo/scripts/demo-up.sh`, `solar-demo/scripts/demo-down.sh`; изменить `.odoo-data/start-demo.sh` (KTD4).
- **Approach:**
  1. Ручная проверка до кода: на 1–2 минуты включить funnel на `:8443`, открыть ссылку с телефона, вернуть tailnet-only по KTD2 и убедиться, что `:8443` остался в `tailscale serve status`. Funnel не работает → stop condition (а).
  2. `demo-up.sh`: `start.sh` → проверки KTD1 → funnel `:8443` (KTD2) → печать ссылки, состояния Funnel и напоминания про `demo-down`.
  3. `demo-down.sh`: tailnet-only по KTD2 → проверка, что `:8443` есть в serve и нет в Funnel → `stop.sh` → печать итогового состояния Funnel.
  4. `start-demo.sh`: отказ при публичном `:8443` (KTD4).
- **Patterns to follow:** стиль `.odoo-data/start-demo19.sh` — понятные ✓/✗ сообщения, ожидание реального HTTP 200.
- **Test scenarios:**
  - `demo-up.sh` при остановленном Odoo → Odoo 19 стартует, ссылка с телефона в мобильной сети открывает страницу входа по https.
  - `demo-up.sh` при запущенном Odoo 20 на 8069 → отказ с понятным сообщением, Funnel не включён.
  - `demo-down.sh` → с телефона ссылка не открывается; из tailnet `:8443` открывается, пока Odoo запущен; `:443` из интернета недоступен всегда.
  - Повторный `demo-up.sh` при уже включённом Funnel → без ошибок, состояние то же.
  - Funnel включён → `.odoo-data/start-demo.sh` (Odoo 20) отказывается стартовать.
- **Verification:** все четыре сценария проходят; `tailscale funnel status` после `demo-down` не показывает публичных портов.

### U2. Права на конфиг

- **Goal:** секреты из `odoo19.conf` недоступны другим локальным пользователям.
- **Requirements:** R3.
- **Dependencies:** нет.
- **Files:** `odoo19.conf` (права), `solar-demo/scripts/render-conf.sh` (создавать файл с `umask 077`).
- **Approach:** `chmod 600 odoo19.conf`; `render-conf.sh` пишет конфиг с правами 600, чтобы повторная генерация не вернула 644.
- **Test scenarios:**
  - После `render-conf.sh` файл `odoo19.conf` имеет права `600`.
  - Odoo 19 стартует через `start.sh` после смены прав.
- **Verification:** `ls -l odoo19.conf` показывает `-rw-------`.

### U3. Runbook

- **Goal:** через месяц демо поднимается без этого разговора (R4).
- **Requirements:** R2, R4, R5. Учитывает ответ на Q2.
- **Dependencies:** U1, U2.
- **Files:** изменить `solar-demo/README.md` (раздел «Tailscale» → «Публичное демо»), `AGENTSTATUS.md`.
- **Approach:** короткий раздел: перед демо `demo-up.sh`, ссылка, какие логины давать зрителям (по ответу на Q2), заходить администратором через публичную ссылку (иначе ссылки в документах ведут на localhost), после демо `demo-down.sh`, проверка статуса.
- **Test expectation:** none — документация; проверяется прочтением при сценариях U1.
- **Verification:** README больше не утверждает «В интернет стенд не публикуется» без оговорки про демо-режим.

---

## Verification Contract

| Проверка | Как | Юниты |
|---|---|---|
| Публичный доступ во время демо | телефон без Tailscale, мобильная сеть → `:8443/odoo` | U1 |
| Закрыто вне демо | тот же телефон после `demo-down.sh` | U1 |
| Защита от Odoo 20 | `demo-up.sh` при Odoo 20, запущенном через `.odoo-data/start-demo.sh` → отказ; `start-demo.sh` при включённом Funnel → отказ | U1 |
| Менеджер БД закрыт | снаружи `/web/database/manager` показывает баннер «disabled» и нет формы создания БД | U1 |
| Tailnet после демо | после `demo-down.sh` `:8443` открывается из tailnet | U1 |
| Права конфига | `odoo19.conf` = `600` | U2 |
| Регрессия демо | `solar-demo/scripts/verify.sh` — прежние 13/13 PASS | после U2 |

---

## Definition of Done

- Все проверки из Verification Contract проходят.
- После `demo-down.sh` `tailscale funnel status` не показывает публичных портов.
- README описывает демо-режим; временные файлы и пробные настройки удалены.

---

## Appendix

### Sources

- Варианты Tailscale для macOS (Funnel на Standalone): https://tailscale.com/kb/1065/macos-variants
- Tailscale Funnel: https://tailscale.com/kb/1223/funnel
- Текущее состояние: Tailscale Standalone 1.102.2, capability `funnel` для портов 443/8443/10000; serve `:8443 → 127.0.0.1:8069` и `:443 → localhost:3013` (tailnet only); `odoo19.conf` с `proxy_mode = True`, `list_db = False`.
