// @ts-check
const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
    testDir: "./tests",
    timeout: 60_000,
    expect: { timeout: 10_000 },
    fullyParallel: false,  // Odoo tests share DB state
    retries: 1,
    reporter: [["line"], ["html", { outputFolder: "playwright-report", open: "never" }]],
    use: {
        baseURL: process.env.ODOO_URL || "http://localhost:8069",
        trace: "on-first-retry",
        screenshot: "only-on-failure",
    },
    projects: [
        { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    ],
});
