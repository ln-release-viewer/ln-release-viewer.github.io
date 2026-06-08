FROM selenium/standalone-chrome:147.0

USER root

# Install Python + pip
RUN apt-get update && apt-get install -y python3 python3-pip python3-distutils

# Create working directory
WORKDIR /app

# Copy scripts and requirements
COPY scripts/ scripts/
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Default command (can be overridden in GitHub Actions)
CMD ["python3", "scripts/fetch_covers.py"]
