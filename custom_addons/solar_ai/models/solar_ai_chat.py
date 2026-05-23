from odoo import fields, models


class SolarAiChat(models.Model):
    _name = "solar.ai.chat"
    _description = "Solar AI — Conversation"
    _order = "last_activity desc"

    name = fields.Char(required=True, default="New Chat")
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda s: s.env.user,
        readonly=True,
        index=True,
    )
    message_ids = fields.One2many("solar.ai.message", "chat_id")
    state = fields.Selection(
        [("active", "Active"), ("archived", "Archived")],
        default="active",
        required=True,
    )
    last_activity = fields.Datetime(default=fields.Datetime.now)
    round_count = fields.Integer(default=0)
    total_tokens = fields.Integer(default=0)
    budget_state = fields.Selection(
        [("ok", "OK"), ("exhausted", "Exhausted")],
        default="ok",
    )

    MAX_ROUNDS = 20
    MAX_TOKENS = 100000
