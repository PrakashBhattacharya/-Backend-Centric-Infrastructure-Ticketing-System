# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT 5000

# Set work directory
WORKDIR /app

# Install dependencies from root backend folder
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the entire project
COPY . /app/

# Create a non-root user and switch to it for security
RUN adduser --disabled-password --gecos '' infratick-user
RUN chown -R infratick-user /app

# Finalize permissions for instance folder
RUN mkdir -p /app/backend/instance && chown -R infratick-user /app/backend/instance

USER infratick-user

# Exposed port
EXPOSE 5000

# Start Gunicorn from within the backend directory
WORKDIR /app/backend
CMD gunicorn --bind 0.0.0.0:$PORT wsgi:app
