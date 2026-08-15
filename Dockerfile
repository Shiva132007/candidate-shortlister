# Stage 1: Build the React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app

# Copy package configurations and install frontend dependencies
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install

# Copy frontend source files and compile static production bundle
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Stage 2: Setup Python FastAPI Backend
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy all application source files
COPY . .

# Copy built React production bundle from Stage 1 into frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure persistent workspace directory exists
RUN mkdir -p /app/roles

EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000
ENV SQLITE_DB_PATH=/app/roles/auth.db

CMD ["python", "backend/server.py"]
