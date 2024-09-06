from functools import wraps
from telebot.types import Message
from config import ADMIN_PASSWORD
from database import get_connection, release_connection
import bcrypt


def register_user(telegram_id: int, password: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
            if cur.fetchone():
                return False  # User already exists
            
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cur.execute(
                "INSERT INTO users (telegram_id, password, is_authenticated) VALUES (%s, %s, TRUE)",
                (telegram_id, hashed_password.decode('utf-8'))
            )
            conn.commit()
            return True
    finally:
        release_connection(conn)

def authenticate_user(telegram_id: int, password: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password FROM users WHERE telegram_id = %s", (telegram_id,))
            result = cur.fetchone()
            if result:
                stored_password = result[0]
                if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                    cur.execute("UPDATE users SET is_authenticated = TRUE WHERE telegram_id = %s", (telegram_id,))
                    conn.commit()
                    return True
    finally:
        release_connection(conn)
    return False

def is_authenticated(bot):
    def decorator(func):
        @wraps(func)
        def wrapper(message: Message, *args, **kwargs):
            user_id = message.from_user.id
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT is_authenticated FROM users WHERE telegram_id = %s", (user_id,))
                    result = cur.fetchone()
                    if result and result[0]:
                        return func(message, *args, **kwargs)
                    else:
                        bot.reply_to(message, "You need to authenticate first. Use /auth <password>")
            finally:
                release_connection(conn)
        return wrapper
    return decorator

def logout_user(telegram_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET is_authenticated = FALSE WHERE telegram_id = %s", (telegram_id,))
            conn.commit()
            return True
    finally:
        release_connection(conn)
