from odoo import http
from odoo.http import request


class Tx10AiBotInfo(http.Controller):
    @http.route("/tx10_ai/bot_partner", type="json", auth="user")
    def bot_partner(self):
        partner = request.env.ref("tx10_ai.partner_ai_bot", raise_if_not_found=False)
        if not partner:
            return {"error": "bot_not_found"}
        return {"partner_id": partner.id}
