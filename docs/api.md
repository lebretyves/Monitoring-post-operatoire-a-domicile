# API

## Health

- `GET /health`

## Patients

- `GET /api/patients`
- `GET /api/patients/{patient_id}/last-vitals`
- `POST /api/patients/refresh`
  - relance une repartition aleatoire de demo
  - garantit `1 patient temoin sain` et `4 cas cliniques de complication`

## Trends

- `GET /api/trends/{patient_id}?metric=hr&hours=24`
- `GET /api/trends/{patient_id}?metric=spo2&hours=48`

## Alerts

- `GET /api/alerts`
- `GET /api/alerts?patient_id=PAT-003`
- `POST /api/alerts/{alert_id}/ack?user=demo`

## Export

- `GET /api/export/{patient_id}/csv`
- `GET /api/export/{patient_id}/pdf`

## Summary

- `GET /api/summaries/{patient_id}`

## LLM

- `GET /api/llm/{patient_id}/scenario-review`
  - analyse locale via Ollama si `ENABLE_LLM=true`
  - sinon fallback `rule-based`

## ML

- `GET /api/ml/{patient_id}/predict`
- `GET /api/ml/feedback?patient_id=PAT-003`
- `GET /api/ml/feedback?pathology=Hemorragie%20J%2B2`
- `POST /api/ml/{patient_id}/feedback`
- `POST /api/ml/train`

## WebSocket

- `WS /ws/live`

Messages broadcast:

```json
{
  "type": "vitals",
  "patient_id": "PAT-002",
  "payload": {
    "hr": 108,
    "spo2": 91,
    "map": 72
  }
}
```
