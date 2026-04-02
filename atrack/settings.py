import os
from datetime import timedelta
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-rog9@vvxb#=yz2un2tmzs31801qsm*7vf(l5k1%@r!lrx3u36$")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.getenv(
    "DJANGO_ALLOWED_HOSTS",
    "127.0.0.1,localhost,chatapi.bazhilgroups.in,api.teqtus.in",
).split(",")

INSTALLED_APPS = [
    "corsheaders",
    "unfold",
    "channels",
    "daphne",
    "rest_framework",
    "task",
    "chat",
    "user",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "atrack.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "atrack.wsgi.application"
ASGI_APPLICATION = "atrack.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
DATABASES = {
    "default": dj_database_url.parse(os.getenv("DATABASE_URL"))
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

CORS_ALLOWED_ORIGINS = [
    origin
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://task-frontend-eight-brown.vercel.app,https://chatapi.bazhilgroups.in,https://api.teqtus.in",
    ).split(",")
    if origin
]

CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "https://chatapi.bazhilgroups.in,https://api.teqtus.in,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin
]

CORS_ALLOW_CREDENTIALS = True

UNFOLD = {
    "SITE_TITLE": "RenderWays ",
    "SITE_HEADER": "RenderWays",
    "SITE_SYMBOL": "dashboard",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Navigation",
                "separator": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "group",
                        "link": "/admin/auth/user/",
                    },
                    {
                        "title": "Groups",
                        "icon": "shield_person",
                        "link": "/admin/auth/group/",
                    },
                    {
                        "title": "Tasks",
                        "icon": "task",
                        "link": "/admin/task/task/",
                    },
                    {
                        "title": "User Profiles",
                        "icon": "badge",
                        "link": "/admin/user/userprofile/",
                    },
                    {
                        "title": "Employee Chat",
                        "icon": "chat",
                        "link": "/admin/chat/message/live-chat/",
                    },
                ],
            }
        ],
    },
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN") or None
CSRF_COOKIE_DOMAIN = os.getenv("CSRF_COOKIE_DOMAIN") or None

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
