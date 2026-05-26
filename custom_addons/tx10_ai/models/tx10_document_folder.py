from odoo import api, fields, models

FOLDER_TEMPLATE = [
    (["01_Вхідні_дані"], "root_input"),
    (["01_Вхідні_дані", "01_Опитувальний_лист"], "survey"),
    (["01_Вхідні_дані", "01_Опитувальний_лист", "01_Оригінал"], "survey_orig"),
    (["01_Вхідні_дані", "01_Опитувальний_лист", "02_Додатки"], "survey_attachments"),
    (["01_Вхідні_дані", "02_Технічні_каталоги"], "catalogs"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "01_Сонячні_модулі"], "01_Сонячні_модулі"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "02_Інвертори"], "02_Інвертори"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "03_Акумулятори"], "03_Акумулятори"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "04_BMS_PDU"], "04_BMS_PDU"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "05_BOS_обладнання"], "05_BOS_обладнання"),
    (["01_Вхідні_дані", "02_Технічні_каталоги", "06_Інше_обладнання"], "06_Інше_обладнання"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника"], "customer_materials"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "01_Фото"], "01_Фото"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "02_Схеми"], "02_Схеми"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "03_Споживання_та_рахунки"], "03_Споживання_та_рахунки"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "04_ТУ_договори_облік"], "04_ТУ_договори_облік"),
    (["01_Вхідні_дані", "03_Матеріали_від_замовника", "05_Інше"], "05_Інше"),
    (["03_Розрахунки"], "root_calculations"),
    (["03_Розрахунки", "02_PVsyst"], "pvsyst"),
    (["03_Розрахунки", "02_PVsyst", "01_Reports"], "pvsyst_reports"),
    (["03_Розрахунки", "02_PVsyst", "02_Project_Files"], "pvsyst_projects"),
    (["03_Розрахунки", "02_PVsyst", "03_Export"], "pvsyst_export"),
    (["03_Розрахунки", "04_SolarEdge_Designer"], "solaredge"),
    (["03_Розрахунки", "05_K2"], "k2"),
]


class Tx10DocumentFolder(models.Model):
    _name = "tx10.document.folder"
    _description = "Document Folder"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "complete_name"
    _order = "complete_name"

    name = fields.Char(required=True)
    project_id = fields.Many2one("project.project", required=True, ondelete="cascade", index=True)
    parent_id = fields.Many2one("tx10.document.folder", ondelete="cascade", index=True)
    child_ids = fields.One2many("tx10.document.folder", "parent_id")
    parent_path = fields.Char(index=True)
    complete_name = fields.Char(compute="_compute_complete_name", store=True, recursive=True)
    folder_code = fields.Char(index=True)
    document_ids = fields.One2many("solar.document", "folder_id")

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for folder in self:
            if folder.parent_id:
                folder.complete_name = f"{folder.parent_id.complete_name} / {folder.name}"
            else:
                folder.complete_name = folder.name

    @api.model
    def _ensure_tree(self, project):
        Folder = self.sudo()
        cache = {}

        for path_parts, folder_code in FOLDER_TEMPLATE:
            key = tuple(path_parts)
            parent_key = tuple(path_parts[:-1]) if len(path_parts) > 1 else None
            parent = cache.get(parent_key) if parent_key else None

            domain = [("project_id", "=", project.id), ("name", "=", path_parts[-1])]
            if parent:
                domain.append(("parent_id", "=", parent.id))
            else:
                domain.append(("parent_id", "=", False))

            folder = Folder.search(domain, limit=1)
            if not folder:
                vals = {
                    "name": path_parts[-1],
                    "project_id": project.id,
                    "folder_code": folder_code,
                }
                if parent:
                    vals["parent_id"] = parent.id
                folder = Folder.create(vals)
            elif not folder.folder_code:
                folder.folder_code = folder_code

            cache[key] = folder

        return cache

    @api.model
    def get_folder_by_code(self, project, code):
        return self.sudo().search(
            [("project_id", "=", project.id), ("folder_code", "=", code)], limit=1,
        )
