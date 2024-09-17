import os

# Telegram Bot Token
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Database configuration
POSTGRES_DB=os.environ.get("POSTGRES_DB")
POSTGRES_USER=os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD=os.environ.get("POSTGRES_PASSWORD")
POSTGRES_HOST=os.environ.get("POSTGRES_HOST", "db")
POSTGRES_PORT=os.environ.get("POSTGRES_PORT", "5432")

# Redis configuration
REDIS_URL = os.environ.get("REDIS_URL")

# Other configurations
MAINTENANCE_MODE = os.environ.get("MAINTENANCE_MODE", "false").lower() == "true"
ADMIN_ID = os.environ.get("ADMIN_ID")