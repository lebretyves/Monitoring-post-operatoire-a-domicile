from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from influxdb_client import InfluxDBClient, Point, WritePrecision


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class InfluxStorage:
    def __init__(self, url: str, token: str, org: str, bucket: str) -> None:
        self.org = org
        self.bucket = bucket
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api()
        self.query_api = self.client.query_api()

    def close(self) -> None:
        self.client.close()

    def write_vital(self, reading: dict[str, Any]) -> None:
        point = (
            Point("vitals")
            .tag("patient_id", reading["patient_id"])
            .tag("profile", reading["profile"])
            .field("hr", reading["hr"])
            .field("spo2", reading["spo2"])
            .field("sbp", reading["sbp"])
            .field("dbp", reading["dbp"])
            .field("map", float(int(reading["map"])))
            .field("rr", reading["rr"])
            .field("temp", float(reading["temp"]))
            .field("shock_index", float(reading["shock_index"]))
            .field("postop_day", reading["postop_day"])
            .time(_parse_ts(reading["ts"]), WritePrecision.NS)
        )
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    def query_history(self, patient_id: str, metric: str = "all", hours: int = 24) -> list[dict[str, Any]]:
        metric_filter = ""
        if metric != "all":
            metric_filter = f'|> filter(fn: (r) => r["_field"] == "{metric}")'
        query = f"""
        from(bucket: "{self.bucket}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "vitals")
          |> filter(fn: (r) => r["patient_id"] == "{patient_id}")
          {metric_filter}
          |> sort(columns: ["_time"])
        """
        tables = self.query_api.query(query=query, org=self.org)
        aggregated: dict[str, dict[str, Any]] = defaultdict(lambda: {"ts": "", "values": {}})
        for table in tables:
            for record in table.records:
                key = record.get_time().isoformat()
                aggregated[key]["ts"] = key
                field_name = record.get_field()
                value = record.get_value()
                if field_name == "map":
                    value = int(round(float(value)))
                aggregated[key]["values"][field_name] = value
        return [aggregated[key] for key in sorted(aggregated)]


class MemoryInfluxStorage:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def close(self) -> None:
        return None

    def write_vital(self, reading: dict[str, Any]) -> None:
        self.rows[reading["patient_id"]].append(
            {
                "ts": reading["ts"],
                "values": {
                    "hr": float(reading["hr"]),
                    "spo2": float(reading["spo2"]),
                    "sbp": float(reading["sbp"]),
                    "dbp": float(reading["dbp"]),
                    "map": float(int(reading["map"])),
                    "rr": float(reading["rr"]),
                    "temp": float(reading["temp"]),
                    "shock_index": float(reading["shock_index"]),
                },
            }
        )

    def query_history(self, patient_id: str, metric: str = "all", hours: int = 24) -> list[dict[str, Any]]:
        rows = self.rows.get(patient_id, [])
        if metric == "all":
            return [
                {
                    "ts": row["ts"],
                    "values": {
                        key: (int(round(float(value))) if key == "map" else value)
                        for key, value in row["values"].items()
                    },
                }
                for row in rows[-512:]
            ]
        filtered = []
        for row in rows[-512:]:
            if metric in row["values"]:
                value = row["values"][metric]
                if metric == "map":
                    value = int(round(float(value)))
                filtered.append({"ts": row["ts"], "values": {metric: value}})
        return filtered
