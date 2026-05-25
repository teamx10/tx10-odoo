# Solar AI Settings UI + Test-Cases Docs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a proper Settings UI (res.config.settings) for the OpenRouter API key and default model so they can be configured in both dev and production, and save the manual test-case catalogue to a project doc for future E2E work.

**Architecture:** Two `fields.Char(..., config_parameter=...)` on `res.config.settings` automatically bind to `ir.config_parameter`; a small XML view inherits the Project settings app to expose them. No env-var bridge needed — the Settings UI is the canonical mechanism. Test-cases doc lives in `docs/testing/`.

**Tech Stack:** Odoo 19 ORM (`res.config.settings` `config_parameter` field attribute), OWL settings view (XML), Odoo `TransactionCase` tests, Markdown.

---

## Task 0: Create feature branch

**Files:** none (git only)

**Step 1: Create branch from develop**

```bash
git checkout develop
git pull
git checkout -b ai-custom-chat
```

Expected: `Switched to a new branch 'ai-custom-chat'`

**Step 2: Commit (empty — just the branch)**

No commit yet, move to Task 1.

---

## Task 1: TDD — res.config.settings Python model

**Files:**
- Create: `custom_addons/solar_ai/tests/test_solar_ai_settings.py`
- Modify: `custom_addons/solar_ai/tests/__init__.py` (add import)
- Create: `custom_addons/solar_ai/models/res_config_settings.py`
- Modify: `custom_addons/solar_ai/models/__init__.py` (add import)

---

### Step 1: Write the failing tests

Create `custom_addons/solar_ai/tests/test_solar_ai_settings.py`:

```python
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSolarAiConfigSettings(TransactionCase):
    """Verify res.config.settings ↔ ir.config_parameter binding for Solar AI."""

    def test_api_key_write_via_settings(self):
        settings = self.env['res.config.settings'].create(
            {'solar_ai_openrouter_api_key': 'sk-test-key'}
        )
        settings.execute()
        val = self.env['ir.config_parameter'].sudo().get_param(
            'solar_ai.openrouter_api_key'
        )
        self.assertEqual(val, 'sk-test-key')

    def test_default_model_write_via_settings(self):
        settings = self.env['res.config.settings'].create(
            {'solar_ai_default_model': 'anthropic/claude-3.5-haiku'}
        )
        settings.execute()
        val = self.env['ir.config_parameter'].sudo().get_param(
            'solar_ai.default_model'
        )
        self.assertEqual(val, 'anthropic/claude-3.5-haiku')

    def test_api_key_read_via_default_get(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'solar_ai.openrouter_api_key', 'sk-existing-key'
        )
        defaults = self.env['res.config.settings'].default_get(
            ['solar_ai_openrouter_api_key']
        )
        self.assertEqual(defaults.get('solar_ai_openrouter_api_key'), 'sk-existing-key')

    def test_default_model_read_via_default_get(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'solar_ai.default_model', 'openai/gpt-4o'
        )
        defaults = self.env['res.config.settings'].default_get(
            ['solar_ai_default_model']
        )
        self.assertEqual(defaults.get('solar_ai_default_model'), 'openai/gpt-4o')
```

Add import to `custom_addons/solar_ai/tests/__init__.py`:

```python
from . import test_solar_ai_settings
```

---

### Step 2: Run tests — expect FAIL

```bash
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070 \
  --test-tags :TestSolarAiConfigSettings
```

Expected: `AttributeError: 'res.config.settings' object has no attribute 'solar_ai_openrouter_api_key'`

(If you get a different error, the test file or `__init__` import is wrong — fix before proceeding.)

---

### Step 3: Implement the model

Create `custom_addons/solar_ai/models/res_config_settings.py`:

```python
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    solar_ai_openrouter_api_key = fields.Char(
        string="OpenRouter API Key",
        config_parameter="solar_ai.openrouter_api_key",
    )
    solar_ai_default_model = fields.Char(
        string="Default Model",
        config_parameter="solar_ai.default_model",
        help="OpenRouter model ID, e.g. anthropic/claude-sonnet-4-5 or anthropic/claude-3.5-haiku",
    )
```

Add import to `custom_addons/solar_ai/models/__init__.py`:

```python
from . import res_config_settings
```

---

### Step 4: Run tests — expect PASS

```bash
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070 \
  --test-tags :TestSolarAiConfigSettings
```

Expected: 4 tests pass. If any fail, debug the `execute()` / `default_get()` path — don't move on until all 4 are green.

---

### Step 5: Lint

```bash
ruff check --fix custom_addons/solar_ai && ruff format custom_addons/solar_ai
ruff check custom_addons/solar_ai
```

Expected: no errors.

---

### Step 6: Run full module test suite (regression)

```bash
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070
```

Expected: 51 tests pass (47 existing + 4 new).

---

### Step 7: Commit

```bash
git add custom_addons/solar_ai/models/res_config_settings.py \
        custom_addons/solar_ai/models/__init__.py \
        custom_addons/solar_ai/tests/test_solar_ai_settings.py \
        custom_addons/solar_ai/tests/__init__.py
git commit -m "[ADD] solar_ai: res.config.settings fields for OpenRouter key + model (TDD, 4 tests)"
```

---

## Task 2: Settings view (XML) + manifest

**Files:**
- Create: `custom_addons/solar_ai/views/res_config_settings_views.xml`
- Modify: `custom_addons/solar_ai/__manifest__.py` (add view to `data`)

(No automated test for view XML — Odoo validates XML at module load. The verification step is starting Odoo and visually checking the block.)

---

### Step 1: Create the settings view

Create `custom_addons/solar_ai/views/res_config_settings_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="res_config_settings_view_form_solar_ai" model="ir.ui.view">
        <field name="name">solar.ai.res.config.settings.view.form</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="project.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//app[@name='project']" position="inside">
                <block title="Solar AI Assistant" id="solar_ai_assistant">
                    <setting string="OpenRouter API Key"
                             help="Required for AI chat and document classification. Get it at openrouter.ai/keys">
                        <field name="solar_ai_openrouter_api_key"
                               widget="password"
                               placeholder="sk-or-v1-..."/>
                    </setting>
                    <setting string="Default Model"
                             help="OpenRouter model ID used for agent and chat. Changes take effect on next request.">
                        <field name="solar_ai_default_model"
                               placeholder="anthropic/claude-sonnet-4-5"/>
                    </setting>
                </block>
            </xpath>
        </field>
    </record>
</odoo>
```

---

### Step 2: Register view in manifest

In `custom_addons/solar_ai/__manifest__.py`, add to the `"data"` list:

```python
"data": [
    "security/ir.model.access.csv",
    "security/solar_ai_security.xml",
    "data/config_params.xml",
    "views/solar_ai_chat_views.xml",
    "views/res_config_settings_views.xml",   # ← add this line
],
```

---

### Step 3: Verify the view loads

```bash
./odoo-bin -d solar_dev --stop-after-init -u solar_ai --http-port 8070
```

Expected: no `ValueError: External ID not found` or XML errors in logs.

Then start the server:

```bash
./odoo-bin -d solar_dev --http-port 8070 --dev=all
```

Open `http://localhost:8070/web#action=base_setup.action_general_configuration`
→ Navigate to **Project** tab
→ Confirm **Solar AI Assistant** block is visible with "OpenRouter API Key" (masked) and "Default Model" fields.

Enter a test value in API Key → Save → re-open Settings → value should persist (masked).
Check Technical → System Parameters → `solar_ai.openrouter_api_key` updated.

---

### Step 4: Commit

```bash
git add custom_addons/solar_ai/views/res_config_settings_views.xml \
        custom_addons/solar_ai/__manifest__.py
git commit -m "[ADD] solar_ai: Settings UI block for OpenRouter API key and default model"
```

---

## Task 3: Create test-cases documentation

**Files:**
- Create: `docs/testing/` (directory)
- Create: `docs/testing/solar-ai-chat-test-cases.md`

---

### Step 1: Create the document

```bash
mkdir -p docs/testing
```

Create `docs/testing/solar-ai-chat-test-cases.md` with this content:

````markdown
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

## Risk Ladder

```
RISK ↑
 │
 L4 ──  Негатив / edge      reject, double-confirm, whitelist, budget, rate-limit
 │
 L3 ──  Запись + confirm    create / update / schedule_activity  ← головний кейс v2
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
| 0.6 | Open Settings → Project → **Solar AI Assistant** block visible | Block present with masked key field + model field | ✅ HttpCase (check view exists) |

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
| 4.6 | **Rate limit** | >20 requests in 60 s as same user | `{status: error, error: rate_limited}` | ⚠️ manual only (per-worker in-memory state) |
| 4.7 | **Unauthorized user** | Log in as user without PM group, open 🤖 panel, send message | `AccessError` / `403` from `/agent/step` | ✅ HttpCase |
| 4.8 | **Persistence & resume** | Send messages, close panel, go to Solar AI → My AI Chats, open chat, click **Continue in assistant** | Panel reopens with resume hint; history context sent to LLM | ✅ HttpCase (check chat record + re-POST /agent/step with chat_id) |
| 4.9 | **Empty message** | Submit empty input | Button disabled (client-side); if bypassed via API, `{status: error, error: empty_message}` | ✅ HttpCase |

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
| Rate limit | `controllers/_guards.py:23` | 20 calls / 60 s, **per-worker in-memory** |
| LLM service | `models/solar_ai_service.py:125` | `chat_with_tools` — OpenRouter HTTP call |
| Config param read | `models/solar_ai_service.py:37` | `_get_config("openrouter_api_key")` |
| Existing tour | `static/tests/tours/ai_panel.js` | starting point for JS E2E |
| Existing unit tests | `tests/test_solar_ai_agent.py` | 47 tests incl. CAS race, whitelist, budget preseed |
````

---

### Step 2: Verify the document renders

```bash
# quick sanity — file exists and isn't empty
wc -l docs/testing/solar-ai-chat-test-cases.md
```

Expected: 150+ lines.

---

### Step 3: Commit

```bash
git add docs/testing/solar-ai-chat-test-cases.md
git commit -m "[ADD] docs: solar AI chat manual test cases L0-L4 + code map for E2E"
```

---

## Final check

```bash
# All 51 tests still pass
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070

# Lint clean
ruff check custom_addons/solar_ai
```

Expected: 51 tests, 0 lint errors.

---

## Summary of commits on `ai-custom-chat`

```
[ADD] solar_ai: res.config.settings fields for OpenRouter key + model (TDD, 4 tests)
[ADD] solar_ai: Settings UI block for OpenRouter API key and default model
[ADD] docs: solar AI chat manual test cases L0-L4 + code map for E2E
```
