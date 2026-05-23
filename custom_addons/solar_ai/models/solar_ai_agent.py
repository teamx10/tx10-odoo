import json
import logging
from datetime import date

from odoo import models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class SolarAiAgent(models.AbstractModel):
    _name = "solar.ai.agent"
    _description = "Solar AI — Tool Registry and Dispatcher"

    # Single source of truth for model permissions (v2 fix M21).
    # Extend by overriding _get_model_registry() in sibling modules via super().
    _MODEL_REGISTRY = {
        "project.project": {
            "capabilities": {"read", "navigate", "write"},
            "write_fields": {"name", "description", "user_id", "date_start", "date"},
            "read_fields": ["id", "name", "description", "user_id"],
        },
        "project.task": {
            "capabilities": {"read", "navigate", "write"},
            "write_fields": {"name", "description", "user_id", "project_id",
                             "date_deadline", "stage_id"},
            "read_fields": ["id", "name", "description", "user_id", "project_id", "stage_id"],
        },
        "res.partner": {
            "capabilities": {"read", "navigate", "write"},
            "write_fields": {"name", "email", "phone", "mobile", "comment"},
            "read_fields": ["id", "name", "email", "phone"],
        },
        "solar.document": {
            "capabilities": {"read", "navigate"},
            "write_fields": set(),
            "read_fields": ["id", "name", "document_type_id"],
        },
    }

    def _get_model_registry(self):
        return dict(self._MODEL_REGISTRY)

    def _get_allowed_models(self):
        return {m: d["capabilities"] for m, d in self._get_model_registry().items()}

    def _get_allowed_fields(self):
        return {m: d["write_fields"]
                for m, d in self._get_model_registry().items()
                if d["write_fields"]}

    def _get_safe_read_fields(self, model):
        return self._get_model_registry().get(model, {}).get("read_fields", ["id", "name"])

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------

    def _get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "find_records",
                    "description": "Search for records by display name. Returns id + display_name list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string", "description": "Odoo model technical name"},
                            "query": {"type": "string", "description": "Search text (display name match)"},
                            "limit": {"type": "integer", "description": "Max results 1-20", "default": 5},
                        },
                        "required": ["model", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_record_summary",
                    "description": "Get key fields of a specific record by id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string"},
                            "id": {"type": "integer"},
                        },
                        "required": ["model", "id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "navigate_to_record",
                    "description": "Open a specific record form view in the user's browser. Executed client-side.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string"},
                            "id": {"type": "integer"},
                        },
                        "required": ["model", "id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "open_model_list",
                    "description": "Open the list view for a model in the browser. Executed client-side.",
                    "parameters": {
                        "type": "object",
                        "properties": {"model": {"type": "string"}},
                        "required": ["model"],
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    _CLIENT_TOOLS = {"navigate_to_record", "open_model_list"}

    _CAPABILITY_MAP = {
        "find_records": "read",
        "get_record_summary": "read",
        "navigate_to_record": "navigate",
        "open_model_list": "navigate",
        # write tools registered in Phase B
    }

    def _check_capability(self, tool_name, model=None):
        allowed = self._get_allowed_models()
        cap = self._CAPABILITY_MAP.get(tool_name)
        if cap is None:
            raise ValueError(f"Unknown tool: {tool_name!r}")
        if model is not None:
            if model not in allowed:
                raise ValueError(f"Model {model!r} is not in the allowed list")
            if cap not in allowed[model]:
                raise ValueError(f"Tool {tool_name!r} (cap={cap!r}) not allowed for {model!r}")

    def _execute_tool(self, tool_name, args):
        """Execute a tool. Raises ValueError on whitelist violation."""
        model = args.get("model")
        self._check_capability(tool_name, model=model)

        if tool_name == "find_records":
            return self._tool_find_records(args)
        if tool_name == "get_record_summary":
            return self._tool_get_record_summary(args)
        if tool_name in self._CLIENT_TOOLS:
            return {"client_tool": tool_name, "args": args}
        raise ValueError(f"Unhandled tool: {tool_name!r}")

    def safe_execute_tool(self, tool_name, args, tool_call_id=""):
        """Wrap _execute_tool; catch ValueError and AccessError as structured results.

        Other exceptions (ORM bugs, DB errors) propagate — do NOT swallow them.
        """
        try:
            result = self._execute_tool(tool_name, args)
            return {"ok": True, "result": result, "tool_call_id_placeholder": tool_call_id}
        except ValueError as exc:
            _logger.warning("solar_ai agent: tool %r validation error: %s", tool_name, exc)
            return {"ok": False, "error": str(exc), "tool_call_id_placeholder": tool_call_id}
        except AccessError as exc:
            _logger.warning("solar_ai agent: tool %r access denied: %s", tool_name, exc)
            return {"ok": False, "error": "access_denied", "tool_call_id_placeholder": tool_call_id}

    # ------------------------------------------------------------------
    # Tool implementations (READ, Phase A)
    # ------------------------------------------------------------------

    def _tool_find_records(self, args):
        model = args["model"]
        query = (args.get("query") or "").strip()
        if not query:
            raise ValueError("query must be a non-empty string")
        try:
            limit = max(1, min(20, int(args.get("limit") or 5)))
        except (TypeError, ValueError):
            limit = 5
        records = self.env[model].name_search(query, limit=limit)
        return [{"id": r[0], "display_name": r[1]} for r in records]

    def _tool_get_record_summary(self, args):
        model = args["model"]
        record_id = int(args["id"])
        safe_fields = self._get_safe_read_fields(model)
        record = self.env[model].browse(record_id)
        if not record.exists():
            return {"error": "record_not_found", "id": record_id, "model": model}
        data = record.read(safe_fields)[0]
        return {k: (v[1] if isinstance(v, tuple) else v) for k, v in data.items()}

    # ------------------------------------------------------------------
    # Validation helper (shared by read and write tools)
    # ------------------------------------------------------------------

    def _validate_write_values(self, model, values):
        allowed = self._get_allowed_fields()
        if model not in allowed:
            raise ValueError(f"Model {model!r} has no write capability")
        bad = set(values.keys()) - allowed[model]
        if bad:
            raise ValueError(f"Fields not in whitelist for {model!r}: {sorted(bad)}")
