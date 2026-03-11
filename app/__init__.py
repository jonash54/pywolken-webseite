import os
from flask import Flask
from .config import load_config


def create_app():
    app = Flask(__name__)
    load_config(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

    from .routes import bp
    app.register_blueprint(bp)

    return app
