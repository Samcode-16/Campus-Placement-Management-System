
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-sb81bon(ka^8c03jtwg8pe-k-fl560%t57-$=0)3!t9doojz&f",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS")
if ALLOWED_HOSTS_ENV:
    ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(",") if h.strip()]
else:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".onrender.com"]

CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
CSRF_TRUSTED_ENV = os.getenv("CSRF_TRUSTED_ORIGINS")
if CSRF_TRUSTED_ENV:
    CSRF_TRUSTED_ORIGINS.extend([origin.strip() for origin in CSRF_TRUSTED_ENV.split(",") if origin.strip()])

# Production HTTPS / SSL settings (activated when DEBUG=False on Render)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'recruitment',
    'training',
]

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

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.legal',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database configuration: Supabase PostgreSQL (via DATABASE_URL)
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is missing. "
        "Please configure DATABASE_URL in your .env file with your Supabase PostgreSQL connection string."
    )

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=True,
    )
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}


# Email (console backend prints emails in the terminal during development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# Uploaded files (student resumes)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# Authentication
# Students and placement officers log in through separate pages.
LOGIN_URL = "accounts:login"
LOGOUT_REDIRECT_URL = "home"


# Legal and privacy details shown on the Privacy Policy, Terms and DPA pages.
# EDIT THESE before you present or deploy: they are placeholders.
INSTITUTION_NAME = "Your College Name"
INSTITUTION_CITY = "Your City"
INSTITUTION_ADDRESS = "Placement Cell, Your College Name, Your City, India"
PRIVACY_CONTACT_EMAIL = "placement@yourcollege.example"
GRIEVANCE_OFFICER = "The Placement Officer"
DATA_RETENTION_YEARS = 2

# Bump POLICY_VERSION whenever the policy text changes in a way that matters.
POLICY_VERSION = "1.0"
POLICY_LAST_UPDATED = "28 October 2026"
