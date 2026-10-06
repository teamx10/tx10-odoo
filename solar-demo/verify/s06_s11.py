# Сценарии 6–11 (и проверка изоляции почты). Изменяющие проверки — в savepoint с откатом,
# кроме запроса подписи (постоянная демо-запись для портальной подписи).
U = {k: xid(env, f"user_{k}") for k in ("pm", "tech", "svcmgr")}

def rollback_block(fn):
    sp = env.cr.savepoint()
    try:
        fn()
    finally:
        sp.close(rollback=True)

# 6. Складская связь оборудования и серийного номера.
with scenario("06 оборудование ↔ серийный номер ↔ склад", "demo-svcmgr"):
    e = env(user=U["svcmgr"])
    inv = e["fsm.equipment"].browse(xid(env, "fsm_eq_inv_0001").id)
    pv = e["fsm.equipment"].browse(xid(env, "fsm_eq_pv_0001").id)
    check(inv.lot_id.fsm_equipment_id == inv, f"{inv.lot_id.name} ⇄ equipment #{inv.id} (обратная ссылка lot)")
    check(inv.current_stock_location_id.usage == "internal", f"INV-0001 stock: {inv.current_stock_location_id.complete_name}")
    check(pv.current_stock_location_id.usage == "customer", f"PV-0001 after delivery: {pv.current_stock_location_id.complete_name}")
    rc = e["stock.picking"].browse(xid(env, "receipt_initial").id)
    check(rc.state == "done", f"receipt {rc.name} done → equipment auto-created")

# 7. Отображение гарантий.
with scenario("07 гарантии", "demo-tech"):
    e = env(user=U["tech"])
    for k in ("inv_0001", "pv_0001", "mtr_0001"):
        q = e["fsm.equipment"].browse(xid(env, f"fsm_eq_{k}").id)
        check(q.warranty_end_date and q.warranty_end_date > q.warranty_start_date,
              f"{q.lot_id.name}: {q.product_warranty} {q.product_warranty_type} → {q.warranty_start_date}..{q.warranty_end_date}")
    si = env(user=U["pm"])["product.supplierinfo"].browse(xid(env, "prod_inv_supplierinfo").id)
    check(si.warranty_duration == 5, f"supplier warranty (product_warranty): {si.warranty_duration}, return → {si.warranty_return_partner}")

# 8. Плановая / повторяющаяся работа штатными механизмами.
with scenario("08 повторяющиеся работы и план ТО", "cron + demo-svcmgr"):
    rec = xid(env, "recurring_st01")
    n0 = len(rec.fsm_order_ids)
    env["fsm.recurring"]._cron_generate_orders()
    check(n0 >= 1 and len(rec.fsm_order_ids) == n0,
          f"{rec.name}: {n0} заказов {rec.fsm_order_ids.mapped(lambda o: str(o.scheduled_date_start.date()))}, cron без дублей")
    plan = xid(env, "mplan_inv_quarterly")
    m0 = plan.maintenance_count
    env["maintenance.equipment"]._cron_generate_requests()
    check(m0 >= 1 and plan.maintenance_count == m0, f"план ТО: {m0} заявок, повторный cron без дублей")
    def new_rec():
        r = env(user=U["svcmgr"])["fsm.recurring"].create({
            "location_id": xid(env, "station_st02").id, "fsm_frequency_set_id": xid(env, "freq_set_monthly").id,
            "fsm_order_template_id": xid(env, "fsm_template_inspect").id, "team_id": xid(env, "fsm_team").id})
        r.action_start()
        check(r.state == "progress" and r.fsm_order_ids, f"svcmgr создал {r.name}: {len(r.fsm_order_ids)} заказа(ов)")
    rollback_block(new_rec)

# 9. Ремонт и связь с сервисом / ТО.
with scenario("09 ремонт ↔ FSM / ТО", "demo-svcmgr"):
    fo = env(user=U["svcmgr"])["fsm.order"].browse(xid(env, "fso_repair").id)
    ro = fo.repair_ids[:1]
    check(ro and ro.lot_id.name == "DEMO-SOLAR-SN-INV-0002", f"{fo.name} (type Repair) → {ro.name}, lot {ro.lot_id.name}")
    mr = env(user=U["svcmgr"])["maintenance.request"].browse(xid(env, "mreq_inv_fan").id)
    check(bool(mr.repair_order_id), f"{mr.name} → {mr.repair_order_id.name}")
    def run_repair():
        r = ro.with_user(U["svcmgr"])
        r.action_validate(); s1 = r.state
        r.action_repair_start(); s2 = r.state
        r.action_repair_end(); s3 = r.state
        check(s3 == "done", f"{r.name}: {s1} → {s2} → {s3} (откат после проверки)")
    rollback_block(run_repair)

# 10. Учёт времени.
with scenario("10 учёт времени", "demo-tech"):
    fo = env(user=U["tech"])["fsm.order"].browse(xid(env, "fso_install").id)
    def add_ts():
        before = sum(fo.timesheet_ids.mapped("unit_amount"))
        env(user=U["tech"])["account.analytic.line"].create({
            "name": "DEMO-SOLAR verify: torque check", "project_id": fo.project_id.id,
            "task_id": fo.project_task_id.id, "fsm_order_id": fo.id, "unit_amount": 0.5})
        fo.invalidate_recordset()
        after = sum(fo.timesheet_ids.mapped("unit_amount"))
        check(after == before + 0.5, f"{fo.name}: {before} ч → {after} ч (запись техника, откат)")
    rollback_block(add_ts)
    prj = env(user=U["pm"])["project.project"].browse(xid(env, "project_epc").id)
    check(prj.total_timesheet_time > 0, f"проект: всего {sum(prj.timesheet_ids.mapped('unit_amount'))} ч")

# 11a. Запрос подписи из FSM-заказа (подпись ставится через портал — scripts/ui-sign).
with scenario("11a запрос подписи из FSM-заказа", "demo-pm"):
    fo = env(user=U["pm"])["fsm.order"].browse(xid(env, "fso_install").id)
    if not fo.sign_request_ids:
        fo.action_request_document_signature()
    req = fo.sign_request_ids[:1]
    bind(env, "sign_request_fo001", req)
    signer = req.signer_ids[:1]
    check(signer.partner_id == xid(env, "partner_customer"), f"{req.name}: signer {signer.partner_id.name}, state {req.state}")
    # ссылку подписанта выводит локально scripts/sign-link.sh (в логи не пишем)

# Изоляция почты: обработать очередь и убедиться, что ничего не ушло наружу.
with scenario("mail изоляция исходящей почты", "system"):
    env["mail.mail"].sudo().process_email_queue()
    mails = env["mail.mail"].sudo().search([])
    sent = mails.filtered(lambda m: m.state == "sent")
    check(not sent, f"mail.mail: {len(mails)} всего, sent={len(sent)}, "
                    f"exception={len(mails.filtered(lambda m: m.state == 'exception'))}")
    reasons = set(mails.mapped(lambda m: (m.failure_reason or "")[:80]))
    check(all(not r or "refused" in r.lower() or "connect" in r.lower() for r in reasons), f"причины: {reasons}")
