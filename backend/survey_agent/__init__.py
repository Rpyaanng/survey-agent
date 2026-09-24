"""Survey Agent API: a multi-tenant, AI-powered survey platform."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify

from .config import Config
from .errors import register_error_handlers
from .extensions import cors, db, limiter, migrate

__version__ = "1.0.0"


def create_app(config: type[Config] | None = None) -> Flask:
    load_dotenv()
    config = config or Config.from_env()
    app = Flask(__name__)
    app.config.from_object(config)
    _configure_logging(app)

    if app.config["APP_ENV"] == "production" and app.config["SECRET_KEY"].startswith("dev-insecure"):
        raise RuntimeError("SECRET_KEY must be set in production")

    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(__file__), "..", "migrations"))
    limiter.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Org-Id", "X-Requested-With", "X-Response-Token"],
    )
    register_error_handlers(app)

    from . import models  # noqa: F401  (register tables with SQLAlchemy)
    from .api import register_blueprints

    register_blueprints(app)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "version": __version__})

    from .cli import register_cli

    register_cli(app)
    return app


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("urllib3", "werkzeug", "httpx", "httpx2", "httpcore2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
