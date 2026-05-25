{
    "name": "Solar AI",
    "version": "19.0.1.1.0",
    "summary": "AI-first document processing and agentic assistant for solar projects",
    "category": "Project",
    "depends": ["solar_project", "base_setup", "project", "mail", "web"],
    "external_dependencies": {"python": ["httpx"]},
    "data": [
        "security/ir.model.access.csv",
        "security/solar_ai_security.xml",
        "data/config_params.xml",
        "views/solar_ai_chat_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "solar_ai/static/src/systray/ai_assistant_systray.js",
            "solar_ai/static/src/systray/ai_assistant_systray.xml",
            "solar_ai/static/src/components/ai_assistant_panel.js",
            "solar_ai/static/src/components/ai_assistant_panel.xml",
            "solar_ai/static/src/components/ai_assistant_panel.scss",
            "solar_ai/static/src/components/model_select_widget.js",
            "solar_ai/static/src/components/model_select_widget.xml",
            "solar_ai/static/src/components/model_select_widget.scss",
        ],
        "web.assets_tests": [
            "solar_ai/static/tests/tours/ai_panel.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
