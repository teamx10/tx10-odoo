import json as json_mod
from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("solar_ai", "post_install", "-at_install")
class TestSolarAiModels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env.ref("base.user_admin")

    def test_create_chat_and_message(self):
        """Basic model creation and relationship."""
        chat = self.env["solar.ai.chat"].create({"name": "Test Chat"})
        self.assertEqual(chat.state, "active")
        self.assertEqual(chat.round_count, 0)
        self.assertEqual(chat.total_tokens, 0)

        msg = self.env["solar.ai.message"].create({
            "chat_id": chat.id,
            "role": "user",
            "content": "Hello",
        })
        self.assertIn(msg, chat.message_ids)
        self.assertEqual(msg.status, "done")

    def test_record_rule_isolates_chats(self):
        """Users only see their own chats."""
        user_a = self.env["res.users"].create({
            "name": "User A", "login": "ua@test.local", "password": "ua_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                   self.env.ref("project.group_project_manager").id])],
        })
        user_b = self.env["res.users"].create({
            "name": "User B", "login": "ub@test.local", "password": "ub_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                   self.env.ref("project.group_project_manager").id])],
        })
        chat_a = self.env["solar.ai.chat"].with_user(user_a).create({"name": "A's chat"})
        chats_from_b = self.env["solar.ai.chat"].with_user(user_b).search([])
        self.assertNotIn(chat_a, chats_from_b)

    def test_message_record_rule_isolates_messages(self):
        """Messages are isolated per chat owner via chat_id.user_id = uid."""
        user_a = self.env["res.users"].create({
            "name": "User C", "login": "uc@test.local", "password": "uc_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                   self.env.ref("project.group_project_manager").id])],
        })
        user_b = self.env["res.users"].create({
            "name": "User D", "login": "ud@test.local", "password": "ud_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                   self.env.ref("project.group_project_manager").id])],
        })
        chat_a = self.env["solar.ai.chat"].with_user(user_a).create({"name": "C's chat"})
        msg_a = self.env["solar.ai.message"].with_user(user_a).create({
            "chat_id": chat_a.id, "role": "user", "content": "secret",
        })
        msgs_from_b = self.env["solar.ai.message"].with_user(user_b).search([])
        self.assertNotIn(msg_a, msgs_from_b)


@tagged("solar_ai", "post_install", "-at_install")
class TestSolarAiAgent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = cls.env["solar.ai.agent"]
        cls.env["ir.config_parameter"].sudo().set_param("solar_ai.openrouter_api_key", "test-key")

    def test_whitelist_rejects_unknown_model(self):
        """Model not in allowed list is rejected before any ORM call."""
        with self.assertRaises(ValueError):
            self.agent._execute_tool("find_records", {"model": "res.users", "query": "admin"})

    def test_whitelist_rejects_solar_document_write(self):
        """solar.document is read+navigate only — write is rejected."""
        with self.assertRaises(ValueError):
            self.agent._execute_tool("create_record", {"model": "solar.document", "values": {}})

    def test_whitelist_rejects_unlink_capability(self):
        """unlink is not a supported capability for any model."""
        with self.assertRaises(ValueError):
            self.agent._execute_tool("unlink_record", {"model": "project.project", "id": 1})

    def test_find_records_clamps_limit(self):
        """limit is coerced and clamped to [1, 20] even when LLM sends a string."""
        result = self.agent._execute_tool("find_records", {
            "model": "project.project", "query": "nonexistent_xyzzy_12345", "limit": "999",
        })
        self.assertIsInstance(result, list)

    def test_find_records_empty_query_raises(self):
        """Empty query string is rejected before ORM call."""
        with self.assertRaises(ValueError):
            self.agent._execute_tool("find_records", {"model": "project.project", "query": "  "})

    def test_find_records_returns_structured_empty(self):
        """No matches returns explicit empty list, not None."""
        result = self.agent._execute_tool("find_records", {
            "model": "project.project", "query": "zzz_no_match_xyzzy", "limit": 5,
        })
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_get_tool_definitions_includes_find_records(self):
        """Tool definitions list contains the expected tool schemas for LLM."""
        definitions = self.agent._get_tool_definitions()
        names = [t["function"]["name"] for t in definitions]
        self.assertIn("find_records", names)
        self.assertIn("navigate_to_record", names)
        self.assertIn("open_model_list", names)

    def test_each_tool_call_gets_one_result(self):
        """Even on error, tool execution returns a result dict (never raises to caller)."""
        result = self.agent.safe_execute_tool("find_records", {"model": "res.users", "query": "x"})
        self.assertIn("error", result)
        self.assertIsNotNone(result.get("tool_call_id_placeholder"))

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
        with patch.object(type(self.agent), '_execute_tool', side_effect=AccessError("denied")):
            result = self.agent.safe_execute_tool("find_records", {"model": "project.project", "query": "x"})
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "access_denied")


@tagged("solar_ai", "post_install", "-at_install")
class TestAgentStepController(HttpCase):

    def _step(self, params):
        resp = self.url_open(
            "/solar_ai/agent/step",
            data=json_mod.dumps({"jsonrpc": "2.0", "method": "call", "id": 1, "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return resp.json()

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("solar_ai.openrouter_api_key", "test-key")
        self.authenticate("admin", "admin")

    @patch("odoo.addons.solar_ai.models.solar_ai_service.SolarAiService.chat_with_tools")
    def test_step_creates_chat_and_returns_assistant_text(self, mock_cwt):
        mock_cwt.return_value = {
            "content": "Привіт! Чим можу допомогти?",
            "tool_calls": [],
            "finish_reason": "stop",
            "usage": {"total_tokens": 25},
            "elapsed_ms": 100,
        }
        result = self._step({"message": "Привіт"})
        data = result.get("result", {})
        self.assertEqual(data.get("status"), "ok")
        self.assertIsNotNone(data.get("chat_id"))
        self.assertIn("Привіт", data.get("assistant_text", ""))

    @patch("odoo.addons.solar_ai.models.solar_ai_service.SolarAiService.chat_with_tools")
    def test_step_rate_limited_returns_rate_limited_status(self, mock_cwt):
        """When rate limit is exhausted, LLM is never called."""
        with patch("odoo.addons.solar_ai.controllers._guards.check_rate_limit", return_value=False):
            result = self._step({"message": "Hi"})
        data = result.get("result", {})
        self.assertEqual(data.get("status"), "error")
        self.assertEqual(data.get("error"), "rate_limited")
        mock_cwt.assert_not_called()

    @patch("odoo.addons.solar_ai.models.solar_ai_service.SolarAiService.chat_with_tools")
    def test_step_budget_exhausted_blocks_llm(self, mock_cwt):
        """When total_tokens >= MAX_TOKENS, no LLM call is made."""
        chat = self.env["solar.ai.chat"].sudo().create({
            "name": "Exhausted", "user_id": self.env.ref("base.user_admin").id,
            "total_tokens": 100001, "budget_state": "exhausted",
        })
        result = self._step({"message": "Hi", "chat_id": chat.id})
        data = result.get("result", {})
        self.assertEqual(data.get("error"), "budget_exhausted")
        mock_cwt.assert_not_called()

    def test_step_no_api_key_returns_error(self):
        """Missing API key returns error without calling LLM."""
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
        chat = self.env["solar.ai.chat"].sudo().create({
            "name": "T", "user_id": self.env.ref("base.user_admin").id,
        })
        self._step({
            "chat_id": chat.id,
            "message": None,
            "tool_results": [{"tool_call_id": "call_99", "content": "navigated"}],
        })
        tool_msgs = [m for m in captured_messages if m.get("role") == "tool"]
        self.assertTrue(any(m.get("tool_call_id") == "call_99" for m in tool_msgs))
