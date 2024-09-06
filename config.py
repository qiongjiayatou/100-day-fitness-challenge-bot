import os

# Telegram Bot Token
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Database configuration
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = os.environ.get("DB_PORT", "5432")

# Other configurations
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")