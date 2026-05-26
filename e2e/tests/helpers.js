/**
 * Shared helpers for tx10_ai E2E tests.
 */

const BASE_URL = process.env.ODOO_URL || "http://localhost:8069";
const ADMIN_LOGIN = process.env.ODOO_LOGIN || "admin";
const ADMIN_PASSWORD = process.env.ODOO_PASSWORD || "admin";

/**
 * Login to Odoo as admin.
 * @param {import('@playwright/test').Page} page
 */
async function loginAsAdmin(page) {
    await page.goto("/web/login");
    await page.fill("#login", ADMIN_LOGIN);
    await page.fill("#password", ADMIN_PASSWORD);
    await page.click("button[type=submit]");
    await page.waitForURL(/\/odoo/, { timeout: 15_000 });
}

/**
 * Open TeamX10 AI chat via systray button.
 * @param {import('@playwright/test').Page} page
 * @returns {import('@playwright/test').Locator} The chat window locator
 */
async function openAiChatViaSystray(page) {
    const btn = page.locator('button[aria-label="TeamX10 AI"]');
    await btn.waitFor({ timeout: 10_000 });
    await btn.click();
    const chatWindow = page.locator(".o-mail-ChatWindow").filter({ hasText: "TeamX10 AI" });
    await chatWindow.waitFor({ timeout: 10_000 });
    return chatWindow;
}

/**
 * Wait until the OWL web client is fully booted and the ORM service is reachable
 * via window.odoo.__WOWL_DEBUG__. Required before any page.evaluate that uses the ORM.
 * @param {import('@playwright/test').Page} page
 */
async function waitForWowl(page) {
    await page.waitForFunction(
        () => window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.orm,
        { timeout: 20_000 },
    );
}

/**
 * Set OpenRouter API key via SQL-equivalent JSON-RPC.
 * @param {import('@playwright/test').Page} page
 * @param {string} value  empty string = unset
 */
async function setApiKey(page, value) {
    await waitForWowl(page);
    await page.evaluate(async (v) => {
        const debug = window.odoo.__WOWL_DEBUG__;
        const orm = debug.root.env.services.orm;
        const params = await orm.searchRead(
            "ir.config_parameter",
            [["key", "=", "tx10_ai.openrouter_api_key"]],
            ["id"],
            { limit: 1 },
        );
        if (params.length) {
            await orm.write("ir.config_parameter", [params[0].id], { value: v });
        } else {
            await orm.create("ir.config_parameter", [{ key: "tx10_ai.openrouter_api_key", value: v }]);
        }
    }, value);
}

module.exports = { BASE_URL, loginAsAdmin, openAiChatViaSystray, setApiKey, waitForWowl };
