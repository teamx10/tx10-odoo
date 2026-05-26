// @ts-check
/**
 * E2E tests for tx10_ai module.
 *
 * Test matrix:
 *   T-NAV  — solar_ai completely gone from UI
 *   T-SYS  — systray button opens floating DM chat
 *   T-DISC — Discuss page shows bot in DM sidebar
 *   T-SET  — Settings > Project shows "TeamX10 AI Assistant", no "Solar AI"
 *   T-ERR  — Empty API key → bot replies with Ukrainian friendly error (no silence)
 *   T-ADM  — Admin sees error_code suffix in bot reply
 */

const { test, expect } = require("@playwright/test");
const { loginAsAdmin, openAiChatViaSystray, setApiKey } = require("./helpers");

// ─── Auth fixture ─────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
});

// ─── T-NAV: No Solar AI traces anywhere ───────────────────────────────────────

test("T-NAV: no Solar AI references in navbar or systray", async ({ page }) => {
    await page.goto("/odoo/project");
    await page.waitForSelector(".o_menu_systray");

    // Use "Solar AI" to avoid matching unrelated buttons like company switcher "iSolar Energy"
    const solarBtn = page.locator('button[aria-label*="Solar AI"], button[title*="Solar AI"]');
    await expect(solarBtn).toHaveCount(0);

    // Only ONE AI button visible
    const aiBtn = page.locator('button[aria-label="TeamX10 AI"]');
    await expect(aiBtn).toHaveCount(1);
});

// ─── T-SYS: Systray click opens floating DM ───────────────────────────────────

test("T-SYS: systray button opens TeamX10 AI floating chat", async ({ page }) => {
    await page.goto("/odoo/project");

    const chatWindow = await openAiChatViaSystray(page);
    await expect(chatWindow).toBeVisible();

    // Header shows bot name
    await expect(chatWindow.locator("text=TeamX10 AI").first()).toBeVisible();

    // Input is ready
    await expect(chatWindow.locator('[placeholder*="Message TeamX10 AI"]')).toBeVisible();
});

test("T-SYS: systray button is idempotent — second click doesn't open duplicate", async ({ page }) => {
    await page.goto("/odoo/project");
    const btn = page.locator('button[aria-label="TeamX10 AI"]');
    await btn.click();
    await page.locator(".o-mail-ChatWindow").filter({ hasText: "TeamX10 AI" }).waitFor();
    // Second click — should not create duplicate
    await btn.click();
    const windows = page.locator(".o-mail-ChatWindow").filter({ hasText: "TeamX10 AI" });
    await expect(windows).toHaveCount(1);
});

// ─── T-DISC: Discuss page shows bot DM ───────────────────────────────────────

test("T-DISC: Discuss sidebar shows TeamX10 AI direct message", async ({ page }) => {
    await page.goto("/odoo/discuss");
    await page.waitForSelector(".o-mail-DiscussSidebar");

    // "TeamX10 AI" DM appears under Direct messages
    const dm = page.locator(".o-mail-DiscussSidebar").getByText("TeamX10 AI");
    await expect(dm).toBeVisible();
});

test("T-DISC: opening TeamX10 AI DM from Discuss shows conversation", async ({ page }) => {
    await page.goto("/odoo/discuss");
    await page.locator(".o-mail-DiscussSidebar").getByText("TeamX10 AI").click();
    // Bot greeting should be visible in the thread
    await expect(page.locator("text=TeamX10 AI assistant")).toBeVisible({ timeout: 10_000 });
});

// ─── T-SET: Settings page ─────────────────────────────────────────────────────

test("T-SET: Settings > Project shows TeamX10 AI Assistant section", async ({ page }) => {
    await page.goto("/odoo/settings#project");
    await page.waitForSelector("text=Project");

    await expect(page.locator("text=TeamX10 AI Assistant")).toBeVisible();
    await expect(page.locator("text=OpenRouter API Key")).toBeVisible();
});

test("T-SET: Settings > Project has no Solar AI section", async ({ page }) => {
    await page.goto("/odoo/settings#project");
    await page.waitForSelector("text=Project");

    await expect(page.locator("text=Solar AI")).toHaveCount(0);
    await expect(page.locator("text=solar_ai")).toHaveCount(0);
});

test("T-SET: Settings page loads without OWL error", async ({ page }) => {
    const errors = [];
    page.on("console", (msg) => {
        if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto("/odoo/settings");
    await page.locator("text=General Settings").first().waitFor();
    await page.locator("a:has-text('Project')").click();
    await page.locator("text=TeamX10 AI Assistant").waitFor();

    // No OWL lifecycle errors about undefined fields
    const owlErrors = errors.filter((e) => e.includes("field is undefined") || e.includes("solar_ai"));
    expect(owlErrors).toHaveLength(0);
});

// ─── T-ERR: Error surfacing — no silence on empty API key ─────────────────────

test("T-ERR: empty API key → bot replies with Ukrainian error (no silence)", async ({ page }) => {
    await page.goto("/odoo/project");

    // Ensure API key is empty
    await setApiKey(page, "");

    const chatWindow = await openAiChatViaSystray(page);
    const input = chatWindow.locator('[placeholder*="Message TeamX10 AI"]');

    // Count bot messages before sending
    const botMsgsBefore = await page.evaluate(() => {
        const debug = window.odoo.__WOWL_DEBUG__;
        const orm = debug.root.env.services.orm;
        return orm.searchCount("mail.message", [
            ["model", "=", "discuss.channel"],
            ["author_id.name", "=", "TeamX10 AI"],
        ]);
    });

    await input.fill("Тест помилки");
    await input.press("Enter");

    // Wait for bot reply (cron fires within 60s in test env)
    await expect(async () => {
        const count = await page.evaluate(() => {
            const debug = window.odoo.__WOWL_DEBUG__;
            const orm = debug.root.env.services.orm;
            return orm.searchCount("mail.message", [
                ["model", "=", "discuss.channel"],
                ["author_id.name", "=", "TeamX10 AI"],
            ]);
        });
        expect(count).toBeGreaterThan(botMsgsBefore);
    }).toPass({ timeout: 65_000, intervals: [3000] });

    // Reload and re-open chat to see reply
    await page.reload();
    await loginAsAdmin(page);
    await page.goto("/odoo/project");
    const chatWindow2 = await openAiChatViaSystray(page);

    // Ukrainian "not configured" message must appear (may be several from prior runs)
    await expect(chatWindow2.locator("text=налаштовано").first()).toBeVisible({ timeout: 10_000 });
});

// ─── T-ADM: Admin sees error code ─────────────────────────────────────────────

test("T-ADM: admin sees error code suffix in bot error reply", async ({ page }) => {
    await page.goto("/odoo/project");

    // Trigger a FRESH error in this run rather than reading stale DB state.
    await setApiKey(page, "");

    const readLatestBotBody = () =>
        page.evaluate(async () => {
            const debug = window.odoo.__WOWL_DEBUG__;
            const orm = debug.root.env.services.orm;
            const msgs = await orm.searchRead(
                "mail.message",
                [
                    ["model", "=", "discuss.channel"],
                    ["author_id.name", "=", "TeamX10 AI"],
                ],
                ["id", "body"],
                { limit: 1, order: "id desc" },
            );
            return msgs[0] ?? null;
        });

    await page.waitForFunction(
        () => window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.orm,
        { timeout: 20_000 },
    );
    const before = await readLatestBotBody();
    const beforeId = before?.id ?? 0;

    const chatWindow = await openAiChatViaSystray(page);
    const input = chatWindow.locator('[placeholder*="Message TeamX10 AI"]');
    await input.fill("Перевірка коду помилки");
    await input.press("Enter");

    // Wait for a NEW bot message (cron fires within ~60s in test env)
    let latest = null;
    await expect(async () => {
        latest = await readLatestBotBody();
        expect(latest && latest.id > beforeId).toBeTruthy();
    }).toPass({ timeout: 65_000, intervals: [3000] });

    // Admin (base.group_system) must see the "— код: ..." technical suffix
    expect(latest.body).toContain("код:");
});
