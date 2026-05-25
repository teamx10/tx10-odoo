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
