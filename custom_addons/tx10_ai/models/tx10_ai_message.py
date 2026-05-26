from odoo import fields, models


class Tx10AiMessage(models.Model):
    _name = "tx10.ai.message"
    _description = "TX10 AI — Message Turn"
    _order = "id asc"

    chat_id = fields.Many2one(
        "tx10.ai.chat",
        required=True,
        ondelete="cascade",
        index=True,
    )
    role = fields.Selection(
        [("user", "User"), ("assistant", "Assistant"), ("tool", "Tool Result")],
        required=True,
    )
    content = fields.Text()
    tool_calls_json = fields.Json()
    tool_call_id = fields.Char()
    tool_name = fields.Char()
    status = fields.Selection(
        [
            ("done", "Done"),
            ("pending_confirmation", "Pending Confirmation"),
            ("confirmed", "Confirmed"),
            ("rejected", "Rejected"),
            ("error", "Error"),
        ],
        default="done",
    )
    proposed_action = fields.Json()
    action_summary = fields.Text()
    prompt_tokens = fields.Integer(default=0)
    completion_tokens = fields.Integer(default=0)
    model_used = fields.Char()
    executed_by_id = fields.Many2one("res.users", readonly=True)
    executed_at = fields.Datetime(readonly=True)
