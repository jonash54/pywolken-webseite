"""Celery tasks for point cloud and raster processing.

DEM creation via PDAL writers.gdal (C++ native, fast).
Hillshade via gdaldem (C native, fast).
Same approach as laz_hillshade.py.
"""

import json
import os
import shutil
import subprocess

from celery import Celery

celery_app = Celery("geowandel")
celery_app.config_from_object(
    {
        "broker_url": os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
        "result_backend": os.environ.get(
            "CELERY_RESULT_BACKEND", "redis://redis:6379/0"
        ),
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "task_track_started": True,
        "task_time_limit": 600,  # 10 min hard limit
        "task_soft_time_limit": 540,  # 9 min soft limit
        "worker_max_memory_per_child": 8_000_000,  # 8GB, restart worker after
    }
)


@celery_app.task(bind=True, name="process_laz")
def process_laz(self, job_id, upload_path, output_dir, params):
    """Convert LAZ/LAS to DEM/DSM GeoTIFF, optionally generate hillshade.

    Uses PDAL writers.gdal + gdaldem — same as laz_hillshade.py.
    """
    import pdal

    try:
        os.makedirs(output_dir, exist_ok=True)

        model_type = params.get("model_type", "dsm")
        resolution = float(params.get("resolution", 1.0))
        dem_path = os.path.join(output_dir, f"{job_id}_dem.tif")

        # Build PDAL pipeline
        pipeline_stages = [upload_path]

        # For DEM: filter to ground points (class 2)
        if model_type == "dem":
            self.update_state(state="PROCESSING", meta={"step": "filtering"})
            pipeline_stages.append(
                {"type": "filters.range", "limits": "Classification[2:2]"}
            )

        self.update_state(state="PROCESSING", meta={"step": "rasterizing"})
        pipeline_stages.append(
            {
                "type": "writers.gdal",
                "filename": dem_path,
                "resolution": resolution,
                "output_type": "idw",
                "window_size": 6,
                "gdaldriver": "GTiff",
                "gdalopts": "COMPRESS=LZW,TILED=YES",
            }
        )

        p = pdal.Pipeline(json.dumps({"pipeline": pipeline_stages}))
        count = p.execute()

        # If DEM filtering produced 0 points, retry without filter (fallback to DSM)
        if count == 0 and model_type == "dem":
            pipeline_stages = [
                upload_path,
                {
                    "type": "writers.gdal",
                    "filename": dem_path,
                    "resolution": resolution,
                    "output_type": "idw",
                    "window_size": 6,
                    "gdaldriver": "GTiff",
                    "gdalopts": "COMPRESS=LZW,TILED=YES",
                },
            ]
            p = pdal.Pipeline(json.dumps({"pipeline": pipeline_stages}))
            p.execute()

        result = {"dem": dem_path}

        # Optional hillshade via gdaldem (fast, C-native)
        if params.get("enable_hillshade"):
            self.update_state(state="PROCESSING", meta={"step": "hillshade"})
            hs_path = os.path.join(output_dir, f"{job_id}_hillshade.tif")
            _run_gdaldem_hillshade(dem_path, hs_path, params)
            result["hillshade"] = hs_path

        # Clean up upload
        _safe_remove(upload_path)

        return result

    except Exception as e:
        _safe_remove(upload_path)
        raise RuntimeError(str(e)) from e


@celery_app.task(bind=True, name="process_hillshade")
def process_hillshade(self, job_id, upload_path, output_dir, params):
    """Generate hillshade from an uploaded GeoTIFF DEM/DSM via gdaldem."""
    try:
        self.update_state(state="PROCESSING", meta={"step": "hillshade"})

        os.makedirs(output_dir, exist_ok=True)
        hs_path = os.path.join(output_dir, f"{job_id}_hillshade.tif")
        _run_gdaldem_hillshade(upload_path, hs_path, params)

        # Clean up upload
        _safe_remove(upload_path)

        return {"hillshade": hs_path}

    except Exception as e:
        _safe_remove(upload_path)
        raise RuntimeError(str(e)) from e


def _run_gdaldem_hillshade(dem_path, output_path, params):
    """Run gdaldem hillshade — same as laz_hillshade.py."""
    cmd = [
        "gdaldem", "hillshade", dem_path, output_path,
        "-z", str(float(params.get("z_factor", 1.0))),
        "-az", str(float(params.get("azimuth", 315.0))),
        "-alt", str(float(params.get("altitude", 45.0))),
        "-compute_edges",
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _safe_remove(path):
    """Remove a file or directory safely."""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
