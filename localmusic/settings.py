"""
Django settings for localmusic project.

Generated by 'django-admin startproject' using Django 5.0.7.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
IS_DEV = os.getenv("IS_DEV", "False") == "True"
DEBUG = IS_DEV

HOST_NAME = os.getenv("HOST_NAME", "localhost")
ALLOWED_HOSTS = [HOST_NAME, f"www.{HOST_NAME}"]
CSRF_TRUSTED_ORIGINS = [f"https://{HOST_NAME}", f"https://www.{HOST_NAME}"]
CSRF_COOKIE_SECURE = not IS_DEV
SESSION_COOKIE_SECURE = not IS_DEV

# Application definition

INSTALLED_APPS = [
    'findshows.apps.FindshowsConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'mjml',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'localmusic.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'localmusic.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME'),
        'USER': os.getenv('DATABASE_USER'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD'),
        'HOST': os.getenv('DATABASE_HOST'),
        'PORT': os.getenv('DATABASE_PORT'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Chicago'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Media files used in this project

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Spotify API credentials
SPOTIFY_CLIENT_ID=os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET=os.getenv("SPOTIFY_CLIENT_SECRET")

# MusicBrainz
MUSICBRAINZ_TOKEN=os.getenv("MUSICBRAINZ_TOKEN")
USER_AGENT_HEADER=os.getenv("USER_AGENT_HEADER")
# This must be at least 14, since that's how often the dataset updates. Higher
# to minimize API calls and be a responsible consumer of their data.
LISTENBRAINZ_SIMILAR_ARTIST_CACHE_DAYS=30

# Memcache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
        "LOCATION": "127.0.0.1:11211",
    }
}


LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "login"
LOGOUT_REDIRECT_URL = "/"


# Email
match os.getenv("EMAIL_BACKEND", "CONSOLE"):
    case "FILEBASED":
        EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
        EMAIL_FILE_PATH = os.path.join(BASE_DIR, '../emails')
    case _:
        EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

ADMINS = [('Test admin','admin@localmusic.com')]

MJML_BACKEND_MODE = 'tcpserver'
MJML_TCPSERVERS = [
    (os.getenv("MJML_HOST"), int(os.getenv("MJML_PORT", 0))),
]

# Misc
MAX_DATE_RANGE = os.getenv("MAX_DATE_RANGE", 7)
MAX_DAILY_CONCERT_CREATES = os.getenv("MAX_DAILY_CONCERT_CREATES", 3)
MAX_DAILY_VENUE_CREATES = os.getenv("MAX_DAILY_VENUE_CREATES", 2)
MAX_DAILY_INVITES = os.getenv("MAX_DAILY_INVITES", 3)
CONCERT_RECS_PER_EMAIL = os.getenv("CONCERT_RECS_PER_EMAIL", 9)
INVITE_CODE_EXPIRATION_DAYS = os.getenv("INVITE_CODE_EXPIRATION_DAYS", 7)
INVITE_BUFFER_DAYS = os.getenv("INVITE_BUFFER_DAYS", 2)
