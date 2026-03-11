# pywolken – LiDAR & GeoTIFF Processing Web App

A self-hosted web application for converting LAS/LAZ point cloud files to DEM/DSM rasters and generating hillshade visualizations.

## Features

- **LAS/LAZ to DEM or DSM** – GeoTIFF output using IDW interpolation via PDAL
- **Hillshade generation** – adjustable sun angle, azimuth, and z-factor via gdaldem
- **GeoTIFF upload** – generate hillshade from an existing DEM/DSM
- Bilingual interface (English / German)
- Automatic light/dark theme
- Drag & drop upload with progress bar
- Uploaded files auto-expire after 1 hour

## Requirements

- Docker & Docker Compose

## Quick Start

```bash
# 1. Create your .env with a secret key
cp .env.example .env
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" > .env

# 2. Build and start
docker compose up -d --build

# 3. Open in browser
# http://localhost:5200
```

This starts 4 containers:

| Container | Role |
|---|---|
| **web** | Flask/gunicorn on port 5200 |
| **worker** | Celery – 2 concurrent processing tasks |
| **redis** | Message broker and result backend |
| **cleanup** | Deletes expired files every 5 minutes |

## Port & Network

The app listens on **port 5200** on all interfaces by default. To change this, edit the `ports` section in `docker-compose.yml`:

```yaml
ports:
  - "127.0.0.1:5200:5200"  # localhost only (for use behind a reverse proxy)
  - "8080:5200"             # map to a different host port
```

If you put a reverse proxy (nginx, caddy, traefik, ...) in front, bind to localhost and proxy to `127.0.0.1:5200`.

## Usage

1. Open `http://localhost:5200`
2. Upload a `.laz`, `.las`, or `.tif` file (max 540 MB)
3. For point clouds: choose DEM or DSM, set resolution (0.1–10 m)
4. Optionally enable hillshade and tweak z-factor, azimuth, altitude
5. Click **Convert** and wait for processing
6. Download the resulting GeoTIFF(s)

## Administration

```bash
# View logs
docker compose logs web --tail 100
docker compose logs worker --tail 100

# Rebuild after code changes (templates/CSS/JS are baked into the image)
docker compose up -d --build

# Stop
docker compose down

# Stop and delete all data (uploads, outputs, Redis)
docker compose down -v
```

## Configuration

Environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | from `.env` | Flask secret key |
| `UPLOAD_FOLDER` | `/data/uploads` | Upload storage path inside container |
| `OUTPUT_FOLDER` | `/data/output` | Output storage path inside container |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | Celery result store |
| `REDIS_URL` | `redis://redis:6379/1` | Rate limiting store |
| `FILE_EXPIRY_SECONDS` | `3600` | Seconds before files are cleaned up |

Worker resource limits (in `docker-compose.yml`): 4 CPU / 16 GB RAM (1 CPU / 2 GB reserved).

## Project Structure

```
pywolken/
├── app/
│   ├── __init__.py       # Flask app factory
│   ├── routes.py         # Endpoints: /, /upload, /status/<id>, /download/<job>/<file>
│   ├── tasks.py          # Celery tasks (PDAL writers.gdal + gdaldem hillshade)
│   ├── security.py       # Upload validation (LAS/TIFF magic bytes, size)
│   ├── config.py         # Config from environment variables
│   ├── cleanup.py        # Periodic expired file removal
│   ├── i18n.py           # EN/DE translations
│   ├── static/
│   │   ├── style.css     # Light/dark theme
│   │   └── app.js        # Upload, progress, polling
│   └── templates/
│       └── index.html    # Single-page Jinja2 template
├── docker-compose.yml
├── Dockerfile            # condaforge/miniforge3 + conda (PDAL/GDAL) + uv (Flask/Celery)
├── pyproject.toml
├── .env.example
└── LICENSE
```

## Security

- Files validated by magic bytes (LAS `LASF` header, TIFF `II`/`MM` header)
- All filenames replaced with UUIDs
- Rate limited: 5 uploads per hour per IP
- Max 10 jobs in queue
- Containers: read-only filesystem, all capabilities dropped, no-new-privileges
- Redis on internal-only Docker network (not exposed)
- Download endpoint checks against path traversal

## License

MIT
