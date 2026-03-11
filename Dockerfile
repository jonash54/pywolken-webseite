FROM condaforge/miniforge3 AS base

# Install PDAL, GDAL, and Python geo stack via conda-forge
RUN conda install -y -q \
    python=3.11 \
    pdal \
    python-pdal \
    gdal \
    rasterio \
    numpy \
    scipy \
    && conda clean -afy

# Install uv for remaining pip packages
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install remaining Python deps (flask, celery, pywolken, etc.)
RUN uv pip install --python /opt/conda/bin/python \
    flask gunicorn celery redis werkzeug pywolken

# Copy application code
COPY app/ ./app/

ENV PATH="/opt/conda/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN useradd -r -s /bin/false appuser && \
    mkdir -p /data/uploads /data/output && \
    chown -R appuser:appuser /data

USER appuser

EXPOSE 5200
