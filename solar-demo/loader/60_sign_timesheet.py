# Шаблон подписываемого документа (sign_oca) для FSM-заказов и записи учёта времени.
import base64
from io import BytesIO
from datetime import date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Синтетический PDF «Акт приёмки пусконаладки» (генерируется локально reportlab).
buf = BytesIO()
c = canvas.Canvas(buf, pagesize=A4)
c.setFont("Helvetica-Bold", 16)
c.drawString(60, 780, "DEMO-SOLAR Commissioning Acceptance Act (SYNTHETIC)")
c.setFont("Helvetica", 11)
for i, line in enumerate([
    "This is a synthetic demo document. It has no legal force.",
    "Site: DEMO-SOLAR-ST01 Solar Park North (5 MWp)",
    "Scope: installation and commissioning of inverter, PV strings and grid meter.",
    "The customer confirms that the work listed in the service order is completed.",
    "", "Customer representative name:", "", "", "Customer signature:",
]):
    c.drawString(60, 740 - i * 20, line)
c.showPage()
c.save()
pdf = base64.b64encode(buf.getvalue())

# Политика «default»: выражение {{object.location_id.owner_id.id}} не входит в whitelist
# mail_allowed_qweb_expressions, и без группы Mail Template Editor PM не может его отрендерить.
role = ensure(env, "sign_role_owner", "sign.oca.role", {
    "name": "DEMO-SOLAR Site Owner",
    "partner_selection_policy": "default",
    "default_partner_id": xid(env, "partner_customer").id,
    "expression_partner": False}, update=True)
tmpl = ensure(env, "sign_tmpl_acceptance", "sign.oca.template", {
    "name": "DEMO-SOLAR Commissioning Acceptance Act",
    "data": pdf, "filename": "demo-solar-acceptance-act.pdf",
    "model_id": env["ir.model"]._get_id("fsm.order")})
ensure(env, "sign_item_name", "sign.oca.template.item", {
    "template_id": tmpl.id, "field_id": env.ref("sign_oca.sign_field_name").id,
    "role_id": role.id, "required": True, "page": 1,
    "position_x": 40, "position_y": 21.2, "width": 35, "height": 3}, update=True)
ensure(env, "sign_item_signature", "sign.oca.template.item", {
    "template_id": tmpl.id, "field_id": env.ref("sign_oca.sign_field_signature").id,
    "role_id": role.id, "required": True, "page": 1,
    "position_x": 40, "position_y": 25, "width": 35, "height": 8})
set_config(env, {"fsm_order_sign_oca_template_id": tmpl.id,
                 "fsm_signature_capture": True, "fsm_document_signing": True})

# Учёт времени: задачи EPC-проекта и сервисные заказы (fieldservice_timesheet).
project = xid(env, "project_epc")
emp = lambda k: xid(env, f"employee_{k}")
install, repair = xid(env, "fso_install"), xid(env, "fso_repair")
TS = [
    ("ts_design_pm", "employee_pm", project, xid(env, "task_1"), None, 4.0, "Single-line diagram review"),
    ("ts_install_tech", "employee_tech", project, xid(env, "task_3"), install, 6.5, "Inverter mounting and DC cabling"),
    ("ts_commission_tech", "employee_tech", project, xid(env, "task_4"), install, 2.0, "Commissioning tests"),
    ("ts_repair_svcmgr", "employee_svcmgr", project, None, repair, 1.5, "Remote diagnostics of DC insulation alarm"),
]
for i, (key, ek, prj, task, fso, hours, name) in enumerate(TS):
    vals = {"name": f"DEMO-SOLAR {name}", "employee_id": xid(env, ek).id, "project_id": prj.id,
            "unit_amount": hours, "date": date.today() - timedelta(days=len(TS) - i)}
    if task:
        vals["task_id"] = task.id
    if fso:
        vals["fsm_order_id"] = fso.id
    ensure(env, key, "account.analytic.line", vals)
LOG.append(f"  FSO-001 timesheets: {install.timesheet_ids.mapped('unit_amount')} | "
           f"project total h: {sum(project.timesheet_ids.mapped('unit_amount'))}")

report("60 sign template & timesheets")
