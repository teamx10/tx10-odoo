# EPC-проект с задачами, сервисные заказы FSM (монтаж, ремонт, закупка ЗИП),
# отгрузка на объект, связанная с заказом, и повторяющиеся работы.
from datetime import timedelta
from odoo import fields as F

now = F.Datetime.now().replace(minute=0, second=0, microsecond=0)
st01, st02 = xid(env, "station_st01"), xid(env, "station_st02")
customer, pm = xid(env, "partner_customer"), xid(env, "user_pm")
tech = xid(env, "fsm_person_tech")
eq = lambda k: xid(env, f"fsm_eq_{k}")

project = ensure(env, "project_epc", "project.project", {
    "name": "DEMO-SOLAR-PRJ-001 Solar Park North EPC",
    "partner_id": customer.id, "user_id": pm.id,
    "allow_timesheets": True, "fsm_location_id": st01.id,
    "description": "Synthetic EPC demo project (design → procurement → install → commissioning).",
})
TASKS = ["Design & permits", "Procurement", "Installation", "Commissioning", "Handover to O&M"]
tasks = {}
for i, name in enumerate(TASKS, 1):
    tasks[i] = ensure(env, f"task_{i}", "project.task", {
        "name": f"DEMO-SOLAR-PRJ-001.{i} {name}", "project_id": project.id,
        "user_ids": [(6, 0, pm.ids)], "sequence": i})

team = ensure(env, "fsm_team", "fsm.team", {"name": "DEMO-SOLAR Service Team", "project_id": project.id})
scheduled = xid(env, "stage_scheduled")
base = {"team_id": team.id, "person_id": tech.id}

o_install = ensure(env, "fso_install", "fsm.order", dict(base,
    location_id=st01.id, project_id=project.id, project_task_id=tasks[3].id,
    description="<p>DEMO-SOLAR-FSO-001: монтаж и пусконаладка инвертора, панелей и счётчика.</p>",
    scheduled_date_start=now + timedelta(days=1), scheduled_duration=8,
    equipment_ids=[(6, 0, (eq("inv_0001") | eq("pv_0001") | eq("pv_0002") | eq("mtr_0001")).ids)]))
if o_install.stage_id != scheduled:
    o_install.stage_id = scheduled

# Ремонт: тип Repair → штатно создаётся repair.order (fieldservice_repair).
o_repair = ensure(env, "fso_repair", "fsm.order", dict(base,
    location_id=st02.id, type=env.ref("fieldservice_repair.fsm_order_type_repair").id,
    description="<p>DEMO-SOLAR-FSO-002: диагностика инвертора — ошибка изоляции DC.</p>",
    scheduled_date_start=now + timedelta(days=2), scheduled_duration=4,
    equipment_ids=[(6, 0, eq("inv_0002").ids)]))
LOG.append(f"  repair orders from FSO-002: {o_repair.repair_ids.mapped('name')}")

# Закупка ЗИП из сервисного заказа (fieldservice_purchase: purchase.order.fsm_order_id).
o_fuse = ensure(env, "fso_fuse", "fsm.order", dict(base,
    location_id=st01.id, project_id=project.id,
    description="<p>DEMO-SOLAR-FSO-003: замена перегоревших DC-предохранителей стрингов.</p>",
    scheduled_date_start=now + timedelta(days=3), scheduled_duration=2))
po = ensure(env, "po_fso_fuse", "purchase.order", {
    "partner_id": xid(env, "partner_vendor").id, "fsm_order_id": o_fuse.id,
    "partner_ref": "DEMO-SOLAR-PO-002", "origin": o_fuse.name,
    "order_line": [(0, 0, {"product_id": xid(env, "prod_fuse").product_variant_id.id, "product_qty": 6})]})
if po.state == "draft":
    po.button_confirm()

# Отгрузка на объект ST01, связанная с заказом монтажа (fieldservice_stock).
out = xid(env, "delivery_install")
if not out:
    ptype = env.ref("stock.picking_type_out")
    out = ensure(env, "delivery_install", "stock.picking", {
        "picking_type_id": ptype.id, "partner_id": customer.id, "fsm_order_id": o_install.id,
        "origin": o_install.name, "location_id": ptype.default_location_src_id.id,
        "location_dest_id": env.ref("stock.stock_location_customers").id})
    for k in ("pv_0001", "pv_0002", "mtr_0001"):
        lot = eq(k).lot_id
        env["stock.move"].create({
            "picking_id": out.id, "product_id": lot.product_id.id, "product_uom_qty": 1,
            "location_id": out.location_id.id, "location_dest_id": out.location_dest_id.id,
            "move_line_ids": [(0, 0, {"product_id": lot.product_id.id, "lot_id": lot.id,
                                      "quantity": 1, "location_id": out.location_id.id,
                                      "location_dest_id": out.location_dest_id.id,
                                      "picking_id": out.id})],
            "picked": True})
    out.action_confirm()
    out.button_validate()
LOG.append(f"  delivery {out.name} state={out.state} fsm_order={out.fsm_order_id.name}")

# Повторяющиеся работы: ежемесячный осмотр ST01 (fieldservice_recurring).
freq = ensure(env, "freq_monthly", "fsm.frequency", {
    "name": "DEMO-SOLAR Monthly", "interval": 1, "interval_type": "monthly"})
fset = ensure(env, "freq_set_monthly", "fsm.frequency.set", {
    "name": "DEMO-SOLAR Monthly inspection", "schedule_days": 90,
    "fsm_frequency_ids": [(6, 0, freq.ids)]})
tmpl = ensure(env, "fsm_template_inspect", "fsm.template", {
    "name": "DEMO-SOLAR Monthly visual inspection", "duration": 3,
    "instructions": "Visual inspection of modules, cabling, inverter alarms (synthetic checklist)."})
rtmpl = ensure(env, "recurring_template", "fsm.recurring.template", {
    "name": "DEMO-SOLAR Monthly O&M inspection",
    "fsm_frequency_set_id": fset.id, "fsm_order_template_id": tmpl.id})
rec = ensure(env, "recurring_st01", "fsm.recurring", {
    "fsm_recurring_template_id": rtmpl.id, "location_id": st01.id,
    "fsm_frequency_set_id": fset.id, "fsm_order_template_id": tmpl.id,
    "team_id": team.id, "person_id": tech.id, "start_date": now + timedelta(days=7),
    "description": "DEMO-SOLAR-REC-001 monthly O&M inspection"})
if rec.state == "draft":
    rec.action_start()
LOG.append(f"  recurring {rec.name} state={rec.state} orders={rec.fsm_order_ids.mapped('name')}")

report("40 project & field service")
