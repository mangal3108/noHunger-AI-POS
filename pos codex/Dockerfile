# Use Python 3.11-slim for a smaller image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if any (none explicitly required for now)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire pos codex directory
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000

# Expose the mono-service port
EXPOSE 8000

# Start the consolidated app
CMD ["python", "combined_app.py"]
