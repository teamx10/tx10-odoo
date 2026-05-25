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
