FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY telemetry/ ./telemetry/
COPY db/ ./db/
COPY automation/ ./automation/
COPY agent.py rag_engine.py parser.py ./
COPY knowledge/ ./knowledge/
COPY services/agent/ ./services/agent/
ENV PYTHONUNBUFFERED=1
CMD ["python", "services/agent/main.py"]
