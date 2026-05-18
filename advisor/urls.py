# advisor/urls.py
from django.urls import path
from . import views

app_name = "advisor"

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("live-update/", views.live_update, name="live_update"),
    path("force-anomaly/", views.force_anomaly, name="force_anomaly"),
    path("solve-anomaly/", views.solve_anomaly, name="solve_anomaly"),
    path("anomalies/", views.anomalies_list, name="anomalies_list"),
    path("recommendations/", views.recommendations_list, name="recommendations_list"),
    path("profile/", views.profile_page, name="profile"),
    path("login/", views.login_user, name="login"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("logout/", views.logout_user, name="logout"),
    path("register/", views.register_user, name="register"),
]
