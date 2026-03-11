"""Periodic cleanup of expired files."""

import os
import time
import shutil


def cleanup_expired():
    upload_folder = os.environ.get("UPLOAD_FOLDER", "/data/uploads")
    output_folder = os.environ.get("OUTPUT_FOLDER", "/data/output")
    expiry = int(os.environ.get("FILE_EXPIRY_SECONDS", "3600"))
    now = time.time()

    for folder in (upload_folder, output_folder):
        if not os.path.isdir(folder):
            continue
        for entry in os.listdir(folder):
            path = os.path.join(folder, entry)
            try:
                mtime = os.path.getmtime(path)
                if now - mtime > expiry:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
            except OSError:
                pass
