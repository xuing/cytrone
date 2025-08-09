# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the project files into the container
COPY . .

# Install the project dependencies
# This will install pyyaml, passlib, and the project itself in editable mode
RUN pip install --no-cache-dir -e .

# The command to run the application will be specified in docker-compose.yml
# EXPOSE ports if needed, but docker-compose will handle this.
# EXPOSE 8082 8083 8084
