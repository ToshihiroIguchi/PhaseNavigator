FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential gfortran git \
      libblas-dev liblapack-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    pmg config --install enumlib && \
    pmg config --install bader

WORKDIR /app
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
