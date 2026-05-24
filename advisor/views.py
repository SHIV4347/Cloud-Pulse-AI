# advisor/views.py

import json
import random
import pandas as pd

from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect
from django.conf import settings

from django.contrib.auth import (
    authenticate,
    login,
    logout
)

from django.contrib.auth.decorators import login_required

from django.contrib.auth.password_validation import (
    validate_password
)

from django.core.mail import send_mail

from django.core.exceptions import ValidationError

from django.core.validators import validate_email

from django.http import JsonResponse

from django.contrib.auth.models import User

from .models import Profile

from .anomaly_detector import detect_hourly_anomalies

from .recommendations import get_recommendations


BASE_DIR = Path(__file__).resolve().parent

ADVISOR_DIR = BASE_DIR

# Prevent repeated anomaly email spam
LAST_EMAIL_ALERTS = {}


# =========================
# FORECAST HELPER
# =========================

try:

    from advisor.forecast_model import (
        train_and_forecast
    )

except Exception:

    train_and_forecast = None


# =========================
# HELPERS
# =========================

def clean_text(value):

    return (value or "").strip()


# =========================
# EMAIL ALERTS
# =========================

def send_anomaly_email(alert):

    global LAST_EMAIL_ALERTS

    service = alert.get("service")

    severity = alert.get("severity")

    timestamp = alert.get("timestamp")

    description = alert.get("description")

    cooldown_key = (
        service,
        severity
    )

    now = datetime.now()

    # 15-minute cooldown
    if cooldown_key in LAST_EMAIL_ALERTS:

        last_sent = LAST_EMAIL_ALERTS[
            cooldown_key
        ]

        if now - last_sent < timedelta(minutes=15):

            return

    LAST_EMAIL_ALERTS[
        cooldown_key
    ] = now

    users = User.objects.all()

    recipient_list = []

    for u in users:

        if u.email:

            recipient_list.append(u.email)

        try:

            extras = (
                u.profile.get_email_list()
            )

            recipient_list.extend(extras)

        except Exception:
            pass

    recipient_list = list(
        set(recipient_list)
    )

    if not recipient_list:
        return

    try:

        send_mail(

            subject=(
                "[CloudPulse AI] "
                "Critical AWS Anomaly Detected"
            ),

            message=(

                "CloudPulse AI has detected "
                "an abnormal AWS spending pattern.\n\n"

                f"Service: {service}\n"

                f"Severity: {severity.upper()}\n"

                f"Detected At: {timestamp}\n\n"

                f"AI Observation:\n"
                f"{description}\n\n"

                "Recommended Action:\n"

                "Review workload scaling, "
                "traffic distribution, and "
                "resource allocation.\n\n"

                "CloudPulse AI Monitoring Engine"
            ),

            from_email=settings.DEFAULT_FROM_EMAIL,

            recipient_list=recipient_list,

            fail_silently=True,
        )

        print(
            "Anomaly email sent successfully."
        )

    except Exception as e:

        print(
            "Anomaly email failed:",
            e
        )


# =========================
# LIVE BILLING SIMULATION
# =========================

def append_one_live_hour(force=False):

    csv_path = (
        ADVISOR_DIR / "billing_hourly.csv"
    )

    if not csv_path.exists():

        df = pd.DataFrame(
            columns=[
                "timestamp",
                "service",
                "cost",
                "forced_anomaly"
            ]
        )

        df.to_csv(csv_path, index=False)

    df = pd.read_csv(csv_path)

    now = datetime.now()

    hour = now.hour

    weekday = now.weekday()

    service_weights = {

        "EC2": 0.34,
        "S3": 0.18,
        "RDS": 0.18,
        "CloudFront": 0.14,
        "Lambda": 0.10,
        "EBS": 0.06,
    }

    services = list(service_weights.keys())

    weights = list(service_weights.values())

    svc = random.choices(
        services,
        weights=weights,
        k=1
    )[0]

    base_map = {

        "EC2": 24,
        "S3": 9,
        "RDS": 16,
        "CloudFront": 12,
        "Lambda": 7,
        "EBS": 6,
    }

    baseline = base_map.get(svc, 10)

    if 9 <= hour <= 19:
        baseline *= 1.45

    elif 0 <= hour <= 5:
        baseline *= 0.65

    if weekday >= 5:
        baseline *= 0.78

    noise = random.normalvariate(
        0,
        baseline * 0.08
    )

    cost = baseline + noise

    if force:

        spike_multiplier = random.uniform(
            3.2,
            5.5
        )

        cost *= spike_multiplier

    elif random.random() < 0.012:

        spike_multiplier = random.uniform(
            2.2,
            3.8
        )

        cost *= spike_multiplier

    cost = round(
        max(0.4, cost),
        2
    )

    new_row = {

        "timestamp": now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "service": svc,

        "cost": cost,

        "forced_anomaly": force
    }

    df = pd.concat(
        [df, pd.DataFrame([new_row])],
        ignore_index=True
    )

    df.to_csv(csv_path, index=False)

    return new_row


# =========================
# DASHBOARD
# =========================

@login_required
def dashboard(request):

    hourly_path = (
        ADVISOR_DIR / "billing_hourly.csv"
    )

    hourly_chart = []

    if hourly_path.exists():

        df_hourly = pd.read_csv(hourly_path)

        df_hourly["timestamp"] = pd.to_datetime(
            df_hourly["timestamp"],
            errors="coerce"
        )

        df_total = (

            df_hourly

            .groupby(
                "timestamp",
                as_index=False
            )["cost"]

            .sum()

            .sort_values("timestamp")
        )

        last_points = df_total.tail(72)

        hourly_chart = [

            {
                "timestamp": t.strftime(
                    "%Y-%m-%d %H:%M"
                ),

                "cost": float(c)
            }

            for t, c in zip(
                last_points["timestamp"],
                last_points["cost"]
            )
        ]

    # =========================
    # ANOMALIES
    # =========================

    anomalies = detect_hourly_anomalies()

    top_anomalies = sorted(

        anomalies,

        key=lambda x: x.get(
            "timestamp",
            ""
        ),

        reverse=True

    )[:12]

    # =========================
    # RECOMMENDATIONS
    # =========================

    recs = get_recommendations()

    top_recs = sorted(

        recs,

        key=lambda x: x.get(
            "savings_value",
            0
        ),

        reverse=True

    )[:5]

    # =========================
    # FORECAST CHART
    # =========================

    forecast_chart = []

    if hourly_chart:

        recent_costs = [

            p["cost"]

            for p in hourly_chart[-12:]
        ]

        avg_recent = (

            sum(recent_costs)

            / max(1, len(recent_costs))
        )

        last_time = datetime.strptime(

            hourly_chart[-1]["timestamp"],

            "%Y-%m-%d %H:%M"
        )

        next_cost = avg_recent

        for i in range(12):

            future_time = (

                last_time

                + timedelta(hours=i + 1)
            )

            # smoother realistic trend
            next_cost *= random.uniform(
                0.992,
                1.018
            )

            forecast_chart.append({

                "timestamp":
                    future_time.strftime(
                        "%Y-%m-%d %H:%M"
                    ),

                "cost":
                    round(next_cost, 2)
            })

    # =========================
    # KPI CALCULATIONS
    # =========================

    if hourly_chart:

        costs = [

            p["cost"]

            for p in hourly_chart
        ]

        # REAL ACTUAL COST
        total_cost = round(
            sum(costs),
            2
        )

        # TREND ANALYSIS
        recent_avg = (

            sum(costs[-12:])

            / max(1, len(costs[-12:]))
        )

        overall_avg = (

            sum(costs)

            / max(1, len(costs))
        )

        trend_multiplier = (
            recent_avg / overall_avg
        )

        trend_multiplier = max(
            0.95,
            min(1.25, trend_multiplier)
        )

        # FORECASTED COST
        predicted_next_month = round(

            total_cost
            * trend_multiplier
            * 1.08,

            2
        )

    else:

        total_cost = 220.00

        predicted_next_month = 245.00

    # =========================
    # SAVINGS CALCULATION
    # =========================

    recommendation_savings = sum(

        float(
            r.get(
                "savings_value",
                0
            )
        )

        for r in top_recs
    )

    # fallback if recommendations empty
    if recommendation_savings <= 0:

        recommendation_savings = (

            predicted_next_month
            * 0.12
        )

    savings = round(
        recommendation_savings,
        2
    )

    # =========================
    # SUMMARY
    # =========================

    summary = {

        "total_cost":
            total_cost,

        "change_percentage":
            round(
                random.uniform(
                    2.0,
                    8.0
                ),
                1
            ),

        "predicted_next_month":
            predicted_next_month,

        "savings":
            savings,
    }

    # =========================
    # CONTEXT
    # =========================

    context = {

        "summary":
            summary,

        "hourly_chart_json":
            json.dumps(hourly_chart),

        "anomaly_points_json":
            json.dumps(top_anomalies),

        "forecast_chart_json":
            json.dumps(forecast_chart),

        "top_anomalies":
            top_anomalies,

        "top_recs":
            top_recs,
    }

    return render(

        request,

        "advisor/dashboard.html",

        context
    )

# =========================
# LIVE UPDATE
# =========================

@login_required
def live_update(request):

    force_flag = (
        request.GET.get("force", "0") == "1"
    )

    append_one_live_hour(
        force=force_flag
    )

    hourly_path = (
        ADVISOR_DIR / "billing_hourly.csv"
    )

    hourly_chart = []

    if hourly_path.exists():

        df_hourly = pd.read_csv(
            hourly_path
        )

        df_hourly["timestamp"] = pd.to_datetime(
            df_hourly["timestamp"],
            errors="coerce"
        )

        df_total = (

            df_hourly

            .groupby(
                "timestamp",
                as_index=False
            )["cost"]

            .sum()

            .sort_values("timestamp")
        )

        last_points = df_total.tail(72)

        hourly_chart = [

            {
                "timestamp": t.strftime(
                    "%Y-%m-%d %H:%M"
                ),

                "cost": float(c)
            }

            for t, c in zip(
                last_points["timestamp"],
                last_points["cost"]
            )
        ]

    anomalies_all = detect_hourly_anomalies()

    top_anoms = sorted(

        anomalies_all,

        key=lambda x: x.get(
            "timestamp",
            ""
        ),

        reverse=True

    )[:12]

    # Send email only for manually triggered anomaly
    if force_flag and top_anoms:

        send_anomaly_email(
            top_anoms[0]
        )

    # Forecast
    if hourly_chart:

        recent = [
            p["cost"]
            for p in hourly_chart[-12:]
        ]

        avg = (
            sum(recent) / len(recent)
        )

    else:

        avg = 20

    forecast = []

    for i in range(12):

        forecast.append({

            "timestamp":
                f"forecast-{i}",

            "cost":
                round(
                    avg * (1 + (i * 0.015)),
                    2
                )
        })

    return JsonResponse({

        "hourly":
            hourly_chart,

        "top_anomalies":
            top_anoms,

        "new_anomalies": (

            top_anoms[:1]

            if force_flag

            else []
        ),

        "forecast":
            forecast,
    })


# =========================
# AUTH
# =========================

def login_user(request):

    if request.method == "POST":

        email = clean_text(
            request.POST.get("email")
        ).lower()

        pwd = request.POST.get(
            "password"
        ) or ""

        user_obj = User.objects.filter(
            email__iexact=email
        ).first()

        user = None

        if user_obj:

            user = authenticate(

                request,

                username=user_obj.username,

                password=pwd
            )

        if user:

            login(request, user)

            return redirect(
                "advisor:dashboard"
            )

        return render(

            request,

            "advisor/login.html",

            {
                "error":
                    "Invalid email or password."
            }
        )

    return render(
        request,
        "advisor/login.html"
    )


def logout_user(request):

    logout(request)

    return redirect("advisor:login")


# =========================
# REGISTER
# =========================

def register_user(request):

    if request.method == "POST":

        username = clean_text(
            request.POST.get("username")
        )

        email = clean_text(
            request.POST.get("email")
        )

        password = request.POST.get(
            "password"
        )

        first_name = clean_text(
            request.POST.get("first_name")
        )

        last_name = clean_text(
            request.POST.get("last_name")
        )

        if User.objects.filter(
            username=username
        ).exists():

            return render(

                request,

                "advisor/register.html",

                {
                    "error":
                        "Username already exists."
                }
            )

        user = User.objects.create_user(

            username=username,

            email=email,

            password=password,

            first_name=first_name,

            last_name=last_name,
        )

        Profile.objects.get_or_create(
            user=user
        )

        try:

            send_mail(

                subject="Welcome to CloudPulse AI",

                message=(

                    f"Hello {user.first_name},\n\n"

                    "Your AWS FinOps account "
                    "has been created successfully.\n\n"

                    "CloudPulse AI"
                ),

                from_email=settings.DEFAULT_FROM_EMAIL,

                recipient_list=[user.email],

                fail_silently=True,
            )

        except Exception as e:

            print("Email failed:", e)

        login(request, user)

        return redirect(
            "advisor:dashboard"
        )

    return render(
        request,
        "advisor/register.html"
    )


# =========================
# PROFILE
# =========================

@login_required
def profile_page(request):

    profile, _ = Profile.objects.get_or_create(
        user=request.user
    )

    return render(

        request,

        "advisor/profile.html",

        {
            "profile": profile
        }
    )


# =========================
# OTHER PAGES
# =========================

@login_required
def anomalies_list(request):

    anomalies = detect_hourly_anomalies()

    return render(

        request,

        "advisor/anomalies.html",

        {
            "anomalies": anomalies
        }
    )


@login_required
def recommendations_list(request):

    recs = get_recommendations()

    return render(

        request,

        "advisor/recommendations.html",

        {
            "recs": recs
        }
    )


def forgot_password(request):

    if request.method == "POST":

        step = request.POST.get("step")

        # =========================
        # STEP 1 — SEND OTP
        # =========================

        if step == "send_otp":

            email = clean_text(
                request.POST.get("email")
            ).lower()

            if not email:

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            "Email is required."
                    }
                )

            user = User.objects.filter(
                email__iexact=email
            ).first()

            if not user:

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            "No account found with this email."
                    }
                )

            otp = str(
                random.randint(
                    100000,
                    999999
                )
            )

            request.session[
                "reset_email"
            ] = email

            request.session[
                "reset_otp"
            ] = otp

            request.session[
                "reset_otp_expiry"
            ] = (
                datetime.now()
                + timedelta(minutes=10)
            ).isoformat()

            try:

                send_mail(

                    subject=
                    "CloudPulse AI Password Reset OTP",

                    message=(

                        f"Hello {user.first_name},\n\n"

                        "Your password reset "
                        f"verification code is:\n\n"

                        f"{otp}\n\n"

                        "This OTP expires in 10 minutes.\n\n"

                        "CloudPulse AI Security"
                    ),

                    from_email=
                        settings.DEFAULT_FROM_EMAIL,

                    recipient_list=[email],

                    fail_silently=False,
                )

            except Exception as e:

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            f"Failed to send OTP email: {e}"
                    }
                )

            return render(

                request,

                "advisor/forgot_password.html",

                {
                    "otp_sent": True,

                    "email": email,

                    "success":
                        "OTP sent successfully."
                }
            )

        # =========================
        # STEP 2 — VERIFY OTP
        # =========================

        elif step == "verify_otp":

            email = clean_text(
                request.POST.get("email")
            ).lower()

            otp = clean_text(
                request.POST.get("otp")
            )

            password = (
                request.POST.get("password")
                or ""
            )

            password2 = (
                request.POST.get("password2")
                or ""
            )

            session_email = request.session.get(
                "reset_email"
            )

            session_otp = request.session.get(
                "reset_otp"
            )

            expiry = request.session.get(
                "reset_otp_expiry"
            )

            if (
                not session_email
                or
                not session_otp
                or
                not expiry
            ):

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            "OTP session expired. Try again."
                    }
                )

            expiry_time = datetime.fromisoformat(
                expiry
            )

            if datetime.now() > expiry_time:

                request.session.flush()

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            "OTP expired."
                    }
                )

            if email != session_email:

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            "Email mismatch.",

                        "otp_sent": True,

                        "email": email
                    }
                )

            if otp != session_otp:

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            "Invalid OTP.",

                        "otp_sent": True,

                        "email": email
                    }
                )

            if password != password2:

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            "Passwords do not match.",

                        "otp_sent": True,

                        "email": email
                    }
                )

            # Django password validation

            try:

                validate_password(password)

            except ValidationError as e:

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            " ".join(e.messages),

                        "otp_sent": True,

                        "email": email
                    }
                )

            user = User.objects.filter(
                email__iexact=email
            ).first()

            if not user:

                return render(

                    request,

                    "advisor/forgot_password.html",

                    {
                        "error":
                            "User not found."
                    }
                )

            user.set_password(password)

            user.save()

            # clear session
            request.session.pop(
                "reset_email",
                None
            )

            request.session.pop(
                "reset_otp",
                None
            )

            request.session.pop(
                "reset_otp_expiry",
                None
            )

            return render(

                request,

                "advisor/login.html",

                {
                    "success":
                        "Password updated successfully. Please login."
                }
            )

    return render(
        request,
        "advisor/forgot_password.html"
    )


# =========================
# INDEX
# =========================

def index(request):

    return render(
        request,
        "advisor/index.html"
    )