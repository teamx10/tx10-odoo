# Закупка комплектации у поставщика → приёмка с серийными номерами.
# FSM-оборудование создаётся штатно при проведении приёмки (fieldservice_equipment_stock).

vendor = xid(env, "partner_vendor")
LINES = [  # (товар, кол-во, префикс серийника)
    ("prod_inv", 2, "DEMO-SOLAR-SN-INV-"),
    ("prod_pv", 4, "DEMO-SOLAR-SN-PV-"),
    ("prod_mtr", 1, "DEMO-SOLAR-SN-MTR-"),
    ("prod_fuse", 10, None),
]

po = xid(env, "po_initial")
if not po:
    po = ensure(env, "po_initial", "purchase.order", {
        "partner_id": vendor.id,
        "partner_ref": "DEMO-SOLAR-PO-001",
        "origin": "DEMO-SOLAR-PRJ-001 equipment",
        "order_line": [(0, 0, {
            "product_id": xid(env, k).product_variant_id.id, "product_qty": q,
        }) for k, q, _ in LINES],
    })
if po.state in ("draft", "sent"):
    po.button_confirm()
    LOG.append(f"PO {po.name} confirmed")

receipt = po.picking_ids.filtered(lambda p: p.picking_type_code == "incoming")[:1]
bind(env, "receipt_initial", receipt)
if receipt.state != "done":
    receipt.action_assign()
    for k, qty, prefix in LINES:
        move = receipt.move_ids.filtered(lambda m: m.product_id.product_tmpl_id == xid(env, k))
        if prefix:
            move.move_line_ids.unlink()
            move.write({"move_line_ids": [(0, 0, {
                "product_id": move.product_id.id, "lot_name": f"{prefix}{i:04d}",
                "quantity": 1, "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
                "picking_id": receipt.id,
            }) for i in range(1, qty + 1)]})
        else:
            move.quantity = qty
        move.picked = True
    res = receipt.button_validate()
    LOG.append(f"receipt {receipt.name} validate -> {res if res is not True else 'done'} state={receipt.state}")

# Оборудование, созданное приёмкой: привязываем к станциям и даём стабильные xmlid.
st01, st02 = xid(env, "station_st01"), xid(env, "station_st02")
PLACEMENT = {
    "DEMO-SOLAR-SN-INV-0001": st01, "DEMO-SOLAR-SN-PV-0001": st01, "DEMO-SOLAR-SN-PV-0002": st01,
    "DEMO-SOLAR-SN-MTR-0001": st01,
    "DEMO-SOLAR-SN-PV-0003": st02, "DEMO-SOLAR-SN-PV-0004": st02,
    "DEMO-SOLAR-SN-INV-0002": st02,
}
for lot_name, station in PLACEMENT.items():
    lot = env["stock.lot"].search([("name", "=", lot_name)], limit=1)
    eq = env["fsm.equipment"].search([("lot_id", "=", lot.id)], limit=1) if lot else False
    if not eq:
        LOG.append(f"! equipment for {lot_name} NOT created by receipt")
        continue
    vals = {"location_id": station.id, "current_location_id": station.id}
    if not eq.name.startswith("DEMO-SOLAR"):
        vals["name"] = f"DEMO-SOLAR {eq.name}"
    eq.write(vals)
    bind(env, "fsm_eq_" + lot_name.split("SN-")[1].lower().replace("-", "_"), eq)
    LOG.append(f"  {eq.name} lot={lot.name} station={station.ref} "
               f"warranty {eq.warranty_start_date}..{eq.warranty_end_date} stock_loc={eq.current_stock_location_id.complete_name}")

report("30 purchase & receipt")
