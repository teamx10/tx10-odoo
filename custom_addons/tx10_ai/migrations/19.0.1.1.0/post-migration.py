from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # The chat/message ir.rule records are noupdate="1", so the security fix that
    # extends own-chat isolation to project_user (was project_manager only) does not
    # propagate on a normal module update. Force it here to close the IDOR on
    # existing installs.
    env = api.Environment(cr, SUPERUSER_ID, {})
    user_group = env.ref("project.group_project_user", raise_if_not_found=False)
    if not user_group:
        return
    for xmlid in ("tx10_ai.rule_tx10_ai_chat_user", "tx10_ai.rule_tx10_ai_message_user"):
        rule = env.ref(xmlid, raise_if_not_found=False)
        if rule:
            rule.write({"groups": [(6, 0, [user_group.id])]})
