import datetime as dt
import logging

from markupsafe import Markup

from odoo import _lt, api, fields, models

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

_ERROR_USER_MESSAGES = {
    "no_api_key": _lt("🔌 AI-асистента ще не налаштовано. Зверніться до адміністратора."),
    "http_error": _lt("⚠️ Сервіс AI тимчасово недоступний. Спробуйте пізніше."),
    "network_error": _lt("⚠️ Сервіс AI тимчасово недоступний. Спробуйте пізніше."),
    "empty_choices": _lt("🤔 Не вдалося згенерувати відповідь. Перефразуйте запит."),
    "terminated_content_filter": _lt("🤔 Відповідь заблокована фільтром. Перефразуйте запит."),
    "terminated_length": _lt("✂️ Відповідь завелика. Звузьте запит."),
    "unknown": _lt("😕 Непередбачена помилка. Спробуйте ще раз."),
}


class Tx10AiChat(models.Model):
    _name = "tx10.ai.chat"
    _description = "TX10 AI — Conversation"
    _order = "last_activity desc"

    name = fields.Char(required=True, default="New Chat")
    user_id = fields.Many2one(
        "res.users", required=True, default=lambda s: s.env.user, readonly=True, index=True
    )
    channel_id = fields.Many2one("discuss.channel", ondelete="set null", index=True)
    message_ids = fields.One2many("tx10.ai.message", "chat_id")
    state = fields.Selection(
        [("active", "Active"), ("archived", "Archived")], default="active", required=True
    )
    last_activity = fields.Datetime(default=fields.Datetime.now)
    round_count = fields.Integer(default=0)
    total_tokens = fields.Integer(default=0)
    budget_state = fields.Selection(
        [("ok", "OK"), ("exhausted", "Exhausted")], default="ok"
    )
    pending_agent_run = fields.Boolean(default=False)

    MAX_ROUNDS = 20
    MAX_TOKENS = 100_000

    # ── Error formatting ──────────────────────────────────────────────────────

    def _format_error(self, error_code, exc_name=None):
        text = str(_ERROR_USER_MESSAGES.get(error_code, _ERROR_USER_MESSAGES["unknown"]))
        result = Markup.escape(text)
        if self.user_id.sudo().has_group("base.group_system"):
            code_part = Markup.escape(error_code)
            if exc_name:
                code_part = code_part + Markup.escape(f" ({exc_name})")
            result = result + Markup("<br/><br/>— код: ") + code_part
        return result

    # ── Cron entry point ──────────────────────────────────────────────────────

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

        if not self.channel_id:
            _logger.warning("tx10_ai: chat %s has no channel_id, skipping agent run", self.id)
            return

        bot_partner = self.env.ref("tx10_ai.partner_ai_bot", raise_if_not_found=False)
        if not bot_partner:
            _logger.warning("tx10_ai: partner_ai_bot not found, cannot run agent")
            return

        bot_member = self.env["discuss.channel.member"].sudo().search(
            [("channel_id", "=", self.channel_id.id), ("partner_id", "=", bot_partner.id)],
            limit=1,
        )

        if bot_member:
            bot_member.sudo()._notify_typing(True)
        try:
            response_text = self._do_agent_cycle()
        except Exception as exc:
            _logger.exception("tx10_ai: _do_agent_cycle failed for chat %s", self.id)
            response_text = self._format_error("unknown", exc_name=type(exc).__name__)
        finally:
            if bot_member:
                bot_member.sudo()._notify_typing(False)

        if not response_text:
            response_text = self._format_error("unknown")
        if self.channel_id:
            self.channel_id.sudo().message_post(
                author_id=bot_partner.id,
                body=response_text,
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

    # ── Agent cycle ───────────────────────────────────────────────────────────

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
            return Markup("Ліміт токенів вичерпано. Почніть нову розмову.")

        messages = self._build_messages()
        lang = self.user_id.lang or "uk_UA"
        lang_label = (
            "Ukrainian" if lang.startswith("uk")
            else "Russian" if lang.startswith("ru")
            else lang
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(lang=lang_label)}
        ] + messages

        agent = (
            self.env["tx10.ai.agent"]
            .with_context(current_chat_id=self.id)
            .with_user(self.user_id)
        )
        tools = agent._get_tool_definitions()

        service = self.env["tx10.ai.service"]
        llm_result = service.chat_with_tools(messages=messages, tools=tools)

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
                   budget_state  = CASE
                       WHEN total_tokens + %(t)s >= %(max)s THEN 'exhausted'
                       ELSE 'ok'
                   END
             WHERE id = %(id)s
            """,
            {"t": tokens_used, "max": self.MAX_TOKENS, "id": self.id},
        )
        self.invalidate_recordset()

        if llm_result.get("error"):
            return self._format_error(llm_result.get("error_code") or "unknown")
        if llm_result.get("finish_reason") == "stop":
            return Markup.escape(llm_result.get("content") or "")

        # Process tool calls — response_parts are Markup throughout to avoid XSS
        response_parts = [Markup.escape(llm_result.get("content") or "")]
        for tc in llm_result.get("tool_calls") or []:
            tool_name = tc.get("name", "")
            args = tc.get("parsed_args") or {}
            tc_id = tc.get("id", "")

            if tc.get("parse_error"):
                self.env["tx10.ai.message"].sudo().create({
                    "chat_id": self.id,
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "tool_name": tool_name,
                    "content": f"parse_error: {tc['parse_error']}",
                    "status": "error",
                })
                continue

            result = agent.safe_execute_tool(tool_name, args, tool_call_id=tc_id)
            tool_result_content = str(result.get("result", result.get("error", "error")))
            self.env["tx10.ai.message"].sudo().create({
                "chat_id": self.id,
                "role": "tool",
                "tool_call_id": tc_id,
                "tool_name": tool_name,
                "content": tool_result_content[:2000],
                "status": "done" if result.get("ok") else "error",
            })

            # Write tool → pending_confirmation
            if result.get("status") == "pending_confirmation":
                summary = (result.get("result") or {}).get("summary", "")
                response_parts.append(
                    Markup.escape(summary) + Markup("\n\nПідтвердити? Відповідайте «так» або «ні».")
                )
            # Navigate tool → HTML link (already Markup from agent)
            elif isinstance(result.get("result"), dict) and "html_link" in (
                result.get("result") or {}
            ):
                response_parts.append(Markup(" ") + result["result"]["html_link"])

        return Markup("").join(filter(None, response_parts))

    # ── Confirmation flow ─────────────────────────────────────────────────────

    def _handle_confirmation(self, pending_msg):
        last_user_msg = self.env["tx10.ai.message"].search(
            [("chat_id", "=", self.id), ("role", "=", "user")],
            order="id desc",
            limit=1,
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
                "content": (
                    f"Proposed: {pending_msg.action_summary}\n\n"
                    f"User reply: {last_user_msg.content or ''}"
                ),
            },
        ]
        result = self.env["tx10.ai.service"].chat_with_tools(
            confirm_messages, tools=CONFIRM_TOOLS
        )
        for tc in result.get("tool_calls") or []:
            if tc.get("name") == "confirm_action":
                return self._execute_confirmed_action(pending_msg)
            if tc.get("name") == "reject_action":
                return self._reject_action(pending_msg)
        return Markup("Не вдалося розпізнати відповідь. Будь ласка, відповідайте «так» або «ні».")

    def _execute_confirmed_action(self, msg):
        self.env.cr.execute(
            "UPDATE tx10_ai_message SET status='confirmed' "
            "WHERE id = %s AND status = 'pending_confirmation' "
            "AND chat_id IN (SELECT id FROM tx10_ai_chat WHERE user_id = %s)",
            [msg.id, self.user_id.id],
        )
        if self.env.cr.rowcount == 0:
            msg.invalidate_recordset()
            return Markup("Дія вже оброблена.")
        msg.invalidate_recordset()

        action = msg.proposed_action or {}
        model = action.get("model")
        method = action.get("method")
        values = action.get("values") or {}

        if method in ("create", "write"):
            self.env["tx10.ai.agent"]._validate_write_values(model, values)

        user_env = self.env(user=self.user_id)
        if method == "create":
            record = user_env[model].create(values)
            msg.write({"executed_by_id": self.user_id.id, "executed_at": fields.Datetime.now()})
            link = Markup("<a href='#' data-oe-model='%s' data-oe-id='%s'>%s</a>") % (
                model, record.id, record.display_name
            )
            return Markup("Готово! Запис створено: ") + link
        if method == "write":
            user_env[model].browse(int(action.get("id"))).write(values)
            msg.write({"executed_by_id": self.user_id.id, "executed_at": fields.Datetime.now()})
            return Markup("Готово! Запис оновлено.")
        if method == "activity_schedule":
            record = user_env[model].browse(int(action.get("id")))
            date_str = action.get("date")
            deadline = dt.date.fromisoformat(date_str) if date_str else None
            record.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=action.get("summary", ""),
                date_deadline=deadline,
            )
            msg.write({"executed_by_id": self.user_id.id, "executed_at": fields.Datetime.now()})
            return Markup("Готово! Активність запланована.")
        raise ValueError(f"Unknown method: {method!r}")

    def _reject_action(self, msg):
        self.env.cr.execute(
            "UPDATE tx10_ai_message SET status='rejected' "
            "WHERE id = %s AND status = 'pending_confirmation' "
            "AND chat_id IN (SELECT id FROM tx10_ai_chat WHERE user_id = %s)",
            [msg.id, self.user_id.id],
        )
        if self.env.cr.rowcount == 0:
            msg.invalidate_recordset()
            return Markup("Дія вже оброблена.")
        msg.invalidate_recordset()
        return Markup("Зрозумів, дію скасовано.")

    # ── Message history builder ───────────────────────────────────────────────

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
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": tc.get("arguments_str", "{}"),
                            },
                        }
                        for tc in msg.tool_calls_json
                        if tc.get("id", "") in responded_ids
                    ]
                    if paired:
                        entry["tool_calls"] = paired
                    elif not msg.content:
                        continue
                messages.append(entry)
            elif msg.role == "tool" and msg.tool_call_id:
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or "",
                })
        return messages
