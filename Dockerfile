# Use Playwright's Python image (includes Chromium)
FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

# Install pip dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py ./

# Expose port and run
ENV PORT 5000
EXPOSE 5000

# Use Gunicorn to serve the Flask app
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:5000"]
