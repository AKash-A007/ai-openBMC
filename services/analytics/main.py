import sys
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from telemetry.database import init_db
from telemetry.query import get_all_sensor_names
from analytics.anomaly_detector import detect_anomalies
from analytics.predictor import predict_all, predict_failure
from analytics.health_score import calculate_fleet_health, calculate_health_score

app = FastAPI(
    title="AI OpsBMC Analytics Service",
    description="Microservice providing real-time anomaly detection, health scoring, and predictive analysis",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Gauges for observability
HEALTH_SCORE_GAUGE = Gauge(
    "aiops_health_score", "Current fleet health score (0-100)", ["sensor"]
)
FAILURE_PROB_GAUGE = Gauge(
    "aiops_failure_probability", "Failure probability of sensor (0.0-1.0)", ["sensor"]
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/anomalies/{sensor}")
def get_anomalies(sensor: str):
    try:
        anomalies = detect_anomalies(sensor)
        return {"sensor": sensor, "anomalies": anomalies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predictions")
def get_predictions():
    try:
        sensors = get_all_sensor_names()
        if not sensors:
            return {"predictions": {}}
        predictions = predict_all(sensors)

        # Update metrics for Prometheus
        for sensor, pred in predictions.items():
            if "failure_probability" in pred:
                FAILURE_PROB_GAUGE.labels(sensor=sensor).set(
                    pred["failure_probability"]
                )

        return {"predictions": predictions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health-score")
def get_health_score():
    try:
        sensors = get_all_sensor_names()
        if not sensors:
            return {"overall_health_score": 100.0, "breakdown": {}}
        fleet_health = calculate_fleet_health(sensors)

        # Update metrics for Prometheus
        overall = fleet_health.get("overall_health_score", 100.0)
        HEALTH_SCORE_GAUGE.labels(sensor="fleet").set(
            overall if overall is not None else 100.0
        )

        for sensor, score_data in fleet_health.get("sensors", {}).items():
            score = score_data.get("health_score")
            if score is not None:
                HEALTH_SCORE_GAUGE.labels(sensor=sensor).set(score)

        return fleet_health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
def metrics():
    # Update metrics before export
    try:
        sensors = get_all_sensor_names()
        if sensors:
            fleet_health = calculate_fleet_health(sensors)
            overall = fleet_health.get("overall_health_score", 100.0)
            HEALTH_SCORE_GAUGE.labels(sensor="fleet").set(
                overall if overall is not None else 100.0
            )
            for sensor, score_data in fleet_health.get("sensors", {}).items():
                score = score_data.get("health_score")
                if score is not None:
                    HEALTH_SCORE_GAUGE.labels(sensor=sensor).set(score)

            predictions = predict_all(sensors)
            for sensor, pred in predictions.items():
                if "failure_probability" in pred:
                    FAILURE_PROB_GAUGE.labels(sensor=sensor).set(
                        pred["failure_probability"]
                    )
    except Exception:
        pass

    from fastapi.responses import Response

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
