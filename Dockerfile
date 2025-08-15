# --------------------
# Base image
# --------------------
FROM python:3.10-slim

# --------------------
# Environment variables
# --------------------
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC
ENV CHROME_BIN=/usr/bin/google-chrome

# --------------------
# Install system dependencies
# --------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        curl \
        unzip \
        gnupg2 \
        fonts-liberation \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxrandr2 \
        libxrender1 \
        libxtst6 \
        ca-certificates \
        python3-pip \
        build-essential \
        git \
        xvfb \
        && rm -rf /var/lib/apt/lists/*

# --------------------
# Install Google Chrome (modern method)
# --------------------
RUN wget -q -O /usr/share/keyrings/google-linux-signing-keyring.gpg https://dl.google.com/linux/linux_signing_key.pub && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# --------------------
# Set workdir
# --------------------
WORKDIR /app

# --------------------
# Copy project files
# --------------------
COPY . /app

# --------------------
# Install Python dependencies
# --------------------
RUN pip install --upgrade pip
RUN pip install --no-cache-dir \
    requests \
    lxml \
    beautifulsoup4 \
    undetected-chromedriver \
    selenium \
    gspread \
    google-auth \
    PyGithub

# --------------------
# Run the script
# --------------------
CMD ["python", "event_scrapper.py"]
