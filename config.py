import os

# Telegram Bot Token
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Database configuration
POSTGRES_DB = os.environ.get("POSTGRES_DB")
POSTGRES_USER = os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "db")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")

# Other configurations
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")