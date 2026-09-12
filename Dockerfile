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

# iproute2: OSのIPアドレス表示(REQ-H09)で`ip addr`を使用するため
RUN apt-get update \
    && apt-get install -y --no-install-recommends iproute2 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./static

ENV PYTHONUNBUFFERED=1
ENV ALIAS_WEB_PORT=8000
ENV ALIAS_DB_PATH=/app/data/alias_sender.db
ENV ALIAS_LOG_DIR=/app/logs

# app.run: システム設定画面からのWebGUIポート変更(再起動不要)に対応するための
# 自前エントリーポイント。`uvicorn app.main:app`のCLI直接起動は使用しない。
CMD ["python", "-m", "app.run"]
