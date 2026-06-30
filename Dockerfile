# Stage 1: Build the React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
# Copy package configurations and install frontend dependencies
COPY frontend/package*.json ./frontend/
RUN npm install --prefix frontend

# Copy frontend source files and compile static production bundle
COPY frontend/ ./frontend/
RUN npm run build --prefix frontend

# Stage 2: Setup Python FastAPI Backend
FROM python:3.12-slim
WORKDIR /app

# Install standard system requirements if any (e.g. ca-certificates for Hugging Face APIs and Gemini API calls)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.12.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend files and static configurations (obeying .dockerignore)
COPY . .

# Copy the built React production bundle from Stage 1 into the static serving folder
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure the persistent roles storage directory is present
RUN mkdir -p /app/roles

# Expose FastAPI backend and set default production configurations
EXPOSE 8000
ENV HOST=0.0.0.0
ENV PORT=8000
ENV SQLITE_DB_PATH=/app/roles/auth.db

# Start the application
CMD ["python", "server.py"]
