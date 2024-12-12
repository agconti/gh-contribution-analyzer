# Use an official Python runtime as a parent image
FROM python:3.9-slim as base

FROM base as deps
# Set the working directory in the container
WORKDIR /app

# Install any needed packages specified in requirements
RUN pip install --no-cache-dir requests pandas

FROM deps as runner

# Copy dependencies
COPY --from=deps /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy the current directory contents into the container at /app
COPY ./github_contributions_script.py .

# Create output directory
RUN mkdir -p github_contributions_reports

# Run the script when the container launches
CMD ["python", "github_contributions_script.py"]