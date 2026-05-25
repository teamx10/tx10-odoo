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
