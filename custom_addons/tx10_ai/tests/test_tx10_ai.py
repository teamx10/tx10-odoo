from unittest.mock import MagicMock, patch
from odoo.tests import TransactionCase, tagged


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
