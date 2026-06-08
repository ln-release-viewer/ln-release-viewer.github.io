FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    wget \
    xvfb \
    unzip \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libxshmfence1 \
    libxrandr2 \
    libxdamage1 \
    libxcomposite1 \
    libxfixes3 \
    libxext6 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libdrm2 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome 147 (matches UDC support)
RUN wget -q https://snapshot.debian.org/archive/google-chrome/20241010T031200Z/pool/main/g/google-chrome-stable/google-chrome-stable_147.0.7727.55-1_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_147.0.7727.55-1_amd64.deb \
    && rm google-chrome-stable_147.0.7727.55-1_amd64.deb

WORKDIR /app

# Copy scripts and requirements
COPY scripts/ scripts/
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Install Playwright Chromium
RUN playwright install --with-deps chromium

# Use entrypoint script
RUN chmod +x scripts/run_all.sh
CMD ["bash", "scripts/run_all.sh"]



