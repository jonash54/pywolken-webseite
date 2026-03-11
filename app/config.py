import os


def load_config(app):
    app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", "/data/uploads")
    app.config["OUTPUT_FOLDER"] = os.environ.get("OUTPUT_FOLDER", "/data/output")
    app.config["MAX_CONTENT_LENGTH"] = 540 * 1024 * 1024  # 540 MB
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    app.config["CELERY_BROKER_URL"] = os.environ.get(
        "CELERY_BROKER_URL", "redis://redis:6379/0"
    )
    app.config["CELERY_RESULT_BACKEND"] = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://redis:6379/0"
    )
    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://redis:6379/1")
    app.config["RATE_LIMIT_MAX"] = int(os.environ.get("RATE_LIMIT_MAX", "5"))
    app.config["RATE_LIMIT_WINDOW"] = int(os.environ.get("RATE_LIMIT_WINDOW", "3600"))
    app.config["FILE_EXPIRY_SECONDS"] = 3600
    app.config["MAX_QUEUE_DEPTH"] = int(os.environ.get("MAX_QUEUE_DEPTH", "10"))
    app.config["PAYPAL_DONATE_URL"] = os.environ.get("PAYPAL_DONATE_URL", "")
    app.config["MIN_RESOLUTION"] = 0.1
    app.config["MAX_RESOLUTION"] = 10.0
