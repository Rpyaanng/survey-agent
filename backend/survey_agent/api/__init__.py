from flask import Flask


def register_blueprints(app: Flask) -> None:
    from . import (
        auth_routes,
        billing_routes,
        developer_routes,
        integration_routes,
        org_routes,
        public_routes,
        response_routes,
        survey_routes,
    )

    for module in (
        auth_routes,
        org_routes,
        survey_routes,
        response_routes,
        public_routes,
        billing_routes,
        developer_routes,
        integration_routes,
    ):
        app.register_blueprint(module.bp)
