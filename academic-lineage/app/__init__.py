"""Flask app factory for the academic lineage local tool."""
from pathlib import Path

from flask import Flask, render_template

from . import db
from .config import Config

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_mapping(
        DATABASE=Config.DATABASE,
        PUBLIC_DATA_DIR=Config.PUBLIC_DATA_DIR,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    db.init_db(app)

    from . import routes

    app.register_blueprint(routes.bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
