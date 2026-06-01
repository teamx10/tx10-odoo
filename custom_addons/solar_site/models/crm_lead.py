from odoo import fields, models
from odoo.tools.translate import _


class CrmLead(models.Model):
    _inherit = "crm.lead"

    solar_site_id = fields.Many2one(
        comodel_name="solar.site",
        string="Solar Site",
        tracking=True,
        ondelete="set null",
    )
    solar_site_status = fields.Selection(
        related="solar_site_id.solar_status",
        string="Site Status",
        readonly=True,
    )
    ready_for_preliminary_proposal = fields.Boolean(
        related="solar_site_id.ready_for_preliminary_proposal",
        string="Ready for Preliminary Proposal",
        readonly=True,
    )

    def action_create_solar_site(self):
        self.ensure_one()
        # Duplicate check: same street + city + partner
        domain = []
        if self.partner_id:
            domain.append(("owner_partner_id", "=", self.partner_id.id))
        if self.street:
            domain.append(("street", "=", self.street))
        if self.city:
            domain.append(("city", "=", self.city))
        if domain:
            existing = self.env["solar.site"].search(domain, limit=1)
            if existing:
                self.solar_site_id = existing
                self.message_post(
                    body=_("Linked to existing Solar Site %s (duplicate address detected).") % existing.solar_code,
                )
                return self.action_open_solar_site()

        # Determine default engineer
        config = self.env["ir.config_parameter"].sudo()
        engineer_id = int(config.get_param("solar_site.default_qualification_engineer_id", 0))
        engineer = self.env["res.users"].browse(engineer_id) if engineer_id else self.env.user

        # Transfer fields from lead
        vals = {
            "owner_partner_id": self.partner_id.id if self.partner_id else False,
            "contact_person_id": self.partner_id.id if self.partner_id else False,
            "street": self.street or False,
            "city": self.city or False,
            "zip": self.zip or False,
            "state_id": self.state_id.id if self.state_id else False,
            "country_id": self.country_id.id if self.country_id else False,
            "solar_status": "remote_assessment",
            "responsible_engineer_id": engineer.id,
        }
        site = self.env["solar.site"].create(vals)
        self.solar_site_id = site

        # Move lead to Remote Assessment stage
        stage = self.env.ref("solar_site.crm_stage_remote_assessment", raise_if_not_found=False)
        if stage:
            self.stage_id = stage

        # Schedule activity for engineer
        deadline_days = int(config.get_param("solar_site.default_qualification_deadline", 1))
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            date_deadline=fields.Date.today() + __import__("datetime").timedelta(days=deadline_days),
            user_id=engineer.id,
            summary=_("Remote site qualification"),
            note=_("Solar Site %s created. Please complete remote assessment.") % site.solar_code,
        )
        self.message_post(
            body=_("Solar Site %s created and linked.") % site.solar_code,
        )
        return self.action_open_solar_site()

    def action_open_solar_site(self):
        self.ensure_one()
        if not self.solar_site_id:
            return None
        return {
            "type": "ir.actions.act_window",
            "res_model": "solar.site",
            "res_id": self.solar_site_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_link_solar_site(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "solar.site.link.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_crm_lead_id": self.id},
        }
