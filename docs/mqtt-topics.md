# MQTT topics

## Topic principal

- `patients/{patient_id}/vitals`
  - Exemple: `patients/PAT-003/vitals`
  - QoS: `1`
  - Payload JSON valide par le backend

## Topic de controle demo

- `simulator/control/refresh`
  - QoS: `1`
  - Usage: le backend envoie une nouvelle repartition aleatoire pour la demo
  - Garantie: `1 patient temoin sain` et `4 cas cliniques de complication`

## Champs de payload

```json
{
  "ts": "2026-03-04T10:15:00Z",
  "patient_id": "PAT-003",
  "profile": "baseline_normale",
  "scenario": "hemorrhage_j2",
  "hr": 128,
  "spo2": 93,
  "sbp": 86,
  "dbp": 54,
  "map": 65,
  "rr": 24,
  "temp": 37.1,
  "room": "A103",
  "battery": 96,
  "postop_day": 2,
  "surgery_type": "colectomie"
}
```

## Convention

- `patient_id` est duplique dans le topic et dans le payload.
- `profile` est neutre et ne porte plus la severite clinique; la derive vient du scenario actif.
- `map` est publie par le simulateur et recalcule par le backend si absent.
- Les topics sont volontairement simples pour la demo.
