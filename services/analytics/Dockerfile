FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY telemetry/ ./telemetry/
COPY analytics/ ./analytics/
COPY services/analytics/ ./services/analytics/
ENV PYTHONUNBUFFERED=1
CMD ["python", "services/analytics/main.py"]
