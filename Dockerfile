# Use a base image that includes Python and has common Playwright dependencies or allows easy installation
# This specific image is recommended by Playwright for its compatibility
FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt first to leverage Docker cache
# This ensures pip install only runs if requirements.txt changes
COPY requirements.txt .

# Install Python dependencies from requirements.txt
# This will also install playwright (the Python library)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port your Flask app will run on
# (Render automatically sets the $PORT environment variable)
EXPOSE 10000

# Command to run your Gunicorn server
# Using the shell form (without square brackets) so $PORT variable is expanded
CMD gunicorn -w 1 -b 0.0.0.0:$PORT main:app
