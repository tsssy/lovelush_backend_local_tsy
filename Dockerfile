# Use the official Python 3.11 slim image as base
# slim variant is smaller and contains only essential packages
FROM python:3.11-slim

# Set environment variables for Python
# PYTHONUNBUFFERED: Ensures that Python output is sent straight to terminal (useful for logging)
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing pyc files to disc
# PYTHONPATH: Add the app directory to Python path
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Set the working directory inside the container
# All subsequent commands will be run from this directory
WORKDIR /app

# Install system dependencies
# Update package list and install required system packages
# curl: For health checks and debugging
# gcc: Required for compiling some Python packages
# --no-install-recommends: Don't install recommended packages to keep image smaller
# rm -rf /var/lib/apt/lists/*: Clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml first for better Docker layer caching
# This allows Docker to cache the pip install step if pyproject.toml hasn't changed
COPY pyproject.toml .

# Install Python dependencies
# --no-cache-dir: Don't save pip cache to reduce image size
# --upgrade: Ensure pip is using the latest version
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copy the entire application code into the container
# This is done after installing dependencies to leverage Docker's layer caching
COPY . .

# Create a non-root user for security best practices
# Running as root in containers can be a security risk
# 1001 is a common choice for user/group IDs in containers
RUN groupadd -r appuser -g 1001 && \
    useradd -r -g appuser -u 1001 appuser && \
    chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port that the FastAPI application will run on
# This is the port defined in main.py (8000)
EXPOSE 8000

# Add a health check to monitor container health
# This will hit the /health endpoint we defined in main.py
# --interval: How often to run the check
# --timeout: How long to wait for a response
# --start-period: How long to wait before starting health checks
# --retries: How many failures before marking unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command to run when container starts
# Use uvicorn to serve the FastAPI application
# --host 0.0.0.0: Bind to all network interfaces (required in containers)
# --port 8000: Port to run the server on
# --workers 1: Number of worker processes (can be increased for production)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
