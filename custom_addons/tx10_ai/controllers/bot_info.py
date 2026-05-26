from odoo import http
from odoo.http import request


class Tx10AiBotInfo(http.Controller):
    @http.route("/tx10_ai/bot_channel", type="jsonrpc", auth="user")
    def bot_channel(self):
        chat = request.env["tx10.ai.chat"].search(
            [("user_id", "=", request.env.uid)], limit=1
        )
        if not chat or not chat.channel_id:
            return {"error": "no_channel"}
        return {"channel_id": chat.channel_id.id}
