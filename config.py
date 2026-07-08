"""
Centralized Configuration
All settings in one place for easy management
"""
import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
from db_path import DB_PATH


# Server settings
MAIN_PORT = 5000
ADMIN_PORT = 5001

# Email settings (configure as needed)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')

# Security
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = 'pbkdf2:sha256:600000$...'  # Set properly

# File upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

# Database
DB_TIMEOUT = 30.0  # seconds
