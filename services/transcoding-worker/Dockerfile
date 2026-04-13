# Transcoding Worker Dockerfile
# FFmpeg + Python + boto3 for MinIO integration

FROM jrottenberg/ffmpeg:4.4-ubuntu

# Install Python and pip
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python

# Create working directory
WORKDIR /app
# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy worker scripts
COPY ffmpeg_presets.py .
COPY worker.py .

# Create temp directory for transcoding
RUN mkdir -p /tmp

# Run as non-root user for security
RUN useradd -m -u 1000 worker && \
    chown -R worker:worker /app /tmp

USER worker

# CRITICAL: Override base image ENTRYPOINT (jrottenberg/ffmpeg sets ENTRYPOINT ["ffmpeg"])
# Without this, CMD becomes arguments to ffmpeg → "ffmpeg python worker.py" → crash
ENTRYPOINT []
CMD ["python", "worker.py"]