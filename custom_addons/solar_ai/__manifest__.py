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
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
