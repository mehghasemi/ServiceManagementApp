import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ['SERVICE_SECRET_KEY']
DEBUG = False
SERVICE_LAN = os.environ.get('SERVICE_MODE') == 'lan'
SERVICE_LAN_HOST = os.environ.get('SERVICE_LAN_HOST', '')
SERVICE_LAN_SUBNETS = os.environ.get('SERVICE_LAN_SUBNETS', '').split(',') if SERVICE_LAN else []
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]', 'testserver'] + ([SERVICE_LAN_HOST] if SERVICE_LAN else [])
SESSION_COOKIE_NAME = 'service_lan_session' if SERVICE_LAN else 'sessionid'
CSRF_COOKIE_NAME = 'service_lan_csrf' if SERVICE_LAN else 'csrftoken'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'planning', 'integrations']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'planning.middleware.LocalOnlyMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'planning.middleware.NetworkIdentityMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages', 'planning.context.common']}}]
# Isolated local prototype only. Production PostgreSQL deployment is a later phase.
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': Path(os.environ.get('SERVICE_DATABASE_PATH', str(BASE_DIR / 'private' / 'preview.sqlite3'))).resolve(), 'OPTIONS': {'timeout': 10}}}
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/welcome/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

SERVICE_ENVIRONMENT = os.environ.get('SERVICE_ENVIRONMENT', 'legacy')
if SERVICE_ENVIRONMENT == 'development':
    SESSION_COOKIE_NAME = 'service_dev_session'
    CSRF_COOKIE_NAME = 'service_dev_csrf'

if SERVICE_ENVIRONMENT == 'stable':
    SESSION_COOKIE_NAME = 'service_stable_lan_session' if SERVICE_LAN else 'service_stable_session'
    CSRF_COOKIE_NAME = 'service_stable_lan_csrf' if SERVICE_LAN else 'service_stable_csrf'
