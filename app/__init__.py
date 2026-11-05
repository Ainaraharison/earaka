import os
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import init_extensions


def create_app(config_class=Config):
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp"),
        static_url_path="",
    )
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    init_extensions(app)

    from .routes import register_blueprints
    register_blueprints(app)

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Route introuvable"}), 404
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Méthode non autorisée"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Erreur serveur interne"}), 500

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app
