# Data model

## InfluxDB

- Measurement: `vitals`
- Tags:
  - `patient_id`
  - `profile`
    - Valeur technique neutre (`baseline_normale`) gardee pour compatibilite.
- Fields:
  - `hr`
  - `spo2`
  - `sbp`
  - `dbp`
  - `map`
  - `rr`
  - `temp`
  - `shock_index`
  - `postop_day`

## PostgreSQL

### `patients`

- `id` primary key
- `full_name`
- `profile`
- `baseline_normale` est utilise comme valeur technique unique; la criticite vient du scenario, pas du profil.
- `surgery_type`
- `postop_day`
- `risk_level`
- `risk_level` est conserve pour compatibilite mais reste neutre (`surveillance_postop`).
- `room`
- `history_json`

### `alerts`

- `id` bigserial primary key
- `rule_id`
- `patient_id`
- `level`
- `status`
- `message`
- `metric_snapshot`
- `acknowledged_at`
- `acknowledged_by`

### `notes`

- `patient_id`
- `note_type`
- `content`
- `source`

### `feedback_ml`

- `patient_id`
- `alert_id`
- `label`
- `comment`
