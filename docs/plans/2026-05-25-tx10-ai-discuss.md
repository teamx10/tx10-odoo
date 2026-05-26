# tx10_ai — AI-бот на нативному Discuss Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Мігрувати `solar_ai` в новий модуль `tx10_ai`, де AI-асистент живе як нативний Discuss-бот: юзер пише у DM-канал, бот асинхронно відповідає через `mail.message` з кліковними `data-oe-model` посиланнями.

**Architecture:** Модуль `custom_addons/tx10_ai/` — rename «мозку» (`solar.*` → `tx10.*`) + два нових inherit-моделі (`discuss.channel`, `res.users`) для перехоплення повідомлень та bootstrap DM-каналу. Агентний цикл виконується асинхронно в `ir.cron`, щоб не блокувати запит юзера. Весь UI — нативний Discuss без кастомного JS.

**Tech Stack:** Python 3.10+, Odoo 19 ORM, `discuss.channel`, `ir.cron`, `markupsafe.Markup`, `httpx` (OpenRouter), `mail_bot` patterns.

---

## Як читати план

Кожен таск: write failing test → verify FAIL → implement → verify PASS → commit.
Не пропускай жодного кроку «verify fail/pass» — це захист від false-positive тестів.

---

## Task 1: Git — архівна гілка + feature-гілка

**Files:** git only (без змін в коді)

**Step 1: Створи архівну гілку від HEAD**

```bash
git branch custom-ai-chat
git log --oneline -3
```
Expected: гілка `custom-ai-chat` вказує на той самий commit, що і `feat/solar-ai-settings`.

**Step 2: Перейди на нову feature-гілку**

```bash
git checkout -b feat/tx10-ai-discuss
git status
```
Expected: `On branch feat/tx10-ai-discuss, nothing to commit`.

**Step 3: Commit**

```bash
git commit --allow-empty -m "[ADD] tx10_ai: init feature branch (from feat/solar-ai-settings)"
```

---

## Task 2: Scaffold модуля `tx10_ai`

**Files:**
- Create: `custom_addons/tx10_ai/__init__.py`
- Create: `custom_addons/tx10_ai/__manifest__.py`
- Create: `custom_addons/tx10_ai/models/__init__.py`
- Create: `custom_addons/tx10_ai/controllers/__init__.py`
- Create: `custom_addons/tx10_ai/tests/__init__.py`
- Create: `custom_addons/tx10_ai/data/.gitkeep`
- Create: `custom_addons/tx10_ai/security/.gitkeep`
- Create: `custom_addons/tx10_ai/views/.gitkeep`
- Create: `custom_addons/tx10_ai/static/src/components/.gitkeep`

**Step 1: Напиши `__manifest__.py`**

```python
# custom_addons/tx10_ai/__manifest__.py
{
    "name": "TX10 AI",
    "version": "19.0.1.0.0",
    "summary": "TeamX10 AI assistant as a native Discuss bot",
    "category": "Project",
    "depends": ["mail", "project", "solar_project", "base_setup", "web"],
    "external_dependencies": {"python": ["httpx"]},
    "data": [
        "security/ir.model.access.csv",
        "security/tx10_ai_security.xml",
        "data/config_params.xml",
        "data/tx10_ai_bot.xml",
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
        "views/tx10_ai_chat_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "tx10_ai/static/src/components/model_select_widget.js",
            "tx10_ai/static/src/components/model_select_widget.xml",
            "tx10_ai/static/src/components/model_select_widget.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
```

**Step 2: Напиши кореневий `__init__.py`**

```python
from . import models, controllers
```

**Step 3: Напиши `models/__init__.py`**

```python
from . import (
    tx10_ai_service,
    tx10_ai_message,
    tx10_ai_chat,
    tx10_ai_agent,
    res_config_settings,
    discuss_channel,
    res_users,
)
```

**Step 4: Напиши `controllers/__init__.py`**

```python
from . import _guards, olg_proxy, openrouter_models
```

**Step 5: Напиши `tests/__init__.py`**

```python
from . import (
    test_tx10_ai,
    test_tx10_ai_agent,
    test_tx10_ai_discuss,
    test_tx10_ai_settings,
    test_tx10_ai_models_endpoint,
)
```

**Step 6: Перевір, що skeleton модуля імпортується без помилок**

Запусти Python import check:
```bash
cd /Users/akoziar/dev/tx10/tx10-odoo
python -c "import sys; sys.path.insert(0, '.'); import odoo; odoo.modules.module.load_information_from_description_file('tx10_ai')" 2>&1 | head -20
```
Expected: або нема помилок, або лише "file not found" для файлів які ще не створено.

**Step 7: Commit scaffold**

```bash
git add custom_addons/tx10_ai/
git commit -m "[ADD] tx10_ai: module scaffold (manifest, __init__ files)"
```

---

## Task 3: Порт `tx10_ai_service.py` — LLM client

**Files:**
- Create: `custom_addons/tx10_ai/models/tx10_ai_service.py`
- Create: `custom_addons/tx10_ai/tests/test_tx10_ai.py` (частина 1: service тести)

**Step 1: Напиши failing test**

```python
# custom_addons/tx10_ai/tests/test_tx10_ai.py
from unittest.mock import MagicMock, patch
from odoo.tests import TransactionCase, tagged


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiService(TransactionCase):
    def _mock_response(self, content):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": content, "role": "assistant"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    @patch("httpx.post")
    def test_chat_returns_content(self, mock_post):
        mock_post.return_value = self._mock_response("Hello from TX10 AI!")
        self.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        result = self.env["tx10.ai.service"].chat([{"role": "user", "content": "Hi"}])
        self.assertEqual(result["content"], "Hello from TX10 AI!")

    @patch("httpx.post")
    def test_no_api_key_returns_empty(self, mock_post):
        self.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "")
        result = self.env["tx10.ai.service"].chat([{"role": "user", "content": "Hi"}])
        self.assertEqual(result["content"], "")
        mock_post.assert_not_called()
```

**Step 2: Запусти — переконайся що FAIL**

```bash
./odoo-bin -d odoo_dev --test-tags :TestTx10AiService --stop-after-init 2>&1 | grep -E "ERROR|FAIL|OK"
```
Expected: `ERROR` (модель `tx10.ai.service` не існує).

**Step 3: Скопіюй і перейменуй `solar_ai_service.py`**

```python
# custom_addons/tx10_ai/models/tx10_ai_service.py
import json
import logging
from datetime import datetime

import httpx

from odoo import models

_logger = logging.getLogger(__name__)

# ... (повний код solar_ai_service.py, але з наступними замінами:)
# class SolarAiService → class Tx10AiService
# _name = "solar.ai.service" → _name = "tx10.ai.service"
# _description = "TX10 AI LLM Service (OpenRouter)"
# self._get_config("solar_ai." → self._get_config("tx10_ai."
# "HTTP-Referer": "https://tx10.team"
# "X-Title": "TX10 Odoo AI"
# _logger prefix: "tx10_ai:" замість "solar_ai:"
```

Скопіюй весь код `solar_ai_service.py`, застосуй описані заміни (5 місць).

**Step 4: Запусти тест — переконайся що PASS**

```bash
./odoo-bin -d odoo_dev --test-tags :TestTx10AiService --stop-after-init 2>&1 | tail -10
```
Expected: `Ran 2 tests ... OK`.

**Step 5: Commit**

```bash
git add custom_addons/tx10_ai/models/tx10_ai_service.py custom_addons/tx10_ai/tests/test_tx10_ai.py
git commit -m "[ADD] tx10_ai: port LLM service model (tx10.ai.service)"
```

---

## Task 4: Порт `tx10_ai_message.py`

**Files:**
- Create: `custom_addons/tx10_ai/models/tx10_ai_message.py`

**Step 1: Напиши failing test** (в `test_tx10_ai.py`, новий клас)

```python
@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiModels(TransactionCase):
    def test_create_message(self):
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.uid})
        msg = self.env["tx10.ai.message"].create({
            "chat_id": chat.id,
            "role": "user",
            "content": "Hello",
        })
        self.assertEqual(msg.status, "done")
        self.assertIn(msg, chat.message_ids)
```

**Step 2: Verify FAIL** — `tx10.ai.message` не існує.

**Step 3: Реалізуй**

```python
# custom_addons/tx10_ai/models/tx10_ai_message.py
from odoo import fields, models


class Tx10AiMessage(models.Model):
    _name = "tx10.ai.message"
    _description = "TX10 AI — Message Turn"
    _order = "id asc"

    chat_id = fields.Many2one("tx10.ai.chat", required=True, ondelete="cascade", index=True)
    role = fields.Selection(
        [("user", "User"), ("assistant", "Assistant"), ("tool", "Tool Result")],
        required=True,
    )
    content = fields.Text()
    tool_calls_json = fields.Json()
    tool_call_id = fields.Char()
    tool_name = fields.Char()
    status = fields.Selection(
        [
            ("done", "Done"),
            ("pending_confirmation", "Pending Confirmation"),
            ("confirmed", "Confirmed"),
            ("rejected", "Rejected"),
            ("error", "Error"),
        ],
        default="done",
    )
    proposed_action = fields.Json()
    action_summary = fields.Text()
    prompt_tokens = fields.Integer(default=0)
    completion_tokens = fields.Integer(default=0)
    model_used = fields.Char()
    executed_by_id = fields.Many2one("res.users", readonly=True)
    executed_at = fields.Datetime(readonly=True)
```

**Step 4: Verify PASS.** Але зачекай — треба спершу `tx10.ai.chat`. Поверни до цього тесту після Task 5.

**Step 5: Commit**

```bash
git add custom_addons/tx10_ai/models/tx10_ai_message.py
git commit -m "[ADD] tx10_ai: port message model (tx10.ai.message)"
```

---

## Task 5: Порт `tx10_ai_chat.py` + нові поля і методи

**Files:**
- Create: `custom_addons/tx10_ai/models/tx10_ai_chat.py`

Це найважливіший файл: тут живуть `channel_id`, `pending_agent_run`, `_run_agent`, `_do_agent_cycle`, `_handle_confirmation`, `_execute_confirmed_action`, `_reject_action`, `_build_messages`.

**Step 1: Напиши failing tests** (в `test_tx10_ai.py`)

```python
@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiChat(TransactionCase):
    def test_create_chat_defaults(self):
        chat = self.env["tx10.ai.chat"].create({"name": "Test", "user_id": self.env.uid})
        self.assertEqual(chat.state, "active")
        self.assertEqual(chat.budget_state, "ok")
        self.assertFalse(chat.pending_agent_run)
        self.assertFalse(chat.channel_id)

    def test_build_messages_empty(self):
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.uid})
        msgs = chat._build_messages()
        self.assertEqual(msgs, [])

    def test_build_messages_user_then_assistant(self):
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.uid})
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "Q"})
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "assistant", "content": "A"})
        msgs = chat._build_messages()
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")
```

**Step 2: Verify FAIL**

**Step 3: Реалізуй `tx10_ai_chat.py`**

```python
# custom_addons/tx10_ai/models/tx10_ai_chat.py
import datetime as dt
import logging

from markupsafe import Markup

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant embedded in an Odoo ERP system for TeamX10. "
    "Respond in {lang}. You can search records and perform write operations with user confirmation. "
    "Always ask for confirmation before any write action."
)

CONFIRM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "confirm_action",
            "description": "User confirmed the proposed action — execute it",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_action",
            "description": "User rejected or did not clearly confirm the proposed action",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class Tx10AiChat(models.Model):
    _name = "tx10.ai.chat"
    _description = "TX10 AI — Conversation"
    _order = "last_activity desc"

    name = fields.Char(required=True, default="New Chat")
    user_id = fields.Many2one("res.users", required=True, default=lambda s: s.env.user, readonly=True, index=True)
    channel_id = fields.Many2one("discuss.channel", ondelete="set null", index=True)
    message_ids = fields.One2many("tx10.ai.message", "chat_id")
    state = fields.Selection([("active", "Active"), ("archived", "Archived")], default="active", required=True)
    last_activity = fields.Datetime(default=fields.Datetime.now)
    round_count = fields.Integer(default=0)
    total_tokens = fields.Integer(default=0)
    budget_state = fields.Selection([("ok", "OK"), ("exhausted", "Exhausted")], default="ok")
    pending_agent_run = fields.Boolean(default=False)

    MAX_ROUNDS = 20
    MAX_TOKENS = 100_000

    # ─── Cron entry point ───────────────────────────────────────────────────────

    @api.model
    def _cron_run_pending_chats(self):
        chats = self.sudo().search([("pending_agent_run", "=", True)])
        for chat in chats:
            try:
                chat.sudo()._run_agent()
            except Exception:
                _logger.exception("tx10_ai: _run_agent failed for chat %s", chat.id)

    def _run_agent(self):
        self.ensure_one()
        # CAS: atomic flag reset — prevents double-run across workers
        self.env.cr.execute(
            "UPDATE tx10_ai_chat SET pending_agent_run = FALSE "
            "WHERE id = %s AND pending_agent_run = TRUE",
            [self.id],
        )
        if self.env.cr.rowcount == 0:
            return
        self.invalidate_recordset()

        bot_partner = self.env.ref("tx10_ai.partner_ai_bot")
        bot_member = self.env["discuss.channel.member"].sudo().search(
            [("channel_id", "=", self.channel_id.id), ("partner_id", "=", bot_partner.id)],
            limit=1,
        )

        if bot_member:
            bot_member.sudo()._notify_typing(True)
        try:
            response_text = self._do_agent_cycle()
        except Exception:
            _logger.exception("tx10_ai: _do_agent_cycle failed for chat %s", self.id)
            response_text = "Вибачте, сталася помилка. Спробуйте ще раз."
        finally:
            if bot_member:
                bot_member.sudo()._notify_typing(False)

        if response_text:
            self.channel_id.sudo().message_post(
                author_id=bot_partner.id,
                body=Markup(response_text),
                message_type="comment",
                silent=True,
                subtype_xmlid="mail.mt_comment",
            )
            self.env["tx10.ai.message"].sudo().create({
                "chat_id": self.id,
                "role": "assistant",
                "content": response_text,
                "status": "done",
            })

    # ─── Agent cycle ────────────────────────────────────────────────────────────

    def _do_agent_cycle(self):
        self.ensure_one()
        pending_msg = self.env["tx10.ai.message"].search(
            [("chat_id", "=", self.id), ("status", "=", "pending_confirmation")],
            order="id desc",
            limit=1,
        )
        if pending_msg:
            return self._handle_confirmation(pending_msg)

        if self.budget_state == "exhausted":
            return "Ліміт токенів вичерпано. Почніть нову розмову."

        messages = self._build_messages()
        lang = self.user_id.lang or "uk_UA"
        lang_label = "Ukrainian" if lang.startswith("uk") else "Russian" if lang.startswith("ru") else lang
        messages = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(lang=lang_label)}] + messages

        agent = self.env["tx10.ai.agent"].with_context(current_chat_id=self.id).with_user(self.user_id)
        tools = agent._get_tool_definitions()

        service = self.env["tx10.ai.service"]
        llm_result = service.chat_with_tools(messages=messages, tools=tools)

        # Store assistant message
        tokens_used = (llm_result.get("usage") or {}).get("total_tokens", 0)
        self.env["tx10.ai.message"].sudo().create({
            "chat_id": self.id,
            "role": "assistant",
            "content": llm_result.get("content"),
            "tool_calls_json": llm_result.get("tool_calls") or None,
            "status": "done",
            "prompt_tokens": (llm_result.get("usage") or {}).get("prompt_tokens", 0),
            "completion_tokens": (llm_result.get("usage") or {}).get("completion_tokens", 0),
        })

        # Atomic budget update
        self.env.cr.execute(
            """
            UPDATE tx10_ai_chat
            SET total_tokens  = total_tokens + %(t)s,
                round_count   = round_count + 1,
                last_activity = (NOW() AT TIME ZONE 'UTC'),
                budget_state  = CASE WHEN total_tokens + %(t)s >= %(max)s THEN 'exhausted' ELSE 'ok' END
            WHERE id = %(id)s
            """,
            {"t": tokens_used, "max": self.MAX_TOKENS, "id": self.id},
        )
        self.invalidate_recordset()

        if llm_result.get("error") or llm_result.get("finish_reason") == "stop":
            return llm_result.get("content") or ""

        # Process tool calls
        response_parts = [llm_result.get("content") or ""]
        for tc in llm_result.get("tool_calls") or []:
            tool_name = tc.get("name", "")
            args = tc.get("parsed_args") or {}
            tc_id = tc.get("id", "")

            if tc.get("parse_error"):
                self.env["tx10.ai.message"].sudo().create({
                    "chat_id": self.id, "role": "tool", "tool_call_id": tc_id,
                    "tool_name": tool_name, "content": f"parse_error: {tc['parse_error']}", "status": "error",
                })
                continue

            result = agent.safe_execute_tool(tool_name, args, tool_call_id=tc_id)
            tool_result_content = str(result.get("result", result.get("error", "error")))
            self.env["tx10.ai.message"].sudo().create({
                "chat_id": self.id, "role": "tool", "tool_call_id": tc_id,
                "tool_name": tool_name, "content": tool_result_content[:2000],
                "status": "done" if result.get("ok") else "error",
            })

            # Write tool → pending_confirmation
            if result.get("status") == "pending_confirmation":
                summary = (result.get("result") or {}).get("summary", "")
                response_parts.append(f"\n{summary}\n\nПідтвердити? Відповідайте «так» або «ні».")
            # Navigate tool → HTML link
            elif isinstance(result.get("result"), dict) and "html_link" in (result.get("result") or {}):
                response_parts.append(" " + result["result"]["html_link"])

        return "".join(filter(None, response_parts))

    # ─── Confirmation flow ───────────────────────────────────────────────────────

    def _handle_confirmation(self, pending_msg):
        last_user_msg = self.env["tx10.ai.message"].search(
            [("chat_id", "=", self.id), ("role", "=", "user")], order="id desc", limit=1
        )
        confirm_messages = [
            {
                "role": "system",
                "content": (
                    "Determine if the user confirms or rejects the proposed action. "
                    "Call confirm_action to confirm, reject_action to reject or if unclear."
                ),
            },
            {
                "role": "user",
                "content": f"Proposed: {pending_msg.action_summary}\n\nUser reply: {last_user_msg.content or ''}",
            },
        ]
        result = self.env["tx10.ai.service"].chat_with_tools(confirm_messages, tools=CONFIRM_TOOLS)
        for tc in result.get("tool_calls") or []:
            if tc.get("name") == "confirm_action":
                return self._execute_confirmed_action(pending_msg)
            if tc.get("name") == "reject_action":
                return self._reject_action(pending_msg)
        return "Не вдалося розпізнати відповідь. Будь ласка, відповідайте «так» або «ні»."

    def _execute_confirmed_action(self, msg):
        self.env.cr.execute(
            "UPDATE tx10_ai_message SET status='confirmed' "
            "WHERE id = %s AND status = 'pending_confirmation' "
            "AND chat_id IN (SELECT id FROM tx10_ai_chat WHERE user_id = %s)",
            [msg.id, self.user_id.id],
        )
        if self.env.cr.rowcount == 0:
            msg.invalidate_recordset()
            return "Дія вже оброблена."
        msg.invalidate_recordset()

        action = msg.proposed_action or {}
        model = action.get("model")
        method = action.get("method")
        values = action.get("values") or {}

        if method in ("create", "write"):
            self.env["tx10.ai.agent"]._validate_write_values(model, values)

        user_env = self.env.with_user(self.user_id)
        if method == "create":
            record = user_env[model].create(values)
            msg.write({"executed_by_id": self.user_id.id, "executed_at": fields.Datetime.now()})
            link = Markup("<a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                model, record.id, record.display_name
            )
            return f"Готово! Запис створено: {link}"
        if method == "write":
            user_env[model].browse(int(action.get("id"))).write(values)
            msg.write({"executed_by_id": self.user_id.id, "executed_at": fields.Datetime.now()})
            return "Готово! Запис оновлено."
        if method == "activity_schedule":
            record = user_env[model].browse(int(action.get("id")))
            date_str = action.get("date")
            deadline = dt.date.fromisoformat(date_str) if date_str else None
            record.activity_schedule("mail.mail_activity_data_todo", summary=action.get("summary", ""), date_deadline=deadline)
            msg.write({"executed_by_id": self.user_id.id, "executed_at": fields.Datetime.now()})
            return "Готово! Активність запланована."
        raise ValueError(f"Unknown method: {method!r}")

    def _reject_action(self, msg):
        self.env.cr.execute(
            "UPDATE tx10_ai_message SET status='rejected' "
            "WHERE id = %s AND status = 'pending_confirmation' "
            "AND chat_id IN (SELECT id FROM tx10_ai_chat WHERE user_id = %s)",
            [msg.id, self.user_id.id],
        )
        msg.invalidate_recordset()
        return "Зрозумів, дію скасовано."

    # ─── Message history builder ─────────────────────────────────────────────────

    def _build_messages(self, limit=20):
        self.ensure_one()
        recent = self.env["tx10.ai.message"].search(
            [("chat_id", "=", self.id)], order="id desc", limit=limit
        )
        responded_ids = {
            msg.tool_call_id
            for msg in recent
            if msg.role == "tool" and msg.tool_call_id
        }
        messages = []
        for msg in reversed(recent):
            if msg.role == "user":
                messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                entry = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls_json:
                    paired = [
                        {"id": tc.get("id", ""), "type": "function", "function": {"name": tc.get("name", ""), "arguments": tc.get("arguments_str", "{}")}}
                        for tc in msg.tool_calls_json
                        if tc.get("id", "") in responded_ids
                    ]
                    if paired:
                        entry["tool_calls"] = paired
                    elif not msg.content:
                        continue
                messages.append(entry)
            elif msg.role == "tool" and msg.tool_call_id:
                messages.append({"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content or ""})
        return messages
```

**Step 4: Verify PASS**

```bash
./odoo-bin -d odoo_dev --test-tags :TestTx10AiChat,:TestTx10AiModels --stop-after-init 2>&1 | tail -10
```
Expected: `Ran N tests ... OK`.

**Step 5: Commit**

```bash
git add custom_addons/tx10_ai/models/tx10_ai_chat.py custom_addons/tx10_ai/models/tx10_ai_message.py
git commit -m "[ADD] tx10_ai: chat + message models with async agent cycle"
```

---

## Task 6: Порт `tx10_ai_agent.py` — HTML-навігація замість `_CLIENT_TOOLS`

**Files:**
- Create: `custom_addons/tx10_ai/models/tx10_ai_agent.py`
- Create: `custom_addons/tx10_ai/tests/test_tx10_ai_agent.py`

**Step 1: Напиши failing test**

```python
# custom_addons/tx10_ai/tests/test_tx10_ai_agent.py
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiAgent(TransactionCase):
    def test_navigate_to_record_returns_html_link(self):
        task = self.env["project.task"].create({
            "name": "Test Task",
            "project_id": self.env["project.project"].create({"name": "P"}).id,
        })
        agent = self.env["tx10.ai.agent"]
        result = agent._tool_navigate_to_record({"model": "project.task", "id": task.id})
        self.assertIn("html_link", result)
        self.assertIn("data-oe-model", result["html_link"])
        self.assertIn(str(task.id), result["html_link"])

    def test_navigate_nonexistent_record_returns_error(self):
        agent = self.env["tx10.ai.agent"]
        result = agent._tool_navigate_to_record({"model": "project.task", "id": 999999})
        self.assertIn("error", result)

    def test_whitelist_blocks_unknown_model(self):
        agent = self.env["tx10.ai.agent"]
        with self.assertRaises(ValueError):
            agent._check_capability("find_records", model="res.country")

    def test_validate_write_values_blocks_extra_fields(self):
        agent = self.env["tx10.ai.agent"]
        with self.assertRaises(ValueError):
            agent._validate_write_values("project.task", {"name": "OK", "sudo_access": True})

    def test_no_client_tools_attribute(self):
        agent = self.env["tx10.ai.agent"]
        self.assertFalse(hasattr(agent, "_CLIENT_TOOLS"))
```

**Step 2: Verify FAIL**

**Step 3: Реалізуй**

Скопіюй `solar_ai_agent.py`, застосуй такі зміни:
- `class SolarAiAgent` → `class Tx10AiAgent`
- `_name = "solar.ai.agent"` → `_name = "tx10.ai.agent"`
- `"solar.ai.chat"` → `"tx10.ai.chat"`, `"solar.ai.message"` → `"tx10.ai.message"` (в інструментах запису)
- Видали `_CLIENT_TOOLS = {...}` повністю
- В `_execute_tool`: видали блок `if tool_name in self._CLIENT_TOOLS: ...`
- Замінь реалізацію `navigate_to_record` та `open_model_list` на серверні:

```python
def _tool_navigate_to_record(self, args):
    model = args["model"]
    record_id = int(args["id"])
    record = self.env[model].browse(record_id)
    if not record.exists():
        return {"error": "record_not_found", "id": record_id}
    link = Markup("<a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
        model, record_id, record.display_name
    )
    return {"html_link": link, "status": "link_rendered"}

def _tool_open_model_list(self, args):
    model = args["model"]
    xmlid = self.resolve_navigation_action(model)
    if not xmlid:
        return {"error": "no_action_for_model", "model": model}
    action = self.env.ref(xmlid)
    link = Markup("<a href='/odoo/action-%s'>%s</a>") % (
        action.id, self.env[model]._description or model
    )
    return {"html_link": link, "status": "link_rendered"}
```

Також у `_execute_tool`:
```python
if tool_name == "navigate_to_record":
    return self._tool_navigate_to_record(args)
if tool_name == "open_model_list":
    return self._tool_open_model_list(args)
```

Видали `solar.document` з `_MODEL_REGISTRY` (або залиш, якщо `solar_project` в depends).

**Step 4: Verify PASS**

```bash
./odoo-bin -d odoo_dev --test-tags :TestTx10AiAgent --stop-after-init 2>&1 | tail -10
```

**Step 5: Commit**

```bash
git add custom_addons/tx10_ai/models/tx10_ai_agent.py custom_addons/tx10_ai/tests/test_tx10_ai_agent.py
git commit -m "[ADD] tx10_ai: agent model — HTML nav links, no _CLIENT_TOOLS"
```

---

## Task 7: Дата-файли — бот-партнер, config params, cron

**Files:**
- Create: `custom_addons/tx10_ai/data/tx10_ai_bot.xml`
- Create: `custom_addons/tx10_ai/data/config_params.xml`
- Create: `custom_addons/tx10_ai/data/ir_cron.xml`

**Step 1: Бот-партнер**

```xml
<!-- custom_addons/tx10_ai/data/tx10_ai_bot.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="partner_ai_bot" model="res.partner">
        <field name="name">TeamX10 AI</field>
        <field name="active" eval="False"/>
        <field name="email">ai@tx10.team</field>
    </record>
</odoo>
```

**Step 2: Config params (rename solar_ai.* → tx10_ai.*)**

```xml
<!-- custom_addons/tx10_ai/data/config_params.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="tx10_ai_openrouter_base_url" model="ir.config_parameter">
        <field name="key">tx10_ai.openrouter_base_url</field>
        <field name="value">https://openrouter.ai/api/v1</field>
    </record>
    <record id="tx10_ai_default_model" model="ir.config_parameter">
        <field name="key">tx10_ai.default_model</field>
        <field name="value">anthropic/claude-sonnet-4-5</field>
    </record>
    <record id="tx10_ai_vision_model" model="ir.config_parameter">
        <field name="key">tx10_ai.vision_model</field>
        <field name="value">anthropic/claude-opus-4-7</field>
    </record>
</odoo>
```

**Step 3: Cron record**

```xml
<!-- custom_addons/tx10_ai/data/ir_cron.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="ir_cron_run_agent" model="ir.cron">
        <field name="name">TX10 AI: Run pending agent cycles</field>
        <field name="model_id" ref="model_tx10_ai_chat"/>
        <field name="state">code</field>
        <field name="code">model._cron_run_pending_chats()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">minutes</field>
        <field name="numbercall">-1</field>
        <field name="active">True</field>
        <field name="priority">5</field>
    </record>
</odoo>
```

**Step 4: Напиши failing test для bot partner**

```python
# В test_tx10_ai.py, новий клас:
@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiData(TransactionCase):
    def test_bot_partner_exists(self):
        partner = self.env.ref("tx10_ai.partner_ai_bot")
        self.assertEqual(partner.name, "TeamX10 AI")
        self.assertFalse(partner.active)

    def test_config_params_loaded(self):
        base_url = self.env["ir.config_parameter"].get_param("tx10_ai.openrouter_base_url")
        self.assertEqual(base_url, "https://openrouter.ai/api/v1")

    def test_cron_exists(self):
        cron = self.env.ref("tx10_ai.ir_cron_run_agent")
        self.assertTrue(cron.active)
```

**Step 5: Install module та verify**

```bash
./odoo-bin -d odoo_dev -i tx10_ai --stop-after-init 2>&1 | tail -20
./odoo-bin -d odoo_dev --test-tags :TestTx10AiData --stop-after-init 2>&1 | tail -5
```
Expected: `Ran 3 tests ... OK`.

**Step 6: Commit**

```bash
git add custom_addons/tx10_ai/data/
git commit -m "[ADD] tx10_ai: bot partner, config params, cron record"
```

---

## Task 8: Security + Settings

**Files:**
- Create: `custom_addons/tx10_ai/security/ir.model.access.csv`
- Create: `custom_addons/tx10_ai/security/tx10_ai_security.xml`
- Create: `custom_addons/tx10_ai/models/res_config_settings.py`
- Create: `custom_addons/tx10_ai/views/res_config_settings_views.xml`
- Copy: `custom_addons/solar_ai/static/src/components/model_select_widget.*` → `custom_addons/tx10_ai/static/src/components/`
- Create: `custom_addons/tx10_ai/views/tx10_ai_chat_views.xml`
- Create: `custom_addons/tx10_ai/tests/test_tx10_ai_settings.py`

**Step 1: Failing test для settings**

```python
# custom_addons/tx10_ai/tests/test_tx10_ai_settings.py
from odoo.tests import TransactionCase, tagged


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiSettings(TransactionCase):
    def test_settings_read_write_api_key(self):
        settings = self.env["res.config.settings"].create({})
        settings.tx10_ai_openrouter_api_key = "sk-test-123"
        settings.execute()
        stored = self.env["ir.config_parameter"].get_param("tx10_ai.openrouter_api_key")
        self.assertEqual(stored, "sk-test-123")

    def test_settings_default_model(self):
        settings = self.env["res.config.settings"].create({})
        settings.tx10_ai_default_model = "openai/gpt-4o-mini"
        settings.execute()
        stored = self.env["ir.config_parameter"].get_param("tx10_ai.default_model")
        self.assertEqual(stored, "openai/gpt-4o-mini")
```

**Step 2: Verify FAIL**

**Step 3: Реалізуй security файли**

```csv
# custom_addons/tx10_ai/security/ir.model.access.csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_tx10_ai_chat_manager,tx10.ai.chat manager,model_tx10_ai_chat,project.group_project_manager,1,1,1,1
access_tx10_ai_message_manager,tx10.ai.message manager,model_tx10_ai_message,project.group_project_manager,1,1,1,1
```

```xml
<!-- custom_addons/tx10_ai/security/tx10_ai_security.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="rule_tx10_ai_chat_user" model="ir.rule">
        <field name="name">TX10 AI: own chats only</field>
        <field name="model_id" ref="model_tx10_ai_chat"/>
        <field name="domain_force">[('user_id', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('project.group_project_manager'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="True"/>
        <field name="perm_unlink" eval="True"/>
    </record>
    <record id="rule_tx10_ai_message_user" model="ir.rule">
        <field name="name">TX10 AI: own messages only</field>
        <field name="model_id" ref="model_tx10_ai_message"/>
        <field name="domain_force">[('chat_id.user_id', '=', user.id)]</field>
        <field name="groups" eval="[(4, ref('project.group_project_manager'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="True"/>
        <field name="perm_unlink" eval="True"/>
    </record>
</odoo>
```

**Step 4: Реалізуй `res_config_settings.py`**

```python
# custom_addons/tx10_ai/models/res_config_settings.py
from odoo import fields, models

_AT_REST_NOTE = (
    "Stored as plaintext in ir.config_parameter (PostgreSQL). "
    "Restrict DB and Odoo admin access in production."
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    tx10_ai_openrouter_api_key = fields.Char(
        string="OpenRouter API Key",
        config_parameter="tx10_ai.openrouter_api_key",
        help=f"Required for AI chat. Get it at openrouter.ai/keys. {_AT_REST_NOTE}",
    )
    tx10_ai_default_model = fields.Char(
        string="Default AI Model",
        config_parameter="tx10_ai.default_model",
        help="OpenRouter model ID. Examples: anthropic/claude-sonnet-4-5, openai/gpt-4o-mini.",
    )
```

**Step 5: Скопіюй model_select_widget**

```bash
cp custom_addons/solar_ai/static/src/components/model_select_widget.js custom_addons/tx10_ai/static/src/components/
cp custom_addons/solar_ai/static/src/components/model_select_widget.xml custom_addons/tx10_ai/static/src/components/
cp custom_addons/solar_ai/static/src/components/model_select_widget.scss custom_addons/tx10_ai/static/src/components/
```

Відредагуй `model_select_widget.js`: замінити URL `/solar_ai/openrouter/models` → `/tx10_ai/openrouter/models`.

**Step 6: Мінімальний views XML**

```xml
<!-- custom_addons/tx10_ai/views/tx10_ai_chat_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_tx10_ai_chat_list" model="ir.ui.view">
        <field name="name">tx10.ai.chat.list</field>
        <field name="model">tx10.ai.chat</field>
        <field name="arch" type="xml">
            <list><field name="name"/><field name="user_id"/><field name="last_activity"/><field name="budget_state"/></list>
        </field>
    </record>
    <record id="action_tx10_ai_chat" model="ir.actions.act_window">
        <field name="name">AI Conversations</field>
        <field name="res_model">tx10.ai.chat</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

**Step 7: Verify PASS**

```bash
./odoo-bin -d odoo_dev -u tx10_ai --stop-after-init 2>&1 | tail -5
./odoo-bin -d odoo_dev --test-tags :TestTx10AiSettings --stop-after-init 2>&1 | tail -5
```

**Step 8: Commit**

```bash
git add custom_addons/tx10_ai/security/ custom_addons/tx10_ai/models/res_config_settings.py custom_addons/tx10_ai/views/ custom_addons/tx10_ai/static/
git commit -m "[ADD] tx10_ai: security, settings model, views, model_select_widget"
```

---

## Task 9: `discuss_channel.py` — хук перехоплення повідомлень

**Files:**
- Create: `custom_addons/tx10_ai/models/discuss_channel.py`
- Create: `custom_addons/tx10_ai/tests/test_tx10_ai_discuss.py`

**Step 1: Напиши failing tests**

```python
# custom_addons/tx10_ai/tests/test_tx10_ai_discuss.py
from unittest.mock import patch, MagicMock

from odoo.tests import TransactionCase, tagged


def _make_llm_response(content="Hello!", tool_calls=None):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "choices": [{
            "message": {"content": content, "role": "assistant", "tool_calls": tool_calls or []},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
    }
    return mock


def _make_manager_user(env, login):
    return env["res.users"].create({
        "name": login,
        "login": f"{login}@test.local",
        "password": "pass",
        "group_ids": [(6, 0, [
            env.ref("base.group_user").id,
            env.ref("project.group_project_manager").id,
        ])],
    })


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiDiscussHook(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        cls.user = _make_manager_user(cls.env, "hook_user")
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

    def _create_dm_channel(self):
        return self.env["discuss.channel"]._get_or_create_chat(
            [self.bot_partner.id, self.user.partner_id.id]
        )

    def _get_or_create_chat(self, channel):
        chat = self.env["tx10.ai.chat"].search([("channel_id", "=", channel.id)], limit=1)
        if not chat:
            chat = self.env["tx10.ai.chat"].create({
                "name": "DM with bot",
                "user_id": self.user.id,
                "channel_id": channel.id,
            })
        return chat

    def test_hook_skips_bot_author(self):
        channel = self._create_dm_channel()
        self._get_or_create_chat(channel)
        msg_count_before = self.env["tx10.ai.message"].search_count([])
        channel.sudo().message_post(
            author_id=self.bot_partner.id,
            body="I am the bot",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        # No tx10.ai.message created for bot-authored messages
        self.assertEqual(self.env["tx10.ai.message"].search_count([]), msg_count_before)

    def test_hook_creates_user_message_and_sets_pending(self):
        channel = self._create_dm_channel()
        chat = self._get_or_create_chat(channel)
        channel.with_user(self.user).message_post(
            body="Знайди задачі проекту X",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        msgs = self.env["tx10.ai.message"].search([("chat_id", "=", chat.id), ("role", "=", "user")])
        self.assertTrue(msgs, "Hook must create a tx10.ai.message with role='user'")
        chat.invalidate_recordset()
        self.assertTrue(chat.pending_agent_run)

    def test_hook_ignores_channel_without_bot(self):
        other_channel = self.env["discuss.channel"].create({"name": "No bot channel"})
        msg_count_before = self.env["tx10.ai.message"].search_count([])
        other_channel.with_user(self.user).message_post(body="Hi", message_type="comment", subtype_xmlid="mail.mt_comment")
        self.assertEqual(self.env["tx10.ai.message"].search_count([]), msg_count_before)


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiCronAgent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        cls.user = _make_manager_user(cls.env, "cron_user")
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

    def _setup_dm_chat(self):
        channel = self.env["discuss.channel"]._get_or_create_chat(
            [self.bot_partner.id, self.user.partner_id.id]
        )
        chat = self.env["tx10.ai.chat"].create({
            "name": "DM",
            "user_id": self.user.id,
            "channel_id": channel.id,
            "pending_agent_run": True,
        })
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "Hello bot"})
        return chat, channel

    @patch("httpx.post")
    def test_cron_posts_bot_reply(self, mock_post):
        mock_post.return_value = _make_llm_response("Привіт! Як можу допомогти?")
        chat, channel = self._setup_dm_chat()
        msgs_before = channel.message_ids.filtered(lambda m: m.author_id == self.bot_partner)
        self.env["tx10.ai.chat"]._cron_run_pending_chats()
        chat.invalidate_recordset()
        self.assertFalse(chat.pending_agent_run)
        msgs_after = channel.message_ids.filtered(lambda m: m.author_id == self.bot_partner)
        self.assertGreater(len(msgs_after), len(msgs_before), "Bot must post a reply to the channel")

    @patch("httpx.post")
    def test_cron_clears_pending_flag(self, mock_post):
        mock_post.return_value = _make_llm_response("OK")
        chat, _ = self._setup_dm_chat()
        self.env["tx10.ai.chat"]._cron_run_pending_chats()
        chat.invalidate_recordset()
        self.assertFalse(chat.pending_agent_run)


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiNlConfirm(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        cls.user = _make_manager_user(cls.env, "confirm_user")
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

    def _make_confirm_tool_response(self, tool_name):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{"id": "tc1", "function": {"name": tool_name, "arguments": "{}"}}],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }
        return mock

    @patch("httpx.post")
    def test_nl_confirm_yes_executes_action(self, mock_post):
        mock_post.return_value = self._make_confirm_tool_response("confirm_action")
        project = self.env["project.project"].with_user(self.user).create({"name": "Test Project NL"})
        channel = self.env["discuss.channel"]._get_or_create_chat([self.bot_partner.id, self.user.partner_id.id])
        chat = self.env["tx10.ai.chat"].create({
            "name": "DM",
            "user_id": self.user.id,
            "channel_id": channel.id,
            "pending_agent_run": True,
        })
        pending_msg = self.env["tx10.ai.message"].create({
            "chat_id": chat.id,
            "role": "assistant",
            "status": "pending_confirmation",
            "proposed_action": {"model": "project.task", "method": "create", "values": {"name": "New Task NL", "project_id": project.id}},
            "action_summary": "Створити задачу New Task NL",
        })
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "так"})

        chat._do_agent_cycle()
        pending_msg.invalidate_recordset()
        self.assertEqual(pending_msg.status, "confirmed")
        task = self.env["project.task"].search([("name", "=", "New Task NL")])
        self.assertTrue(task, "Task must be created after NL confirm")

    @patch("httpx.post")
    def test_nl_confirm_no_rejects_action(self, mock_post):
        mock_post.return_value = self._make_confirm_tool_response("reject_action")
        channel = self.env["discuss.channel"]._get_or_create_chat([self.bot_partner.id, self.user.partner_id.id])
        chat = self.env["tx10.ai.chat"].create({
            "name": "DM", "user_id": self.user.id, "channel_id": channel.id,
        })
        pending_msg = self.env["tx10.ai.message"].create({
            "chat_id": chat.id, "role": "assistant", "status": "pending_confirmation",
            "proposed_action": {"model": "project.task", "method": "create", "values": {"name": "X"}},
            "action_summary": "Створити X",
        })
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "ні"})
        chat._do_agent_cycle()
        pending_msg.invalidate_recordset()
        self.assertEqual(pending_msg.status, "rejected")
```

**Step 2: Verify FAIL** — `discuss_channel._message_post_after_hook` ще не перевизначено.

**Step 3: Реалізуй `discuss_channel.py`**

```python
# custom_addons/tx10_ai/models/discuss_channel.py
import logging
import re

from odoo import models

_logger = logging.getLogger(__name__)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html_body):
    return _HTML_TAG_RE.sub("", html_body or "").strip()


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _message_post_after_hook(self, message, msg_vals):
        bot_partner = self.env.ref("tx10_ai.partner_ai_bot", raise_if_not_found=False)
        if not bot_partner:
            return super()._message_post_after_hook(message, msg_vals)

        # Anti-loop: skip bot-authored messages
        if msg_vals.get("author_id") == bot_partner.id:
            return super()._message_post_after_hook(message, msg_vals)

        # Skip non-comment messages (automated, system, etc.)
        if msg_vals.get("message_type") not in ("comment", "email"):
            return super()._message_post_after_hook(message, msg_vals)

        # Only act on channels where bot is a member
        bot_member = self.env["discuss.channel.member"].search(
            [("channel_id", "=", self.id), ("partner_id", "=", bot_partner.id)],
            limit=1,
        )
        if not bot_member:
            return super()._message_post_after_hook(message, msg_vals)

        # Find linked tx10.ai.chat
        chat = self.env["tx10.ai.chat"].search([("channel_id", "=", self.id)], limit=1)
        if not chat:
            _logger.debug("tx10_ai: no tx10.ai.chat linked to channel %s, skipping", self.id)
            return super()._message_post_after_hook(message, msg_vals)

        # Identify the sending user from author_id (partner_id)
        author_partner_id = msg_vals.get("author_id")
        user = self.env["res.users"].search([("partner_id", "=", author_partner_id)], limit=1)
        if not user:
            return super()._message_post_after_hook(message, msg_vals)

        content = _strip_html(msg_vals.get("body") or "")
        if not content:
            return super()._message_post_after_hook(message, msg_vals)

        self.env["tx10.ai.message"].sudo().create({
            "chat_id": chat.id,
            "role": "user",
            "content": content,
            "status": "done",
        })

        chat.sudo().write({"pending_agent_run": True})
        self.env.ref("tx10_ai.ir_cron_run_agent").sudo()._trigger()

        return super()._message_post_after_hook(message, msg_vals)
```

**Step 4: Verify PASS**

```bash
./odoo-bin -d odoo_dev --test-tags :TestTx10AiDiscussHook,:TestTx10AiCronAgent --stop-after-init 2>&1 | tail -10
```
Expected: `Ran 5+ tests ... OK`.

**Step 5: Verify NL confirm tests**

```bash
./odoo-bin -d odoo_dev --test-tags :TestTx10AiNlConfirm --stop-after-init 2>&1 | tail -10
```

**Step 6: Commit**

```bash
git add custom_addons/tx10_ai/models/discuss_channel.py custom_addons/tx10_ai/tests/test_tx10_ai_discuss.py
git commit -m "[ADD] tx10_ai: discuss_channel hook, cron agent cycle, NL confirm flow"
```

---

## Task 10: `res_users.py` — bootstrap DM-канал

**Files:**
- Create: `custom_addons/tx10_ai/models/res_users.py`

**Step 1: Напиши failing tests** (додай до `test_tx10_ai_discuss.py`)

```python
@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiBootstrap(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

    def test_bootstrap_creates_dm_channel(self):
        user = _make_manager_user(self.env, "bootstrap_user")
        user.sudo().write({"tx10_ai_state": "not_initialized"})
        user.sudo()._on_webclient_bootstrap()
        channel = self.env["discuss.channel"].search([
            ("channel_type", "=", "chat"),
            ("channel_member_ids.partner_id", "=", self.bot_partner.id),
            ("channel_member_ids.partner_id", "=", user.partner_id.id),
        ])
        self.assertTrue(channel, "Bootstrap must create a DM channel with the bot")
        chat = self.env["tx10.ai.chat"].search([("channel_id", "=", channel.id)])
        self.assertTrue(chat, "Bootstrap must link a tx10.ai.chat to the channel")
        self.assertEqual(chat.user_id, user)

    def test_bootstrap_no_duplicate_on_second_call(self):
        user = _make_manager_user(self.env, "bootstrap_user2")
        user.sudo()._on_webclient_bootstrap()
        user.sudo()._on_webclient_bootstrap()
        chats = self.env["tx10.ai.chat"].search([("user_id", "=", user.id)])
        self.assertEqual(len(chats), 1, "Second bootstrap must not create duplicate chat")
```

**Step 2: Verify FAIL**

**Step 3: Реалізуй `res_users.py`**

```python
# custom_addons/tx10_ai/models/res_users.py
from markupsafe import Markup

from odoo import fields, models, _


class ResUsers(models.Model):
    _inherit = "res.users"

    tx10_ai_state = fields.Selection(
        [("not_initialized", "Not initialized"), ("initialized", "Initialized")],
        string="TX10 AI Status",
        readonly=True,
        required=False,
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["tx10_ai_state"]

    def _on_webclient_bootstrap(self):
        super()._on_webclient_bootstrap()
        if self._is_internal() and self.tx10_ai_state in (False, "not_initialized"):
            self.sudo()._init_tx10_ai_chat()

    def _init_tx10_ai_chat(self):
        self.ensure_one()
        bot_partner = self.env.ref("tx10_ai.partner_ai_bot", raise_if_not_found=False)
        if not bot_partner:
            return

        # Check for existing chat to avoid duplicates
        existing = self.env["tx10.ai.chat"].sudo().search([("user_id", "=", self.id)], limit=1)
        if existing:
            self.sudo().tx10_ai_state = "initialized"
            return

        channel = self.env["discuss.channel"]._get_or_create_chat(
            [bot_partner.id, self.partner_id.id]
        )
        self.env["tx10.ai.chat"].sudo().create({
            "name": f"TX10 AI — {self.name}",
            "user_id": self.id,
            "channel_id": channel.id,
        })

        welcome_msg = Markup("%s<br/>%s") % (
            _("Hi! I'm the TeamX10 AI assistant."),
            _("Ask me to find tasks, projects, contacts, or to create and update records."),
        )
        channel.sudo().message_post(
            author_id=bot_partner.id,
            body=welcome_msg,
            message_type="comment",
            silent=True,
            subtype_xmlid="mail.mt_comment",
        )
        self.sudo().tx10_ai_state = "initialized"
```

**Step 4: Verify PASS**

```bash
./odoo-bin -d odoo_dev --test-tags :TestTx10AiBootstrap --stop-after-init 2>&1 | tail -10
```

**Step 5: Commit**

```bash
git add custom_addons/tx10_ai/models/res_users.py
git commit -m "[ADD] tx10_ai: res_users bootstrap — auto-create DM channel with bot"
```

---

## Task 11: Порт контролерів (olg_proxy, openrouter_models, _guards)

**Files:**
- Create: `custom_addons/tx10_ai/controllers/_guards.py`
- Create: `custom_addons/tx10_ai/controllers/olg_proxy.py`
- Create: `custom_addons/tx10_ai/controllers/openrouter_models.py`
- Create: `custom_addons/tx10_ai/tests/test_tx10_ai_models_endpoint.py`

**Step 1: Напиши failing test**

```python
# custom_addons/tx10_ai/tests/test_tx10_ai_models_endpoint.py
from unittest.mock import MagicMock, patch
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.tx10_ai.controllers._guards import check_authorized, check_rate_limit, RATE_LIMIT_MAX_CALLS


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiGuards(TransactionCase):
    def test_admin_always_authorized(self):
        check_authorized(self.env)  # admin — must not raise

    def test_rate_limit_allows_under_limit(self):
        self.assertTrue(check_rate_limit(99999))

    def test_rate_limit_blocks_over_limit(self):
        from odoo.addons.tx10_ai.controllers._guards import _rate_limit_state
        _rate_limit_state[99998] = [__import__("time").monotonic()] * RATE_LIMIT_MAX_CALLS
        self.assertFalse(check_rate_limit(99998))
```

**Step 2: Verify FAIL** — `tx10_ai.controllers._guards` не існує.

**Step 3: Скопіюй і перейменуй `_guards.py`**

```python
# Скопіюй solar_ai/controllers/_guards.py → tx10_ai/controllers/_guards.py
# Заміни:
# "Solar AI:" → "TX10 AI:" (у повідомленнях AccessError та логах)
# "project manager group" — без змін (той самий group)
```

**Step 4: Скопіюй `olg_proxy.py`**

```python
# Замінити:
# /solar_ai/olg/ → /tx10_ai/olg/
# solar_ai.service → tx10_ai.service  (у request.env["..."])
# _logger prefix: "tx10_ai:"
# import path: from odoo.addons.tx10_ai.controllers._guards import ...
```

**Step 5: Скопіюй `openrouter_models.py`**

```python
# Замінити:
# _CACHE_KEY = "tx10_ai.models_cache"
# _CACHE_TS_KEY = "tx10_ai.models_cache_ts"
# route: /solar_ai/openrouter/models → /tx10_ai/openrouter/models
```

**Step 6: Verify PASS**

```bash
./odoo-bin -d odoo_dev --test-tags :TestTx10AiGuards --stop-after-init 2>&1 | tail -5
```

**Step 7: Commit**

```bash
git add custom_addons/tx10_ai/controllers/
git commit -m "[ADD] tx10_ai: port controllers (_guards, olg_proxy, openrouter_models)"
```

---

## Task 12: Migrate existing tests + full test run

**Files:**
- Complete: `custom_addons/tx10_ai/tests/test_tx10_ai.py` (rate limit, olg proxy tests)
- Complete: `custom_addons/tx10_ai/tests/test_tx10_ai_agent.py` (whitelist, IDOR, TOCTOU, budget)

**Step 1: Перенеси тести з `test_solar_ai.py` → `test_tx10_ai.py`**

Відкрий `custom_addons/solar_ai/tests/test_solar_ai.py`. Додай наступні тести в `test_tx10_ai.py`:
- `TestTx10AiRateLimit` — port `TestSolarAiRateLimit` (заміни всі `solar_ai.*` → `tx10_ai.*`, `solar.ai.service` → `tx10.ai.service`)
- `TestTx10AiOlgProxy` (HttpCase) — port HTTP route tests, update route path `/solar_ai/olg/` → `/tx10_ai/olg/`

**Step 2: Перенеси тести з `test_solar_ai_agent.py`**

Відкрий `custom_addons/solar_ai/tests/test_solar_ai_agent.py`. Перенеси в `test_tx10_ai_agent.py`:
- IDOR test (cross-user chat access)
- TOCTOU re-validation test
- Budget CAS test
- `_build_messages` dangling tool_calls pruning test
- Capability/whitelist tests

Ключові заміни:
```
solar.ai.chat → tx10.ai.chat
solar.ai.message → tx10.ai.message
solar.ai.agent → tx10.ai.agent
solar_ai_chat (SQL table) → tx10_ai_chat
solar_ai_message (SQL table) → tx10_ai_message
```

**Step 3: Запусти всі tx10_ai тести**

```bash
./odoo-bin -d odoo_dev --test-tags tx10_ai --stop-after-init 2>&1 | tail -20
```
Expected: `Ran N tests ... OK` (має бути >= 30 тестів).

**Step 4: Commit**

```bash
git add custom_addons/tx10_ai/tests/
git commit -m "[ADD] tx10_ai: migrate all tests from solar_ai + new Discuss integration tests"
```

---

## Task 13: Верифікація — install + E2E smoke

**Step 1: Fresh install**

```bash
./odoo-bin -d odoo_test_tx10ai -i tx10_ai --stop-after-init 2>&1 | grep -E "ERROR|WARNING|Successfully" | tail -20
```
Expected: `Successfully installed tx10_ai`, нуль помилок в tail.

**Step 2: Full test run**

```bash
./odoo-bin -d odoo_test_tx10ai --test-tags tx10_ai --stop-after-init 2>&1 | tail -5
```
Expected: `OK` без FAIL.

**Step 3: Перевір відсутність `solar_ai` залежностей у `tx10_ai`**

```bash
grep -r "solar_ai\|solar\.ai\." custom_addons/tx10_ai/ --include="*.py" --include="*.xml" --include="*.js"
```
Expected: **нуль результатів** (тільки якщо `solar.document` залишений у `_MODEL_REGISTRY` — це ок, якщо `solar_project` в depends).

**Step 4: gitnexus detect changes**

```bash
npx gitnexus detect-changes 2>&1 | tail -20
```
Перевір, що змінені символи відповідають очікуваним (тільки `tx10_ai`).

**Step 5: Commit фінальний**

```bash
git add -p  # перевір що нема зайвого
git commit -m "[ADD] tx10_ai: complete AI Discuss bot module"
```

---

## Task 14: Impl doc + docs/plans

**Step 1: Збережи implementation log**

```bash
cat > docs/plans/2026-05-25-tx10-ai-discuss-IMPLEMENTED.md << 'EOF'
# tx10_ai Implementation Log

**Date:** 2026-05-25
**Branch:** feat/tx10-ai-discuss
**PR:** → develop

## Delivered
- Module `custom_addons/tx10_ai/` — 7 model files, 3 controller files, 5 test files
- `tx10.ai.chat`, `tx10.ai.message`, `tx10.ai.service`, `tx10.ai.agent` — brain ported
- `discuss.channel._message_post_after_hook` — captures user DM messages
- `res.users._on_webclient_bootstrap` — auto DM channel init
- Async `ir.cron` agent cycle with CAS pending flag
- NL confirm/reject via dedicated LLM tools
- HTML `data-oe-model/data-oe-id` links (zero custom JS)
- Removed: `controllers/ai_chat.py`, all custom OWL components, systray

## Key patterns
- Anti-loop guard: skip if `author_id == bot_partner.id`
- Typing indicator: `discuss.channel.member._notify_typing()`
- Cron CAS: `UPDATE tx10_ai_chat SET pending_agent_run=FALSE WHERE id=X AND pending_agent_run=TRUE`
- Tool execution under `env.with_user(chat.user_id)` — AI cannot exceed user's ACL

## Deviations from plan
- (fill in during implementation)
EOF
```

**Step 2: Commit**

```bash
git add docs/plans/
git commit -m "[ADD] tx10_ai: implementation log + plan docs"
```

---

## Task 15: PR

**Step 1: Push та відкрий PR**

```bash
git push origin feat/tx10-ai-discuss
gh pr create \
  --title "feat: tx10_ai — AI assistant as native Discuss bot" \
  --base develop \
  --body "$(cat docs/plans/2026-05-25-tx10-ai-discuss-IMPLEMENTED.md)"
```

---

## Verification Checklist

- [ ] `./odoo-bin -d X -i tx10_ai --stop-after-init` → нуль ERROR
- [ ] `--test-tags tx10_ai` → OK (≥30 тестів)
- [ ] Новий юзер → `_on_webclient_bootstrap` → DM-канал «TeamX10 AI» в Discuss
- [ ] Написати боту → через ≤1 хв отримати відповідь + кліковна посилання
- [ ] Задати на write → підтвердження → «так» → запис створено → «ні» → не створено
- [ ] `gitnexus detect-changes` → без несподіваних символів
- [ ] `grep -r "solar_ai" custom_addons/tx10_ai/` → нуль

---

## Key File Map

```
custom_addons/tx10_ai/
├── __manifest__.py               depends: mail, project, solar_project, base_setup, web
├── models/
│   ├── tx10_ai_service.py        tx10.ai.service — OpenRouter LLM client
│   ├── tx10_ai_message.py        tx10.ai.message — conversation turns
│   ├── tx10_ai_chat.py           tx10.ai.chat — main model: cron loop, confirm, build_messages
│   ├── tx10_ai_agent.py          tx10.ai.agent — tool registry (HTML nav, no _CLIENT_TOOLS)
│   ├── res_config_settings.py    tx10_ai.* config params
│   ├── discuss_channel.py        _message_post_after_hook — intercept user DM
│   └── res_users.py              _on_webclient_bootstrap — auto-create DM + welcome msg
├── controllers/
│   ├── _guards.py                check_authorized, check_rate_limit
│   ├── olg_proxy.py              /tx10_ai/olg/* — html_editor AI proxy
│   └── openrouter_models.py      /tx10_ai/openrouter/models — model list cache
├── data/
│   ├── tx10_ai_bot.xml           res.partner "TeamX10 AI" (active=False)
│   ├── config_params.xml         tx10_ai.openrouter_base_url / default_model / vision_model
│   └── ir_cron.xml               ir.cron — runs _cron_run_pending_chats()
├── security/
│   ├── ir.model.access.csv
│   └── tx10_ai_security.xml      record rules: own chats/messages only
└── tests/
    ├── test_tx10_ai.py            service, config, rate limit, olg proxy
    ├── test_tx10_ai_agent.py      whitelist, IDOR, TOCTOU, budget, nav HTML
    ├── test_tx10_ai_discuss.py    hook, cron, NL confirm, bootstrap
    ├── test_tx10_ai_settings.py   settings save/read
    └── test_tx10_ai_models_endpoint.py  openrouter models cache
```

## Pattern References

| Потреба | Файл для копіювання |
|---------|---------------------|
| `_message_post_after_hook` pattern | `addons/mail_bot/models/discuss_channel.py` |
| `_on_webclient_bootstrap` + `_get_or_create_chat` | `addons/mail_bot/models/res_users.py` |
| `_notify_typing` | `addons/mail/models/discuss/discuss_channel_member.py:341` |
| `_trigger()` cron fire-ASAP | `addons/mail/models/mail_push.py:71` |
| `_get_or_create_chat` | `addons/mail/models/discuss/discuss_channel.py:1319` |
| `data-oe-model` HTML links | `odoo/models.py:848` (`_get_html_link`) |
