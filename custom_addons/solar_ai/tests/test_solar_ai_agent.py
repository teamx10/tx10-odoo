import json as json_mod

from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("solar_ai", "post_install", "-at_install")
class TestSolarAiModels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env.ref("base.user_admin")

    def test_create_chat_and_message(self):
        """Basic model creation and relationship."""
        chat = self.env["solar.ai.chat"].create({"name": "Test Chat"})
        self.assertEqual(chat.state, "active")
        self.assertEqual(chat.round_count, 0)
        self.assertEqual(chat.total_tokens, 0)

        msg = self.env["solar.ai.message"].create({
            "chat_id": chat.id,
            "role": "user",
            "content": "Hello",
        })
        self.assertIn(msg, chat.message_ids)
        self.assertEqual(msg.status, "done")

    def test_record_rule_isolates_chats(self):
        """Users only see their own chats."""
        user_a = self.env["res.users"].create({
            "name": "User A", "login": "ua@test.local", "password": "ua_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                   self.env.ref("project.group_project_manager").id])],
        })
        user_b = self.env["res.users"].create({
            "name": "User B", "login": "ub@test.local", "password": "ub_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                   self.env.ref("project.group_project_manager").id])],
        })
        chat_a = self.env["solar.ai.chat"].with_user(user_a).create({"name": "A's chat"})
        chats_from_b = self.env["solar.ai.chat"].with_user(user_b).search([])
        self.assertNotIn(chat_a, chats_from_b)

    def test_message_record_rule_isolates_messages(self):
        """Messages are isolated per chat owner via chat_id.user_id = uid."""
        user_a = self.env["res.users"].create({
            "name": "User C", "login": "uc@test.local", "password": "uc_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                   self.env.ref("project.group_project_manager").id])],
        })
        user_b = self.env["res.users"].create({
            "name": "User D", "login": "ud@test.local", "password": "ud_pass",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                   self.env.ref("project.group_project_manager").id])],
        })
        chat_a = self.env["solar.ai.chat"].with_user(user_a).create({"name": "C's chat"})
        msg_a = self.env["solar.ai.message"].with_user(user_a).create({
            "chat_id": chat_a.id, "role": "user", "content": "secret",
        })
        msgs_from_b = self.env["solar.ai.message"].with_user(user_b).search([])
        self.assertNotIn(msg_a, msgs_from_b)
