FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua source code + ML models
COPY . .

EXPOSE 8000

# Bootstrap DB dulu, baru jalankan server
CMD ["sh", "-c", "python bootstrap.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
