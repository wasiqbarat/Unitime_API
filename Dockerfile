FROM python:3.11-slim-bullseye as builder

# Install build dependencies and create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim-bullseye

# Install only the necessary JDK packages and clean up in one layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user and set up directories
RUN useradd -m -u 1000 appuser && \
    mkdir -p ./cpsolver && \
    chown -R appuser:appuser /app && \
    chmod -R 755 ./cpsolver

# Copy application
COPY --chown=appuser:appuser ./app ./app

USER appuser

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOLVER_PATH=/app/cpsolver

# Declare volume for persistent data
VOLUME ["/app/cpsolver"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
