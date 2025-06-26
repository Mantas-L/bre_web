from flask import Flask


def create_app():
    run = Flask(__name__)
    run.config["SECRET_KEY"] = "Let's keep this just between you and me, okay? 😉"

    from .app import app

    run.register_blueprint(app, url_prefix="/")

    return run
