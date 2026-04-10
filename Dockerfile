# Stage 1: Build frontend
FROM node:25-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python application
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Copy built frontend assets (vite outDir is ../static relative to /frontend, so built files land at /static)
COPY --from=frontend-builder /static ./static
ARG BUILD_SHA=dev
ENV BUILD_SHA=${BUILD_SHA}
RUN chmod +x entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
