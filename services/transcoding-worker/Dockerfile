# Transcoding Worker Dockerfile
# Using jrottenberg/ffmpeg Debian variant (has Python)

FROM jrottenberg/ffmpeg:4.4-ubuntu

# Install Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python

# Create working directory
WORKDIR /app

# Copy worker scripts
COPY ffmpeg_presets.py .
COPY worker.py .

# Make worker executable
RUN chmod +x worker.py

# Create directories for input/output
RUN mkdir -p /tmp/uploads /tmp/outputs

# Run as non-root user for security
RUN useradd -m -u 1000 worker && \
    chown -R worker:worker /app /tmp/uploads /tmp/outputs

USER worker

# Run worker
CMD ["python", "worker.py"]
