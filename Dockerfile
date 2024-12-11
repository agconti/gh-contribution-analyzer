# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY github_contributions_script.py .

# Install any needed packages specified in requirements
RUN pip install --no-cache-dir requests pandas

# Set environment variables with placeholders (to be replaced at runtime)
ENV GITHUB_TOKEN=""
ENV ORGANIZATION_NAME=""

# Create output directory
RUN mkdir -p github_contributions_reports

# Run the script when the container launches
CMD ["python", "github_contributions_script.py"]