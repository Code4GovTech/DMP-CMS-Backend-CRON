# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install necessary tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends git openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Copy the current directory contents, including the .git directory
COPY . /app

# Set up the SSH agent forwarding
RUN --mount=type=ssh git submodule update --init --recursive

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 5000

# Run app.py when the container launches
CMD ["python", "app.py"]
