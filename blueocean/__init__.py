"""Blue Ocean Finder Flask application factory."""
from __future__ import annotations

import logging

from flask import Flask

import config as app_config


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=app_config.SECRET_KEY,
        DEBUG=app_config.DEBUG,
        PORT=app_config.PORT,
        JSON_SORT_KEYS=False,
    )

    logging.basicConfig(
        level=logging.DEBUG if app_config.DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from .routes.pages import bp as pages_bp
    from .routes.api import bp as api_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(404)
    def not_found(_e):
        from flask import jsonify, request

        if request.path.startswith("/api/"):
            return jsonify(error={"code": "NOT_FOUND", "message": "리소스를 찾을 수 없습니다."}), 404
        return "Not Found", 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import jsonify, request

        logging.getLogger(__name__).exception("Unhandled server error: %s", e)
        if request.path.startswith("/api/"):
            return jsonify(error={"code": "INTERNAL", "message": "서버 오류가 발생했습니다."}), 500
        return "Internal Server Error", 500

    return app
