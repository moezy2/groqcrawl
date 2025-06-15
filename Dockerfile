# Use a base image with Python
FROM python:3.11-slim

# Install system dependencies and Chromium for Pydoll
RUN apt-get update && apt-get install -y \
    chromium-browser \
    curl \
    fonts-liberation \
    libnss3 \
    libgconf-2-4 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*
# Create symlink so Pydoll can find the browser
RUN ln -s /usr/bin/chromium-browser /usr/bin/google-chrome

# Install Pydoll/Chromium automatically via pydoll-python
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py ./

# Expose port and start
ENV PORT 5000
EXPOSE 5000
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:5000"]
