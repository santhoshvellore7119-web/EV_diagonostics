# ==============================================================================
# EV Battery Diagnostics & Active Rebalancing Platform
# Production Multi-Stage Container Image
# ==============================================================================

# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend/ ./
ENV CI=false
RUN npm run build

# Stage 2: Python Backend Runtime
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and full-stack modules
COPY backend/ ./backend/
COPY active_rebalancing/ ./active_rebalancing/
COPY ml_pipeline/ ./ml_pipeline/
COPY simulation_3d_demo/ ./simulation_3d_demo/
COPY gazebo/ ./gazebo/
COPY hardware/ ./hardware/
COPY matlab_simulink_demo/ ./matlab_simulink_demo/
COPY run.py ./

# Copy built frontend assets to static serving directory
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Expose HTTP ports
EXPOSE 8000

# Default environment variables
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Run FastAPI via Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
