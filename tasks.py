from celery import Celery
from celery.schedules import crontab
from telebot import TeleBot
import types
import os
from database import Database  # Import the Database class
import random
from logger import log_error, log_info
from config import ADMIN_ID, BOT_TOKEN
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pytz
from datetime import datetime, timedelta
from config import *

app = Celery('tasks', broker=REDIS_URL)

# Update the Celery configuration
app.conf.update(
    broker_connection_retry_on_startup=True  # Add this line
)

bot = TeleBot(BOT_TOKEN)

# Create a Database instance
db = Database()

# List of 100 inspirational quotes
QUOTES = [
    "The only way to do great work is to love what you do. - Steve Jobs",
    "Success is not final, failure is not fatal: it is the courage to continue that counts. - Winston Churchill",
    "Believe you can and you're halfway there. - Theodore Roosevelt",
    "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
    "It does not matter how slowly you go as long as you do not stop. - Confucius",
    "Everything you've ever wanted is on the other side of fear. - George Addair",
    "Success is not how high you have climbed, but how you make a positive difference to the world. - Roy T. Bennett",
    "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt",
    "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
    "The secret of getting ahead is getting started. - Mark Twain",
    "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle. - Christian D. Larson",
    "The best way to predict the future is to invent it. - Alan Kay",
    "Success is not the key to happiness. Happiness is the key to success. If you love what you are doing, you will be successful. - Albert Schweitzer",
    "The only person you are destined to become is the person you decide to be. - Ralph Waldo Emerson",
    "The greatest glory in living lies not in never falling, but in rising every time we fall. - Nelson Mandela",
    "Life is what happens to you while you're busy making other plans. - John Lennon",
    "Strive not to be a success, but rather to be of value. - Albert Einstein",
    "The way to get started is to quit talking and begin doing. - Walt Disney",
    "Your time is limited, don't waste it living someone else's life. - Steve Jobs",
    "If you look at what you have in life, you'll always have more. - Oprah Winfrey",
    "The purpose of our lives is to be happy. - Dalai Lama",
    "You miss 100% of the shots you don't take. - Wayne Gretzky",
    "Whether you think you can or you think you can't, you're right. - Henry Ford",
    "I have not failed. I've just found 10,000 ways that won't work. - Thomas A. Edison",
    "The only impossible journey is the one you never begin. - Tony Robbins",
    "It is never too late to be what you might have been. - George Eliot",
    "Life is 10% what happens to me and 90% of how I react to it. - Charles Swindoll",
    "Happiness is not something ready made. It comes from your own actions. - Dalai Lama",
    "If you want to lift yourself up, lift up someone else. - Booker T. Washington",
    "You can't use up creativity. The more you use, the more you have. - Maya Angelou",
    "I have learned over the years that when one's mind is made up, this diminishes fear. - Rosa Parks",
    "Everything has beauty, but not everyone sees it. - Confucius",
    "When everything seems to be going against you, remember that the airplane takes off against the wind, not with it. - Henry Ford",
    "The only way to achieve the impossible is to believe it is possible. - Charles Kingsleigh",
    "Success is not in what you have, but who you are. - Bo Bennett",
    "The harder you work for something, the greater you'll feel when you achieve it. - Unknown",
    "Don't be pushed around by the fears in your mind. Be led by the dreams in your heart. - Roy T. Bennett",
    "Challenges are what make life interesting and overcoming them is what makes life meaningful. - Joshua J. Marine",
    "The pessimist sees difficulty in every opportunity. The optimist sees opportunity in every difficulty. - Winston Churchill",
    "Believe in yourself, take on your challenges, dig deep within yourself to conquer fears. Never let anyone bring you down. You got this. - Chantal Sutherland",
    "Hardships often prepare ordinary people for an extraordinary destiny. - C.S. Lewis",
    "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt",
    "It's not whether you get knocked down, it's whether you get up. - Vince Lombardi",
    "Embrace the glorious mess that you are. - Elizabeth Gilbert",
    "You are never too old to set another goal or to dream a new dream. - C.S. Lewis",
    "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
    "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
    "The secret of getting ahead is getting started. - Mark Twain",
    "Your time is limited, don't waste it living someone else's life. - Steve Jobs",
    "The best way to predict the future is to create it. - Peter Drucker",


    # ... (add the rest of the quotes here)
]

# Add this list of encouraging phrases
ENCOURAGEMENTS = [
    "Did you workout today?",
    "Have you exercised today?",
    "Did you get your heart rate up today?",
    "Have you moved your body today?",
    "Did you stretch or do any physical activity?",
    "Have you taken time for exercise today?",
    "Did you engage in any sports or fitness activities?",
    "Have you done any strength training today?",
    "Did you go for a walk or run today?",
    "Have you done any yoga or pilates?",
    "Did you participate in any group fitness classes?",
    "Have you done any cardio exercises today?",
    "Did you take the stairs instead of the elevator?",
    "Have you done any bodyweight exercises at home?",
    "Did you play any active games or sports today?",
    "Have you done any swimming or water exercises?",
    "Did you do any flexibility or mobility work today?",
]

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Schedule the encouragement task to run every minute
    sender.add_periodic_task(
        # crontab(minute='*'),
        # check_activity_and_send_encouragement.s(1)
        crontab(hour='18', minute='0', tz='Europe/Nicosia'),  # This will run the task every day at 6pm Nicosia time
        send_encouragement.s()
    )

@app.task
def send_encouragement():
    nicosia_tz = pytz.timezone('Europe/Nicosia')
    now = datetime.now(nicosia_tz)
    
    log_info(f"Running send_encouragement at {now}")
    
    try:
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
        else:
            log_error(f"User {user_id} not found in the database")
            return  # Exit the function if user is not found
        bot.send_message(telegram_id, message)
        log_info(f"Successfully sent message to user {user_id}")
    except Exception as e:
        log_error(f"Failed to send message to user {user_id}: {str(e)}")

def get_random_quote():
    return random.choice(QUOTES)

def get_random_encouragement():
    return random.choice(ENCOURAGEMENTS)

# ... (rest of your tasks.py file)