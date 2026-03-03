FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY brain-core/pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY brain-core/src ./src

# Copy schemas and skills
COPY schemas ./schemas
COPY skills ./skills

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]