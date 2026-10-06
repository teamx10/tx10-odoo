# Maintenance: карточки оборудования станции ST01 (отдельная модель от fsm.equipment —
# штатной синхронизации между ними нет), сертификат, теги, план ТО,
# корректирующая заявка с закупкой и ремонтом.
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

project = xid(env, "project_epc")
vendor = xid(env, "partner_vendor")
tags = lambda *k: [(6, 0, [xid(env, f"mtag_{x}").id for x in k])]
team = env.ref("maintenance.equipment_team_maintenance", raise_if_not_found=False) \
    or env["maintenance.team"].search([], limit=1)

CARDS = [  # key, имя, категория, серийник, теги
    ("meq_inv_0001", "DEMO-SOLAR-ST01 Inverter #1", "inverters", "DEMO-SOLAR-SN-INV-0001", ("st01", "critical", "grid")),
    ("meq_pv_array", "DEMO-SOLAR-ST01 PV Array String A", "panels", "DEMO-SOLAR-SN-PV-0001..0002", ("st01",)),
    ("meq_mtr_0001", "DEMO-SOLAR-ST01 Grid Meter", "meters", "DEMO-SOLAR-SN-MTR-0001", ("st01", "grid")),
]
cards = {}
for key, name, cat, serial, tg in CARDS:
    cards[key] = ensure(env, key, "maintenance.equipment", {
        "name": name, "category_id": xid(env, f"mcat_{cat}").id, "serial_no": serial,
        "tag_ids": tags(*tg), "partner_id": vendor.id,
        "maintenance_team_id": team.id, "project_id": project.id,
        "warranty_date": date.today() + relativedelta(years=5),
        "note": "Site: DEMO-SOLAR-ST01 Solar Park North. Synthetic maintenance card. Linked to FSM equipment only by serial number (manual)."})

inv = cards["meq_inv_0001"]
ensure(env, "cert_inv_grid", "maintenance.equipment.certificate", {
    "name": "Grid code compliance (synthetic)", "certificate_number": "DEMO-SOLAR-CERT-001",
    "equipment_id": inv.id, "date": date.today() - timedelta(days=30),
    "renewal_date": date.today() + relativedelta(years=1),
    "notes": "Synthetic certificate for demo purposes only."})

# План ТО: ежеквартальный осмотр инвертора, горизонт 6 месяцев; заявки создаёт штатный cron.
kind = ensure(env, "mkind_quarterly", "maintenance.kind", {"name": "DEMO-SOLAR Quarterly inspection"})
plan = ensure(env, "mplan_inv_quarterly", "maintenance.plan", {
    "name": "DEMO-SOLAR-MP-001 Inverter quarterly inspection", "equipment_id": inv.id,
    "maintenance_kind_id": kind.id, "interval": 3, "interval_step": "month",
    "duration": 2, "start_maintenance_date": date.today() + timedelta(days=14),
    "maintenance_plan_horizon": 6, "planning_step": "month", "maintenance_team_id": team.id,
    "instruction_type": "text",
    "instruction_text": "<p>Check fans, DC insulation alarms, torque on AC terminals (synthetic).</p>"})
env["maintenance.equipment"]._cron_generate_requests()
LOG.append(f"  plan requests: {plan.maintenance_ids.mapped(lambda r: f'{r.name} @ {r.schedule_date}')}")

# Ремонт инвертора (в цехе/на складе WH) и корректирующая заявка, связанная с ним и закупкой.
lot = env["stock.lot"].search([("name", "=", "DEMO-SOLAR-SN-INV-0001")], limit=1)
repair = ensure(env, "repair_inv_fan", "repair.order", {
    "product_id": lot.product_id.id, "lot_id": lot.id, "product_qty": 1,
    "partner_id": xid(env, "partner_customer").id,
    "internal_notes": "<p>DEMO-SOLAR-RO-001: cooling fan replacement (synthetic).</p>"})
po = ensure(env, "po_mr_fan", "purchase.order", {
    "partner_id": vendor.id, "partner_ref": "DEMO-SOLAR-PO-003",
    "origin": "DEMO-SOLAR-MR-001",
    "order_line": [(0, 0, {"product_id": xid(env, "prod_fuse").product_variant_id.id,
                           "product_qty": 4, "name": "Spare parts for inverter repair (synthetic)"})]})
req = ensure(env, "mreq_inv_fan", "maintenance.request", {
    "name": "DEMO-SOLAR-MR-001 Inverter #1 cooling fan noise",
    "equipment_id": inv.id, "maintenance_type": "corrective",
    "maintenance_team_id": team.id, "project_id": project.id,
    "task_id": xid(env, "task_5").id, "repair_order_id": repair.id,
    "purchase_order_ids": [(6, 0, po.ids)], "user_id": xid(env, "user_svcmgr").id,
    "schedule_date": date.today() + timedelta(days=5)})
LOG.append(f"  request {req.name}: repair={req.repair_order_id.name} POs={req.purchase_order_ids.mapped('name')}")

report("50 maintenance")
