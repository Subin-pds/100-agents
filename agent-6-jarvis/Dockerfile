FROM python:3.11-slim

WORKDIR /app

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY api.py .
COPY agent/__init__.py agent/graph.py agent/tools.py ./agent/
COPY static/ ./static/

# Cloud Run injects PORT; uvicorn must bind to it.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
