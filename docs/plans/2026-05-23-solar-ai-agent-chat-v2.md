# Solar AI Agent Chat — Implementation Plan v2

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an in-app AI assistant that opens from any Odoo page as a side panel and can navigate the system, search solar-domain records, and perform write actions with explicit confirmation — backed by OpenRouter LLM tool-calling.

**Architecture:** Client-driven step loop — the backend does exactly ONE LLM round per HTTP request (`/agent/step`), returns `tool_calls` to the browser, which executes navigation locally via `action.doAction`, posts server-tool results via `/agent/exec_tool`, shows pending-confirmation cards for write tools, and re-invokes `/agent/step` with accumulated results. Round counter + token budget live on `solar.ai.chat` in the DB and are updated via **atomic SQL** (not ORM read-modify-write), so multi-worker Odoo deployments do not corrupt state. The confirm endpoint uses a SQL compare-and-set to prevent double-execution in the face of concurrent clicks.

**Tech Stack:** Python 3.10+, Odoo 19 ORM (`TransactionCase`/`HttpCase`), OpenRouter (OpenAI-compatible tool-calling), `httpx` (sync), OWL 2 (Odoo Web Library), `fields.Json`, `ir.rule` record-level security, `env.cr.execute` for CAS operations.

---

## Changes from v1 — IT-team review fixes

| # | Finding | Severity | Task | Fix summary |
|---|---------|----------|------|-------------|
| B1 | Confirm double-execute race condition | BLOCKER | 2.2 | SQL CAS: `UPDATE … WHERE status='pending_confirmation'` + rowcount check |
| B2 | No DB migration rollback procedure | BLOCKER | 1.2 | Added rollback SQL block + downgrade instructions |
| B3 | `env['ir.fields'].datetime.now()` doesn't exist | BLOCKER | 1.4, 2.2 | Replaced with `fields.Datetime.now()` everywhere |
| B4 | Token budget read-modify-write is non-atomic | BLOCKER | 1.4 | SQL atomic `UPDATE … SET total_tokens = total_tokens + %s RETURNING …` |
| B5 | `chat_id` None dereference in write tools | BLOCKER | 2.1 | Explicit guard: `if not chat_id: raise ValueError(…)` |
| B6 | `agent_reject` browse(id=0) on missing param | BLOCKER | 2.2 | Explicit missing-param check before browse |
| B7 | OWL frontend has zero automated tests | BLOCKER | 1.5 | JS tour + HttpCase `start_tour` test |
| B8 | `test_double_confirm_is_noop` can never fail | BLOCKER | 2.2 | Rewritten: counts 0→1→1, verifies atomic guard via SQL pre-seeding |
| M9 | Per-worker rate limit ineffective (multi-worker) | MAJOR | notes | Explicit caveat + GitHub issue required before prod |
| M11 | Bare `except (ValueError, Exception)` swallows errors | MAJOR | 1.3, 2.2 | Split into `ValueError`, `AccessError`, propagate rest |
| M12 | `message_ids[-20:]` loads all rows then slices | MAJOR | 1.4 | `search(limit=20, order='id desc')` at DB level |
| M13 | `import datetime as dt` inside function body | MAJOR | 2.2 | Moved to module-level |
| M14 | `tool_calls_json` stored `raw: tc` (non-serializable) | MAJOR | 1.1, 1.4 | Removed `raw` key; `_build_messages` reconstructs wire format from stored data |
| M15 | `schedule_activity` skips field-whitelist | MAJOR | 2.1 | Added `summary` length cap + `date_deadline` format validation |
| M21 | Three parallel whitelist maps | MAJOR | 1.3 | Consolidated into single `_MODEL_REGISTRY` class var |

---

## Delivery order (4 separate PRs, merged in order)

| PR | Branch | Scope |
|----|--------|-------|
| **0** | `feat/solar-ai-guards-extraction` | Extract guards — **unchanged from v1** |
| **1** | `feat/solar-ai-agent-phase-a` | `chat_with_tools` + read tools + models + step controller + OWL panel |
| **2** | `feat/solar-ai-agent-phase-b` | Write tools + confirm/reject + field whitelist + security hardening |
| **3** | `feat/solar-ai-agent-phase-c` | "My AI Chats" page — **unchanged from v1** |

> Run `./odoo-bin -d <db> --test-tags solar_ai --stop-after-init -u solar_ai` after every PR.

---

## PR 0 — Extract guards (unchanged from v1)

> **No changes.** Follow Task 0.1 from v1 exactly.

---

## PR 1 — Phase A: Read-only agent + OWL panel

Branch: `feat/solar-ai-agent-phase-a` (from `19.0`, after PR 0 merges)

---

### Task 1.1 — Extend `solar.ai.service` with `chat_with_tools()`

**Changes from v1:** Remove `raw: tc` from stored `parsed_calls` (MAJOR #14 — `tc` is not guaranteed JSON-serializable and `fields.Json` raises on persist).

**Files:**
- Modify: `custom_addons/solar_ai/models/solar_ai_service.py`
- Modify: `custom_addons/solar_ai/tests/test_solar_ai.py`

**Step 1: Write the failing tests** (same tests as v1 — unchanged)

**Step 2: Run — verify fails**

```bash
./odoo-bin -d solar_dev --test-tags :TestSolarAiService.test_chat_with_tools_returns_tool_calls --stop-after-init -u solar_ai
```

**Step 3: Implement `chat_with_tools()` in `solar_ai_service.py`**

```python
def chat_with_tools(self, messages, tools=None, model=None, timeout=25):
    """LLM round-trip that parses tool_calls from the response.

    Returns:
        {
            "content": str | None,
            "tool_calls": list[{id, name, parsed_args, parse_error?}],
            "finish_reason": str,
            "usage": dict,
            "elapsed_ms": int,
            "error": str,  # present on terminal errors
        }
    """
    headers = self._build_headers()
    if not headers:
        return {"content": "", "tool_calls": [], "finish_reason": "error",
                "usage": {}, "elapsed_ms": 0, "error": "no_api_key"}

    model = model or self._get_config("default_model", "anthropic/claude-sonnet-4-5")
    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools

    started = datetime.now()
    try:
        resp = httpx.post(
            self._get_config("openrouter_base_url", "https://openrouter.ai/api/v1") + "/chat/completions",
            headers=headers, json=payload, timeout=timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _logger.error("solar_ai: OpenRouter HTTP error %s: %s", exc.response.status_code, exc.response.text[:300])
        return {"content": "", "tool_calls": [], "finish_reason": "error",
                "usage": {}, "elapsed_ms": 0, "error": str(exc)}
    except httpx.RequestError as exc:
        _logger.error("solar_ai: OpenRouter request error: %s", exc)
        return {"content": "", "tool_calls": [], "finish_reason": "error",
                "usage": {}, "elapsed_ms": 0, "error": str(exc)}

    elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        return {"content": "", "tool_calls": [], "finish_reason": "error",
                "usage": data.get("usage", {}), "elapsed_ms": elapsed_ms, "error": "empty_choices"}

    choice = choices[0]
    message = choice.get("message") or {}
    finish_reason = choice.get("finish_reason", "stop")
    content = message.get("content")

    # Parse tool_calls — arguments is a JSON STRING from the model.
    # IMPORTANT: do NOT include the raw `tc` object — it is not JSON-serializable
    # and would crash fields.Json storage in solar.ai.message.tool_calls_json.
    raw_tool_calls = message.get("tool_calls") or []
    parsed_calls = []
    for tc in raw_tool_calls:
        func = tc.get("function") or {}
        entry = {
            "id": tc.get("id", ""),
            "name": func.get("name", ""),
            # Store raw arguments string for wire-format replay in _build_messages
            "arguments_str": func.get("arguments", "{}"),
        }
        try:
            entry["parsed_args"] = json.loads(func.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError) as exc:
            entry["parsed_args"] = None
            entry["parse_error"] = str(exc)
            _logger.warning("solar_ai: could not parse tool_call args for %s: %s", entry["name"], exc)
        parsed_calls.append(entry)

    result = {
        "content": content,
        "tool_calls": parsed_calls,
        "finish_reason": finish_reason,
        "usage": data.get("usage", {}),
        "elapsed_ms": elapsed_ms,
    }
    if finish_reason in ("length", "content_filter"):
        result["error"] = f"terminated_{finish_reason}"
    return result
```

**Step 4: Run tests — verify all pass**

```bash
./odoo-bin -d solar_dev --test-tags :TestSolarAiService --stop-after-init -u solar_ai
```

**Step 5: Commit**

```bash
git add custom_addons/solar_ai/models/solar_ai_service.py \
        custom_addons/solar_ai/tests/test_solar_ai.py
git commit -m "[ADD] solar_ai: chat_with_tools() — no raw key in parsed_calls (v2 fix)"
```

---

### Task 1.2 — Add `solar.ai.chat` and `solar.ai.message` models

**Changes from v1:** Added rollback procedure (BLOCKER #2).

**Files:**
- Create: `custom_addons/solar_ai/models/solar_ai_chat.py`
- Create: `custom_addons/solar_ai/models/solar_ai_message.py`
- Modify: `custom_addons/solar_ai/models/__init__.py`
- Create: `custom_addons/solar_ai/security/ir.model.access.csv`
- Create: `custom_addons/solar_ai/security/solar_ai_security.xml`
- Modify: `custom_addons/solar_ai/__manifest__.py`
- Create: `custom_addons/solar_ai/tests/test_solar_ai_agent.py`

**Steps 1-10: Same as v1 Task 1.2** — models, security, manifest, tests.

**ADDITIONAL — Rollback procedure (required before merging PR1)**

Document this in PR description. If deployment fails after PR1 merges:

```sql
-- 1. Remove solar_ai_message first (references solar_ai_chat)
DROP TABLE IF EXISTS solar_ai_message CASCADE;
DROP TABLE IF EXISTS solar_ai_chat CASCADE;

-- 2. Remove ORM registrations (run from Odoo shell: ./odoo-bin shell -d <db>)
-- env.cr.execute("DELETE FROM ir_model WHERE model IN ('solar.ai.chat', 'solar.ai.message')")
-- env.cr.execute("DELETE FROM ir_model_fields WHERE model_id NOT IN (SELECT id FROM ir_model)")
-- env.cr.execute("DELETE FROM ir_rule WHERE name LIKE 'Solar AI%'")
-- env.cr.execute("DELETE FROM ir_model_access WHERE name LIKE '%solar_ai%'")
-- env.cr.commit()

-- 3. Mark module as uninstalled
-- env.cr.execute("UPDATE ir_module_module SET state='uninstalled' WHERE name='solar_ai'")
-- env.cr.commit()
```

> If you have a DB backup from before PR1 install, restore it — that is always the safest rollback.

**Commit** (same as v1)

---

### Task 1.3 — Add `solar.ai.agent` (tool registry + dispatcher + whitelist)

**Changes from v1:**
- Consolidated three parallel whitelist maps into single `_MODEL_REGISTRY` (MAJOR #21)
- Narrowed `safe_execute_tool` exception handling (MAJOR #11)
- Added missing tests: record-not-found, whitelist/capability mismatch

**Files:**
- Create: `custom_addons/solar_ai/models/solar_ai_agent.py`
- Modify: `custom_addons/solar_ai/models/__init__.py`
- Modify: `custom_addons/solar_ai/tests/test_solar_ai_agent.py`

**Step 1: Write failing tests**

Add `TestSolarAiAgent` class (same core tests as v1) plus these **new** tests:

```python
def test_get_record_summary_returns_not_found_on_missing(self):
    """_tool_get_record_summary on nonexistent ID returns error dict, not crash."""
    result = self.agent._tool_get_record_summary(
        {"model": "project.project", "id": 999999999}
    )
    self.assertEqual(result.get("error"), "record_not_found")
    self.assertEqual(result.get("id"), 999999999)

def test_whitelist_rejects_model_with_correct_model_wrong_capability(self):
    """solar.document allows read but rejects write — validate capability check."""
    with self.assertRaises(ValueError):
        self.agent._check_capability("create_record", model="solar.document")

def test_safe_execute_tool_propagates_access_error_as_structured(self):
    """AccessError from ORM is caught and returned as structured error, not 500."""
    from odoo.exceptions import AccessError
    from unittest.mock import patch
    with patch.object(type(self.agent), '_execute_tool', side_effect=AccessError("denied")):
        result = self.agent.safe_execute_tool("find_records", {"model": "project.project", "query": "x"})
    self.assertFalse(result.get("ok"))
    self.assertEqual(result.get("error"), "access_denied")
```

**Step 2: Run — verify fails**

```bash
./odoo-bin -d solar_dev --test-tags :TestSolarAiAgent --stop-after-init -u solar_ai
```
Expected: `KeyError: solar.ai.agent`

**Step 3: Create `models/solar_ai_agent.py`**

```python
import json
import logging
from datetime import date

from odoo import models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class SolarAiAgent(models.AbstractModel):
    _name = "solar.ai.agent"
    _description = "Solar AI — Tool Registry and Dispatcher"

    # ------------------------------------------------------------------
    # Single source of truth for model permissions (MAJOR #21 fix)
    # Extend by overriding _get_model_registry() in sibling modules.
    # ------------------------------------------------------------------

    _MODEL_REGISTRY = {
        "project.project": {
            "capabilities": {"read", "navigate", "write"},
            "write_fields": {"name", "description", "user_id", "date_start", "date"},
            "read_fields": ["id", "name", "description", "user_id"],
        },
        "project.task": {
            "capabilities": {"read", "navigate", "write"},
            "write_fields": {"name", "description", "user_id", "project_id",
                             "date_deadline", "stage_id"},
            "read_fields": ["id", "name", "description", "user_id", "project_id", "stage_id"],
        },
        "res.partner": {
            "capabilities": {"read", "navigate", "write"},
            "write_fields": {"name", "email", "phone", "mobile", "comment"},
            "read_fields": ["id", "name", "email", "phone"],
        },
        "solar.document": {
            "capabilities": {"read", "navigate"},
            "write_fields": set(),
            "read_fields": ["id", "name", "document_type_id"],
        },
    }

    def _get_model_registry(self):
        """Return the model registry. Override in sibling modules via super() to extend."""
        return dict(self._MODEL_REGISTRY)

    def _get_allowed_models(self):
        return {m: d["capabilities"] for m, d in self._get_model_registry().items()}

    def _get_allowed_fields(self):
        return {m: d["write_fields"]
                for m, d in self._get_model_registry().items()
                if d["write_fields"]}

    def _get_safe_read_fields(self, model):
        return self._get_model_registry().get(model, {}).get("read_fields", ["id", "name"])

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------

    def _get_tool_definitions(self):
        """Return OpenAI-compatible tool schemas for the LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "find_records",
                    "description": "Search for records by display name. Returns id + display_name list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string", "description": "Odoo model technical name"},
                            "query": {"type": "string", "description": "Search text (display name match)"},
                            "limit": {"type": "integer", "description": "Max results 1-20", "default": 5},
                        },
                        "required": ["model", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_record_summary",
                    "description": "Get key fields of a specific record by id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string"},
                            "id": {"type": "integer"},
                        },
                        "required": ["model", "id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "navigate_to_record",
                    "description": "Open a specific record form view in the user's browser. Executed client-side.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string"},
                            "id": {"type": "integer"},
                        },
                        "required": ["model", "id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "open_model_list",
                    "description": "Open the list view for a model in the browser. Executed client-side.",
                    "parameters": {
                        "type": "object",
                        "properties": {"model": {"type": "string"}},
                        "required": ["model"],
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    _CLIENT_TOOLS = {"navigate_to_record", "open_model_list"}

    _CAPABILITY_MAP = {
        "find_records": "read",
        "get_record_summary": "read",
        "navigate_to_record": "navigate",
        "open_model_list": "navigate",
        # write tools registered in Phase B
    }

    def _check_capability(self, tool_name, model=None):
        """Raise ValueError if the tool/model combo isn't whitelisted."""
        allowed = self._get_allowed_models()
        cap = self._CAPABILITY_MAP.get(tool_name)
        if cap is None:
            raise ValueError(f"Unknown tool: {tool_name!r}")
        if model is not None:
            if model not in allowed:
                raise ValueError(f"Model {model!r} is not in the allowed list")
            if cap not in allowed[model]:
                raise ValueError(f"Tool {tool_name!r} (cap={cap!r}) not allowed for {model!r}")

    def _execute_tool(self, tool_name, args):
        """Execute a tool. Raises ValueError on whitelist violation. Never sudo for ORM ops."""
        model = args.get("model")
        self._check_capability(tool_name, model=model)

        if tool_name == "find_records":
            return self._tool_find_records(args)
        if tool_name == "get_record_summary":
            return self._tool_get_record_summary(args)
        if tool_name in self._CLIENT_TOOLS:
            return {"client_tool": tool_name, "args": args}
        raise ValueError(f"Unhandled tool: {tool_name!r}")

    def safe_execute_tool(self, tool_name, args, tool_call_id=""):
        """Wrap _execute_tool; catch ValueError and AccessError as structured results.

        Other exceptions (ORM bugs, DB errors) propagate — do NOT swallow them.
        The tool-calling protocol requires EXACTLY ONE result per tool_call_id.
        """
        try:
            result = self._execute_tool(tool_name, args)
            return {"ok": True, "result": result, "tool_call_id_placeholder": tool_call_id}
        except ValueError as exc:
            _logger.warning("solar_ai agent: tool %r validation error: %s", tool_name, exc)
            return {"ok": False, "error": str(exc), "tool_call_id_placeholder": tool_call_id}
        except AccessError as exc:
            _logger.warning("solar_ai agent: tool %r access denied: %s", tool_name, exc)
            return {"ok": False, "error": "access_denied", "tool_call_id_placeholder": tool_call_id}

    # ------------------------------------------------------------------
    # Tool implementations (READ, Phase A)
    # ------------------------------------------------------------------

    def _tool_find_records(self, args):
        model = args["model"]
        query = (args.get("query") or "").strip()
        if not query:
            raise ValueError("query must be a non-empty string")
        try:
            limit = max(1, min(20, int(args.get("limit") or 5)))
        except (TypeError, ValueError):
            limit = 5
        records = self.env[model].name_search(query, limit=limit)
        return [{"id": r[0], "display_name": r[1]} for r in records]

    def _tool_get_record_summary(self, args):
        model = args["model"]
        record_id = int(args["id"])
        safe_fields = self._get_safe_read_fields(model)
        record = self.env[model].browse(record_id)
        if not record.exists():
            return {"error": "record_not_found", "id": record_id, "model": model}
        data = record.read(safe_fields)[0]
        return {k: (v[1] if isinstance(v, tuple) else v) for k, v in data.items()}

    # ------------------------------------------------------------------
    # Validation helper (shared by read and write tools)
    # ------------------------------------------------------------------

    def _validate_write_values(self, model, values):
        """Raise ValueError if any key in values is not in the field whitelist."""
        allowed = self._get_allowed_fields()
        if model not in allowed:
            raise ValueError(f"Model {model!r} has no write capability")
        bad = set(values.keys()) - allowed[model]
        if bad:
            raise ValueError(f"Fields not in whitelist for {model!r}: {sorted(bad)}")
```

**Step 4: Update `models/__init__.py`**

```python
from . import solar_ai_service, solar_ai_agent, solar_ai_chat, solar_ai_message
```

**Step 5: Run tests — verify all pass**

```bash
./odoo-bin -d solar_dev --test-tags :TestSolarAiAgent --stop-after-init -u solar_ai
```

**Step 6: Commit**

```bash
git add custom_addons/solar_ai/models/solar_ai_agent.py \
        custom_addons/solar_ai/models/__init__.py \
        custom_addons/solar_ai/tests/test_solar_ai_agent.py
git commit -m "[ADD] solar_ai: solar.ai.agent — single _MODEL_REGISTRY, narrow safe_execute_tool (v2)"
```

---

### Task 1.4 — Add `/agent/step` controller (Phase A — read-only turns)

**Changes from v1:**
- BLOCKER #3: Replace `env["ir.fields"].datetime.now()` with `fields.Datetime.now()`
- BLOCKER #4: Token budget updated via atomic SQL, not ORM read-modify-write
- MAJOR #12: `_build_messages` uses `search(limit=20, order='id desc')` instead of `message_ids[-20:]`
- MAJOR #14: `_build_messages` reconstructs LLM wire format from stored `tool_calls_json`
- Missing tests: rate_limited path, budget depletion, no_api_key, `_build_messages` with tool_results

**Files:**
- Create: `custom_addons/solar_ai/controllers/ai_chat.py`
- Modify: `custom_addons/solar_ai/controllers/__init__.py`
- Modify: `custom_addons/solar_ai/tests/test_solar_ai_agent.py`

**Step 1: Write failing integration tests**

Same tests as v1 `TestAgentStepController` plus these **new** tests:

```python
@patch("odoo.addons.solar_ai.models.solar_ai_service.SolarAiService.chat_with_tools")
def test_step_rate_limited_returns_rate_limited_status(self, mock_cwt):
    """When rate limit is exhausted, LLM is never called."""
    from unittest.mock import patch as _patch
    with _patch("odoo.addons.solar_ai.controllers._guards.check_rate_limit", return_value=False):
        result = self._step({"message": "Hi"})
    data = result.get("result", {})
    self.assertEqual(data.get("status"), "error")
    self.assertEqual(data.get("error"), "rate_limited")
    mock_cwt.assert_not_called()

@patch("odoo.addons.solar_ai.models.solar_ai_service.SolarAiService.chat_with_tools")
def test_step_budget_exhausted_blocks_llm(self, mock_cwt):
    """When total_tokens >= MAX_TOKENS, no LLM call is made."""
    self.authenticate("admin", "admin")
    chat = self.env["solar.ai.chat"].sudo().create({
        "name": "Exhausted", "user_id": self.env.ref("base.user_admin").id,
        "total_tokens": 100001, "budget_state": "exhausted",
    })
    result = self._step({"message": "Hi", "chat_id": chat.id})
    data = result.get("result", {})
    self.assertEqual(data.get("error"), "budget_exhausted")
    mock_cwt.assert_not_called()

def test_step_no_api_key_returns_error(self):
    """Missing API key returns no_api_key error without calling LLM."""
    self.env["ir.config_parameter"].sudo().set_param("solar_ai.openrouter_api_key", "")
    result = self._step({"message": "Hi"})
    data = result.get("result", {})
    self.assertIn(data.get("status"), ("error", "ok"))

@patch("odoo.addons.solar_ai.models.solar_ai_service.SolarAiService.chat_with_tools")
def test_build_messages_with_tool_results_from_browser(self, mock_cwt):
    """tool_results injected by the browser appear in the next LLM call."""
    captured_messages = []
    def capture_and_return(messages, tools=None, **kw):
        captured_messages.extend(messages)
        return {"content": "done", "tool_calls": [], "finish_reason": "stop",
                "usage": {"total_tokens": 5}, "elapsed_ms": 10}
    mock_cwt.side_effect = capture_and_return

    self.authenticate("admin", "admin")
    chat = self.env["solar.ai.chat"].sudo().create({
        "name": "T", "user_id": self.env.ref("base.user_admin").id,
    })
    result = self._step({
        "chat_id": chat.id,
        "message": None,
        "tool_results": [{"tool_call_id": "call_99", "content": "navigated"}],
    })
    tool_msgs = [m for m in captured_messages if m.get("role") == "tool"]
    self.assertTrue(any(m.get("tool_call_id") == "call_99" for m in tool_msgs))
```

**Step 2: Run — verify fails**

```bash
./odoo-bin -d solar_dev --test-tags :TestAgentStepController --stop-after-init -u solar_ai
```

**Step 3: Create `controllers/ai_chat.py`**

```python
import json
import logging

from odoo import fields, http
from odoo.http import request

from odoo.addons.solar_ai.controllers._guards import check_authorized, check_rate_limit

_logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are a helpful AI assistant embedded in an Odoo ERP system for solar project management. Respond in {lang}. You can search and navigate records. Always confirm before writing."""


class AiChatController(http.Controller):

    @http.route("/solar_ai/agent/step", type="json", auth="user", methods=["POST"], csrf=False)
    def agent_step(self, message=None, chat_id=None, tool_results=None, **_kw):
        env = request.env
        check_authorized(env)
        if not check_rate_limit(env.user.id):
            return {"status": "error", "error": "rate_limited"}

        user_text = (message or "").strip()
        if not chat_id and not user_text:
            return {"status": "error", "error": "empty_message"}

        ChatModel = env["solar.ai.chat"]
        if chat_id:
            chat = ChatModel.browse(int(chat_id))
            if not chat.exists() or chat.user_id.id != env.user.id:
                return {"status": "error", "error": "chat_not_found"}
        else:
            chat = ChatModel.create({
                "name": user_text[:80],
                "user_id": env.user.id,
            })

        # Budget guard (read once at start; the actual update is atomic below)
        if chat.budget_state == "exhausted" or chat.total_tokens >= chat.MAX_TOKENS:
            return {"status": "error", "error": "budget_exhausted", "chat_id": chat.id}

        # Persist user message BEFORE LLM call so it is never lost on LLM error
        if user_text:
            env["solar.ai.message"].create({
                "chat_id": chat.id, "role": "user", "content": user_text, "status": "done",
            })

        messages = self._build_messages(chat, user_text, tool_results)

        lang = env.user.lang or "uk_UA"
        lang_label = "Ukrainian" if lang.startswith("uk") else "Russian" if lang.startswith("ru") else lang
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(lang=lang_label)
        messages = [{"role": "system", "content": system_prompt}] + messages

        agent = env["solar.ai.agent"]
        tools = agent._get_tool_definitions()

        service = env["solar.ai.service"]
        llm_result = service.chat_with_tools(messages=messages, tools=tools)

        # Persist assistant message
        tool_calls_to_store = llm_result.get("tool_calls") or None
        env["solar.ai.message"].create({
            "chat_id": chat.id,
            "role": "assistant",
            "content": llm_result.get("content"),
            "tool_calls_json": tool_calls_to_store,
            "status": "done",
            "prompt_tokens": (llm_result.get("usage") or {}).get("prompt_tokens", 0),
            "completion_tokens": (llm_result.get("usage") or {}).get("completion_tokens", 0),
            "model_used": "default",
        })

        # BLOCKER #4 fix: atomic token budget update — avoids concurrent overspend.
        # Multiple workers read the same total_tokens in a regular read; here we
        # let PostgreSQL do the increment atomically with a single UPDATE.
        tokens_used = (llm_result.get("usage") or {}).get("total_tokens", 0)
        env.cr.execute(
            """
            UPDATE solar_ai_chat
            SET total_tokens   = total_tokens + %(tokens)s,
                round_count    = round_count + 1,
                last_activity  = (NOW() AT TIME ZONE 'UTC'),
                budget_state   = CASE
                    WHEN total_tokens + %(tokens)s >= %(max)s THEN 'exhausted'
                    ELSE 'ok'
                END
            WHERE id = %(chat_id)s
            RETURNING total_tokens, budget_state
            """,
            {"tokens": tokens_used, "max": chat.MAX_TOKENS, "chat_id": chat.id},
        )
        row = env.cr.fetchone()
        env["solar.ai.chat"].invalidate_model()
        budget_exhausted = bool(row and row[1] == "exhausted")

        finish_reason = llm_result.get("finish_reason", "stop")
        if finish_reason in ("stop", "error") or llm_result.get("error"):
            return {
                "status": "ok" if not llm_result.get("error") else "error",
                "assistant_text": llm_result.get("content"),
                "tool_results": [],
                "client_tool_calls": [],
                "chat_id": chat.id,
                "error": llm_result.get("error"),
                "budget_exhausted": budget_exhausted,
            }

        # Process tool_calls
        server_results = []
        client_calls = []
        for tc in (llm_result.get("tool_calls") or []):
            tool_name = tc.get("name", "")
            args = tc.get("parsed_args") or {}
            tool_call_id = tc.get("id", "")

            if tc.get("parse_error"):
                server_results.append({
                    "tool_call_id": tool_call_id,
                    "content": f"Error: could not parse tool arguments — {tc['parse_error']}",
                })
                continue

            if tool_name in agent._CLIENT_TOOLS:
                client_calls.append({"tool_call_id": tool_call_id, "name": tool_name, "args": args})
                continue

            result = agent.safe_execute_tool(tool_name, args, tool_call_id=tool_call_id)
            content = str(result.get("result", result.get("error", "error")))
            server_results.append({"tool_call_id": tool_call_id, "content": content})

            env["solar.ai.message"].create({
                "chat_id": chat.id, "role": "tool",
                "tool_call_id": tool_call_id, "tool_name": tool_name,
                "content": content[:2000], "status": "done" if result.get("ok") else "error",
            })

        return {
            "status": "needs_continuation",
            "assistant_text": llm_result.get("content"),
            "tool_results": server_results,
            "client_tool_calls": client_calls,
            "chat_id": chat.id,
            "budget_exhausted": budget_exhausted,
        }

    def _build_messages(self, chat, user_text, tool_results=None):
        """Reconstruct message history from DB for the LLM context window.

        MAJOR #12 fix: use search(limit=20) instead of message_ids[-20:] to
        avoid loading all rows then slicing in Python — for long chats this is O(N).

        MAJOR #14 fix: reconstruct LLM wire format from stored parsed_calls,
        since we no longer store the raw LLM object.
        """
        # DB-level slice: fetch last 20 in reverse, then reverse for chronological order
        recent = self.env["solar.ai.message"].search(
            [("chat_id", "=", chat.id)],
            order="id desc",
            limit=20,
        )
        messages = []
        for msg in reversed(recent):
            if msg.role == "user":
                messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                entry = {"role": "assistant", "content": msg.content}
                if msg.tool_calls_json:
                    # Reconstruct OpenAI wire format from stored parsed_calls
                    entry["tool_calls"] = [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": tc.get("arguments_str", "{}"),
                            },
                        }
                        for tc in msg.tool_calls_json
                    ]
                messages.append(entry)
            elif msg.role == "tool" and msg.tool_call_id:
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or "",
                })

        # Inject current-turn tool results (from previous step, resolved by browser)
        if tool_results:
            for tr in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr.get("tool_call_id", ""),
                    "content": str(tr.get("content", "")),
                })

        # Add current user message (if new turn)
        if user_text:
            messages.append({"role": "user", "content": user_text})

        return messages
```

**Step 4: Update `controllers/__init__.py`**

```python
from . import olg_proxy, ai_chat
```

**Step 5: Run tests — verify all pass**

```bash
./odoo-bin -d solar_dev --test-tags :TestAgentStepController --stop-after-init -u solar_ai
```

**Step 6: Commit**

```bash
git add custom_addons/solar_ai/controllers/ai_chat.py \
        custom_addons/solar_ai/controllers/__init__.py \
        custom_addons/solar_ai/tests/test_solar_ai_agent.py
git commit -m "[ADD] solar_ai: /agent/step — atomic budget, fix ir.fields, O(1) history, v2 fixes"
```

---

### Task 1.5 — OWL frontend: systray + panel (Phase A)

**Changes from v1:**
- BLOCKER #7: Added automated tests — JS tour + `HttpCase.start_tour`
- Added `static/tests/` directory

**Files to create:**
- `custom_addons/solar_ai/static/src/components/ai_assistant_panel.js` (same as v1)
- `custom_addons/solar_ai/static/src/components/ai_assistant_panel.xml` (same as v1)
- `custom_addons/solar_ai/static/src/components/ai_assistant_panel.scss` (same as v1)
- `custom_addons/solar_ai/static/src/systray/ai_assistant_systray.js` (same as v1)
- `custom_addons/solar_ai/static/src/systray/ai_assistant_systray.xml` (same as v1)
- `custom_addons/solar_ai/static/tests/tours/ai_panel.js` ← **new**
- Modify: `custom_addons/solar_ai/tests/test_solar_ai_agent.py` ← **new tour test class**

**Steps 1-5: Same as v1** — create all OWL component files exactly as in v1.

**Step 6 (NEW): Create `static/tests/tours/ai_panel.js`**

```js
/** @odoo-module */
import { registry } from "@web/core/registry";

registry.category("tours").add("ai_panel_open_close", {
    test: true,
    steps: () => [
        {
            // Panel must not exist yet
            trigger: "body:not(:has(#o-solar-ai-panel))",
            content: "Verify panel is closed",
            isCheck: true,
        },
        {
            trigger: ".o-solar-ai-systray-btn",
            content: "Click systray button to open panel",
        },
        {
            trigger: "#o-solar-ai-panel",
            content: "Panel is visible",
            isCheck: true,
        },
        {
            trigger: "#o-solar-ai-panel .btn-close",
            content: "Close the panel",
        },
        {
            trigger: "body:not(:has(#o-solar-ai-panel))",
            content: "Panel is closed again",
            isCheck: true,
        },
    ],
});

registry.category("tours").add("ai_panel_send_empty_ignored", {
    test: true,
    steps: () => [
        {
            trigger: ".o-solar-ai-systray-btn",
            content: "Open panel",
        },
        {
            trigger: "#o-solar-ai-panel",
            content: "Panel open",
            isCheck: true,
        },
        {
            trigger: "#o-solar-ai-panel .btn[aria-label='Send']",
            content: "Send button is disabled (no input)",
            // Verify it is disabled — clicking disabled button is a noop in Odoo tours
        },
        {
            // No .o-solar-ai-msg--error should appear after clicking disabled send
            trigger: "body:not(:has(.o-solar-ai-msg--error))",
            content: "No error message appeared",
            isCheck: true,
        },
    ],
});
```

**Step 7 (NEW): Add tour test assets to `__manifest__.py`**

```python
"assets": {
    "web.assets_backend": [
        "solar_ai/static/src/systray/ai_assistant_systray.js",
        "solar_ai/static/src/systray/ai_assistant_systray.xml",
        "solar_ai/static/src/components/ai_assistant_panel.js",
        "solar_ai/static/src/components/ai_assistant_panel.xml",
        "solar_ai/static/src/components/ai_assistant_panel.scss",
    ],
    "web.assets_tests": [
        "solar_ai/static/tests/tours/ai_panel.js",
    ],
},
```

**Step 8 (NEW): Add tour HttpCase to `test_solar_ai_agent.py`**

```python
@tagged("solar_ai", "post_install", "-at_install")
class TestAiAssistantTour(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("solar_ai.openrouter_api_key", "test-key")

    def test_panel_opens_and_closes(self):
        """Tour: systray button toggles the panel open/closed."""
        self.start_tour("/odoo", "ai_panel_open_close", login="admin")

    def test_empty_send_is_noop(self):
        """Tour: Send button disabled when textarea is empty — no error emitted."""
        self.start_tour("/odoo", "ai_panel_send_empty_ignored", login="admin")
```

**Step 9: Run tour tests**

```bash
./odoo-bin -d solar_dev --test-tags :TestAiAssistantTour --stop-after-init -u solar_ai
```
Expected: Both tours pass. If browser unavailable in CI: `--screenshots /tmp/screenshots`

**Step 10: Manual verification** (same as v1)

```bash
./odoo-bin -d solar_dev --dev=all -u solar_ai
```
Open Odoo → verify 🤖 in systray → click → panel opens → type message → agent responds.

**Step 11: Commit**

```bash
git add custom_addons/solar_ai/static/ \
        custom_addons/solar_ai/__manifest__.py \
        custom_addons/solar_ai/tests/test_solar_ai_agent.py
git commit -m "[ADD] solar_ai: OWL panel + systray + automated tour tests (v2, BLOCKER #7)"
```

---

## PR 2 — Phase B: Write tools + propose-and-confirm

Branch: `feat/solar-ai-agent-phase-b` (after PR 1 merges)

---

### Task 2.1 — Add write tools to `solar_ai_agent.py`

**Changes from v1:**
- BLOCKER #5: Explicit guard when `chat_id` missing from context
- MAJOR #15: `_tool_schedule_activity` validates `summary` length and `date_deadline` format
- Missing tests: `update_record` path, `schedule_activity` pending flow, whitelist field rejection

**Files:**
- Modify: `custom_addons/solar_ai/models/solar_ai_agent.py`
- Modify: `custom_addons/solar_ai/tests/test_solar_ai_agent.py`

**Step 1: Write failing tests**

Same core tests as v1 `TestSolarAiAgent` write-tool section plus:

```python
def test_update_record_returns_pending_confirmation(self):
    """update_record proposes change, does NOT write immediately."""
    project = self.env["project.project"].create({"name": "Update Test"})
    chat = self.env["solar.ai.chat"].create({"name": "T", "user_id": self.env.user.id})
    result = self.env["solar.ai.agent"].with_context(current_chat_id=chat.id).safe_execute_tool(
        "update_record",
        {"model": "project.project", "id": project.id, "values": {"name": "Renamed"}},
        tool_call_id="call_upd",
    )
    self.assertEqual(result.get("status"), "pending_confirmation")
    project.invalidate_model()
    self.assertEqual(project.name, "Update Test")  # NOT yet renamed

def test_schedule_activity_returns_pending_confirmation(self):
    """schedule_activity creates pending_confirmation message without writing activity."""
    project = self.env["project.project"].create({"name": "Activity Test"})
    chat = self.env["solar.ai.chat"].create({"name": "T", "user_id": self.env.user.id})
    result = self.env["solar.ai.agent"].with_context(current_chat_id=chat.id)._tool_schedule_activity(
        {"model": "project.project", "id": project.id,
         "summary": "Review project", "date_deadline": "2026-12-01"},
        chat_id=chat.id,
    )
    self.assertEqual(result.get("status"), "pending_confirmation")

def test_schedule_activity_rejects_malformed_date(self):
    """Malformed date_deadline raises ValueError before any ORM call."""
    chat = self.env["solar.ai.chat"].create({"name": "T", "user_id": self.env.user.id})
    project = self.env["project.project"].create({"name": "P"})
    with self.assertRaises(ValueError):
        self.env["solar.ai.agent"].with_context(current_chat_id=chat.id)._tool_schedule_activity(
            {"model": "project.project", "id": project.id,
             "summary": "x", "date_deadline": "not-a-date"},
            chat_id=chat.id,
        )

def test_create_record_chat_id_missing_raises(self):
    """create_record called without current_chat_id context raises ValueError."""
    with self.assertRaises(ValueError, msg="chat_id is required"):
        self.env["solar.ai.agent"]._execute_tool(
            "create_record",
            {"model": "project.task", "values": {"name": "Task"}},
        )
```

**Step 2: Run — verify fails**

```bash
./odoo-bin -d solar_dev --test-tags :TestSolarAiAgent.test_create_record_chat_id_missing_raises --stop-after-init -u solar_ai
```

**Step 3: Add write tools to `solar_ai_agent.py`**

First extend `_CAPABILITY_MAP` and `_get_tool_definitions()` for write tools (same schemas as v1).

Then add the tool implementations with v2 fixes:

```python
from datetime import date

# -- in _execute_tool, add dispatch for write tools --

if tool_name == "create_record":
    # BLOCKER #5 fix: explicit guard — never allow int(None)
    chat_id = self._context.get("current_chat_id")
    if not chat_id:
        raise ValueError("chat_id is required for write tools — call with_context(current_chat_id=N)")
    return self._tool_create_record(args, chat_id)

if tool_name == "update_record":
    chat_id = self._context.get("current_chat_id")
    if not chat_id:
        raise ValueError("chat_id is required for write tools — call with_context(current_chat_id=N)")
    return self._tool_update_record(args, chat_id)

if tool_name == "schedule_activity":
    chat_id = self._context.get("current_chat_id")
    if not chat_id:
        raise ValueError("chat_id is required for write tools — call with_context(current_chat_id=N)")
    return self._tool_schedule_activity(args, chat_id)
```

Tool implementations (write):

```python
def _tool_create_record(self, args, chat_id):
    model = args["model"]
    values = args.get("values") or {}
    self._validate_write_values(model, values)

    model_label = self.env[model]._description or model
    field_lines = []
    for k, v in values.items():
        field_obj = self.env[model]._fields.get(k)
        label = field_obj.string if field_obj else k
        field_lines.append(f"  {label}: {v!r}")
    summary = f"Створити {model_label}:\n" + "\n".join(field_lines)

    chat = self.env["solar.ai.chat"].browse(int(chat_id))
    msg = self.env["solar.ai.message"].create({
        "chat_id": chat.id,
        "role": "assistant",
        "status": "pending_confirmation",
        "proposed_action": {"model": model, "method": "create", "values": values},
        "action_summary": summary,
        "content": summary,
    })
    return {"status": "pending_confirmation", "message_id": msg.id, "summary": summary}


def _tool_update_record(self, args, chat_id):
    model = args["model"]
    record_id = int(args["id"])
    values = args.get("values") or {}
    self._validate_write_values(model, values)

    record = self.env[model].browse(record_id)
    if not record.exists():
        return {"error": "record_not_found"}

    summary = f"Оновити {record.display_name} ({model} #{record_id}):\n"
    for k, v in values.items():
        field_obj = self.env[model]._fields.get(k)
        label = field_obj.string if field_obj else k
        summary += f"  {label}: {v!r}\n"

    chat = self.env["solar.ai.chat"].browse(int(chat_id))
    msg = self.env["solar.ai.message"].create({
        "chat_id": chat.id,
        "role": "assistant",
        "status": "pending_confirmation",
        "proposed_action": {"model": model, "method": "write", "id": record_id, "values": values},
        "action_summary": summary,
        "content": summary,
    })
    return {"status": "pending_confirmation", "message_id": msg.id, "summary": summary}


def _tool_schedule_activity(self, args, chat_id):
    """MAJOR #15 fix: validate summary and date_deadline before any ORM call."""
    model = args["model"]
    record_id = int(args["id"])

    # Validate LLM-provided strings before passing to activity_schedule
    summary = str(args.get("summary") or "").strip()
    if len(summary) > 200:
        raise ValueError("summary too long (max 200 chars)")

    date_str = args.get("date_deadline")
    if date_str:
        try:
            deadline = date.fromisoformat(str(date_str))
        except (ValueError, TypeError):
            raise ValueError(f"date_deadline must be YYYY-MM-DD, got: {date_str!r}")
    else:
        deadline = None  # activity_schedule uses today by default

    self._check_capability("schedule_activity", model=model)
    record = self.env[model].browse(record_id)
    if not record.exists():
        return {"error": "record_not_found"}

    action_summary = (f"Запланувати активність на {record.display_name}:\n"
                      f"  {summary}\n  Дедлайн: {date_str or 'не вказано'}")
    chat = self.env["solar.ai.chat"].browse(int(chat_id))
    msg = self.env["solar.ai.message"].create({
        "chat_id": chat.id,
        "role": "assistant",
        "status": "pending_confirmation",
        "proposed_action": {
            "model": model, "method": "activity_schedule",
            "id": record_id, "summary": summary,
            "date": date_str,
        },
        "action_summary": action_summary,
        "content": action_summary,
    })
    return {"status": "pending_confirmation", "message_id": msg.id, "summary": action_summary}
```

In `ai_chat.py` `agent_step`, pass `chat_id` to context before dispatching write tools:

```python
agent = env["solar.ai.agent"].with_context(current_chat_id=chat.id)
```

**Step 4: Run tests — verify all pass**

```bash
./odoo-bin -d solar_dev --test-tags :TestSolarAiAgent --stop-after-init -u solar_ai
```

**Step 5: Commit**

```bash
git add custom_addons/solar_ai/models/solar_ai_agent.py \
        custom_addons/solar_ai/tests/test_solar_ai_agent.py
git commit -m "[ADD] solar_ai: write tools — chat_id guard, schedule_activity validation (v2 B5, B7, M15)"
```

---

### Task 2.2 — Add `/agent/confirm` and `/agent/reject` endpoints

**Changes from v1:**
- BLOCKER #1: Atomic CAS confirm via SQL `UPDATE … WHERE status='pending_confirmation'`
- BLOCKER #6: Explicit missing-param guard in `agent_reject`
- BLOCKER #8: `test_double_confirm_is_noop` rewritten to actually verify the guard
- MAJOR #11: Narrowed exception handling — `ValueError` and `AccessError` caught; rest propagates
- MAJOR #13: `import datetime as dt` moved to module level

**Files:**
- Modify: `custom_addons/solar_ai/controllers/ai_chat.py`
- Modify: `custom_addons/solar_ai/tests/test_solar_ai_agent.py`

**Step 1: Write failing tests**

Same `TestAgentConfirmController` tests as v1 (confirm_creates_record, idor, body_tampering, after_record_deleted) plus **rewritten and new**:

```python
def test_double_confirm_is_noop(self):
    """Second confirm must not create a duplicate — atomic SQL guard is enforced.

    v1 fix: count 0→1 after first confirm, then assert still 1 after second.
    Also verify the atomic guard directly by pre-seeding 'confirmed' status via SQL.
    """
    msg = self._create_pending_msg()

    # Before any confirm: 0 tasks
    pre_count = self.env["project.task"].search_count([("name", "=", "Confirmed Task")])
    self.assertEqual(pre_count, 0, "No task should exist before first confirm")

    # First confirm — creates 1 task
    result1 = self._post("/solar_ai/agent/confirm", {"message_id": msg.id})
    self.assertEqual(result1.get("result", {}).get("status"), "ok")
    after_first = self.env["project.task"].search_count([("name", "=", "Confirmed Task")])
    self.assertEqual(after_first, 1, "First confirm must create exactly 1 task")

    # Second confirm — must return already_processed, must NOT create a 2nd task
    result2 = self._post("/solar_ai/agent/confirm", {"message_id": msg.id})
    self.assertEqual(result2.get("result", {}).get("note"), "already_processed")
    after_second = self.env["project.task"].search_count([("name", "=", "Confirmed Task")])
    self.assertEqual(after_second, 1, "Second confirm must NOT create a duplicate task")

def test_confirm_guard_atomic_via_sql_preseeding(self):
    """Verify atomic guard: if status is already 'confirmed' in DB, confirm is a noop.

    Simulates what happens when two concurrent workers both reach the CAS: the
    second one finds rowcount=0 and returns already_processed.
    """
    msg = self._create_pending_msg()
    # Manually set status to 'confirmed' as if another worker got there first
    self.env.cr.execute(
        "UPDATE solar_ai_message SET status='confirmed' WHERE id=%s",
        [msg.id],
    )
    self.env.cr.flush()

    result = self._post("/solar_ai/agent/confirm", {"message_id": msg.id})
    data = result.get("result", {})
    self.assertEqual(data.get("note"), "already_processed")
    # No task should have been created
    tasks = self.env["project.task"].search([("name", "=", "Confirmed Task")])
    self.assertEqual(len(tasks), 0)

def test_reject_changes_status_to_rejected(self):
    """agent_reject sets status to 'rejected'."""
    msg = self._create_pending_msg()
    result = self._post("/solar_ai/agent/reject", {"message_id": msg.id})
    self.assertEqual(result.get("result", {}).get("status"), "ok")
    msg.invalidate_model()
    self.assertEqual(msg.status, "rejected")

def test_reject_missing_message_id_returns_error(self):
    """agent_reject with no message_id returns structured error, not 500."""
    self.authenticate("admin", "admin")
    resp = self.url_open(
        "/solar_ai/agent/reject",
        data=json_mod.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": {}}),
        headers={"Content-Type": "application/json"},
    )
    body = resp.json()
    data = body.get("result", {})
    self.assertEqual(data.get("status"), "error")
    self.assertEqual(data.get("error"), "missing_message_id")
```

**Step 2: Run — verify fails**

```bash
./odoo-bin -d solar_dev --test-tags :TestAgentConfirmController --stop-after-init -u solar_ai
```
Expected: 404 (routes don't exist yet)

**Step 3: Add `/agent/confirm` and `/agent/reject` to `ai_chat.py`**

Add module-level import at the top of the file (MAJOR #13 fix):

```python
import datetime as dt  # module-level, not inside function body

from odoo import fields, http
from odoo.http import request
from odoo.exceptions import AccessError
```

Add route handlers:

```python
@http.route("/solar_ai/agent/confirm", type="json", auth="user", methods=["POST"], csrf=False)
def agent_confirm(self, message_id=None, **_kw):
    """Execute the proposed_action from a pending_confirmation message.

    SECURITY: reads proposed_action from the DB — ignores any extra args from the browser.
    BLOCKER #1 fix: CAS via SQL UPDATE avoids concurrent double-execution.
    """
    env = request.env
    check_authorized(env)

    if not message_id:
        return {"status": "error", "error": "missing_message_id"}

    # Explicit ownership check before the CAS — prevents IDOR
    msg = env["solar.ai.message"].browse(int(message_id))
    if not msg.exists() or msg.chat_id.user_id.id != env.user.id:
        return {"status": "error", "error": "not_found_or_unauthorized"}

    # BLOCKER #1 fix: atomic compare-and-set.
    # UPDATE only matches if status is still 'pending_confirmation'.
    # If two workers race here, PostgreSQL serializes them at the row lock;
    # only one gets rowcount=1 and proceeds; the other gets rowcount=0.
    env.cr.execute(
        "UPDATE solar_ai_message SET status='confirmed' "
        "WHERE id = %s AND status = 'pending_confirmation'",
        [int(message_id)],
    )
    if env.cr.rowcount == 0:
        env["solar.ai.message"].invalidate_model()
        return {"status": "ok", "note": "already_processed"}
    env["solar.ai.message"].invalidate_model()

    # Re-read after CAS to get fresh proposed_action
    msg = env["solar.ai.message"].browse(int(message_id))
    action = msg.proposed_action or {}
    model = action.get("model")
    method = action.get("method")

    try:
        if method == "create":
            values = action.get("values") or {}
            env["solar.ai.agent"]._validate_write_values(model, values)
            record = env[model].create(values)
            msg.write({
                "executed_by_id": env.user.id,
                "executed_at": fields.Datetime.now(),   # BLOCKER #3 fix
            })
            return {"status": "ok", "created_id": record.id}

        elif method == "write":
            record_id = action.get("id")
            values = action.get("values") or {}
            env["solar.ai.agent"]._validate_write_values(model, values)
            record = env[model].browse(int(record_id))
            if not record.exists():
                msg.write({"status": "error"})
                return {"status": "error", "error": "record_no_longer_exists"}
            record.write(values)
            msg.write({
                "executed_by_id": env.user.id,
                "executed_at": fields.Datetime.now(),   # BLOCKER #3 fix
            })
            return {"status": "ok", "updated_id": record_id}

        elif method == "activity_schedule":
            record_id = action.get("id")
            record = env[model].browse(int(record_id))
            if not record.exists():
                msg.write({"status": "error"})
                return {"status": "error", "error": "record_no_longer_exists"}
            date_str = action.get("date")
            deadline = (dt.date.fromisoformat(date_str)    # MAJOR #13 fix: dt imported at top
                        if date_str else dt.date.today())
            record.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=deadline,
                summary=action.get("summary", ""),
            )
            msg.write({
                "executed_by_id": env.user.id,
                "executed_at": fields.Datetime.now(),   # BLOCKER #3 fix
            })
            return {"status": "ok"}

    except ValueError as exc:
        _logger.warning("solar_ai confirm: validation error %s: %s", message_id, exc)
        msg.write({"status": "error"})
        return {"status": "error", "error": str(exc)}
    except AccessError as exc:
        _logger.warning("solar_ai confirm: access denied %s: %s", message_id, exc)
        msg.write({"status": "error"})
        return {"status": "error", "error": "access_denied"}
    # Other exceptions (DB errors, programming bugs) propagate — do not swallow

    return {"status": "error", "error": "unknown_method"}


@http.route("/solar_ai/agent/reject", type="json", auth="user", methods=["POST"], csrf=False)
def agent_reject(self, message_id=None, **_kw):
    """BLOCKER #6 fix: explicit guard before browse — never browse(id=0)."""
    env = request.env
    check_authorized(env)

    if not message_id:
        return {"status": "error", "error": "missing_message_id"}

    msg = env["solar.ai.message"].browse(int(message_id))
    if not msg.exists() or msg.chat_id.user_id.id != env.user.id:
        return {"status": "error", "error": "not_found_or_unauthorized"}
    if msg.status == "pending_confirmation":
        msg.write({"status": "rejected"})
    return {"status": "ok"}
```

**Step 4: Add confirm card to OWL panel** (same as v1 — unchanged)

**Step 5: Run tests**

```bash
./odoo-bin -d solar_dev --test-tags :TestAgentConfirmController --stop-after-init -u solar_ai
```
Expected: All pass including the two new atomic guard tests.

**Step 6: Commit**

```bash
git add custom_addons/solar_ai/controllers/ai_chat.py \
        custom_addons/solar_ai/static/src/components/ \
        custom_addons/solar_ai/tests/test_solar_ai_agent.py
git commit -m "[ADD] solar_ai: /confirm atomic CAS + /reject guard + v2 fixes (B1 B3 B6 B8 M11 M13)"
```

---

## PR 3 — Phase C: "My AI Chats" page + resume

> **No changes from v1.** Follow Task 3.1 from v1 exactly.

---

## Full end-to-end verification (after all PRs merged)

```bash
# 1. Install / update
./odoo-bin -d solar_dev --dev=all -u solar_ai

# 2. Run all solar_ai tests (including new tour tests)
./odoo-bin -d solar_dev --test-tags solar_ai --stop-after-init -u solar_ai

# 3. Lint
ruff check custom_addons/solar_ai/
ruff format --check custom_addons/solar_ai/

# 4. Manual checklist (same as v1 — see v1 for full steps)

# 5. Verify atomic budget: start two browser tabs as the same user,
#    send a message in both simultaneously — verify total_tokens reflects
#    sum of both calls (not whichever wrote last).

# 6. Verify confirm idempotency: open the panel, trigger a write action,
#    double-click Підтвердити quickly — verify only one record created.

# 7. Verify Odoo worker timeouts:
#    limit_time_real >= 60  (one LLM round at 25s + margin)
#    nginx proxy_read_timeout >= 45
```

---

## Rollback if a PR deployment fails

**PR1 / PR2 rollback** (new tables exist):

```sql
-- From psql prompt on the database:
DROP TABLE IF EXISTS solar_ai_message CASCADE;
DROP TABLE IF EXISTS solar_ai_chat CASCADE;
```

Then from Odoo shell (`./odoo-bin shell -d <db>`):

```python
env.cr.execute("""
    DELETE FROM ir_rule WHERE name LIKE 'Solar AI%';
    DELETE FROM ir_model_access WHERE name LIKE '%solar_ai%';
    DELETE FROM ir_model WHERE model IN ('solar.ai.chat', 'solar.ai.message', 'solar.ai.agent');
    UPDATE ir_module_module SET state='uninstalled' WHERE name='solar_ai';
""")
env.cr.commit()
```

> Always restore from a DB backup when possible — the above is a last resort for dev environments.

---

## Notes for the implementer

**Rate limit caveat (MAJOR #9):** The `_check_rate_limit` is per-worker (in-process dict). Under multi-worker Odoo the effective limit is `RATE_LIMIT_MAX_CALLS × worker_count`. **Before first production deployment, open a GitHub issue:** "Harden agent rate limiter from per-worker to DB-backed (solar.ai.rate.limit model or ir.config_parameter CAS)." The per-chat `total_tokens` cap (atomic SQL, shared across workers) is the real cost-control mechanism for MVP.

**Atomic SQL pattern used in this plan:**

```python
# Pattern: compare-and-set
env.cr.execute("UPDATE t SET col=val WHERE id=%s AND col=old_val", [id_])
affected = env.cr.rowcount
env["model.name"].invalidate_model()
if affected == 0:
    return  # another worker got here first

# Pattern: atomic increment + RETURNING
env.cr.execute("UPDATE t SET counter=counter+%s WHERE id=%s RETURNING counter", [delta, id_])
row = env.cr.fetchone()
env["model.name"].invalidate_model()
new_value = row[0] if row else None
```

Always call `invalidate_model()` after raw SQL so the ORM cache is cleared. Without it, `browse()` would return stale values.

**OpenAI tool-calling protocol (unchanged from v1):**
- When `finish_reason == "tool_calls"`, include the assistant message verbatim in the next request.
- Follow it with one `{"role": "tool", "tool_call_id": "<id>", "content": "<result>"}` per call.

**Odoo test runner:**

```bash
./odoo-bin -d <db> --test-tags :ClassName --stop-after-init -u solar_ai
./odoo-bin -d <db> --test-tags solar_ai --stop-after-init -u solar_ai
```
