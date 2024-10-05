from celery import Celery
from celery.schedules import crontab
from telebot import TeleBot
from database import Database  # Import the Database class
import random
from logger import log_error, log_info
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pytz
from datetime import datetime, timedelta
from config import *
from quotes import QUOTES, ENCOURAGEMENTS
from telebot.apihelper import ApiTelegramException

app = Celery('tasks', broker=REDIS_URL)

# Update the Celery configuration
app.conf.update(
    broker_connection_retry_on_startup=True,
    timezone='Europe/Nicosia',
    enable_utc=False
)

bot = TeleBot(BOT_TOKEN)

# Create a Database instance
db = Database()

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Schedule the encouragement task to run every minute
    # sender.add_periodic_task(
    #     crontab(minute='*'),
    #     send_encouragement.s()
    # )
    
    sender.add_periodic_task(
        crontab(hour=12, minute=0), 
        send_encouragement.s(),
        name='send_encouragement_at_12'
    )

    sender.add_periodic_task(
        crontab(hour=20, minute=0), 
        send_encouragement.s(),
        name='send_encouragement_at_20'
    )

@app.task
def send_encouragement():
    nicosia_tz = pytz.timezone('Europe/Nicosia')
    now = datetime.now(nicosia_tz)
    
    log_info(f"Running send_encouragement at {now}")
    
    try:
        if ADMIN_ID:
            log_info(f"Checking activity for ADMIN_ID: {ADMIN_ID}")
            check_activity_and_send_encouragement.delay(1)
        else:
            users = db.get_all_users()
            log_info(f"Checking activity for {len(users)} users")
            for user in users:
                user_id = user[0]  # Assuming user[0] is the user_id
                check_activity_and_send_encouragement.delay(user_id)
                log_info(f"Scheduled activity check and encouragement for user {user_id}")
    except Exception as e:
        log_error(f"Failed in send_encouragement: {str(e)}")

@app.task
def check_activity_and_send_encouragement(user_id):
    nicosia_tz = pytz.timezone('Europe/Nicosia')
    now = datetime.now(nicosia_tz)
    today = now.date()
    
    try:
        # Check if the user was active today
        was_active = db.was_user_active_today(user_id, today)
        
        log_info(f"User {user_id} activity check result: {'active' if was_active else 'not active'}")
        
        if not was_active:
            send_encouragement_and_quote.delay(user_id)
            log_info(f"User {user_id} was not active today, sending encouragement")
        else:
            log_info(f"User {user_id} was already active today, skipping encouragement")
    except Exception as e:
        log_error(f"Failed to check activity for user {user_id}: {str(e)}")

@app.task
def send_encouragement_and_quote(user_id, custom_message=None):
    if custom_message:
        message = custom_message
    else:
        message = get_random_encouragement() + "\n\n"
        quote = get_random_quote()
        message += f"Here's a quote to keep you motivated:\n\n{quote}"
    
    try:
        # Get user's telegram_id from the database
        user = db.get_user_by_id(user_id)
        if user:
            telegram_id = user[1]  # Assuming telegram_id is the second column in the user tuple
            log_info(f"Retrieved telegram_id {telegram_id} for user {user_id}")
        else:
            log_error(f"User {user_id} not found in the database")
            return  # Exit the function if user is not found
        
        log_info(f"Attempting to send message to telegram_id {telegram_id}")
        sent_message = bot.send_message(telegram_id, message)
        log_info(f"Successfully sent message to user {user_id}. Message ID: {sent_message.message_id}")
    except ApiTelegramException as api_error:
        log_error(f"Telegram API error when sending message to user {user_id}: {str(api_error)}")
    except Exception as e:
        log_error(f"Failed to send message to user {user_id}: {str(e)}")

def get_random_quote():
    return random.choice(QUOTES)

def get_random_encouragement():
    return random.choice(ENCOURAGEMENTS)

# ... (rest of your tasks.py file)