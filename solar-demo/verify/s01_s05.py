# Сценарии 1–5. Запуск: scripts/verify.sh (склеивается с _lib.py и verify/_check.py).
from odoo.exceptions import ValidationError, AccessError, UserError

U = {k: xid(env, f"user_{k}") for k in ("pm", "tech", "svcmgr")}
st01, st02 = xid(env, "station_st01"), xid(env, "station_st02")
stage = lambda k: xid(env, f"stage_{k}")

# 1. Объект и связанное оборудование (под исполнителем сервиса).
with scenario("01 объект → оборудование", "demo-tech"):
    e = env(user=U["tech"])
    loc = e["fsm.location"].browse(st01.id)
    eqs = e["fsm.equipment"].search([("location_id", "=", st01.id)])
    check(loc.name.startswith("DEMO-SOLAR-ST01"), f"location {loc.name}")
    check(len(eqs) >= 4, f"{len(eqs)} equipment: {', '.join(eqs.mapped('lot_id.name'))}")
    check(bool(loc.partner_latitude and loc.partner_longitude),
          f"coords {loc.partner_latitude}, {loc.partner_longitude}")

# 2. Сервисная работа: создание (руководитель), назначение, этапы (исполнитель).
with scenario("02 работа: создать → назначить → этапы", "demo-svcmgr → demo-tech"):
    def walk(wo):
        """Полный проход этапов штатными действиями; возвращает фактический путь."""
        path = [wo.stage_id.name]
        wo = wo.with_user(U["svcmgr"])
        wo.person_id = xid(env, "fsm_person_tech")
        wo.stage_id = stage("scheduled"); path.append(wo.stage_id.name)
        t = wo.with_user(U["tech"])
        t.stage_id = stage("in_progress"); path.append(t.stage_id.name)
        acts = env["mail.activity"].search([("res_model", "=", "fsm.order"), ("res_id", "=", wo.id),
                                            ("user_id", "=", U["svcmgr"].id)])
        check(bool(acts), f"server action → activity for svcmgr: {acts.mapped('summary')}")
        t.resolution = "<p>Panels cleaned, no defects (synthetic).</p>"
        t.action_complete(); path.append(t.stage_id.name)
        t.stage_id = stage("closed"); path.append(t.stage_id.name)
        check(wo.stage_id == stage("closed"), f"{wo.name}: {' → '.join(path)}")

    new_order = lambda: env(user=U["svcmgr"])["fsm.order"].create({
        "location_id": st02.id, "team_id": xid(env, "fsm_team").id,
        "description": "<p>DEMO-SOLAR-FSO-T01: walkthrough — panel cleaning ST02.</p>",
        "equipment_ids": [(6, 0, [xid(env, "fsm_eq_pv_0003").id])]})
    if not xid(env, "fso_walkthrough"):  # постоянная демо-запись — один раз
        walk(bind(env, "fso_walkthrough", new_order()))
    else:  # повторная проверка — на временном заказе с откатом
        sp = env.cr.savepoint()
        try:
            walk(new_order())
        finally:
            sp.close(rollback=True)

# 3. Блокировка перехода при невыполненном условии stage_validation (под исполнителем).
with scenario("03 stage_validation блокирует переход", "demo-tech"):
    sp = env.cr.savepoint()
    try:
        o = env(user=U["svcmgr"])["fsm.order"].create({
            "location_id": st01.id, "team_id": xid(env, "fsm_team").id})
        try:
            o.with_user(U["tech"]).stage_id = stage("scheduled")
            o.flush_recordset()
            check(False, "переход в «Запланирована» без исполнителя НЕ заблокирован")
        except (ValidationError, AccessError) as ex:
            check(isinstance(ex, ValidationError) or "own" in str(ex), f"без исполнителя: {type(ex).__name__}: {str(ex)[:120]}")
        o.person_id = xid(env, "fsm_person_tech")
        o.with_user(U["tech"]).stage_id = stage("scheduled")
        try:
            o.with_user(U["tech"]).action_complete()
            o.flush_recordset()
            check(False, "«Выполнена» без resolution НЕ заблокирована")
        except ValidationError as ex:
            check(True, f"без итога работ: ValidationError: {str(ex)[:120]}")
    finally:
        sp.close(rollback=True)

# 4. Связь проекта и сервисной работы.
with scenario("04 проект ↔ сервисная работа", "demo-pm"):
    e = env(user=U["pm"])
    prj = e["project.project"].browse(xid(env, "project_epc").id)
    task = e["project.task"].browse(xid(env, "task_3").id)
    check(bool(prj.fsm_order_ids), f"project orders: {prj.fsm_order_ids.mapped('name')}")
    check(xid(env, "fso_install") in task.fsm_order_ids, f"task «{task.name}» → {task.fsm_order_ids.mapped('name')}")
    check(prj.fsm_location_id == st01, f"project FSM location: {prj.fsm_location_id.ref}")

# 5. Закупка из сервисного и ТО-сценария.
with scenario("05 закупка из FSM и из заявки ТО", "demo-pm / demo-svcmgr"):
    fo = env(user=U["pm"])["fsm.order"].browse(xid(env, "fso_fuse").id)
    check(fo.purchase_count >= 1, f"{fo.name}: POs {fo.purchase_ids.mapped(lambda p: f'{p.name}/{p.state}')}")
    po = env(user=U["pm"])["purchase.order"].create({
        "partner_id": xid(env, "partner_vendor").id, "fsm_order_id": fo.id,
        "order_line": [(0, 0, {"product_id": xid(env, "prod_fuse").product_variant_id.id, "product_qty": 2})]})
    check(po in fo.purchase_ids, f"PM создал {po.name} из заказа {fo.name} (draft, удаляется)")
    po.button_cancel(); po.unlink()
    mr = env(user=U["svcmgr"])["maintenance.request"].browse(xid(env, "mreq_inv_fan").id)
    check(bool(mr.purchase_order_ids), f"{mr.name}: POs {mr.purchase_order_ids.mapped('name')}")
