# Use Python 3.10 as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY string_help.py .

# Copy config directory
COPY config/ ./config/

# Create config file from example if it doesn't exist
# Note: You should mount your own config or set environment variables
RUN if [ ! -f config/server.config ]; then \
        cp config/server.config.example config/server.config; \
    fi

# Expose the port (default 57416, but configurable via config file)
EXPOSE 57416

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Use exec form to ensure proper signal handling
CMD ["python", "server.py"]

