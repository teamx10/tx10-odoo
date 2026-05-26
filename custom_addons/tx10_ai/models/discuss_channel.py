import html as _html
import logging
import re

from odoo import models

_logger = logging.getLogger(__name__)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html_body):
    stripped = _HTML_TAG_RE.sub("", html_body or "").strip()
    return _html.unescape(stripped)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _message_post_after_hook(self, message, msg_vals):
        bot_partner = self.env.ref("tx10_ai.partner_ai_bot", raise_if_not_found=False)
        if not bot_partner:
            return super()._message_post_after_hook(message, msg_vals)

        # Anti-loop: skip bot-authored messages
        if msg_vals.get("author_id") == bot_partner.id:
            return super()._message_post_after_hook(message, msg_vals)

        # Skip non-comment messages (automated, system, etc.)
        if msg_vals.get("message_type") not in ("comment", "email"):
            return super()._message_post_after_hook(message, msg_vals)

        # Only act on channels where bot is a member
        bot_member = self.env["discuss.channel.member"].search(
            [("channel_id", "=", self.id), ("partner_id", "=", bot_partner.id)],
            limit=1,
        )
        if not bot_member:
            return super()._message_post_after_hook(message, msg_vals)

        # Find linked tx10.ai.chat (sudo: hook runs in caller's context, avoid ACL interference)
        chat = self.env["tx10.ai.chat"].sudo().search([("channel_id", "=", self.id)], limit=1)
        if not chat:
            _logger.debug("tx10_ai: no tx10.ai.chat linked to channel %s, skipping", self.id)
            return super()._message_post_after_hook(message, msg_vals)

        # Identify the sending user from author_id (partner_id)
        author_partner_id = msg_vals.get("author_id")
        user = self.env["res.users"].search([("partner_id", "=", author_partner_id)], limit=1)
        if not user:
            return super()._message_post_after_hook(message, msg_vals)

        content = _strip_html(msg_vals.get("body") or "")
        if not content:
            return super()._message_post_after_hook(message, msg_vals)

        self.env["tx10.ai.message"].sudo().create({
            "chat_id": chat.id,
            "role": "user",
            "content": content,
            "status": "done",
        })

        chat.sudo().write({"pending_agent_run": True})
        try:
            cron = self.env.ref("tx10_ai.ir_cron_run_agent", raise_if_not_found=False)
            if cron:
                cron.sudo()._trigger()
        except Exception:
            _logger.warning("tx10_ai: failed to trigger cron for chat %s", chat.id, exc_info=True)

        return super()._message_post_after_hook(message, msg_vals)
