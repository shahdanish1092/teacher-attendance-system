# Dockerfile for Flyers: python + system deps for dlib / opencv
FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libxrender1 \
    libxext6 \
    libglib2.0-0 \
    libsm6 \
    libx11-6 \
    libgtk2.0-0 \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt

# Upgrade pip and install wheels
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app
ENV PORT=8080
EXPOSE 8080

# Use gunicorn; bind to 0.0.0.0:$PORT
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1"]
