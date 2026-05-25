import datetime as dt
import logging

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request

from odoo.addons.solar_ai.controllers import _guards

_logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant embedded in an Odoo ERP system for solar project management. "
    "Respond in {lang}. You can search and navigate records. Always confirm before writing."
)


class AiChatController(http.Controller):
    @http.route(
        "/solar_ai/agent/step",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def agent_step(self, message=None, chat_id=None, tool_results=None, **_kw):
        env = request.env
        _guards.check_authorized(env)
        if not _guards.check_rate_limit(env.user.id):
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
            chat = ChatModel.create(
                {
                    "name": user_text[:80],
                    "user_id": env.user.id,
                },
            )

        # Budget guard
        if chat.budget_state == "exhausted" or chat.total_tokens >= chat.MAX_TOKENS:
            return {"status": "error", "error": "budget_exhausted", "chat_id": chat.id}

        if user_text:
            env["solar.ai.message"].create(
                {
                    "chat_id": chat.id,
                    "role": "user",
                    "content": user_text,
                    "status": "done",
                },
            )

        messages = self._build_messages(chat, user_text, tool_results)

        lang = env.user.lang or "uk_UA"
        lang_label = (
            "Ukrainian"
            if lang.startswith("uk")
            else "Russian"
            if lang.startswith("ru")
            else lang
        )
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(lang=lang_label)
        messages = [{"role": "system", "content": system_prompt}] + messages

        agent = env["solar.ai.agent"].with_context(current_chat_id=chat.id)
        tools = agent._get_tool_definitions()

        service = env["solar.ai.service"]
        llm_result = service.chat_with_tools(messages=messages, tools=tools)

        tool_calls_to_store = llm_result.get("tool_calls") or None
        env["solar.ai.message"].create(
            {
                "chat_id": chat.id,
                "role": "assistant",
                "content": llm_result.get("content"),
                "tool_calls_json": tool_calls_to_store,
                "status": "done",
                "prompt_tokens": (llm_result.get("usage") or {}).get(
                    "prompt_tokens",
                    0,
                ),
                "completion_tokens": (llm_result.get("usage") or {}).get(
                    "completion_tokens",
                    0,
                ),
                "model_used": "default",
            },
        )

        # BLOCKER #4: atomic token budget update — avoids concurrent overspend
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
        for tc in llm_result.get("tool_calls") or []:
            tool_name = tc.get("name", "")
            args = tc.get("parsed_args") or {}
            tool_call_id = tc.get("id", "")

            if tc.get("parse_error"):
                server_results.append(
                    {
                        "tool_call_id": tool_call_id,
                        "content": f"Error: could not parse tool arguments — {tc['parse_error']}",
                    },
                )
                continue

            if tool_name in agent._CLIENT_TOOLS:
                action_xmlid = agent.resolve_navigation_action(args.get("model"))
                client_calls.append(
                    {
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "args": {**args, "action_xml_id": action_xmlid},
                    },
                )
                continue

            result = agent.safe_execute_tool(tool_name, args, tool_call_id=tool_call_id)
            content = str(result.get("result", result.get("error", "error")))
            server_results.append({"tool_call_id": tool_call_id, "content": content})

            env["solar.ai.message"].create(
                {
                    "chat_id": chat.id,
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "content": content[:2000],
                    "status": "done" if result.get("ok") else "error",
                },
            )

        return {
            "status": "needs_continuation",
            "assistant_text": llm_result.get("content"),
            "tool_results": server_results,
            "client_tool_calls": client_calls,
            "chat_id": chat.id,
            "budget_exhausted": budget_exhausted,
        }

    @http.route(
        "/solar_ai/agent/confirm",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def agent_confirm(self, message_id=None, **_kw):
        env = request.env
        _guards.check_authorized(env)

        if not message_id:
            return {"status": "error", "error": "missing_message_id"}

        mid = int(message_id)

        # atomic CAS — only one confirm wins; ownership check prevents cross-user mutation
        env.cr.execute(
            "UPDATE solar_ai_message SET status='confirmed' "
            "WHERE id = %s AND status = 'pending_confirmation' "
            "AND chat_id IN (SELECT id FROM solar_ai_chat WHERE user_id = %s)",
            [mid, env.user.id],
        )
        if env.cr.rowcount == 0:
            env["solar.ai.message"].invalidate_model()
            return {"status": "ok", "note": "already_processed"}

        env["solar.ai.message"].invalidate_model()

        msg = env["solar.ai.message"].browse(mid)
        action = msg.proposed_action or {}
        try:
            result = self._execute_confirmed_action(env, action)
        except (ValueError, AccessError) as exc:
            _logger.warning("solar_ai confirm: action failed: %s", exc)
            msg.write({"status": "error"})
            return {"status": "error", "error": str(exc)}

        msg.write({"executed_by_id": env.user.id, "executed_at": fields.Datetime.now()})
        return {"status": "ok", **result}

    @http.route(
        "/solar_ai/agent/reject",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def agent_reject(self, message_id=None, **_kw):
        env = request.env
        _guards.check_authorized(env)

        # BLOCKER #6: explicit message_id guard
        if not message_id:
            return {"status": "error", "error": "missing_message_id"}

        mid = int(message_id)

        env.cr.execute(
            "UPDATE solar_ai_message SET status='rejected' "
            "WHERE id = %s AND status = 'pending_confirmation' "
            "AND chat_id IN (SELECT id FROM solar_ai_chat WHERE user_id = %s)",
            [mid, env.user.id],
        )
        env["solar.ai.message"].invalidate_model()

        if env.cr.rowcount == 0:
            return {"status": "ok", "note": "already_processed"}

        return {"status": "ok"}

    def _execute_confirmed_action(self, env, action):
        """Execute a confirmed write action from proposed_action."""
        model = action.get("model")
        method = action.get("method")
        values = action.get("values") or {}
        record_id = action.get("id")

        # Re-validate against agent whitelist at execution time (TOCTOU guard).
        # proposed_action is stored in DB and could be mutated directly via ORM.
        if method in ("create", "write"):
            env["solar.ai.agent"]._validate_write_values(model, values)

        if method == "create":
            record = env[model].create(values)
            return {"created_id": record.id}
        if method == "write":
            env[model].browse(int(record_id)).write(values)
            return {"updated_id": record_id}
        if method == "activity_schedule":
            record = env[model].browse(int(record_id))
            date_str = action.get("date")
            deadline = dt.date.fromisoformat(date_str) if date_str else None
            record.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=action.get("summary", ""),
                date_deadline=deadline,
            )
            return {"scheduled": True}
        raise ValueError(f"Unknown confirmed action method: {method!r}")

    def _build_messages(self, chat, user_text, tool_results=None):
        """Reconstruct message history from DB for the LLM context window.

        Guarantees a valid OpenAI-format sequence: every assistant tool_call must have a
        matching tool response. Calls without a response are pruned so the API never sees
        a dangling tool_call (which causes a 400 error). This covers:
          - client-tool calls (navigate_to_record / open_model_list) whose results are
            never persisted to DB but may arrive in the incoming tool_results parameter
          - already-corrupted rows in older chats (no migration required)
        """
        recent = request.env["solar.ai.message"].search(
            [("chat_id", "=", chat.id)],
            order="id desc",
            limit=20,
        )

        # Build the set of tool_call_ids that have a response available.
        responded_ids = {
            msg.tool_call_id
            for msg in recent
            if msg.role == "tool" and msg.tool_call_id
        }
        if tool_results:
            responded_ids.update(tr["tool_call_id"] for tr in tool_results if tr.get("tool_call_id"))

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
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content or "",
                    },
                )

        if tool_results:
            for tr in tool_results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.get("tool_call_id", ""),
                        "content": str(tr.get("content", "")),
                    },
                )

        if user_text:
            messages.append({"role": "user", "content": user_text})

        return messages
