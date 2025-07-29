from flask import Flask
import json

with open(".env", "r") as f:
    env = json.load(f)


def create_app():
    run = Flask(__name__)
    run.config["SECRET_KEY"] = env["SECRET_KEY"]

    from app import app

    run.register_blueprint(app, url_prefix="/")

    return run


def main():
    app = create_app()
    app.run(debug=True)
    # app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
