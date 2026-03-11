"""Flask routes for file upload, processing, and download."""

import os
import time
import uuid

import redis
from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)

from .i18n import get_translations
from .security import validate_upload

bp = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {"laz", "las", "tif", "tiff"}


def _get_redis():
    url = current_app.config.get("REDIS_URL", "redis://redis:6379/1")
    return redis.from_url(url, decode_responses=True)


def _check_rate_limit(client_ip):
    r = _get_redis()
    key = f"ratelimit:{client_ip}"
    current = r.get(key)
    max_req = current_app.config["RATE_LIMIT_MAX"]
    window = current_app.config["RATE_LIMIT_WINDOW"]

    if current and int(current) >= max_req:
        return False

    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    pipe.execute()
    return True


def _check_queue_depth():
    from .tasks import celery_app

    inspector = celery_app.control.inspect()
    try:
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
        total = sum(len(v) for v in active.values()) + sum(
            len(v) for v in reserved.values()
        )
        return total < current_app.config["MAX_QUEUE_DEPTH"]
    except Exception:
        return True


def _get_file_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("laz", "las"):
        return "laz"
    if ext in ("tif", "tiff"):
        return "tif"
    return None


@bp.route("/")
def index():
    lang = request.args.get("lang", request.accept_languages.best_match(["de", "en"], default="en"))
    if lang not in ("en", "de"):
        lang = "en"
    t = get_translations(lang)
    return render_template("index.html", t=t, lang=lang)


@bp.route("/upload", methods=["POST"])
def upload():
    lang = request.form.get("lang", "en")
    if lang not in ("en", "de"):
        lang = "en"
    t = get_translations(lang)

    client_ip = request.headers.get("X-Real-IP", request.remote_addr)
    if not _check_rate_limit(client_ip):
        return jsonify({"error": t["rate_limited"]}), 429

    if not _check_queue_depth():
        return jsonify({"error": t["queue_full"]}), 503

    if "file" not in request.files:
        return jsonify({"error": t["invalid_file"]}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": t["invalid_file"]}), 400

    file_type = _get_file_type(file.filename)
    if not file_type:
        return jsonify({"error": t["invalid_file"]}), 400

    # Save with UUID name
    job_id = uuid.uuid4().hex
    ext = "laz" if file_type == "laz" else "tif"
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    upload_path = os.path.join(upload_dir, f"{job_id}.{ext}")
    file.save(upload_path)

    # Validate file contents
    valid, error_msg = validate_upload(upload_path, file_type)
    if not valid:
        os.remove(upload_path)
        return jsonify({"error": error_msg}), 400

    output_dir = os.path.join(current_app.config["OUTPUT_FOLDER"], job_id)

    # Build processing params
    params = {
        "model_type": request.form.get("model_type", "dsm"),
        "resolution": _clamp_resolution(request.form.get("resolution", "1.0")),
        "enable_hillshade": request.form.get("enable_hillshade") == "true",
        "z_factor": _clamp_float(request.form.get("z_factor", "1.0"), 0.01, 100.0),
        "azimuth": _clamp_float(request.form.get("azimuth", "315.0"), 0.0, 360.0),
        "altitude": _clamp_float(request.form.get("altitude", "45.0"), 0.0, 90.0),
    }

    # Dispatch task
    from .tasks import process_hillshade, process_laz

    if file_type == "tif":
        task = process_hillshade.delay(job_id, upload_path, output_dir, params)
    else:
        task = process_laz.delay(job_id, upload_path, output_dir, params)

    return jsonify({"job_id": job_id, "task_id": task.id}), 202


@bp.route("/status/<task_id>")
def status(task_id):
    from .tasks import celery_app

    result = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        return jsonify({"state": "pending"})
    elif result.state == "PROCESSING":
        meta = result.info or {}
        return jsonify({"state": "processing", "step": meta.get("step", "")})
    elif result.state == "SUCCESS":
        files = {}
        for key, path in (result.result or {}).items():
            if os.path.isfile(path):
                files[key] = os.path.basename(path)
        return jsonify({"state": "done", "files": files})
    elif result.state == "FAILURE":
        return jsonify({"state": "failed", "error": str(result.info)}), 200
    else:
        return jsonify({"state": result.state.lower()})


@bp.route("/download/<job_id>/<filename>")
def download(job_id, filename):
    # Sanitize: job_id must be hex, filename must be simple
    if not _is_safe_id(job_id) or not _is_safe_filename(filename):
        return jsonify({"error": "Invalid request"}), 400

    output_dir = current_app.config["OUTPUT_FOLDER"]
    job_dir = os.path.join(output_dir, job_id)
    filepath = os.path.join(job_dir, filename)

    # Prevent path traversal
    filepath = os.path.realpath(filepath)
    if not filepath.startswith(os.path.realpath(output_dir)):
        return jsonify({"error": "Invalid request"}), 400

    if not os.path.isfile(filepath):
        return jsonify({"error": "File not found or expired"}), 404

    response = send_file(filepath, as_attachment=True, download_name=filename)

    # Mark file as downloaded, delete job dir when all files are downloaded
    @response.call_on_close
    def _cleanup():
        try:
            os.remove(filepath)
            # If job dir is now empty, remove it
            remaining = os.listdir(job_dir)
            if not remaining:
                os.rmdir(job_dir)
        except OSError:
            pass

    return response


def _clamp_resolution(val):
    try:
        v = float(val)
        return max(0.1, min(10.0, v))
    except (ValueError, TypeError):
        return 1.0


def _clamp_float(val, lo, hi):
    try:
        v = float(val)
        return max(lo, min(hi, v))
    except (ValueError, TypeError):
        return lo


def _is_safe_id(s):
    return len(s) == 32 and all(c in "0123456789abcdef" for c in s)


def _is_safe_filename(s):
    return (
        len(s) < 100
        and ".." not in s
        and "/" not in s
        and "\\" not in s
        and s.endswith(".tif")
    )
