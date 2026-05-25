from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged


def _make_llm_response(content="Hello!", tool_calls=None):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "choices": [{
            "message": {"content": content, "role": "assistant", "tool_calls": tool_calls or []},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
    }
    return mock


def _make_manager_user(env, login):
    return env["res.users"].create({
        "name": login,
        "login": f"{login}@test.local",
        "password": "pass",
        "group_ids": [(6, 0, [
            env.ref("base.group_user").id,
            env.ref("project.group_project_manager").id,
        ])],
    })


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiDiscussHook(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        cls.user = _make_manager_user(cls.env, "hook_user")
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

    def _create_dm_channel(self):
        # Run as self.user so _get_or_create_chat adds self.user.partner_id
        # (the current user's partner) — yielding a 2-person DM: bot + user.
        return self.env["discuss.channel"].with_user(self.user)._get_or_create_chat(
            [self.bot_partner.id, self.user.partner_id.id]
        )

    def _get_or_create_chat(self, channel):
        chat = self.env["tx10.ai.chat"].search([("channel_id", "=", channel.id)], limit=1)
        if not chat:
            chat = self.env["tx10.ai.chat"].create({
                "name": "DM with bot",
                "user_id": self.user.id,
                "channel_id": channel.id,
            })
        return chat

    def test_hook_skips_bot_author(self):
        channel = self._create_dm_channel()
        self._get_or_create_chat(channel)
        msg_count_before = self.env["tx10.ai.message"].search_count([])
        channel.sudo().message_post(
            author_id=self.bot_partner.id,
            body="I am the bot",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self.assertEqual(self.env["tx10.ai.message"].search_count([]), msg_count_before)

    def test_hook_creates_user_message_and_sets_pending(self):
        channel = self._create_dm_channel()
        chat = self._get_or_create_chat(channel)
        channel.with_user(self.user).message_post(
            body="Знайди задачі проекту X",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        msgs = self.env["tx10.ai.message"].search([("chat_id", "=", chat.id), ("role", "=", "user")])
        self.assertTrue(msgs, "Hook must create a tx10.ai.message with role='user'")
        chat.invalidate_recordset()
        self.assertTrue(chat.pending_agent_run)

    def test_hook_ignores_channel_without_bot(self):
        other_channel = self.env["discuss.channel"].create({"name": "No bot channel"})
        msg_count_before = self.env["tx10.ai.message"].search_count([])
        other_channel.with_user(self.user).message_post(
            body="Hi", message_type="comment", subtype_xmlid="mail.mt_comment"
        )
        self.assertEqual(self.env["tx10.ai.message"].search_count([]), msg_count_before)


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiCronAgent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        cls.user = _make_manager_user(cls.env, "cron_user")
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

    def _setup_dm_chat(self):
        channel = self.env["discuss.channel"].with_user(self.user)._get_or_create_chat(
            [self.bot_partner.id, self.user.partner_id.id]
        )
        chat = self.env["tx10.ai.chat"].create({
            "name": "DM",
            "user_id": self.user.id,
            "channel_id": channel.id,
            "pending_agent_run": True,
        })
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "Hello bot"})
        return chat, channel

    @patch("httpx.post")
    def test_cron_posts_bot_reply(self, mock_post):
        mock_post.return_value = _make_llm_response("Привіт! Як можу допомогти?")
        chat, channel = self._setup_dm_chat()
        msgs_before = channel.message_ids.filtered(lambda m: m.author_id == self.bot_partner)
        self.env["tx10.ai.chat"]._cron_run_pending_chats()
        chat.invalidate_recordset()
        self.assertFalse(chat.pending_agent_run)
        msgs_after = channel.message_ids.filtered(lambda m: m.author_id == self.bot_partner)
        self.assertGreater(len(msgs_after), len(msgs_before), "Bot must post a reply to the channel")

    @patch("httpx.post")
    def test_cron_clears_pending_flag(self, mock_post):
        mock_post.return_value = _make_llm_response("OK")
        chat, _ = self._setup_dm_chat()
        self.env["tx10.ai.chat"]._cron_run_pending_chats()
        chat.invalidate_recordset()
        self.assertFalse(chat.pending_agent_run)


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiNlConfirm(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].set_param("tx10_ai.openrouter_api_key", "test-key")
        cls.user = _make_manager_user(cls.env, "confirm_user")
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

    def _make_confirm_tool_response(self, tool_name):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{"id": "tc1", "function": {"name": tool_name, "arguments": "{}"}}],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }
        return mock

    @patch("httpx.post")
    def test_nl_confirm_yes_executes_action(self, mock_post):
        mock_post.return_value = self._make_confirm_tool_response("confirm_action")
        project = self.env["project.project"].with_user(self.user).create({"name": "Test Project NL"})
        channel = self.env["discuss.channel"].with_user(self.user)._get_or_create_chat(
            [self.bot_partner.id, self.user.partner_id.id]
        )
        chat = self.env["tx10.ai.chat"].create({
            "name": "DM", "user_id": self.user.id, "channel_id": channel.id, "pending_agent_run": True,
        })
        pending_msg = self.env["tx10.ai.message"].create({
            "chat_id": chat.id, "role": "assistant", "status": "pending_confirmation",
            "proposed_action": {"model": "project.task", "method": "create",
                                "values": {"name": "New Task NL", "project_id": project.id}},
            "action_summary": "Створити задачу New Task NL",
        })
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "так"})
        chat._do_agent_cycle()
        pending_msg.invalidate_recordset()
        self.assertEqual(pending_msg.status, "confirmed")
        task = self.env["project.task"].search([("name", "=", "New Task NL")])
        self.assertTrue(task, "Task must be created after NL confirm")

    @patch("httpx.post")
    def test_nl_confirm_no_rejects_action(self, mock_post):
        mock_post.return_value = self._make_confirm_tool_response("reject_action")
        channel = self.env["discuss.channel"].with_user(self.user)._get_or_create_chat(
            [self.bot_partner.id, self.user.partner_id.id]
        )
        chat = self.env["tx10.ai.chat"].create({
            "name": "DM", "user_id": self.user.id, "channel_id": channel.id,
        })
        pending_msg = self.env["tx10.ai.message"].create({
            "chat_id": chat.id, "role": "assistant", "status": "pending_confirmation",
            "proposed_action": {"model": "project.task", "method": "create", "values": {"name": "X"}},
            "action_summary": "Створити X",
        })
        self.env["tx10.ai.message"].create({"chat_id": chat.id, "role": "user", "content": "ні"})
        chat._do_agent_cycle()
        pending_msg.invalidate_recordset()
        self.assertEqual(pending_msg.status, "rejected")


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiBootstrap(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot_partner = cls.env.ref("tx10_ai.partner_ai_bot")

    def test_bootstrap_creates_dm_channel(self):
        user = _make_manager_user(self.env, "bootstrap_user")
        user.sudo().write({"tx10_ai_state": "not_initialized"})
        user.with_user(user)._on_webclient_bootstrap()
        channel = self.env["discuss.channel"].search([
            ("channel_type", "=", "chat"),
            ("channel_member_ids.partner_id", "=", self.bot_partner.id),
            ("channel_member_ids.partner_id", "=", user.partner_id.id),
        ])
        self.assertTrue(channel, "Bootstrap must create a DM channel with the bot")
        chat = self.env["tx10.ai.chat"].search([("channel_id", "=", channel.id)])
        self.assertTrue(chat, "Bootstrap must link a tx10.ai.chat to the channel")
        self.assertEqual(chat.user_id, user)

    def test_bootstrap_no_duplicate_on_second_call(self):
        user = _make_manager_user(self.env, "bootstrap_user2")
        user.with_user(user)._on_webclient_bootstrap()
        user.with_user(user)._on_webclient_bootstrap()
        chats = self.env["tx10.ai.chat"].search([("user_id", "=", user.id)])
        self.assertEqual(len(chats), 1, "Second bootstrap must not create duplicate chat")
