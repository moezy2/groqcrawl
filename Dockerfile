# Use Playwright's Python image (includes Chromium)
FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    chromium-browser \
    && rm -rf /var/lib/apt/lists/*

# Install pip dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py ./

# Set environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Use Gunicorn to serve the Flask app
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "1"]
