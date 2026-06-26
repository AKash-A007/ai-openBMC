FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY telemetry/ ./telemetry/
COPY db/ ./db/
COPY services/collector/ ./services/collector/
ENV PYTHONUNBUFFERED=1
CMD ["python", "services/collector/main.py"]
