from odoo import api, fields, models
from odoo.tools.translate import _

SOLAR_STATUS_SELECTION = [
    ("new", "New"),
    ("remote_assessment", "Remote Assessment"),
    ("data_requested", "Data Requested"),
    ("engineer_visit", "Engineer Visit Needed"),
    ("qualified", "Qualified"),
    ("rejected", "Rejected"),
]

SUITABILITY_SELECTION = [
    ("excellent", "Excellent"),
    ("good", "Good"),
    ("moderate", "Moderate"),
    ("poor", "Poor"),
    ("unsuitable", "Unsuitable"),
]

NEXT_STEP_SELECTION = [
    ("proceed_proposal", "Proceed to Proposal"),
    ("engineer_visit", "Schedule Engineer Visit"),
    ("request_data", "Request More Data"),
    ("on_hold", "Put on Hold"),
    ("reject", "Reject Site"),
]

PRIORITY_SELECTION = [
    ("0", "Normal"),
    ("1", "Important"),
    ("2", "Very Important"),
    ("3", "Critical"),
]

# Shading risk ordering for overall calculation
SHADING_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
SHADING_REVERSE = {v: k for k, v in SHADING_ORDER.items()}


class SolarSite(models.Model):
    _name = "solar.site"
    _description = "Solar Site"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "solar_code desc"
    _rec_name = "solar_code"

    # ── Identification ──────────────────────────────────────────────────────
    solar_code = fields.Char(
        string="Site Code",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )
    solar_status = fields.Selection(
        selection=SOLAR_STATUS_SELECTION,
        string="Status",
        default="new",
        required=True,
        tracking=True,
    )
    owner_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Site Owner",
        tracking=True,
    )
    contact_person_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact Person",
    )
    responsible_manager_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsible Manager",
        default=lambda self: self.env.user,
        tracking=True,
    )
    responsible_engineer_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsible Engineer",
        tracking=True,
    )

    # ── CRM links ────────────────────────────────────────────────────────────
    crm_lead_ids = fields.One2many(
        comodel_name="crm.lead",
        inverse_name="solar_site_id",
        string="CRM Leads",
    )
    crm_lead_count = fields.Integer(
        compute="_compute_crm_lead_count",
        string="Leads",
    )

    # ── Address + Geo ────────────────────────────────────────────────────────
    street = fields.Char(string="Street")
    city = fields.Char(string="City")
    zip = fields.Char(string="ZIP")
    state_id = fields.Many2one(comodel_name="res.country.state", string="State")
    country_id = fields.Many2one(comodel_name="res.country", string="Country")
    latitude = fields.Float(string="Latitude", digits=(9, 6))
    longitude = fields.Float(string="Longitude", digits=(9, 6))
    google_maps_url = fields.Char(
        compute="_compute_map_urls",
        string="Google Maps URL",
    )
    google_satellite_url = fields.Char(
        compute="_compute_map_urls",
        string="Google Satellite URL",
    )

    # ── Roof Planes ──────────────────────────────────────────────────────────
    roof_plane_ids = fields.One2many(
        comodel_name="solar.roof.plane",
        inverse_name="solar_site_id",
        string="Roof Planes",
    )
    estimated_total_roof_area_m2 = fields.Float(
        compute="_compute_roof_totals",
        string="Total Roof Area (m²)",
        store=True,
        digits=(10, 2),
    )
    estimated_total_usable_area_m2 = fields.Float(
        compute="_compute_roof_totals",
        string="Total Usable Area (m²)",
        store=True,
        digits=(10, 2),
    )
    overall_shading_risk = fields.Selection(
        selection=[
            ("none", "None"),
            ("low", "Low (<10%)"),
            ("medium", "Medium (10–30%)"),
            ("high", "High (>30%)"),
            ("critical", "Critical (obstructed)"),
        ],
        compute="_compute_roof_totals",
        string="Overall Shading Risk",
        store=True,
    )

    # ── Remote Assessment ────────────────────────────────────────────────────
    remote_assessment_notes = fields.Text(string="Remote Assessment Notes")
    satellite_image_url = fields.Char(string="Satellite Image URL")
    street_view_url = fields.Char(string="Street View URL")

    # ── Preliminary System Potential ─────────────────────────────────────────
    panel_wattage_wp = fields.Float(
        string="Panel Wattage (Wp)",
        default=580.0,
        digits=(10, 0),
    )
    panel_area_m2 = fields.Float(
        string="Panel Area (m²)",
        default=2.6,
        digits=(5, 2),
    )
    area_utilization_pct = fields.Float(
        string="Area Utilisation (%)",
        default=60.0,
        digits=(5, 1),
        help="Percentage of usable area covered by panels.",
    )
    specific_yield_kwh_kwp = fields.Float(
        string="Specific Yield (kWh/kWp)",
        default=1100.0,
        digits=(7, 0),
    )
    estimated_panel_count = fields.Integer(
        compute="_compute_potential",
        string="Estimated Panel Count",
        store=True,
    )
    estimated_dc_kw = fields.Float(
        compute="_compute_potential",
        string="Estimated DC Capacity (kWp)",
        store=True,
        digits=(10, 2),
    )
    estimated_annual_generation_kwh = fields.Float(
        compute="_compute_potential",
        string="Est. Annual Generation (kWh)",
        store=True,
        digits=(10, 0),
    )

    # ── Qualification Decision ───────────────────────────────────────────────
    site_suitability = fields.Selection(
        selection=SUITABILITY_SELECTION,
        string="Site Suitability",
        tracking=True,
    )
    recommended_next_step = fields.Selection(
        selection=NEXT_STEP_SELECTION,
        string="Recommended Next Step",
    )
    priority = fields.Selection(
        selection=PRIORITY_SELECTION,
        string="Priority",
        default="0",
    )
    ready_for_preliminary_proposal = fields.Boolean(
        string="Ready for Preliminary Proposal",
        tracking=True,
    )
    qualification_notes = fields.Text(string="Qualification Notes")

    # ────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("solar_code", _("New")) == _("New"):
                vals["solar_code"] = self.env["ir.sequence"].next_by_code("solar.site") or _("New")
        return super().create(vals_list)

    def name_get(self):
        return [(rec.id, rec.solar_code) for rec in self]

    @api.depends("crm_lead_ids")
    def _compute_crm_lead_count(self):
        for rec in self:
            rec.crm_lead_count = len(rec.crm_lead_ids)

    @api.depends("latitude", "longitude")
    def _compute_map_urls(self):
        for rec in self:
            if rec.latitude and rec.longitude:
                coords = f"{rec.latitude},{rec.longitude}"
                rec.google_maps_url = f"https://www.google.com/maps?q={coords}"
                rec.google_satellite_url = (
                    f"https://www.google.com/maps/@{coords},18z/data=!3m1!1e3"
                )
            else:
                rec.google_maps_url = False
                rec.google_satellite_url = False

    @api.depends("roof_plane_ids.total_area_m2", "roof_plane_ids.usable_area_m2", "roof_plane_ids.shading_risk")
    def _compute_roof_totals(self):
        for rec in self:
            planes = rec.roof_plane_ids
            rec.estimated_total_roof_area_m2 = sum(p.total_area_m2 for p in planes)
            rec.estimated_total_usable_area_m2 = sum(p.usable_area_m2 for p in planes)
            if planes:
                max_order = max(SHADING_ORDER.get(p.shading_risk or "none", 0) for p in planes)
                rec.overall_shading_risk = SHADING_REVERSE.get(max_order, "none")
            else:
                rec.overall_shading_risk = False

    @api.depends(
        "estimated_total_usable_area_m2",
        "panel_area_m2",
        "area_utilization_pct",
        "panel_wattage_wp",
        "specific_yield_kwh_kwp",
    )
    def _compute_potential(self):
        for rec in self:
            if rec.panel_area_m2 and rec.area_utilization_pct:
                area_util = rec.area_utilization_pct / 100.0
                panel_count = int(
                    (rec.estimated_total_usable_area_m2 * area_util) / rec.panel_area_m2,
                )
                dc_kw = (panel_count * rec.panel_wattage_wp) / 1000.0
                generation = dc_kw * rec.specific_yield_kwh_kwp
            else:
                panel_count = 0
                dc_kw = 0.0
                generation = 0.0
            rec.estimated_panel_count = panel_count
            rec.estimated_dc_kw = dc_kw
            rec.estimated_annual_generation_kwh = generation

    # ── Action buttons ───────────────────────────────────────────────────────

    def action_recalculate_potential(self):
        for rec in self:
            rec._compute_potential()
            rec.message_post(
                body=_(
                    "Potential recalculated: %(count)d panels / %(dc).1f kWp / %(gen).0f kWh/year",
                    count=rec.estimated_panel_count,
                    dc=rec.estimated_dc_kw,
                    gen=rec.estimated_annual_generation_kwh,
                ),
            )

    def _sync_lead_stage(self, stage_xmlid):
        stage = self.env.ref(stage_xmlid, raise_if_not_found=False)
        if not stage:
            return
        for rec in self:
            rec.crm_lead_ids.filtered(lambda lead: lead.probability != 100).write(
                {"stage_id": stage.id},
            )

    def action_qualify_site(self):
        for rec in self:
            rec.solar_status = "qualified"
            rec.ready_for_preliminary_proposal = True
            rec.message_post(body=_("Site qualified — Ready for Preliminary Proposal."))
            rec._sync_lead_stage("solar_site.crm_stage_ready_for_proposal")
            manager = rec.responsible_manager_id or rec.env.user
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=manager.id,
                summary=_("Site qualified — prepare proposal"),
                note=_("Solar site %s is ready for preliminary proposal.") % rec.solar_code,
            )

    def action_request_more_data(self):
        for rec in self:
            rec.solar_status = "data_requested"
            rec.message_post(body=_("More data requested from client."))
            rec._sync_lead_stage("solar_site.crm_stage_data_requested")

    def action_engineer_visit_needed(self):
        for rec in self:
            rec.solar_status = "engineer_visit"
            rec.message_post(body=_("Engineer site visit required before further assessment."))
            rec._sync_lead_stage("solar_site.crm_stage_engineer_visit")
            engineer = rec.responsible_engineer_id or rec.env.user
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=engineer.id,
                summary=_("Schedule site visit"),
                note=_("Site visit needed for %s.") % rec.solar_code,
            )

    def action_reject_site(self):
        for rec in self:
            rec.solar_status = "rejected"
            rec.ready_for_preliminary_proposal = False
            rec.message_post(body=_("Site rejected — not suitable for solar installation."))
            rec._sync_lead_stage("solar_site.crm_stage_lost")

    def action_geolocalize(self):
        for rec in self:
            address_parts = [rec.street, rec.city, rec.zip]
            if rec.state_id:
                address_parts.append(rec.state_id.name)
            if rec.country_id:
                address_parts.append(rec.country_id.name)
            address = ", ".join(p for p in address_parts if p)
            if not address:
                continue
            result = self.env["base.geocoder"].geocode(address)
            if result:
                rec.latitude, rec.longitude = result
                rec.message_post(
                    body=_("Geolocalized: lat %(lat).6f, lon %(lon).6f", lat=rec.latitude, lon=rec.longitude),
                )

    def action_view_crm_leads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "CRM Leads",
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [("solar_site_id", "=", self.id)],
            "context": {"default_solar_site_id": self.id},
        }

    def action_open_google_maps(self):
        self.ensure_one()
        if self.google_maps_url:
            return {"type": "ir.actions.act_url", "url": self.google_maps_url, "target": "new"}
        return None

    def action_open_satellite(self):
        self.ensure_one()
        if self.google_satellite_url:
            return {"type": "ir.actions.act_url", "url": self.google_satellite_url, "target": "new"}
        return None
