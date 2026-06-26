# AI OpsBMC — API Reference

This document covers all REST API endpoints exposed by the AI OpsBMC platform.

> **Base URL (Docker Compose):** `http://localhost:8000`  
> **Authentication:** Bearer JWT token required on all endpoints except `/health` and `/token`.

---

## Authentication

### POST /token

Obtain a JWT access token.

**Request body (form data):**
```
username=admin&password=yourpassword
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Include the token in all subsequent requests:
```
Authorization: Bearer <access_token>
```

---

## Health & Status

### GET /health

Returns system health status. No authentication required.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "collector": "up",
    "analytics": "up",
    "agent": "up"
  }
}
```

### GET /status

Returns current system health score and risk level. **Requires:** `viewer` role.

**Response:**
```json
{
  "health_score": 84.2,
  "risk_level": "LOW",
  "anomaly_count": 0,
  "last_updated": "2026-06-26T15:30:00Z"
}
```

---

## Telemetry

### GET /telemetry/latest

Returns the latest sensor readings for all sensors. **Requires:** `viewer` role.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Max readings to return |
| `sensor` | str | (all) | Filter by sensor name |
| `host` | str | (all) | Filter by BMC host |

**Response:**
```json
{
  "readings": [
    {
      "id": 1,
      "timestamp": "2026-06-26T15:30:00Z",
      "sensor": "cpu0_temp",
      "value": 72.4,
      "unit": "C",
      "host": "bmc-01"
    }
  ],
  "count": 1
}
```

### GET /telemetry/history/{sensor}

Returns historical readings for a specific sensor. **Requires:** `viewer` role.

**Path parameters:**
| Parameter | Description |
|-----------|-------------|
| `sensor` | Sensor identifier (e.g. `cpu0_temp`, `fan1_speed`, `psu0_power`) |

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | int | 24 | Hours of history |
| `limit` | int | 1000 | Max readings |

**Response:**
```json
{
  "sensor": "cpu0_temp",
  "readings": [
    {"timestamp": "2026-06-26T14:00:00Z", "value": 71.2},
    {"timestamp": "2026-06-26T15:00:00Z", "value": 72.4}
  ],
  "stats": {
    "min": 68.1,
    "max": 78.3,
    "mean": 72.1,
    "std": 2.4
  }
}
```

---

## Anomaly Detection

### GET /anomalies

Returns detected anomalies. **Requires:** `viewer` role.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | int | 24 | Look-back window in hours |
| `min_score` | float | 0.5 | Minimum anomaly score (0-1) |

**Response:**
```json
{
  "anomalies": [
    {
      "id": 42,
      "sensor": "cpu0_temp",
      "timestamp": "2026-06-26T15:28:00Z",
      "value": 91.3,
      "anomaly_score": 0.87,
      "risk_level": "HIGH"
    }
  ],
  "count": 1
}
```

### POST /anomalies/detect

Trigger an immediate anomaly detection scan. **Requires:** `operator` role.

**Response:**
```json
{
  "triggered": true,
  "anomalies_found": 2,
  "health_score": 61.4,
  "timestamp": "2026-06-26T15:30:00Z"
}
```

---

## Prediction

### GET /predictions/{sensor}

Returns failure predictions for a sensor at multiple horizons. **Requires:** `viewer` role.

**Path parameters:**
| Parameter | Description |
|-----------|-------------|
| `sensor` | Sensor identifier |

**Response:**
```json
{
  "sensor": "cpu0_temp",
  "predictions": {
    "1min": {"value": 73.1, "confidence": 0.94},
    "5min": {"value": 74.8, "confidence": 0.87},
    "15min": {"value": 78.2, "confidence": 0.71}
  },
  "failure_probability": 0.12,
  "risk_level": "LOW"
}
```

---

## Diagnosis

### POST /diagnose

Trigger an AI-powered diagnosis on a sensor anomaly. **Requires:** `operator` role.

**Request body:**
```json
{
  "sensor": "cpu0_temp",
  "value": 91.3,
  "context": "Temperature spike started 5 minutes ago"
}
```

**Response:**
```json
{
  "diagnosis": {
    "fault_type": "CPU_OVERHEAT",
    "confidence": 0.89,
    "root_cause": "CPU temperature has exceeded safe operating limits (85C). This may indicate inadequate cooling, high ambient temperature, or a failing fan.",
    "evidence": [
      "cpu0_temp reading: 91.3C (threshold: 85C)",
      "fan1_speed: 2100 RPM (normal: 4500 RPM)"
    ],
    "recommended_actions": [
      {"action": "increase_fan_speed", "priority": 1},
      {"action": "alert_operator", "priority": 2},
      {"action": "reduce_cpu_freq", "priority": 3}
    ]
  },
  "rag_sources": [
    "cpu_failures.txt (chunk 3)",
    "cpu_failures.txt (chunk 7)"
  ],
  "latency_ms": 1240
}
```

### GET /diagnoses

Returns recent diagnosis history. **Requires:** `viewer` role.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | int | 24 | Look-back window |
| `fault_type` | str | (all) | Filter by fault type |

---

## Remediation

### GET /remediation/actions

Returns all pending and recent remediation actions. **Requires:** `operator` role.

**Response:**
```json
{
  "actions": [
    {
      "id": "rem_001",
      "fault_type": "CPU_OVERHEAT",
      "action": "increase_fan_speed",
      "status": "PENDING_APPROVAL",
      "risk_level": "HIGH",
      "created_at": "2026-06-26T15:28:00Z",
      "expires_at": "2026-06-26T15:43:00Z"
    }
  ]
}
```

### POST /remediation/approve/{action_id}

Approve a pending remediation action. **Requires:** `admin` role.

**Path parameters:**
| Parameter | Description |
|-----------|-------------|
| `action_id` | Remediation action ID |

**Request body:**
```json
{
  "comment": "Approved - confirmed fan failure by visual inspection"
}
```

**Response:**
```json
{
  "action_id": "rem_001",
  "status": "APPROVED",
  "approved_by": "admin",
  "approved_at": "2026-06-26T15:29:00Z"
}
```

### POST /remediation/reject/{action_id}

Reject a pending remediation action. **Requires:** `admin` role.

**Request body:**
```json
{
  "comment": "Rejected - will handle manually"
}
```

**Response:**
```json
{
  "action_id": "rem_001",
  "status": "REJECTED",
  "rejected_by": "admin",
  "rejected_at": "2026-06-26T15:29:30Z"
}
```

### POST /remediation/execute/{action_id}

Immediately execute an approved action. **Requires:** `automation` role.

---

## Audit Log

### GET /audit

Returns the immutable audit log. **Requires:** `admin` role.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | int | 24 | Look-back window |
| `actor` | str | (all) | Filter by actor |
| `action` | str | (all) | Filter by action type |

**Response:**
```json
{
  "entries": [
    {
      "id": "audit_001",
      "timestamp": "2026-06-26T15:29:00Z",
      "actor": "admin",
      "event_type": "ACTION_APPROVED",
      "action_id": "rem_001",
      "action": "increase_fan_speed",
      "pre_health_score": 61.4,
      "post_health_score": 78.2,
      "duration_ms": 2340,
      "status": "SUCCEEDED"
    }
  ],
  "count": 1
}
```

---

## Metrics

### GET /metrics

Returns Prometheus-format metrics. No authentication required (internal scrape).

Key exported metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `aiobmc_health_score` | Gauge | System health score (0-100) |
| `aiobmc_anomaly_count_total` | Counter | Total anomalies detected |
| `aiobmc_failure_probability` | Gauge | Current failure probability |
| `aiobmc_rag_latency_seconds` | Histogram | RAG retrieval latency |
| `aiobmc_http_requests_total` | Counter | HTTP requests by endpoint/status |
| `aiobmc_remediation_executions_total` | Counter | Remediation actions executed |
| `aiobmc_rollbacks_total` | Counter | Automatic rollbacks triggered |

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "UNAUTHORIZED",
  "message": "Invalid or expired token",
  "detail": "JWT signature verification failed",
  "status_code": 401
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request (invalid parameters) |
| 401 | Unauthenticated (no/invalid token) |
| 403 | Forbidden (insufficient role) |
| 404 | Resource not found |
| 422 | Validation error |
| 429 | Rate limit exceeded (100 req/min) |
| 500 | Internal server error |

---

## SDK / Client Example

```python
import httpx

BASE_URL = "http://localhost:8000"

# Authenticate
resp = httpx.post(f"{BASE_URL}/token", data={"username": "admin", "password": "admin"})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Get health status
status = httpx.get(f"{BASE_URL}/status", headers=headers).json()
print(f"Health Score: {status['health_score']}")

# Trigger diagnosis
diagnosis = httpx.post(f"{BASE_URL}/diagnose", headers=headers, json={
    "sensor": "cpu0_temp",
    "value": 91.3
}).json()
print(f"Fault Type: {diagnosis['diagnosis']['fault_type']}")
```
