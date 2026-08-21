FROM python:3.13-slim

# Build tooling required by scientific dependencies when no wheel is available.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential gfortran git \
      libblas-dev liblapack-dev && \
    rm -rf /var/lib/apt/lists/*

# Install into a dedicated virtual environment instead of the system interpreter,
# so the container matches the local development setup.
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
