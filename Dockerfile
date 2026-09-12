# ---- frontend build stage ----
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- backend runtime stage ----
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./static

ENV PYTHONUNBUFFERED=1
ENV ALIAS_WEB_PORT=8000
ENV ALIAS_DB_PATH=/app/data/alias_sender.db
ENV ALIAS_LOG_DIR=/app/logs

CMD python -m uvicorn app.main:app --host 0.0.0.0 --port ${ALIAS_WEB_PORT}
