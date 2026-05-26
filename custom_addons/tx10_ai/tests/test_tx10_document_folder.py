from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTx10DocumentFolderTree(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create({"name": "Test Solar P1"})
        cls.project2 = cls.env["project.project"].create({"name": "Test Solar P2"})

    def test_ensure_tree_creates_24_folders(self):
        Folder = self.env["tx10.document.folder"]
        Folder._ensure_tree(self.project)
        count = Folder.search_count([("project_id", "=", self.project.id)])
        self.assertEqual(count, 24)

    def test_ensure_tree_idempotent(self):
        Folder = self.env["tx10.document.folder"]
        Folder._ensure_tree(self.project)
        Folder._ensure_tree(self.project)
        count = Folder.search_count([("project_id", "=", self.project.id)])
        self.assertEqual(count, 24)

    def test_tree_isolation_between_projects(self):
        Folder = self.env["tx10.document.folder"]
        Folder._ensure_tree(self.project)
        Folder._ensure_tree(self.project2)
        p1_count = Folder.search_count([("project_id", "=", self.project.id)])
        p2_count = Folder.search_count([("project_id", "=", self.project2.id)])
        self.assertEqual(p1_count, 24)
        self.assertEqual(p2_count, 24)
        # no cross-contamination
        total = Folder.search_count([
            ("project_id", "in", [self.project.id, self.project2.id]),
        ])
        self.assertEqual(total, 48)

    def test_complete_name_computed(self):
        Folder = self.env["tx10.document.folder"]
        Folder._ensure_tree(self.project)
        folder = Folder.get_folder_by_code(self.project, "02_Інвертори")
        self.assertIn("02_Інвертори", folder.complete_name)
        # must show full path with separators
        self.assertIn(" / ", folder.complete_name)

    def test_get_folder_by_code_known(self):
        Folder = self.env["tx10.document.folder"]
        Folder._ensure_tree(self.project)
        folder = Folder.get_folder_by_code(self.project, "01_Фото")
        self.assertTrue(folder)
        self.assertEqual(folder.folder_code, "01_Фото")

    def test_get_folder_by_code_unknown_returns_empty(self):
        Folder = self.env["tx10.document.folder"]
        Folder._ensure_tree(self.project)
        folder = Folder.get_folder_by_code(self.project, "nonexistent_code")
        self.assertFalse(folder)
