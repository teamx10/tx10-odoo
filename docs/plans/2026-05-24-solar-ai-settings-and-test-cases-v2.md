# Solar AI Settings UI + Test-Cases Docs — v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `res.config.settings` Settings UI for the OpenRouter API key and default model; extend the test suite to cover the service read-path and edge cases; reconcile the `config_params.xml` seed with the new UI; save the manual test-case catalogue to `docs/testing/`.

**Architecture:** Two `fields.Char(..., config_parameter=...)` on `res.config.settings` bind to `ir.config_parameter`. The existing empty `solar_ai_openrouter_api_key` seed record is removed — the Settings UI becomes the sole write path for the key. `solar_ai.default_model` seed is kept (`noupdate=1`) with an explicit reinstall-behaviour comment. A `TransactionCase` test guards against xpath silent-fail in the settings view. The per-worker rate-limit limitation is documented in code but not changed (out of scope).

**Tech Stack:** Odoo 19 ORM (`res.config.settings` `config_parameter` field attribute), OWL settings view (XML), `odoo.tests.TransactionCase`, Markdown.

---

## Changes from v1 (IT-team review findings addressed)

| # | Finding | What changed in v2 |
|---|---------|-------------------|
| 1 | Dual seed source-of-truth | Task 2: remove empty `openrouter_api_key` seed; add reinstall comment to `default_model` |
| 2 | API key plaintext at rest | Task 3: add `help` note to both model fields |
| 3 | Rate-limit per-worker | Task 2: add `# NOTE:` to `_guards.py` |
| 4 | No rollback doc | Task 3: explicit rollback steps added |
| 5 | xpath silent-fail | Task 3 TDD: `test_settings_view_renders_solar_ai_fields` |
| 6 | No empty-key test | Task 1: `test_empty_api_key_service_returns_no_headers` |
| 7 | No service read test | Task 1: `test_service_reads_config_after_settings_execute` |

---

## Task 0: Create feature branch

**Files:** none (git only)

### Step 1: Create branch from develop

```bash
git checkout develop
git pull
git checkout -b feat/solar-ai-settings
```

Expected: `Switched to a new branch 'feat/solar-ai-settings'`

---

## Task 1: TDD — res.config.settings Python model (6 tests)

**Files:**
- Create: `custom_addons/solar_ai/tests/test_solar_ai_settings.py`
- Modify: `custom_addons/solar_ai/tests/__init__.py`
- Create: `custom_addons/solar_ai/models/res_config_settings.py`
- Modify: `custom_addons/solar_ai/models/__init__.py`

---

### Step 1: Write the failing tests

Create `custom_addons/solar_ai/tests/test_solar_ai_settings.py`:

```python
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSolarAiConfigSettings(TransactionCase):
    """Verify res.config.settings ↔ ir.config_parameter binding for Solar AI."""

    # --- ORM binding (happy path) ---

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

    # --- Edge case: empty key (finding #6) ---

    def test_empty_api_key_service_returns_no_headers(self):
        """Empty key saved via Settings must not produce auth headers (finding #6)."""
        settings = self.env['res.config.settings'].create(
            {'solar_ai_openrouter_api_key': ''}
        )
        settings.execute()
        service = self.env['solar.ai.service']
        self.assertIsNone(
            service._build_headers(),
            "Empty API key must not produce auth headers — _build_headers must return None",
        )

    # --- Service read-path integration (finding #7) ---

    def test_service_reads_config_after_settings_execute(self):
        """_get_config must return updated values immediately after settings.execute() (finding #7)."""
        settings = self.env['res.config.settings'].create({
            'solar_ai_openrouter_api_key': 'sk-roundtrip',
            'solar_ai_default_model': 'openai/gpt-4o-mini',
        })
        settings.execute()
        service = self.env['solar.ai.service']
        self.assertEqual(service._get_config('openrouter_api_key'), 'sk-roundtrip')
        self.assertEqual(service._get_config('default_model'), 'openai/gpt-4o-mini')
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

(Any other error means the import or test file has a problem — fix before continuing.)

---

### Step 3: Implement the model

Create `custom_addons/solar_ai/models/res_config_settings.py`:

```python
from odoo import fields, models

_AT_REST_NOTE = (
    "Stored as plaintext in ir.config_parameter (PostgreSQL). "
    "Readable by any user with 'Technical > System Parameters' access or direct DB access. "
    "Restrict DB and Odoo admin access in production."
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    solar_ai_openrouter_api_key = fields.Char(
        string="OpenRouter API Key",
        config_parameter="solar_ai.openrouter_api_key",
        help=f"Required for AI chat and document classification. Get it at openrouter.ai/keys. {_AT_REST_NOTE}",
    )
    solar_ai_default_model = fields.Char(
        string="Default Model",
        config_parameter="solar_ai.default_model",
        help=(
            "OpenRouter model ID used for agent and chat. "
            "Changes take effect on the next request. "
            "Examples: anthropic/claude-sonnet-4-5, anthropic/claude-3.5-haiku, openai/gpt-4o-mini."
        ),
    )
```

Add import to `custom_addons/solar_ai/models/__init__.py` (end of existing imports line):

```python
from . import res_config_settings, solar_ai_agent, solar_ai_chat, solar_ai_message, solar_ai_service
```

---

### Step 4: Run tests — expect PASS (6 tests)

```bash
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070 \
  --test-tags :TestSolarAiConfigSettings
```

Expected: 6 tests pass. If any fail, fix before moving on — do not skip.

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

Expected: 53 tests pass (47 existing + 6 new). If the count differs, investigate.

---

### Step 7: Commit

```bash
git add custom_addons/solar_ai/models/res_config_settings.py \
        custom_addons/solar_ai/models/__init__.py \
        custom_addons/solar_ai/tests/test_solar_ai_settings.py \
        custom_addons/solar_ai/tests/__init__.py
git commit -m "[ADD] solar_ai: res.config.settings fields for OpenRouter key + model (TDD, 6 tests)"
```

---

## Task 2: Reconcile config_params.xml + document rate-limit

**Files:**
- Modify: `custom_addons/solar_ai/data/config_params.xml`
- Modify: `custom_addons/solar_ai/controllers/_guards.py`

(No automated tests — these are documentation/config changes. The regression run in Task 1 Step 6 already validates the service reads correctly.)

---

### Step 1: Remove the empty API key seed from config_params.xml

The `solar_ai_openrouter_api_key` record in `config_params.xml` has always been empty (`value=""`). Now that the Settings UI is the canonical write path for this key, the seed record serves no purpose. Remove it.

Edit `custom_addons/solar_ai/data/config_params.xml` — remove the `solar_ai_openrouter_api_key` record and add a comment to `solar_ai_default_model`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <!-- noupdate="1": these records are written only on fresh install.
         On module UPDATE (-u solar_ai) existing DB values are preserved.
         On module REINSTALL (uninstall + install), these seed values are
         re-applied, which will shadow any Settings-configured default_model.
         The API key is NOT seeded here — it must be set via Settings UI. -->
    <record id="solar_ai_openrouter_base_url" model="ir.config_parameter">
        <field name="key">solar_ai.openrouter_base_url</field>
        <field name="value">https://openrouter.ai/api/v1</field>
    </record>
    <record id="solar_ai_default_model" model="ir.config_parameter">
        <field name="key">solar_ai.default_model</field>
        <field name="value">anthropic/claude-sonnet-4-5</field>
    </record>
    <record id="solar_ai_vision_model" model="ir.config_parameter">
        <field name="key">solar_ai.vision_model</field>
        <field name="value">anthropic/claude-opus-4-7</field>
    </record>
    <record id="html_editor_olg_endpoint" model="ir.config_parameter">
        <field name="key">html_editor.olg_api_endpoint</field>
        <field name="value"></field>
    </record>
</odoo>
```

Key change: the `solar_ai_openrouter_api_key` record is removed. The `solar_ai.openrouter_api_key` ir.config_parameter will be created on first Settings save via `set_param`.

---

### Step 2: Document per-worker rate-limit in _guards.py

Open `custom_addons/solar_ai/controllers/_guards.py`. The existing docstring on `check_rate_limit` already says `(NOTE: per-worker process only)`. Expand it:

```python
def check_rate_limit(user_id) -> bool:
    """Sliding-window rate limit per user.

    NOTE: per-worker in-memory state — not shared across gunicorn workers.
    With N workers the effective limit is 20×N calls / 60 s, making this
    guard weaker in multi-worker production deployments.
    A future fix would use Redis or PostgreSQL for shared state.
    Tracked in: TODO — replace with shared-state rate limiter before scaling beyond 2 workers.
    """
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SEC
    with _rate_limit_lock:
        calls = _rate_limit_state[user_id]
        calls[:] = [t for t in calls if t > cutoff]
        if not calls:
            _rate_limit_state.pop(user_id, None)
            _rate_limit_state[user_id].append(now)
            return True
        if len(calls) >= RATE_LIMIT_MAX_CALLS:
            return False
        calls.append(now)
    return True
```

---

### Step 3: Verify no regression

```bash
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070
```

Expected: still 53 tests pass. Removing the seed record does not affect tests (the `test_api_key_write_via_settings` test creates the param via `execute()`).

---

### Step 4: Commit

```bash
git add custom_addons/solar_ai/data/config_params.xml \
        custom_addons/solar_ai/controllers/_guards.py
git commit -m "[IMP] solar_ai: remove duplicate api_key seed; document per-worker rate-limit (#1 #3)"
```

---

## Task 3: TDD — Settings view (XML) + xpath guard test + manifest

**Files:**
- Modify: `custom_addons/solar_ai/tests/test_solar_ai_settings.py` (add new test class)
- Create: `custom_addons/solar_ai/views/res_config_settings_views.xml`
- Modify: `custom_addons/solar_ai/__manifest__.py`

---

### Step 1: Write the failing xpath guard test

Add a second test class to `custom_addons/solar_ai/tests/test_solar_ai_settings.py` (append after `TestSolarAiConfigSettings`):

```python
@tagged('post_install', '-at_install')
class TestSolarAiSettingsView(TransactionCase):
    """Guard: Solar AI fields must appear in the rendered settings form (xpath silent-fail guard, finding #5)."""

    def test_settings_view_renders_solar_ai_fields(self):
        """get_views merges all inherited views — if xpath mismatches, our block is absent."""
        views = self.env['res.config.settings'].get_views([[False, 'form']])
        arch = views['views']['form']['arch']
        self.assertIn(
            'solar_ai_openrouter_api_key',
            arch,
            "solar_ai_openrouter_api_key missing from rendered settings form — "
            "check //app[@name='project'] xpath in res_config_settings_views.xml",
        )
        self.assertIn(
            'solar_ai_default_model',
            arch,
            "solar_ai_default_model missing from rendered settings form",
        )
```

---

### Step 2: Run test — expect FAIL

```bash
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070 \
  --test-tags :TestSolarAiSettingsView
```

Expected: `AssertionError: solar_ai_openrouter_api_key missing from rendered settings form`

(The field exists in the Python model but is not yet wired into the settings form view.)

---

### Step 3: Create the settings view

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
                             help="Required for AI chat and document classification. Get it at openrouter.ai/keys. Stored as plaintext in PostgreSQL — restrict DB access in production.">
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

### Step 4: Register view in manifest

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

### Step 5: Run test — expect PASS

```bash
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070 \
  --test-tags :TestSolarAiSettingsView
```

Expected: 1 test passes.

---

### Step 6: Verify the view loads (no XML errors)

```bash
./odoo-bin -d solar_dev --stop-after-init -u solar_ai --http-port 8070
```

Expected: no `ValueError: External ID not found` or XML errors in the log.

---

### Step 7: Manual verification

Start the server:

```bash
./odoo-bin -d solar_dev --http-port 8070 --dev=all
```

Open `http://localhost:8070/web#action=base_setup.action_general_configuration`
→ Navigate to the **Project** tab
→ Confirm **Solar AI Assistant** block is visible with "OpenRouter API Key" (masked) and "Default Model" fields

Enter a test API key → Save → re-open Settings → value should persist (masked).  
Check Technical → System Parameters → `solar_ai.openrouter_api_key` updated.

---

### Step 8: Rollback procedure (for incidents)

If a broken view must be reverted after deployment:

```bash
# 1. Revert the manifest entry and view file
git revert HEAD  # or manually remove the view file + manifest line

# 2. Re-apply the module without the view
./odoo-bin -d solar_dev --stop-after-init -u solar_ai --http-port 8070

# 3. Verify no XML errors in log and settings page loads normally
```

The Python model fields (`solar_ai_openrouter_api_key`, `solar_ai_default_model`) remain on `res.config.settings` — they just won't be visible in the form. The `ir.config_parameter` values are unaffected.

---

### Step 9: Run full test suite (regression)

```bash
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070
```

Expected: 54 tests pass (47 existing + 6 from Task 1 + 1 from this task).

---

### Step 10: Lint

```bash
ruff check --fix custom_addons/solar_ai && ruff format custom_addons/solar_ai
ruff check custom_addons/solar_ai
```

Expected: no errors.

---

### Step 11: Commit

```bash
git add custom_addons/solar_ai/views/res_config_settings_views.xml \
        custom_addons/solar_ai/__manifest__.py \
        custom_addons/solar_ai/tests/test_solar_ai_settings.py
git commit -m "[ADD] solar_ai: Settings UI block for OpenRouter API key and default model (xpath guard test)"
```

---

## Task 4: Create test-cases documentation

**Files:**
- Create: `docs/testing/` (directory)
- Create: `docs/testing/solar-ai-chat-test-cases.md`

---

### Step 1: Create the directory and document

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
````

---

### Step 2: Verify the document renders

```bash
wc -l docs/testing/solar-ai-chat-test-cases.md
```

Expected: 150+ lines.

---

### Step 3: Commit

```bash
git add docs/testing/solar-ai-chat-test-cases.md
git commit -m "[ADD] docs: solar AI chat manual test cases L0-L4 + code map for E2E (v2)"
```

---

## Final check

```bash
# All 54 tests pass
./odoo-bin -d solar_dev --test-enable --stop-after-init \
  -u solar_ai --http-port 8070

# Lint clean
ruff check custom_addons/solar_ai
```

Expected: 54 tests, 0 lint errors.

---

## Summary of commits on `feat/solar-ai-settings`

```
[ADD] solar_ai: res.config.settings fields for OpenRouter key + model (TDD, 6 tests)
[IMP] solar_ai: remove duplicate api_key seed; document per-worker rate-limit (#1 #3)
[ADD] solar_ai: Settings UI block for OpenRouter API key and default model (xpath guard test)
[ADD] docs: solar AI chat manual test cases L0-L4 + code map for E2E (v2)
```
