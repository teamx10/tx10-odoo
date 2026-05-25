{
    "name": "TX10 AI",
    "version": "19.0.1.0.0",
    "summary": "TeamX10 AI assistant as a native Discuss bot",
    "category": "Project",
    "depends": ["mail", "project", "solar_project", "base_setup", "web"],
    "external_dependencies": {"python": ["httpx"]},
    "data": [
        "security/ir.model.access.csv",
        "security/tx10_ai_security.xml",
        "data/config_params.xml",
        "data/tx10_ai_bot.xml",
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
        "views/tx10_ai_chat_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "tx10_ai/static/src/components/model_select_widget.js",
            "tx10_ai/static/src/components/model_select_widget.xml",
            "tx10_ai/static/src/components/model_select_widget.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
