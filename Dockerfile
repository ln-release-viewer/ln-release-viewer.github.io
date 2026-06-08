FROM selenium/standalone-chrome:147.0

USER root

# Install Python + pip
RUN apt-get update && apt-get install -y python3 python3-pip

# Create working directory
WORKDIR /app

# Copy scripts and requirements
COPY scripts/ scripts/
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install -r requirements.txt
RUN pip3 install playwright
RUN playwright install --with-deps chromium


# Default command (can be overridden in GitHub Actions)
CMD ["python3", "scripts/fetch_covers.py"]
