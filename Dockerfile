FROM node:24-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json vite.config.js ./
RUN npm ci
COPY frontend ./frontend
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend /build/static/dist ./static/dist
EXPOSE 8000
ENV HOST=0.0.0.0
CMD ["python", "main.py"]
