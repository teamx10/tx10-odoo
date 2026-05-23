/** @odoo-module */
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class AiAssistantPanel extends Component {
    static template = "solar_ai.AiAssistantPanel";
    static props = { onClose: Function };

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            messages: [],
            inputValue: "",
            thinking: false,
            chatId: null,
        });
        this.composerRef = useRef("composer");
        onMounted(() => this.composerRef.el?.focus());
    }

    get examplePrompts() {
        return [
            _t("Знайди контакт Іванов"),
            _t("Відкрий список проєктів"),
            _t("Яка інформація по проєкту X?"),
        ];
    }

    async sendMessage(text) {
        text = (text || this.state.inputValue).trim();
        if (!text || this.state.thinking) return;

        this.state.messages.push({ role: "user", content: text });
        this.state.inputValue = "";
        this.state.thinking = true;

        await this._runAgentLoop(text, null);
        this.state.thinking = false;
    }

    async _runAgentLoop(userMessage, toolResults, maxRounds = 10) {
        let round = 0;
        let pendingUserMessage = userMessage;
        let pendingToolResults = toolResults;

        while (round < maxRounds) {
            round++;
            let resp;
            try {
                resp = await this.rpc("/solar_ai/agent/step", {
                    message: pendingUserMessage,
                    chat_id: this.state.chatId,
                    tool_results: pendingToolResults,
                });
            } catch (e) {
                this.state.messages.push({ role: "error", content: _t("Connection error. Try again.") });
                return;
            }

            this.state.chatId = resp.chat_id;
            pendingUserMessage = null;

            if (resp.status === "error" || resp.status === "budget_exhausted") {
                const errMsg = resp.error === "budget_exhausted"
                    ? _t("Ліміт запитів вичерпано для цього чату.")
                    : _t("Помилка: ") + (resp.error || "unknown");
                this.state.messages.push({ role: "error", content: errMsg });
                return;
            }

            if (resp.assistant_text) {
                this.state.messages.push({ role: "assistant", content: resp.assistant_text });
            }

            if (resp.status === "ok") return;

            const clientResults = await this._executeClientTools(resp.client_tool_calls || []);
            pendingToolResults = [...(resp.tool_results || []), ...clientResults];
        }

        this.state.messages.push({ role: "error", content: _t("Досягнуто ліміт кроків.") });
    }

    async _executeClientTools(toolCalls) {
        const results = [];
        for (const tc of toolCalls) {
            try {
                if (tc.name === "navigate_to_record") {
                    await this.action.doAction({
                        type: "ir.actions.act_window",
                        res_model: tc.args.model,
                        res_id: tc.args.id,
                        views: [[false, "form"]],
                    });
                    results.push({ tool_call_id: tc.tool_call_id, content: "navigated" });
                } else if (tc.name === "open_model_list") {
                    await this.action.doAction({
                        type: "ir.actions.act_window",
                        res_model: tc.args.model,
                        views: [[false, "list"]],
                    });
                    results.push({ tool_call_id: tc.tool_call_id, content: "opened_list" });
                }
            } catch (e) {
                results.push({ tool_call_id: tc.tool_call_id, content: `error: ${e.message}` });
            }
        }
        return results;
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
        if (ev.key === "Escape") {
            this.props.onClose();
        }
    }
}
