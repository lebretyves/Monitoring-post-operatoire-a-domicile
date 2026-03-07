from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURES = [
    "heart_rate",
    "spo2",
    "temperature",
    "systolic_bp",
    "diastolic_bp",
    "respiratory_rate",
    "alert_count",
]
TARGET = "has_critical"


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


class CriticityMLService:
    def __init__(self, runtime_dir: Path) -> None:
        self.data_dir = runtime_dir
        self.vitals_csv = self.data_dir / "vitals.csv"
        self.feedback_csv = self.data_dir / "labeled_feedback.csv"
        self.model_path = self.data_dir / "model.pkl"
        self.ensure_data_files()

    def ensure_data_files(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.vitals_csv.exists():
            header = (
                "timestamp,patient_id,room,scenario,profile,pathology,heart_rate,spo2,temperature,"
                "systolic_bp,diastolic_bp,respiratory_rate,alert_count,has_critical\n"
            )
            self.vitals_csv.write_text(header, encoding="utf-8")

    def _normalize_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        return {
            "timestamp": sample.get("timestamp") or sample.get("ts"),
            "patient_id": sample.get("patient_id"),
            "room": sample.get("room", ""),
            "scenario": sample.get("scenario", ""),
            "profile": sample.get("profile", ""),
            "pathology": sample.get("pathology") or sample.get("scenario_label") or sample.get("scenario", ""),
            "heart_rate": float(sample.get("heart_rate", sample.get("hr", 0.0))),
            "spo2": float(sample.get("spo2", 0.0)),
            "temperature": float(sample.get("temperature", sample.get("temp", 0.0))),
            "systolic_bp": float(sample.get("systolic_bp", sample.get("sbp", 0.0))),
            "diastolic_bp": float(sample.get("diastolic_bp", sample.get("dbp", 0.0))),
            "respiratory_rate": float(sample.get("respiratory_rate", sample.get("rr", 0.0))),
            "alert_count": int(sample.get("alert_count", 0)),
            "has_critical": int(sample.get("has_critical", 0)),
        }

    def record_vital_sample(self, sample: dict[str, Any]) -> None:
        row = self._normalize_sample(sample)
        pd.DataFrame([row]).to_csv(
            self.vitals_csv,
            mode="a",
            index=False,
            header=False,
        )

    def load_dataset(self) -> pd.DataFrame:
        self.ensure_data_files()
        df = pd.read_csv(self.vitals_csv)
        if self.feedback_csv.exists():
            df_feedback = pd.read_csv(self.feedback_csv)
            df = pd.concat([df, df_feedback], ignore_index=True)
        for col in FEATURES + [TARGET]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        before = len(df)
        df = df.dropna(subset=FEATURES + [TARGET])
        after = len(df)
        if after == 0:
            raise ValueError("Pas de donnees exploitables pour entrainer le modele.")
        log(f"[dataset] {after}/{before} lignes conservees apres nettoyage.")
        return df

    def build_pipeline(self) -> Pipeline:
        return Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=200)),
            ]
        )

    def train(self) -> dict[str, float | str | None]:
        df = self.load_dataset()
        X = df[FEATURES]
        y = df[TARGET]
        if y.nunique() < 2:
            raise ValueError("Le dataset ne contient qu'une seule classe.")
        pipeline = self.build_pipeline()
        class_counts = y.value_counts()
        if len(df) < 10 or int(class_counts.min()) < 2:
            pipeline.fit(X, y)
            acc = None
            mode = "fit_without_holdout"
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            pipeline.fit(X_train, y_train)
            acc = float(accuracy_score(y_test, pipeline.predict(X_test)))
            mode = "train_test_split"
        joblib.dump(pipeline, self.model_path)
        log(f"[train] Modele sauvegarde dans {self.model_path}")
        return {"accuracy": acc, "rows": float(len(df)), "mode": mode}

    def load_model(self):
        if not self.model_path.exists():
            try:
                self.train()
            except Exception as exc:  # noqa: BLE001
                log(f"[model] Impossible d'entrainer: {exc}")
                return None
        try:
            return joblib.load(self.model_path)
        except Exception as exc:  # noqa: BLE001
            log(f"[model] Chargement impossible: {exc}")
            return None

    def predict(self, sample: dict[str, Any]) -> float | None:
        pipeline = self.load_model()
        row = self._normalize_sample(sample)
        X = pd.DataFrame([{feature: row[feature] for feature in FEATURES}])
        if pipeline is None:
            return None
        proba = pipeline.predict_proba(X)[0][1]
        return float(proba)

    def append_feedback(self, sample: dict[str, Any], label: int) -> None:
        row = self._normalize_sample(sample)
        row[TARGET] = int(label)
        write_header = not self.feedback_csv.exists()
        pd.DataFrame([row]).to_csv(self.feedback_csv, mode="a", index=False, header=write_header)


def build_cli(service: CriticityMLService) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Service ML CLI (train/predict).")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("train", help="Entraine et sauvegarde le modele.")
    predict_parser = subparsers.add_parser("predict", help="Predit la probabilite de criticite.")
    predict_parser.add_argument("--sample", type=str, required=True, help="Echantillon JSON.")
    return parser


def cli() -> None:
    service = CriticityMLService(Path("/app/runtime/ml"))
    parser = build_cli(service)
    args = parser.parse_args()
    if args.command == "train":
        try:
            print(json.dumps(service.train()))
        except Exception as exc:  # noqa: BLE001
            log(f"[train] Echec: {exc}")
            sys.exit(1)
    if args.command == "predict":
        sample = json.loads(args.sample)
        try:
            proba = service.predict(sample)
            print(json.dumps({"probability": proba}))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"probability": None, "warning": str(exc)}))
            sys.exit(1)


if __name__ == "__main__":
    cli()
