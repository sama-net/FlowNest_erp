import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── File Persistence (Railway Volumes Support) ───────────────────
# Priority: RAILWAY_VOLUME_MOUNT_PATH > /app/persistent_data > Local MEDIA
RAILWAY_VOL = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
IS_PERSISTENT = False

if RAILWAY_VOL:
    PERSISTENT_DATA_DIR = Path(RAILWAY_VOL)
    IS_PERSISTENT = True
elif os.path.exists('/app/persistent_data'):
    PERSISTENT_DATA_DIR = Path('/app/persistent_data')
    IS_PERSISTENT = True
else:
    PERSISTENT_DATA_DIR = BASE_DIR

SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-key-here')
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=lambda v: [s.strip() for s in v.split(',')])
if '.pythonanywhere.com' not in ALLOWED_HOSTS and '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.pythonanywhere.com')

CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.app',
    'https://*.ngrok-free.dev',
    'https://*.up.railway.app',
    'https://*.railway.app',
    'https://*.onrender.com',
    'https://*.pythonanywhere.com',
]

INSTALLED_APPS = [
    'products.apps.ProductsConfig',
    'pages.apps.PagesConfig',
    'rag',                          # Re-enabled (ensure tf-keras/chromadb are ready)
    'chat',                         # Internal Chat App
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# ChromaDB Vector Store settings for RAG
CHROMADB = {
    "PERSIST_DIRECTORY": PERSISTENT_DATA_DIR / "chroma_db",
    "COLLECTION_NAME": "erp_docs_v2",
    "DISTANCE_METRIC": "cosine",
    "TOP_K": 5,
    "EMBEDDING_MODEL": "all-MiniLM-L6-v2",
}

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True



MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'yasso.middleware.DynamicSessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'yasso.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'yasso.context_processors.global_sidebar_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'yasso.wsgi.application'

# File Persistence moved above.

import dj_database_url

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

if IS_PERSISTENT:
    # سيتم حفظ قاعدة البيانات في التخزين الدائم لضمان عدم ضياع البيانات
    DB_PATH = PERSISTENT_DATA_DIR / 'db.sqlite3'
    # إنشاء المجلد فوراً لضمان عدم تعطل قاعدة البيانات
    os.makedirs(PERSISTENT_DATA_DIR, exist_ok=True)
else:
    DB_PATH = BASE_DIR / 'db.sqlite3'

# Robust Database Connectivity (Retry logic for Railway Internal DNS)
db_config = dj_database_url.config(
    default=os.environ.get('DATABASE_URL', f"sqlite:///{DB_PATH}"),
    conn_max_age=600,
    conn_health_checks=True,
)

DATABASES = {
    'default': db_config
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
if EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
    EMAIL_FILE_PATH = os.path.join(PERSISTENT_DATA_DIR, 'media', 'reset_emails')
    os.makedirs(EMAIL_FILE_PATH, exist_ok=True)



STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(PERSISTENT_DATA_DIR, 'media')

# Ensure directories exist
os.makedirs(MEDIA_ROOT, exist_ok=True)

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# AI Keys
# ── AI Keys (Google Gemini, Groq & Daily.co) ───────────────────────
GOOGLE_API_KEY = config('GOOGLE_API_KEY', default='').strip()
GROQ_API_KEY   = config('GROQ_API_KEY', default='').strip()
GROQ_MODEL     = config('GROQ_MODEL', default='llama-3.3-70b-versatile')
DAILY_API_KEY  = config('DAILY_API_KEY', default='').strip()   # ← ضع هنا Daily.co API Key
# ─── Security & AI Optimization ──────────────────────────────────
import os
# Suppress noisy ChromaDB telemetry
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['CHROMA_TELEMETRY'] = 'False'

# ── Persistent AI Model Cache (CRITICAL for Railway) ──────────────
# ChromaDB downloads ~80MB ONNX model to ~/.cache/chroma by default.
# On Railway, /root is WIPED on every new deploy → re-downloads every time!
# Fix: Redirect HOME to our Persistent Volume so the cache survives deploys.
_AI_CACHE_DIR = PERSISTENT_DATA_DIR / '.cache'
os.makedirs(_AI_CACHE_DIR, exist_ok=True)

# This is the nuclear option — redirects ALL ~/.cache calls to persistent storage
os.environ['HOME'] = str(PERSISTENT_DATA_DIR)
os.environ['HF_HOME'] = str(_AI_CACHE_DIR / 'huggingface')
os.environ['SENTENCE_TRANSFORMERS_HOME'] = str(_AI_CACHE_DIR / 'sentence_transformers')

os.makedirs(os.environ['HF_HOME'], exist_ok=True)
os.makedirs(os.environ['SENTENCE_TRANSFORMERS_HOME'], exist_ok=True)

# ─── Production HTTPS Security (only when DEBUG=False) ─────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
