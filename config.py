import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'bhouma-dev-secret-key-change-in-production')

    # Render gives postgres:// but SQLAlchemy needs postgresql://
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'bhouma.db'))
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    # Meta (Facebook + Instagram)
    META_APP_ID = os.environ.get('META_APP_ID', '')
    META_APP_SECRET = os.environ.get('META_APP_SECRET', '')

    # LinkedIn
    LINKEDIN_CLIENT_ID = os.environ.get('LINKEDIN_CLIENT_ID', '')
    LINKEDIN_CLIENT_SECRET = os.environ.get('LINKEDIN_CLIENT_SECRET', '')

    # Base URL for OAuth redirects
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8090')

    # Scheduler
    SCHEDULER_API_ENABLED = False
