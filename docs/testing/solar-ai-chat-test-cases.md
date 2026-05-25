# Solar AI Chat — Manual Test Cases

> Source of truth for future E2E tests (HttpCase / JS tour automation).
> Companion to `custom_addons/solar_ai/static/tests/tours/ai_panel.js`.

## Prerequisites

| Requirement | How to satisfy |
|-------------|----------------|
| Odoo running | `./odoo-bin -d solar_dev --dev=all` |
| `solar_ai` installed | `-u solar_ai` or `-i solar_ai` on first run |
| API key set | Settings → Project → Solar AI → OpenRouter API Key |
| Logged in user | Must be **admin** or have **Project Manager** group (`_guards.py:14`) |

> Without API key the chat degrades gracefully — no crash, empty assistant response.

## Known Limitations

| Limitation | Location | Status |
|------------|----------|--------|
| Rate limit is per-worker in-memory | `controllers/_guards.py:23` | Known; fix requires shared state (Redis/PostgreSQL). Test 4.6 is manual-only. |
| API key stored plaintext at rest | `ir.config_parameter` (PostgreSQL) | By design (Odoo standard). Restrict DB + Odoo admin access in production. |

## Risk Ladder

```
RISK ↑
 │
 L4 ──  Негатив / edge      reject, double-confirm, whitelist, budget, rate-limit
 │
 L3 ──  Запис + confirm     create / update / schedule_activity  ← головний кейс v2
 │
 L2 ──  Навігація           open_model_list, navigate_to_record  (client-side)
 │
 L1 ──  Read-only           find_records, get_record_summary
 │
 L0 ──  Smoke (без ключа)   меню/systray/панель, graceful degradation
 ▼
```

---

## L0 — Smoke (no API key needed)

| # | Action | Expected | E2E candidate? |
|---|--------|----------|----------------|
| 0.1 | Log in → check menu **Solar AI → My AI Chats** exists | Menu visible | ✅ JS tour (already in `ai_panel.js`) |
| 0.2 | Check systray 🤖 button in top-right | Button visible | ✅ JS tour |
| 0.3 | Click 🤖 → panel opens | Panel opens; example prompts visible; composer focused | ✅ JS tour |
| 0.4 | Send any message **without API key** | No crash; assistant returns empty/silent response; panel stays open | ✅ HttpCase (mock service returns `""`) |
| 0.5 | Press Escape | Panel closes | ✅ JS tour |
| 0.6 | Open Settings → Project → **Solar AI Assistant** block visible | Block present with masked key field + model field | ✅ TransactionCase (`test_settings_view_renders_solar_ai_fields`) |

---

## L1 — Read-only queries (with API key; zero data-change risk)

Tool path: `find_records` (`solar_ai_agent.py:298`), `get_record_summary` (`solar_ai_agent.py:311`)

| # | Prompt | Tool invoked | Expected | E2E candidate? |
|---|--------|-------------|----------|----------------|
| 1.1 | `Знайди контакт <name from demo>` | `find_records(model=res.partner, query=<name>)` | List of id+display_name in reply; `role=tool` message in My AI Chats | ✅ HttpCase (mock LLM → known tool call) |
| 1.2 | `Дай зведення по проєкту <name>` | `get_record_summary(model=project.project, id=N)` | Only whitelisted fields returned (`read_fields` in `_MODEL_REGISTRY`) | ✅ HttpCase |
| 1.3 | Try a model NOT in registry: `Знайди рахунок account.move` | `find_records(model=account.move, ...)` | Agent gets error `"Model 'account.move' is not in the allowed list"` | ✅ HttpCase |

**What to check after:** My AI Chats → open the chat → messages with `role=user / assistant / tool`, all `status=done`.

---

## L2 — Navigation (client-side, no data change)

Tool path: client tools executed in browser (`ai_assistant_panel.js:91-115`)

| # | Prompt | Tool invoked | Expected | E2E candidate? |
|---|--------|-------------|----------|----------------|
| 2.1 | `Відкрий список проєктів` | `open_model_list(model=project.project)` | Browser navigates to project.project list view | ✅ JS tour (check URL / page title) |
| 2.2 | `Відкрий проєкт <name>` | `navigate_to_record(model=project.project, id=N)` | Browser opens form for that specific project | ✅ JS tour |
| 2.3 | `Відкрий список контактів` | `open_model_list(model=res.partner)` | res.partner list view opened | ✅ JS tour |

---

## L3 — Write with confirmation (core v2 feature)

Every write tool creates a `pending_confirmation` message. Data only changes **after Підтвердити** is clicked.

Tool path: `solar_ai_agent.py:325` (create_record), `:359` (update_record), `:397` (schedule_activity)
Confirm: `ai_chat.py:189` → `_execute_confirmed_action` `:251`

| # | Prompt | Tool | Before confirm | After confirm | E2E candidate? |
|---|--------|------|---------------|---------------|----------------|
| 3.1 | `Створи контакт «Тест Клієнт», email test@example.com` | `create_record(model=res.partner)` | No record in Contacts | Record exists | ✅ HttpCase (mock LLM, call /agent/confirm) |
| 3.2 | `Онови телефон контакту <name> на +380991234567` | `update_record(model=res.partner, id=N)` | Old phone | Field changed | ✅ HttpCase |
| 3.3 | `Заплануй активність «Передзвонити» на проєкт <name> на 2026-06-01` | `schedule_activity(model=project.project)` | No activity | Activity on record with deadline | ✅ HttpCase |
| 3.4 | `Онови назву задачі <name>` | `update_record(model=project.task)` | Old name | New name | ✅ HttpCase |

**Important verify:** after 3.1–3.4, re-open the record **before** clicking Підтвердити and confirm the data has NOT changed yet. Then confirm → data changes.

---

## L4 — Edge cases / negative / races

| # | Scenario | How to trigger | Expected | E2E candidate? |
|---|----------|---------------|----------|----------------|
| 4.1 | **Відхилити** | Trigger write-tool → click Відхилити | `status=rejected`; data unchanged; no ORM call | ✅ HttpCase |
| 4.2 | **Double-confirm (race)** | Two rapid POST `/solar_ai/agent/confirm` with same `message_id` | First: ok; second: `{status: ok, note: already_processed}`; no duplicate record | ✅ HttpCase (`test_double_confirm_is_noop` already exists) |
| 4.3 | **Whitelist field violation** | `Онови поле credit_limit контакту X` | Agent error: `"Fields not in whitelist for 'res.partner': ['credit_limit']"` | ✅ HttpCase (call `safe_execute_tool` directly) |
| 4.4 | **Disallowed model** | `Створи рахунок account.move` | Error: `"Model 'account.move' is not in the allowed list"` | ✅ HttpCase |
| 4.5 | **Budget exhausted** | Set `total_tokens = MAX_TOKENS - 1` via SQL, send one more message | `{status: error, error: budget_exhausted}` in response | ✅ HttpCase (SQL preseed, like `test_confirm_guard_atomic_via_sql_preseeding`) |
| 4.6 | **Rate limit** | >20 requests in 60 s as same user | `{status: error, error: rate_limited}` | ⚠️ **manual only** — per-worker in-memory state is not testable in single-process test runner; fix requires shared-state rate limiter |
| 4.7 | **Unauthorized user** | Log in as user without PM group, open 🤖 panel, send message | `AccessError` / `403` from `/agent/step` | ✅ HttpCase |
| 4.8 | **Persistence & resume** | Send messages, close panel, go to Solar AI → My AI Chats, open chat, click **Continue in assistant** | Panel reopens with resume hint; history context sent to LLM | ✅ HttpCase (check chat record + re-POST /agent/step with chat_id) |
| 4.9 | **Empty message** | Submit empty input | Button disabled (client-side); if bypassed via API, `{status: error, error: empty_message}` | ✅ HttpCase |
| 4.10 | **Empty API key** | Settings → clear API key → Save; send a message | `_build_headers()` returns `None`; no crash; graceful empty response | ✅ TransactionCase (`test_empty_api_key_service_returns_no_headers`) |

---

## Code Map (for E2E authors)

| Component | File:line | Notes |
|-----------|-----------|-------|
| System prompt | `controllers/ai_chat.py:12` | `SYSTEM_PROMPT_TEMPLATE` — replace `{lang}` with user language |
| Agent step endpoint | `controllers/ai_chat.py:26` | main loop entry; handles create-chat and budget-guard |
| Confirm endpoint | `controllers/ai_chat.py:189` | atomic CAS: `rowcount == 0` → already processed |
| Reject endpoint | `controllers/ai_chat.py:229` | same CAS, sets `rejected` |
| Tool registry | `models/solar_ai_agent.py:16` | `_MODEL_REGISTRY` — whitelist of models + capabilities + read_fields |
| Tool definitions (JSON schema) | `models/solar_ai_agent.py:75` | what gets sent to the LLM |
| Capability check | `models/solar_ai_agent.py:220` | `_check_capability(tool_name, model)` |
| create_record impl | `models/solar_ai_agent.py:325` | creates `pending_confirmation` message |
| update_record impl | `models/solar_ai_agent.py:359` | same pattern |
| schedule_activity impl | `models/solar_ai_agent.py:397` | validates date + summary length |
| Client tool loop | `static/src/components/ai_assistant_panel.js:48` | `_runAgentLoop` max 10 rounds |
| Client navigation | `static/src/components/ai_assistant_panel.js:91` | `navigate_to_record`, `open_model_list` |
| Authorization guard | `controllers/_guards.py:14` | `project.group_project_manager` or admin |
| Rate limit | `controllers/_guards.py:23` | 20 calls / 60 s, **per-worker in-memory** (see Known Limitations) |
| LLM service | `models/solar_ai_service.py:125` | `chat_with_tools` — OpenRouter HTTP call |
| Config param read | `models/solar_ai_service.py:37` | `_get_config("openrouter_api_key")` |
| Settings model | `models/res_config_settings.py` | `config_parameter=` binding to `ir.config_parameter` |
| Existing tour | `static/tests/tours/ai_panel.js` | starting point for JS E2E |
| Existing unit tests | `tests/test_solar_ai_agent.py` | 47 tests incl. CAS race, whitelist, budget preseed |
