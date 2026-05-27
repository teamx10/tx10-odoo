from odoo import SUPERUSER_ID, api

# v1.3.0 removes the custom folder DMS (tx10.document.folder + result line) in
# favour of LLM classification onto solar.document.type. The PR #4 install left
# ir.ui.view / ir.actions records that still reference the dropped folder_id
# field and tx10.document.folder model. They must be unlinked BEFORE the new
# views load, otherwise rebuilding the shared inheritance chains (project form,
# solar.document list) pulls these orphans in and fails view validation.
_OBSOLETE_XMLIDS = [
    "tx10_ai.view_tx10_document_folder_tree",
    "tx10_ai.view_tx10_document_folder_form",
    "tx10_ai.action_tx10_document_folder",
    "tx10_ai.view_project_project_tx10_folders_button",
    "tx10_ai.view_solar_document_list_tx10_folder",
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in _OBSOLETE_XMLIDS:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            record.unlink()
