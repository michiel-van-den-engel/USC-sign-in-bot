# Use the official Python 3.11.9 image based on Debian Bookworm
FROM python:3.11.9-bookworm

# Set the working directory
WORKDIR /app

# Copy the application code into the container
COPY .  .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
