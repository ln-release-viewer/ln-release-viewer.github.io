FROM selenium/standalone-chrome:147.0

USER root

# Install Python + pip + Xvfb
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    xvfb

WORKDIR /app

# Copy scripts and requirements
COPY scripts/ scripts/
COPY requirements.txt .

# Install setuptools so UDC can import distutils shim
RUN pip3 install setuptools

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Install Playwright browser
RUN playwright install --with-deps chromium

# Run scraper under Xvfb
CMD ["xvfb-run", "-a", "python3", "scripts/fetch_covers.py"]

