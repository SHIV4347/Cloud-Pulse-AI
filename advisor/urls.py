from django.urls import path
from . import views

app_name = "advisor"

urlpatterns = [

    path("", views.index, name="index"),

    path("login/", views.login_user, name="login"),

    path("register/", views.register_user, name="register"),

    path("logout/", views.logout_user, name="logout"),

    path(
        "forgot-password/",
        views.forgot_password,
        name="forgot_password"
    ),

    path(
        "dashboard/",
        views.dashboard,
        name="dashboard"
    ),

    path(
        "profile/",
        views.profile_page,
        name="profile"
    ),

    path(
        "anomalies/",
        views.anomalies_list,
        name="anomalies_list"
    ),

    path(
        "recommendations/",
        views.recommendations_list,
        name="recommendations_list"
    ),

    path(
        "live-update/",
        views.live_update,
        name="live_update"
    ),

]