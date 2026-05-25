import json as _json
from unittest.mock import MagicMock, patch

from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiService(TransactionCase):

    def _mock_response(self, content):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": content, "role": "assistant"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
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

    @patch("httpx.post")
    def test_chat_with_tools_parses_tool_calls(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "tc1",
                        "function": {"name": "find_records", "arguments": '{"model":"project.task","query":"test"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        self.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        result = self.env["tx10.ai.service"].chat_with_tools(
            [{"role": "user", "content": "find tasks"}],
            tools=[{"type": "function", "function": {"name": "find_records", "parameters": {}}}],
        )
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["name"], "find_records")
        self.assertEqual(result["tool_calls"][0]["parsed_args"], {"model": "project.task", "query": "test"})

    @patch("httpx.post")
    def test_chat_with_tools_handles_malformed_json_args(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "x", "function": {"name": "bad", "arguments": "INVALID_JSON{"}}]}, "finish_reason": "tool_calls"}],
            "usage": {},
        }
        self.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        result = self.env["tx10.ai.service"].chat_with_tools(
            messages=[{"role": "user", "content": "hi"}], tools=[]
        )
        self.assertIsNone(result["tool_calls"][0].get("parsed_args"))
        self.assertIn("parse_error", result["tool_calls"][0])

    @patch("httpx.post")
    def test_chat_returns_error_on_empty_choices(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {"choices": [], "usage": {}}
        self.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        result = self.env["tx10.ai.service"].chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result.get("error"), "empty_choices")
        self.assertEqual(result["content"], "")

    @patch("httpx.post")
    def test_chat_with_tools_handles_finish_reason_length(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "cut off..."}, "finish_reason": "length"}],
            "usage": {},
        }
        self.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        result = self.env["tx10.ai.service"].chat_with_tools(
            messages=[{"role": "user", "content": "hi"}], tools=[]
        )
        self.assertEqual(result["finish_reason"], "length")
        self.assertIn("error", result)


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiModels(TransactionCase):

    def test_create_message(self):
        # tx10.ai.chat must exist first as FK parent
        chat = self.env["tx10.ai.chat"].create({
            "name": "Test Chat",
            "user_id": self.env.uid,
        })
        msg = self.env["tx10.ai.message"].create({
            "chat_id": chat.id,
            "role": "user",
            "content": "Hello TX10 AI",
        })
        self.assertEqual(msg.status, "done")
        self.assertEqual(msg.role, "user")
        self.assertIn(msg, chat.message_ids)

    def test_record_rule_isolates_chats(self):
        """IDOR: user B cannot see user A's chats."""
        user_a = self.env["res.users"].create({
            "name": "User A", "login": "ua@test.local", "password": "ua_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("project.group_project_manager").id])],
        })
        user_b = self.env["res.users"].create({
            "name": "User B", "login": "ub@test.local", "password": "ub_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("project.group_project_manager").id])],
        })
        chat_a = self.env["tx10.ai.chat"].with_user(user_a).create({"name": "A's chat"})
        chats_from_b = self.env["tx10.ai.chat"].with_user(user_b).search([])
        self.assertNotIn(chat_a, chats_from_b)

    def test_message_record_rule_isolates_messages(self):
        """IDOR: messages are isolated by chat owner."""
        user_c = self.env["res.users"].create({
            "name": "User C", "login": "uc@test.local", "password": "uc_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("project.group_project_manager").id])],
        })
        user_d = self.env["res.users"].create({
            "name": "User D", "login": "ud@test.local", "password": "ud_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("project.group_project_manager").id])],
        })
        chat_c = self.env["tx10.ai.chat"].with_user(user_c).create({"name": "C's chat"})
        msg_c = self.env["tx10.ai.message"].with_user(user_c).create({"chat_id": chat_c.id, "role": "user", "content": "secret"})
        msgs_from_d = self.env["tx10.ai.message"].with_user(user_d).search([])
        self.assertNotIn(msg_c, msgs_from_d)


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiChat(TransactionCase):

    def test_create_chat_defaults(self):
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.uid})
        self.assertEqual(chat.state, "active")
        self.assertEqual(chat.budget_state, "ok")
        self.assertFalse(chat.pending_agent_run)
        self.assertFalse(chat.channel_id)

    def test_build_messages_empty(self):
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.uid})
        self.assertEqual(chat._build_messages(), [])

    def test_build_messages_user_then_assistant(self):
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.uid})
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "Q"})
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "assistant", "content": "A"})
        msgs = chat._build_messages()
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

    def test_reject_action_sets_status(self):
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.uid})
        pending = self.env["tx10.ai.message"].create({
            "chat_id": chat.id,
            "role": "assistant",
            "status": "pending_confirmation",
            "proposed_action": {"model": "project.task", "method": "create", "values": {"name": "X"}},
            "action_summary": "Створити задачу X",
        })
        chat._reject_action(pending)
        pending.invalidate_recordset()
        self.assertEqual(pending.status, "rejected")

    def test_budget_exhausted_returns_message(self):
        chat = self.env["tx10.ai.chat"].create({
            "name": "T", "user_id": self.env.uid, "budget_state": "exhausted"
        })
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "hi"})
        result = chat._do_agent_cycle()
        self.assertIn("вичерпано", result.lower())

    def test_build_messages_prunes_dangling_tool_calls(self):
        """_build_messages must omit assistant tool_calls that have no matching tool response."""
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.uid})
        # assistant message with tool_calls but NO matching tool response
        self.env["tx10.ai.message"].create({
            "chat_id": chat.id, "role": "user", "content": "Q",
        })
        self.env["tx10.ai.message"].create({
            "chat_id": chat.id, "role": "assistant", "content": None,
            "tool_calls_json": [{"id": "orphan_tc", "name": "find_records", "arguments_str": "{}"}],
        })
        msgs = chat._build_messages()
        # The dangling assistant message must be skipped (no tool result for orphan_tc)
        for m in msgs:
            self.assertNotIn("tool_calls", m, "Dangling tool_call must be pruned from history")

    def test_cas_prevents_double_run(self):
        """CAS: second _run_agent call on same chat is a no-op (rowcount==0)."""
        chat = self.env["tx10.ai.chat"].create({
            "name": "CAS Test", "user_id": self.env.uid, "pending_agent_run": True
        })
        # Simulate: DB already flipped to FALSE by first worker
        self.env.cr.execute(
            "UPDATE tx10_ai_chat SET pending_agent_run = FALSE WHERE id = %s", [chat.id]
        )
        chat.invalidate_recordset()
        # Second worker tries _run_agent — should return silently (no crash)
        try:
            chat._run_agent()
        except Exception as e:
            self.fail(f"_run_agent raised on already-processed CAS: {e}")
        # State unchanged (still false), no error
        self.assertFalse(chat.pending_agent_run)


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


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiOlgProxy(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("tx10_ai.openrouter_api_key", "test-key")
        self.authenticate("admin", "admin")

    @patch("httpx.post")
    def test_olg_chat_route_returns_success(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "AI response", "role": "assistant"}}],
            "usage": {},
        }
        resp = self.url_open(
            "/tx10_ai/olg/api/olg/1/chat",
            data=_json.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": {"prompt": "Translate this", "conversation_history": []}}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        result = resp.json()
        self.assertEqual(result.get("result", {}).get("status"), "success")

    def test_olg_chat_rejects_non_manager_user(self):
        """Non-PM user gets AccessError via JSON-RPC error envelope."""
        self.env["res.users"].create({
            "name": "Plain User", "login": "plain@test.local", "password": "plain_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.authenticate("plain@test.local", "plain_pass")
        resp = self.url_open(
            "/tx10_ai/olg/api/olg/1/chat",
            data=_json.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": {"prompt": "Hi", "conversation_history": []}}),
            headers={"Content-Type": "application/json"},
        )
        self.assertIn("error", resp.json())

    def test_rate_limit_blocks_after_threshold(self):
        """Per-user sliding window denies after RATE_LIMIT_MAX_CALLS."""
        from odoo.addons.tx10_ai.controllers._guards import (
            RATE_LIMIT_MAX_CALLS,
            _rate_limit_state,
            check_rate_limit,
        )
        synthetic_id = -42
        _rate_limit_state.pop(synthetic_id, None)
        for _ in range(RATE_LIMIT_MAX_CALLS):
            self.assertTrue(check_rate_limit(synthetic_id))
        self.assertFalse(check_rate_limit(synthetic_id))
        _rate_limit_state.pop(synthetic_id, None)
