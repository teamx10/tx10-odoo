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

    def test_find_records_clamps_limit(self):
        """limit is coerced and clamped to [1, 20] even for string '999'."""
        result = self.env["tx10.ai.agent"]._execute_tool(
            "find_records", {"model": "project.project", "query": "nonexistent_xyzzy", "limit": "999"}
        )
        self.assertIsInstance(result, list)

    def test_find_records_empty_query_raises(self):
        with self.assertRaises(ValueError):
            self.env["tx10.ai.agent"]._execute_tool("find_records", {"model": "project.project", "query": "  "})

    def test_find_records_returns_empty_list(self):
        result = self.env["tx10.ai.agent"]._execute_tool(
            "find_records", {"model": "project.project", "query": "zzz_no_match_xyzzy", "limit": 5}
        )
        self.assertEqual(result, [])

    def test_get_tool_definitions_has_expected_tools(self):
        names = [t["function"]["name"] for t in self.env["tx10.ai.agent"]._get_tool_definitions()]
        self.assertIn("find_records", names)
        self.assertIn("navigate_to_record", names)
        self.assertIn("open_model_list", names)

    def test_safe_execute_tool_returns_structured_on_access_error(self):
        from unittest.mock import patch
        from odoo.exceptions import AccessError
        with patch.object(type(self.env["tx10.ai.agent"]), "_execute_tool", side_effect=AccessError("denied")):
            result = self.env["tx10.ai.agent"].safe_execute_tool("find_records", {"model": "project.project", "query": "x"})
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "access_denied")

    def test_update_record_returns_pending_confirmation(self):
        project = self.env["project.project"].create({"name": "Update Test"})
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.user.id})
        result = self.env["tx10.ai.agent"].with_context(current_chat_id=chat.id).safe_execute_tool(
            "update_record", {"model": "project.project", "id": project.id, "values": {"name": "Renamed"}},
            tool_call_id="call_upd",
        )
        self.assertEqual(result.get("status"), "pending_confirmation")
        project.invalidate_model()
        self.assertEqual(project.name, "Update Test")

    def test_toctou_write_re_validates_whitelist(self):
        """_execute_confirmed_action re-validates at execution time — not just at proposal."""
        chat = self.env["tx10.ai.chat"].create({"name": "T", "user_id": self.env.user.id})
        # Create a pending_confirmation message with a non-whitelisted model.
        # Leave status as 'pending_confirmation' so the CAS in _execute_confirmed_action succeeds,
        # then _validate_write_values raises because res.country is not whitelisted.
        msg = self.env["tx10.ai.message"].create({
            "chat_id": chat.id, "role": "assistant", "status": "pending_confirmation",
            "proposed_action": {"model": "res.country", "method": "create", "values": {"name": "X"}},
            "action_summary": "Create country X",
        })
        # Execution must raise ValueError because re-validation catches the non-whitelisted model
        with self.assertRaises(ValueError):
            chat._execute_confirmed_action(msg)
