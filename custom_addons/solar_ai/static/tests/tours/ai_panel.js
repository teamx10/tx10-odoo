/** @odoo-module */
import { registry } from "@web/core/registry";

registry.category("tours").add("ai_panel_open_close", {
    test: true,
    steps: () => [
        {
            trigger: "body:not(:has(#o-solar-ai-panel))",
            content: "Verify panel is closed",
            isCheck: true,
        },
        {
            trigger: ".o-solar-ai-systray-btn",
            content: "Click systray button to open panel",
        },
        {
            trigger: "#o-solar-ai-panel",
            content: "Panel is visible",
            isCheck: true,
        },
        {
            trigger: "#o-solar-ai-panel .btn-close",
            content: "Close the panel",
        },
        {
            trigger: "body:not(:has(#o-solar-ai-panel))",
            content: "Panel is closed again",
            isCheck: true,
        },
    ],
});

registry.category("tours").add("ai_panel_send_empty_ignored", {
    test: true,
    steps: () => [
        {
            trigger: ".o-solar-ai-systray-btn",
            content: "Open panel",
        },
        {
            trigger: "#o-solar-ai-panel",
            content: "Panel open",
            isCheck: true,
        },
        {
            trigger: "#o-solar-ai-panel .btn[aria-label='Send']",
            content: "Send button is disabled (no input)",
        },
        {
            trigger: "body:not(:has(.o-solar-ai-msg--error))",
            content: "No error message appeared",
            isCheck: true,
        },
    ],
});
