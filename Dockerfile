FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy source
COPY arxiv_recent/ arxiv_recent/

# Create data dir
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "arxiv_recent"]
CMD ["scheduler"]
