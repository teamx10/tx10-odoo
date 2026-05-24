from odoo import fields, models

_AT_REST_NOTE = (
    "Stored as plaintext in ir.config_parameter (PostgreSQL). "
    "Readable by any user with 'Technical > System Parameters' access or direct DB access. "
    "Restrict DB and Odoo admin access in production."
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    solar_ai_openrouter_api_key = fields.Char(
        string="OpenRouter API Key",
        config_parameter="solar_ai.openrouter_api_key",
        help=f"Required for AI chat and document classification. Get it at openrouter.ai/keys. {_AT_REST_NOTE}",
    )
    solar_ai_default_model = fields.Char(
        string="Default Model",
        config_parameter="solar_ai.default_model",
        help=(
            "OpenRouter model ID used for agent and chat. "
            "Changes take effect on the next request. "
            "Examples: anthropic/claude-sonnet-4-5, anthropic/claude-3.5-haiku, openai/gpt-4o-mini."
        ),
    )
