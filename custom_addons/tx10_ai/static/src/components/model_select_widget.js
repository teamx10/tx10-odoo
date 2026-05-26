/** @odoo-module */
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ModelSelectWidget extends Component {
    static template = "tx10_ai.ModelSelectWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.inputRef = useRef("input");
        this._lastValid = this.props.record.data[this.props.name] || "";
        this.state = useState({
            query: this._lastValid,
            isOpen: false,
            models: [],
            loading: false,
            error: null,
            invalid: false,
            activeId: null,
        });
        this._blurTimer = null;
        onMounted(() => this._loadModels());
        onWillUnmount(() => clearTimeout(this._blurTimer));
    }

    async _loadModels() {
        this.state.loading = true;
        try {
            const resp = await fetch("/tx10_ai/openrouter/models");
            if (!resp.ok) throw new Error(resp.statusText);
            const data = await resp.json();
            this.state.models = data.models || [];
        } catch (e) {
            this.state.error = "Could not load model list";
        } finally {
            this.state.loading = false;
        }
    }

    get groups() {
        const q = (this.state.query || "").toLowerCase();
        const map = {};
        for (const m of this.state.models) {
            if (q && !m.id.toLowerCase().includes(q) && !m.name.toLowerCase().includes(q)) {
                continue;
            }
            if (!map[m.provider]) map[m.provider] = [];
            map[m.provider].push(m);
        }
        return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
    }

    get flatModels() {
        return this.groups.flatMap(([, models]) => models);
    }

    get currentModel() {
        return this.state.models.find((m) => m.id === this.state.query) || null;
    }

    optId(modelId) {
        return "tx10_ai_opt_" + modelId.replace(/[^a-zA-Z0-9]/g, "_");
    }

    onInput = (ev) => {
        this.state.query = ev.target.value;
        this.state.isOpen = true;
        this.state.invalid = false;
        this.state.activeId = null;
    };

    onFocus = () => {
        if (this.state.models.length) this.state.isOpen = true;
    };

    onKeydown = (ev) => {
        const list = this.flatModels;
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.state.isOpen = true;
            const i = list.findIndex((m) => m.id === this.state.activeId);
            const next = list[Math.min(i + 1, list.length - 1)] || list[0];
            if (next) this.state.activeId = next.id;
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            const i = list.findIndex((m) => m.id === this.state.activeId);
            const prev = i > 0 ? list[i - 1] : list[0];
            if (prev) this.state.activeId = prev.id;
        } else if (ev.key === "Enter") {
            if (this.state.isOpen && this.state.activeId) {
                ev.preventDefault();
                this.onSelect(this.state.activeId);
            }
        } else if (ev.key === "Escape") {
            this.state.isOpen = false;
        }
    };

    onBlur = () => {
        this._blurTimer = setTimeout(() => {
            this.state.isOpen = false;
            const q = this.state.query;
            if (!q) {
                this._lastValid = "";
                this._commit("");
            } else if (this.currentModel) {
                this._lastValid = q;
                this._commit(q);
            } else {
                this.state.query = this._lastValid;
                this.state.invalid = true;
            }
        }, 150);
    };

    onSelect = (modelId) => {
        clearTimeout(this._blurTimer);
        this._lastValid = modelId;
        this.state.query = modelId;
        this.state.isOpen = false;
        this.state.invalid = false;
        this.state.activeId = null;
        this._commit(modelId);
    };

    _commit = (value) => {
        this.props.record.update({ [this.props.name]: value || "" });
    };

    formatPrice = (model) => {
        const fmt = (n) => n == null ? "?" : Number(n).toFixed(2).replace(/\.?0+$/, "");
        return `$${fmt(model.pricing_in)} / $${fmt(model.pricing_out)}`;
    };
}

registry.category("fields").add("tx10_ai_model_select", {
    component: ModelSelectWidget,
    supportedTypes: ["char"],
});
