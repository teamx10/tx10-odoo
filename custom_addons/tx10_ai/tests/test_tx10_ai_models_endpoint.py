from unittest.mock import MagicMock, patch
from odoo.tests import TransactionCase, tagged

from odoo.addons.tx10_ai.controllers._guards import check_authorized, check_rate_limit, RATE_LIMIT_MAX_CALLS


@tagged("tx10_ai", "post_install", "-at_install")
class TestTx10AiGuards(TransactionCase):
    def test_admin_always_authorized(self):
        check_authorized(self.env)  # admin — must not raise

    def test_rate_limit_allows_under_limit(self):
        self.assertTrue(check_rate_limit(99999))

    def test_rate_limit_blocks_over_limit(self):
        from odoo.addons.tx10_ai.controllers._guards import _rate_limit_state
        _rate_limit_state[99998] = [__import__("time").monotonic()] * RATE_LIMIT_MAX_CALLS
        try:
            self.assertFalse(check_rate_limit(99998))
        finally:
            _rate_limit_state.pop(99998, None)
