# advisor/views.py
import json
import random
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse, HttpResponse

BASE_DIR = Path(__file__).resolve().parent
ADVISOR_DIR = BASE_DIR  # files live in advisor/

# Try to import long-term forecast helper. If missing, we continue without crash.
try:
    from advisor.forecast_model import train_and_forecast
except Exception as e:
    train_and_forecast = None

from .anomaly_detector import detect_hourly_anomalies
from .recommendations import get_recommendations
from .models import Profile
from django.contrib.auth.models import User


def clean_text(value):
    return (value or "").strip()


def validate_account_fields(data, current_user=None, require_password=True):
    errors = {}
    username = clean_text(data.get("username"))
    email = clean_text(data.get("email")).lower()
    first_name = clean_text(data.get("first_name"))
    last_name = clean_text(data.get("last_name"))
    phone = clean_text(data.get("phone"))
    company = clean_text(data.get("company"))
    role = clean_text(data.get("role"))
    cloud_provider = clean_text(data.get("cloud_provider"))
    monthly_budget_raw = clean_text(data.get("monthly_budget"))
    password = data.get("password") or ""
    password2 = data.get("password2") or ""

    if not username:
        errors["username"] = "Username is required."
    elif len(username) < 3:
        errors["username"] = "Username must be at least 3 characters."
    elif "@" in username:
        errors["username"] = "Username must be different from your email."
    elif User.objects.filter(username__iexact=username).exclude(pk=getattr(current_user, "pk", None)).exists():
        errors["username"] = "This username is already taken."

    if not email:
        errors["email"] = "Email is required."
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors["email"] = "Enter a valid email address."
        if User.objects.filter(email__iexact=email).exclude(pk=getattr(current_user, "pk", None)).exists():
            errors["email"] = "This email is already registered."

    if username and email and username.lower() == email.lower():
        errors["username"] = "Username and email must be different."

    if not first_name:
        errors["first_name"] = "First name is required."
    if not last_name:
        errors["last_name"] = "Last name is required."
    if phone and (len(phone) < 7 or not all(ch.isdigit() or ch in "+- ()" for ch in phone)):
        errors["phone"] = "Enter a valid phone number."
    if not company:
        errors["company"] = "Company is required."
    if not role:
        errors["role"] = "Role is required."
    if cloud_provider not in {"AWS", "Azure", "GCP", "Multi-cloud", "Other"}:
        errors["cloud_provider"] = "Select a cloud provider."

    monthly_budget = None
    if monthly_budget_raw:
        try:
            monthly_budget = Decimal(monthly_budget_raw)
            if monthly_budget < 0:
                errors["monthly_budget"] = "Budget cannot be negative."
        except InvalidOperation:
            errors["monthly_budget"] = "Enter a valid budget amount."

    if require_password:
        if not password:
            errors["password"] = "Password is required."
        elif password != password2:
            errors["password2"] = "Passwords do not match."
        else:
            try:
                validate_password(password, user=current_user)
            except ValidationError as exc:
                errors["password"] = " ".join(exc.messages)

    cleaned = {
        "username": username,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "company": company,
        "role": role,
        "cloud_provider": cloud_provider,
        "monthly_budget": monthly_budget,
    }
    return cleaned, errors

# helper read/write extra emails (simple file-based fallback removed: use Profile)
def read_extra_emails(username):
    try:
        u = User.objects.get(username=username)
        return u.profile.get_email_list()
    except Exception:
        return []

def write_extra_emails(username, emails_list):
    try:
        u = User.objects.get(username=username)
        u.profile.extra_emails = ",".join(emails_list)
        u.profile.save()
    except Exception:
        pass

# Append a simulated hour row to billing_hourly.csv
def append_one_live_hour(force=False):
    csv_path = ADVISOR_DIR / "billing_hourly.csv"
    if not csv_path.exists():
        # create an initial file with some synthetic data
        df = pd.DataFrame(columns=["timestamp", "service", "cost"])
        df.to_csv(csv_path, index=False)

    df = pd.read_csv(csv_path)
    now = datetime.now()
    svc = random.choice(["EC2", "S3", "RDS", "CloudFront"])
    baseline = round(random.uniform(8.0, 25.0), 2)

    # if force True -> big spike
    if force or random.random() < 0.02:
        cost = round(baseline * random.uniform(2.5, 5.0), 2)
    else:
        noise = random.normalvariate(0, baseline * 0.08)
        cost = round(max(0.1, baseline + noise), 2)

    new_row = {"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "service": svc, "cost": cost}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(csv_path, index=False)
    return new_row

@login_required
def live_update(request):
    # if client asked to force anomaly (button), we set force=True
    force_flag = request.GET.get("force", "0") == "1"
    new_row = append_one_live_hour(force=force_flag)

    hourly_path = ADVISOR_DIR / "billing_hourly.csv"
    df_hourly = pd.read_csv(hourly_path)
    df_hourly["timestamp"] = pd.to_datetime(df_hourly["timestamp"], errors="coerce")
    df_total = df_hourly.groupby("timestamp", as_index=False)["cost"].sum().sort_values("timestamp")
    last_points = df_total.tail(72)

    hourly_chart = [{"timestamp": t.strftime("%Y-%m-%d %H:%M"), "cost": float(c)} for t, c in zip(last_points["timestamp"], last_points["cost"])]

    # simple short-term "prediction": linear extrapolation from last 6 points
    future = []
    if len(last_points) >= 6:
        window = last_points.tail(6).reset_index(drop=True)
        x = list(range(len(window)))
        coef = (window["cost"].iloc[-1] - window["cost"].iloc[0]) / max(1, (x[-1] - x[0]))
        last_ts = pd.to_datetime(window["timestamp"].iloc[-1])
        for i in range(1, 13):  # next 12 hours (demo)
            ts = (last_ts + pd.Timedelta(hours=i)).strftime("%Y-%m-%d %H:%M")
            pred_val = float(max(0.1, window["cost"].iloc[-1] + coef * i))
            future.append({"timestamp": ts, "predicted": round(pred_val, 2)})

    anomalies_all = detect_hourly_anomalies()
    # pick anomalies that match last appended timestamp (minute resolution)
    new_anoms = []
    if new_row:
        new_ts_min = datetime.strptime(new_row["timestamp"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
        for a in anomalies_all:
            if a.get("timestamp") == new_ts_min:
                new_anoms.append(a)

    # send email on new_anoms
    if new_anoms:
        try:
            user = request.user
            recipients = [user.email] if user.email else []
            recipients += read_extra_emails(user.username)
            subject = f"[CloudPulse AI] Anomaly detected at {new_ts_min}"
            body_lines = []
            for a in new_anoms:
                body_lines.append(f"{a['timestamp']} | {a['service']} | {a['severity']}\n{a['description']}\n")
            body = "\n".join(body_lines)
            if recipients:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
        except Exception as e:
            print("Email send failed:", e)

    # top 3 anomalies for UI
    top_anoms = sorted(anomalies_all, key=lambda x: x.get("timestamp", ""), reverse=True)[:3]

    # top recs
    recs = get_recommendations()
    top_recs = sorted(recs, key=lambda x: x.get("savings_value", 0), reverse=True)[:3]

    # summary numbers (from daily if exists)
    daily_path = ADVISOR_DIR / "billing_daily.csv"
    if daily_path.exists():
        df_daily = pd.read_csv(daily_path)
        total_cost = round(df_daily.tail(30)["total_cost"].sum(), 2) if not df_daily.empty else 0.0
    else:
        total_cost = round(df_total.tail(30)["cost"].sum(), 2) if not df_total.empty else 0.0

    # long-term forecast (if function exists)
    next_month_pred = 0.0
    if train_and_forecast:
        try:
            fdf = train_and_forecast()
            next_month_pred = round(float(fdf.tail(30)["yhat"].sum()), 2)
        except Exception:
            next_month_pred = 0.0

    savings = round(next_month_pred - total_cost, 2)

    return JsonResponse({
        "hourly": hourly_chart,
        "future": future,
        "new_anomalies": new_anoms,
        "top_anomalies": top_anoms,
        "top_recs": top_recs,
        "summary": {"total_cost": total_cost, "predicted_next_month": next_month_pred, "savings": savings}
    })


@login_required
def dashboard(request):
    hourly_path = ADVISOR_DIR / "billing_hourly.csv"
    if hourly_path.exists():
        df_hourly = pd.read_csv(hourly_path)
        df_hourly["timestamp"] = pd.to_datetime(df_hourly["timestamp"], errors="coerce")
        df_total = df_hourly.groupby("timestamp", as_index=False)["cost"].sum().sort_values("timestamp")
        last_points = df_total.tail(72)
        hourly_chart = [{"timestamp": t.strftime("%Y-%m-%d %H:%M"), "cost": float(c)} for t, c in zip(last_points["timestamp"], last_points["cost"])]
    else:
        hourly_chart = []

    anomalies = detect_hourly_anomalies()
    top_anomalies = sorted(anomalies, key=lambda x: x.get("timestamp", ""), reverse=True)[:3]
    recs = get_recommendations()
    top_recs = sorted(recs, key=lambda x: x.get("savings_value", 0), reverse=True)[:3]

    # summary (attempt train_and_forecast)
    next_month_pred = 0.0
    if train_and_forecast:
        try:
            fdf = train_and_forecast()
            next_month_pred = round(float(fdf.tail(30)["yhat"].sum()), 2)
        except Exception:
            next_month_pred = 0.0

    daily_path = ADVISOR_DIR / "billing_daily.csv"
    if daily_path.exists():
        df_daily = pd.read_csv(daily_path)
        total_cost = round(df_daily.tail(30)["total_cost"].sum(), 2) if not df_daily.empty else 0.0
    else:
        total_cost = 0.0

    summary = {"total_cost": total_cost, "change_percentage": 0.0, "predicted_next_month": next_month_pred, "savings": round(next_month_pred - total_cost, 2)}

    context = {
        "summary": summary,
        "hourly_chart_json": json.dumps(hourly_chart),
        "top_anomalies": top_anomalies,
        "top_recs": top_recs,
    }
    return render(request, "advisor/dashboard.html", context)


@login_required
def force_anomaly(request):
    # create an anomaly_flag file used in other logic (if you used file-based)
    (ADVISOR_DIR / "anomaly_flag.txt").write_text("1")
    # also append an immediate forced spike (so live_update picks it)
    append_one_live_hour(force=True)
    return redirect("advisor:dashboard")


@login_required
def solve_anomaly(request):
    flag = ADVISOR_DIR / "anomaly_flag.txt"
    if flag.exists():
        flag.unlink()
    return redirect("advisor:dashboard")


@login_required
def anomalies_list(request):
    anomalies = detect_hourly_anomalies()
    return render(request, "advisor/anomalies.html", {"anomalies": anomalies})


@login_required
def recommendations_list(request):
    recs = get_recommendations()
    return render(request, "advisor/recommendations.html", {"recs": recs})


@login_required
def profile_page(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    if request.method == "POST":
        cleaned, errors = validate_account_fields(request.POST, current_user=user, require_password=False)
        extra = clean_text(request.POST.get("extra_emails"))
        emails = [e.strip() for e in extra.split(",") if e.strip()]
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                errors["extra_emails"] = "Enter valid comma-separated notification emails."
                break

        if errors:
            return render(request, "advisor/profile.html", {
                "errors": errors,
                "form": request.POST,
                "extras": emails,
            })

        user.username = cleaned["username"]
        user.email = cleaned["email"]
        user.first_name = cleaned["first_name"]
        user.last_name = cleaned["last_name"]
        user.save()

        profile.phone = cleaned["phone"]
        profile.company = cleaned["company"]
        profile.role = cleaned["role"]
        profile.cloud_provider = cleaned["cloud_provider"]
        profile.monthly_budget = cleaned["monthly_budget"]
        profile.extra_emails = ",".join(emails)
        profile.save()
        return redirect("advisor:profile")
    extras = read_extra_emails(user.username)
    form = {
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": profile.phone,
        "company": profile.company,
        "role": profile.role,
        "cloud_provider": profile.cloud_provider,
        "monthly_budget": profile.monthly_budget if profile.monthly_budget is not None else "",
        "extra_emails": ", ".join(extras),
    }
    return render(request, "advisor/profile.html", {"extras": extras, "form": form})


def index(request):
    return render(request, "advisor/index.html")



def login_user(request):
    if request.method == "POST":
        email = clean_text(request.POST.get("email")).lower()
        pwd = request.POST.get("password") or ""
        errors = {}
        if not email:
            errors["email"] = "Email is required."
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors["email"] = "Enter a valid email address."
        if not pwd:
            errors["password"] = "Password is required."
        if errors:
            return render(request, "advisor/login.html", {"errors": errors, "form": request.POST})

        user_obj = User.objects.filter(email__iexact=email).first()
        u = authenticate(request, username=user_obj.username, password=pwd) if user_obj else None
        if u:
            login(request, u)
            return redirect("advisor:dashboard")
        else:
            return render(request, "advisor/login.html", {
                "error": "Invalid email or password.",
                "form": request.POST,
            })
    return render(request, "advisor/login.html")


def logout_user(request):
    logout(request)
    return redirect("advisor:login")


def register_user(request):
    if request.method == "POST":
        cleaned, errors = validate_account_fields(request.POST, require_password=True)
        if errors:
            return render(request, "advisor/register.html", {"errors": errors, "form": request.POST})

        u = User.objects.create_user(
            username=cleaned["username"],
            email=cleaned["email"],
            password=request.POST.get("password"),
            first_name=cleaned["first_name"],
            last_name=cleaned["last_name"],
        )
        profile, _ = Profile.objects.get_or_create(user=u)
        profile.phone = cleaned["phone"]
        profile.company = cleaned["company"]
        profile.role = cleaned["role"]
        profile.cloud_provider = cleaned["cloud_provider"]
        profile.monthly_budget = cleaned["monthly_budget"]
        profile.save()
        login(request, u)
        return redirect("advisor:dashboard")
    return render(request, "advisor/register.html")


def forgot_password(request):
    if request.method == "POST":
        email = clean_text(request.POST.get("email")).lower()
        username = clean_text(request.POST.get("username"))
        password = request.POST.get("password") or ""
        password2 = request.POST.get("password2") or ""
        errors = {}

        if not email:
            errors["email"] = "Email is required."
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors["email"] = "Enter a valid email address."
        if not username:
            errors["username"] = "Username is required."
        if not password:
            errors["password"] = "New password is required."
        elif password != password2:
            errors["password2"] = "Passwords do not match."

        user = None
        if not errors:
            user = User.objects.filter(email__iexact=email, username__iexact=username).first()
            if not user:
                errors["email"] = "No account matched that email and username."
            else:
                try:
                    validate_password(password, user=user)
                except ValidationError as exc:
                    errors["password"] = " ".join(exc.messages)

        if errors:
            return render(request, "advisor/forgot_password.html", {"errors": errors, "form": request.POST})

        user.set_password(password)
        user.save()
        return render(request, "advisor/forgot_password.html", {
            "success": "Password updated. You can login with your new password.",
            "form": {"email": email, "username": username},
        })

    return render(request, "advisor/forgot_password.html")
