# ==============================================
# HiveFlow Core - Dockerfile
# ==============================================
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy package source
COPY hiveflow/ ./hiveflow/
COPY pyproject.toml .

# Install package in editable mode
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "hiveflow.app"]
