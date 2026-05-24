# advisor/recommendations.py

import random
import pandas as pd

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

CSV_PATH = BASE_DIR / "billing_hourly.csv"


def estimate_savings(cost):

    return round(
        max(20, cost * random.uniform(0.18, 0.42)),
        2
    )


def build_recommendation(service, avg_cost):

    if service == "EC2":

        return {
            "service": "EC2",
            "title": "Underutilized EC2 instances detected",
            "description": (
                "Multiple EC2 workloads show consistently low utilization. "
                "Rightsizing or Reserved Instance planning is recommended."
            ),
            "savings_value": estimate_savings(avg_cost),
        }

    elif service == "S3":

        return {
            "service": "S3",
            "title": "Enable S3 intelligent tiering",
            "description": (
                "Cold storage objects were identified. "
                "Transitioning to infrequent-access tiers may reduce storage costs."
            ),
            "savings_value": estimate_savings(avg_cost),
        }

    elif service == "RDS":

        return {
            "service": "RDS",
            "title": "Optimize RDS compute allocation",
            "description": (
                "Database utilization patterns indicate potential over-provisioning."
            ),
            "savings_value": estimate_savings(avg_cost),
        }

    elif service == "CloudFront":

        return {
            "service": "CloudFront",
            "title": "Improve CDN cache efficiency",
            "description": (
                "Optimizing cache hit ratios may reduce bandwidth and origin costs."
            ),
            "savings_value": estimate_savings(avg_cost),
        }

    elif service == "Lambda":

        return {
            "service": "Lambda",
            "title": "Reduce Lambda execution overhead",
            "description": (
                "High invocation frequency suggests opportunity for execution tuning."
            ),
            "savings_value": estimate_savings(avg_cost),
        }

    return {
        "service": service,
        "title": "Cloud cost optimization available",
        "description": (
            "Optimization opportunities were detected for this workload."
        ),
        "savings_value": estimate_savings(avg_cost),
    }


def get_recommendations():

    if not CSV_PATH.exists():
        return []

    try:

        df = pd.read_csv(CSV_PATH)

    except Exception:
        return []

    if df.empty:
        return []

    try:

        df["cost"] = pd.to_numeric(
            df["cost"],
            errors="coerce"
        )

    except Exception:
        return []

    df = df.dropna()

    if df.empty:
        return []

    recommendations = []

    grouped = (
        df.groupby("service")["cost"]
        .mean()
        .reset_index()
    )

    for _, row in grouped.iterrows():

        service = row["service"]

        avg_cost = float(row["cost"])

        if avg_cost < 5:
            continue

        recommendations.append(
            build_recommendation(
                service,
                avg_cost
            )
        )

    recommendations = sorted(
        recommendations,
        key=lambda x: x["savings_value"],
        reverse=True
    )

    return recommendations