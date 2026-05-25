from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSolarAiConfigSettings(TransactionCase):
    """Verify res.config.settings ↔ ir.config_parameter binding for Solar AI."""

    # --- ORM binding (happy path) ---

    def test_api_key_write_via_settings(self):
        settings = self.env["res.config.settings"].create(
            {"solar_ai_openrouter_api_key": "sk-test-key"},
        )
        settings.execute()
        val = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "solar_ai.openrouter_api_key",
            )
        )
        self.assertEqual(val, "sk-test-key")

    def test_default_model_write_via_settings(self):
        settings = self.env["res.config.settings"].create(
            {"solar_ai_default_model": "anthropic/claude-3.5-haiku"},
        )
        settings.execute()
        val = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "solar_ai.default_model",
            )
        )
        self.assertEqual(val, "anthropic/claude-3.5-haiku")

    def test_api_key_read_via_default_get(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "solar_ai.openrouter_api_key",
            "sk-existing-key",
        )
        defaults = self.env["res.config.settings"].default_get(
            ["solar_ai_openrouter_api_key"],
        )
        self.assertEqual(defaults.get("solar_ai_openrouter_api_key"), "sk-existing-key")

    def test_default_model_read_via_default_get(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "solar_ai.default_model",
            "openai/gpt-4o",
        )
        defaults = self.env["res.config.settings"].default_get(
            ["solar_ai_default_model"],
        )
        self.assertEqual(defaults.get("solar_ai_default_model"), "openai/gpt-4o")

    # --- Edge case: empty key (finding #6) ---

    def test_empty_api_key_service_returns_no_headers(self):
        """Empty key saved via Settings must not produce auth headers (finding #6)."""
        settings = self.env["res.config.settings"].create(
            {"solar_ai_openrouter_api_key": ""},
        )
        settings.execute()
        service = self.env["solar.ai.service"]
        self.assertIsNone(
            service._build_headers(),
            "Empty API key must not produce auth headers — _build_headers must return None",
        )

    # --- Service read-path integration (finding #7) ---

    def test_service_reads_config_after_settings_execute(self):
        """_get_config must return updated values immediately after settings.execute() (finding #7)."""
        settings = self.env["res.config.settings"].create(
            {
                "solar_ai_openrouter_api_key": "sk-roundtrip",
                "solar_ai_default_model": "openai/gpt-4o-mini",
            },
        )
        settings.execute()
        service = self.env["solar.ai.service"]
        self.assertEqual(service._get_config("openrouter_api_key"), "sk-roundtrip")
        self.assertEqual(service._get_config("default_model"), "openai/gpt-4o-mini")

    # --- Empty-credential degradation paths end-to-end (review MAJOR) ---

    def test_chat_without_api_key_short_circuits_before_http(self):
        """chat() with no key returns empty content via the no-key guard, before any HTTP call.

        This intentionally exercises only the guard (service lines 59-63): no key means
        no network call regardless of model. It does NOT cover the live HTTP path — that
        belongs in an HttpCase with a mocked OpenRouter endpoint.
        """
        self.env["ir.config_parameter"].sudo().set_param(
            "solar_ai.openrouter_api_key",
            "",
        )
        service = self.env["solar.ai.service"]
        result = service.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result.get("content"), "")

    def test_chat_with_tools_without_api_key_returns_no_api_key_error(self):
        """chat_with_tools() with no key returns structured no_api_key error, no tool calls."""
        self.env["ir.config_parameter"].sudo().set_param(
            "solar_ai.openrouter_api_key",
            "",
        )
        service = self.env["solar.ai.service"]
        result = service.chat_with_tools([{"role": "user", "content": "hi"}])
        self.assertEqual(result.get("error"), "no_api_key")
        self.assertEqual(result.get("tool_calls"), [])

    def test_classify_document_without_api_key_returns_unknown(self):
        """classify_document_text() with no key must degrade to unknown, not raise.

        chat() returns {"content": ""} with no key; json.loads("") raises JSONDecodeError
        which classify_document_text catches and maps to the unknown fallback.
        """
        self.env["ir.config_parameter"].sudo().set_param(
            "solar_ai.openrouter_api_key",
            "",
        )
        service = self.env["solar.ai.service"]
        result = service.classify_document_text("some document text")
        self.assertEqual(result, {"document_type_code": "unknown", "confidence": 0.0})

    def test_default_model_fallback_when_param_absent(self):
        """When solar_ai.default_model is absent, service falls back to the hardcoded default."""
        param = self.env["ir.config_parameter"].sudo()
        param.search([("key", "=", "solar_ai.default_model")]).unlink()
        service = self.env["solar.ai.service"]
        self.assertEqual(
            service._get_config("default_model", "anthropic/claude-sonnet-4-5"),
            "anthropic/claude-sonnet-4-5",
        )

    def test_empty_default_model_falls_back_to_hardcoded_default(self):
        """A blank default_model saved via Settings must not send model='' to OpenRouter.

        ir.config_parameter keeps an empty string (it is not deleted), so the service must
        treat a blank value the same as absent and fall back to the hardcoded default model.
        """
        settings = self.env["res.config.settings"].create(
            {"solar_ai_default_model": ""},
        )
        settings.execute()
        service = self.env["solar.ai.service"]
        self.assertEqual(
            service._resolve_model(None),
            "anthropic/claude-sonnet-4-5",
        )


@tagged("post_install", "-at_install")
class TestBuildMessages(TransactionCase):
    """Unit tests for AiChatController._build_messages dangling tool_call pruning (MAJOR #6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chat = cls.env["solar.ai.chat"].create({"user_id": cls.env.user.id})

    def _build(self, user_text="Next turn", tool_results=None):
        from odoo.addons.solar_ai.controllers.ai_chat import (  # noqa: PLC0415
            AiChatController,
        )

        ctrl = AiChatController()
        with patch("odoo.addons.solar_ai.controllers.ai_chat.request") as mock_req:
            mock_req.env = self.env
            return ctrl._build_messages(self.chat, user_text, tool_results)

    def test_dangling_tool_call_is_skipped(self):
        """Empty assistant msg whose tool_call has no response is dropped from LLM context."""
        self.env["solar.ai.message"].create([
            {"chat_id": self.chat.id, "role": "user", "content": "Hello"},
            {
                "chat_id": self.chat.id,
                "role": "assistant",
                "content": "",
                "tool_calls_json": [{"id": "tc_dangling", "name": "find_records", "arguments_str": "{}"}],
            },
        ])
        messages = self._build()
        for msg in messages:
            self.assertFalse(
                msg.get("role") == "assistant" and "tool_calls" in msg,
                "Dangling tool_call must not appear in LLM context",
            )

    def test_matched_tool_call_is_included(self):
        """Assistant tool_call with a matching tool response is preserved in LLM context."""
        self.env["solar.ai.message"].create([
            {"chat_id": self.chat.id, "role": "user", "content": "Find tasks"},
            {
                "chat_id": self.chat.id,
                "role": "assistant",
                "content": "",
                "tool_calls_json": [{"id": "tc_matched", "name": "find_records", "arguments_str": "{}"}],
            },
            {
                "chat_id": self.chat.id,
                "role": "tool",
                "tool_call_id": "tc_matched",
                "content": '[{"id": 1, "display_name": "Task A"}]',
            },
        ])
        messages = self._build()
        assistant_msgs = [m for m in messages if m.get("role") == "assistant" and "tool_calls" in m]
        self.assertTrue(assistant_msgs, "Matched tool_call must appear in LLM context")
        self.assertEqual(assistant_msgs[0]["tool_calls"][0]["id"], "tc_matched")


@tagged("post_install", "-at_install")
class TestResolveNavigationAction(TransactionCase):
    """Unit tests for SolarAiAgent.resolve_navigation_action (MAJOR #9)."""

    def test_invalid_xmlid_returns_none(self):
        """Returns None when the stored action xmlid is absent from the DB."""
        agent = self.env["solar.ai.agent"]
        bad_registry = {
            "project.project": {
                "capabilities": {"navigate"},
                "write_fields": set(),
                "read_fields": [],
                "action": "solar_ai.xmlid_that_will_never_exist_abc123",
            },
        }
        with patch.object(type(agent), "_MODEL_REGISTRY", bad_registry):
            result = agent.resolve_navigation_action("project.project")
        self.assertIsNone(result, "Must return None when action xmlid is not found in DB")

    def test_unknown_model_returns_none(self):
        """Returns None for a model not present in _MODEL_REGISTRY."""
        result = self.env["solar.ai.agent"].resolve_navigation_action("nonexistent.model")
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestSolarAiSettingsView(TransactionCase):
    """Guard: Solar AI fields must appear in the rendered settings form (xpath silent-fail guard, finding #5)."""

    def test_settings_view_renders_solar_ai_fields(self):
        """get_views merges all inherited views — if xpath mismatches, our block is absent."""
        views = self.env["res.config.settings"].get_views([[False, "form"]])
        arch = views["views"]["form"]["arch"]
        self.assertIn(
            "solar_ai_openrouter_api_key",
            arch,
            "solar_ai_openrouter_api_key missing from rendered settings form — "
            "check //app[@name='project'] xpath in res_config_settings_views.xml",
        )
        self.assertIn(
            "solar_ai_default_model",
            arch,
            "solar_ai_default_model missing from rendered settings form",
        )
