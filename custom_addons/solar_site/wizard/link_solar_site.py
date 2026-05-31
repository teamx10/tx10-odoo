from odoo import fields, models
from odoo.tools.translate import _


class SolarSiteLinkWizard(models.TransientModel):
    _name = "solar.site.link.wizard"
    _description = "Link Existing Solar Site to CRM Lead"

    crm_lead_id = fields.Many2one(
        comodel_name="crm.lead",
        string="CRM Lead",
        required=True,
    )
    solar_site_id = fields.Many2one(
        comodel_name="solar.site",
        string="Solar Site",
        required=True,
    )

    def action_link(self):
        self.ensure_one()
        lead = self.crm_lead_id
        site = self.solar_site_id
        lead.solar_site_id = site
        lead.message_post(
            body=_("Linked to Solar Site %s.") % site.solar_code,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "solar.site",
            "res_id": site.id,
            "view_mode": "form",
            "target": "current",
        }
