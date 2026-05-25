from markupsafe import Markup

from odoo import _, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    tx10_ai_state = fields.Selection(
        [("not_initialized", "Not initialized"), ("initialized", "Initialized")],
        string="TX10 AI Status",
        readonly=True,
        required=False,
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["tx10_ai_state"]

    def _on_webclient_bootstrap(self):
        super()._on_webclient_bootstrap()
        if self._is_internal() and self.tx10_ai_state in (False, "not_initialized"):
            self.sudo()._init_tx10_ai_chat()

    def _init_tx10_ai_chat(self):
        self.ensure_one()
        bot_partner = self.env.ref("tx10_ai.partner_ai_bot", raise_if_not_found=False)
        if not bot_partner:
            return

        # Avoid duplicate chat on repeated bootstrap calls
        existing = self.env["tx10.ai.chat"].sudo().search([("user_id", "=", self.id)], limit=1)
        if existing:
            self.sudo().tx10_ai_state = "initialized"
            return

        channel = self.env["discuss.channel"].with_user(self)._get_or_create_chat(
            [bot_partner.id, self.partner_id.id]
        )
        self.env["tx10.ai.chat"].sudo().create({
            "name": f"TX10 AI — {self.name}",
            "user_id": self.id,
            "channel_id": channel.id,
        })

        welcome_msg = Markup("%s<br/>%s") % (
            _("Hi! I'm the TeamX10 AI assistant."),
            _("Ask me to find tasks, projects, contacts, or to create and update records."),
        )
        channel.sudo().message_post(
            author_id=bot_partner.id,
            body=welcome_msg,
            message_type="comment",
            silent=True,
            subtype_xmlid="mail.mt_comment",
        )
        self.sudo().tx10_ai_state = "initialized"
