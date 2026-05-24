# advisor/anomaly_detector.py

import pandas as pd

from pathlib import Path

from sklearn.ensemble import IsolationForest


BASE_DIR = Path(__file__).resolve().parent

CSV_PATH = BASE_DIR / "billing_hourly.csv"

LAST_ALERTS = {}


SERVICE_DESCRIPTIONS = {

    "EC2":
        "Unexpected EC2 compute surge detected",

    "S3":
        "Abnormal S3 storage activity detected",

    "RDS":
        "RDS workload exceeded learned baseline",

    "CloudFront":
        "CloudFront traffic anomaly detected",

    "Lambda":
        "Lambda invocation spike detected",

    "EBS":
        "Unexpected EBS usage variation detected",
}


def calculate_severity(score):

    if score < -0.35:
        return "high"

    elif score < -0.18:
        return "medium"

    return "low"


def detect_hourly_anomalies():

    if not CSV_PATH.exists():
        return []

    try:

        df = pd.read_csv(CSV_PATH)

    except Exception:
        return []

    if len(df) < 20:
        return []

    try:

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce"
        )

        df["cost"] = pd.to_numeric(
            df["cost"],
            errors="coerce"
        )

    except Exception:
        return []

    df = df.dropna()

    if df.empty:
        return []

    # Ensure forced flag exists
    if "forced_anomaly" not in df.columns:

        df["forced_anomaly"] = False

    # ===== FEATURES =====

    df["hour"] = df["timestamp"].dt.hour

    df["weekday"] = df["timestamp"].dt.weekday

    service_map = {

        s: i

        for i, s in enumerate(
            df["service"].unique()
        )
    }

    df["service_encoded"] = (
        df["service"]
        .map(service_map)
    )

    features = df[[

        "cost",

        "hour",

        "weekday",

        "service_encoded"
    ]]

    # ===== ML MODEL =====

    model = IsolationForest(

        contamination=0.04,

        random_state=42,

        n_estimators=150
    )

    model.fit(features)

    df["anomaly"] = model.predict(
        features
    )

    df["score"] = model.decision_function(
        features
    )

    anomalies = []

    for _, row in df.iterrows():

        is_forced = bool(
            row.get("forced_anomaly", False)
        )

        is_ml_anomaly = (
            row["anomaly"] == -1
        )

        if not (
            is_forced
            or
            is_ml_anomaly
        ):
            continue

        service = row["service"]

        timestamp = row["timestamp"]

        score = float(
            row["score"]
        )

        severity = (

            "critical"

            if is_forced

            else calculate_severity(score)
        )

        description = SERVICE_DESCRIPTIONS.get(

            service,

            "Cloud anomaly detected"
        )

        anomalies.append({

            "timestamp":
                timestamp.strftime(
                    "%Y-%m-%d %H:%M"
                ),

            "service":
                service,

            "severity":
                severity,

            "cost":
                round(
                    float(row["cost"]),
                    2
                ),

            "score":
                round(score, 3),

            "description":
                description,

            "forced":
                is_forced,
        })

    anomalies = sorted(

        anomalies,

        key=lambda x: x["timestamp"],

        reverse=True
    )

    return anomalies[:30]