from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables

load_dotenv()

# Base directory

BASE_DIR = Path(__file__).resolve().parent.parent

# Security

SECRET_KEY = os.getenv(
"SECRET_KEY",
"django-insecure-cloudpulse-dev-key"
)

DEBUG = os.getenv("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    ".onrender.com",
    "localhost",
    "127.0.0.1",
]

# Installed apps

INSTALLED_APPS = [
'django.contrib.admin',
'django.contrib.auth',
'django.contrib.contenttypes',
'django.contrib.sessions',
'django.contrib.messages',
'django.contrib.staticfiles',


# Local apps
'advisor.apps.AdvisorConfig',

]

# Middleware

MIDDLEWARE = [
'django.middleware.security.SecurityMiddleware',
'whitenoise.middleware.WhiteNoiseMiddleware',
'django.contrib.sessions.middleware.SessionMiddleware',
'django.middleware.common.CommonMiddleware',
'django.middleware.csrf.CsrfViewMiddleware',
'django.contrib.auth.middleware.AuthenticationMiddleware',
'django.contrib.messages.middleware.MessageMiddleware',
'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cloudPulse.urls'

# Templates

TEMPLATES = [
{
'BACKEND': 'django.template.backends.django.DjangoTemplates',


    # Template directory
    'DIRS': [
        BASE_DIR / "advisor/templates",
    ],

    'APP_DIRS': True,

    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
},


]

WSGI_APPLICATION = 'cloudPulse.wsgi.application'

# Database

DATABASES = {
'default': {
'ENGINE': 'django.db.backends.sqlite3',
'NAME': BASE_DIR / 'db.sqlite3',
}
}

# Password validators

AUTH_PASSWORD_VALIDATORS = [
{
'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
},
{
'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
},
{
'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
},
{
'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
},
]

# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True
USE_TZ = True

# Static files

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "advisor/static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

# Default primary key

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication redirects

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Email configuration

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Session settings

SESSION_COOKIE_AGE = 86400
SESSION_SAVE_EVERY_REQUEST = True

STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
)