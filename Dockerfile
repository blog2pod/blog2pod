# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /blog2pod

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip3 install newspaper3k

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg
RUN apt-get update && apt-get install -y chromium

# Copy the rest of the application code into the container
COPY blog2pod.py .

# Create a 'completed' directory inside the container
RUN mkdir /blog2pod/completed

# Set permissions for the 'completed' directory
RUN chmod 755 /blog2pod/completed
RUN chmod 777 /usr/bin/chromium

# Set the entry point for the container
CMD ["python", "blog2pod.py"]