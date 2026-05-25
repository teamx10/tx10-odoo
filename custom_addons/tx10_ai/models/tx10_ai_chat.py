# Minimal stub — full implementation in Task 5
from odoo import fields, models


class Tx10AiChat(models.Model):
    _name = "tx10.ai.chat"
    _description = "TX10 AI — Conversation"
    _order = "last_activity desc"

    name = fields.Char(required=True, default="New Chat")
    user_id = fields.Many2one("res.users", required=True, default=lambda s: s.env.user)
    message_ids = fields.One2many("tx10.ai.message", "chat_id")
    last_activity = fields.Datetime(default=fields.Datetime.now)
