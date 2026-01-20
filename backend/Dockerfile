# Mobius OS Backend - Cloud Run Dockerfile
FROM python:3.13-slim

# Set working directory
WORKDIR /backend

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install gunicorn for production
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV PYTHONPATH=/backend

# Expose port
EXPOSE 8080

# Run with gunicorn using server.py entry point
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 "server:create_app()"
