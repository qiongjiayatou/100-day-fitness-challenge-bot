from celery import Celery
from celery.schedules import crontab
import telebot
import types
import os
from database import Database  # Import the Database class
import random
import logging
from config import ADMIN_ID, BOT_TOKEN
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pytz
from datetime import datetime, timedelta
from config import *

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Tasks module initialized")

app = Celery('tasks', broker=REDIS_URL)
bot = telebot.TeleBot(BOT_TOKEN)

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
    "Great job! Keep up the good work! 💪",
    "That's the spirit! Every step counts towards your goal. 🏃‍♂️",
    "You're making progress! Remember, consistency is key. 🔑",
    "Awesome effort! Your future self will thank you. 🙌",
    "You're crushing it! Stay motivated and keep pushing. 💥",
    "Fantastic! Small daily improvements lead to stunning results. 🌟",
    "The only bad workout is the one that didn't happen.",
    "Strength doesn't come from what you can do. It comes from overcoming the things you once thought you couldn't.",
    "The difference between try and triumph is just a little umph!",
    "The only way to define your limits is by going beyond them.",
    "Success is walking from failure to failure with no loss of enthusiasm.",
    "The body achieves what the mind believes.",
    "Don't wish for it, work for it.",
    "Your body can stand almost anything. It's your mind that you have to convince.",
]

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Schedule the daily check task
    sender.add_periodic_task(
        crontab(minute='*'),  # This will run the task every minute
        # crontab(hour=19, minute=0),
        send_daily_check.s(),
    )

@app.task
def send_daily_check():
    nicosia_tz = pytz.timezone('Europe/Nicosia')
    now = datetime.now(nicosia_tz)
    
    logger.info(f"Running send_daily_check at {now}")
    
    # Send a summary to the admin
    # Check maintenance mode
    try:
        if MAINTENANCE_MODE:
            if ADMIN_ID:
                try:
                    users_count = db.get_total_users_count()
                    activities_count = db.get_activities_count_last_24h(now - timedelta(days=1), now)
                    admin_message = f"Daily Summary:\n"
                    admin_message += f"Total Users: {users_count}\n"
                    admin_message += f"Activities in the last 24 hours: {activities_count}\n"
                    admin_message += f"Current time in Nicosia: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                    bot.send_message(ADMIN_ID, admin_message)
                    logger.info(f"Sent daily summary to admin {ADMIN_ID}")
                except Exception as e:
                    logger.error(f"Failed to send daily summary to admin: {str(e)}")
            else:
                logger.warning("Admin Telegram ID not set in config")
            return
    except Exception as e:
        logger.error(f"Failed to check maintenance mode: {str(e)}")
        # Continue with the daily check even if we can't check maintenance mode
    

    # Only send the daily check if it's between 19:00 and 19:59 Nicosia time
    if now.hour == 19:
        users = db.get_all_users()
        logger.info(f"Sending daily check to {len(users)} users")
        for user in users:
            user_id = user[1]  # Assuming user[1] is the telegram_id
            send_daily_check_to_user(user_id)
            logger.info(f"Sent daily check to user {user_id}")
    else:
        logger.info("Not sending daily check (outside of scheduled hour)")

def send_daily_check_to_user(user_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Yes", callback_data="daily_check_yes"),
        types.InlineKeyboardButton("No", callback_data="daily_check_no")
    )
    try:
        bot.send_message(user_id, "Did you exercise today?", reply_markup=keyboard)
        logger.info(f"Successfully sent message to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send message to user {user_id}: {str(e)}")

@app.task
def send_encouragement_and_quote(user_id, was_active):
    if was_active:
        message = random.choice(ENCOURAGEMENTS) + "\n\n"
    else:
        message = "Don't worry if you missed today. Tomorrow is a new opportunity! 🌟\n\n"
    
    quote = get_random_quote()
    message += f"Here's a quote to keep you motivated:\n\n{quote}"
    
    bot.send_message(user_id, message)

def get_random_quote():
    return random.choice(QUOTES)

# ... (rest of your tasks.py file)