from celery import Celery
from celery.schedules import crontab
from database import get_connection, release_connection
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot_handlers import bot
import datetime

# Initialize Celery app
app = Celery('tasks', broker='redis://redis:6379/0')

# Configure Celery
app.conf.update(
    result_backend='redis://redis:6379/0',
    timezone='UTC',
    enable_utc=True,
)

@app.task
def update_streaks():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days=1)
            
            # Get all users and their last activity date
            cursor.execute("""
                SELECT u.telegram_id, MAX(a.created_at::date) as last_activity_date
                FROM users u
                LEFT JOIN activities a ON u.telegram_id = a.telegram_id
                GROUP BY u.telegram_id
            """)
            users = cursor.fetchall()
            
            for user in users:
                telegram_id, last_activity_date = user
                
                if last_activity_date == yesterday:
                    # User logged activity yesterday, increase streak
                    cursor.execute("UPDATE users SET streak = streak + 1 WHERE telegram_id = %s", (telegram_id,))
                elif last_activity_date != today:
                    # User missed a day, reset streak
                    cursor.execute("UPDATE users SET streak = 0 WHERE telegram_id = %s", (telegram_id,))
            
            conn.commit()
    finally:
        release_connection(conn)

@app.task
def send_daily_check():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            today = datetime.date.today()
            cursor.execute("""
                SELECT u.telegram_id, 
                       CASE WHEN MAX(a.created_at::date) = %s THEN TRUE ELSE FALSE END as logged_today
                FROM users u
                LEFT JOIN activities a ON u.telegram_id = a.telegram_id AND a.created_at::date = %s
                WHERE u.is_authenticated = TRUE
                GROUP BY u.telegram_id
            """, (today, today))
            users = cursor.fetchall()
            
            for user in users:
                telegram_id, logged_today = user
                
                # Create inline keyboard
                keyboard = InlineKeyboardMarkup()
                keyboard.row(
                    InlineKeyboardButton("Yes", callback_data="daily_check_yes"),
                    InlineKeyboardButton("No", callback_data="daily_check_no")
                )
                
                message = "🏋️‍♀️ Have you completed your fitness activities for today? 💪"
                bot.send_message(telegram_id, message, reply_markup=keyboard)
    finally:
        release_connection(conn)

# Schedule tasks
app.conf.beat_schedule = {
    'send-daily-check': {
        'task': 'tasks.send_daily_check',
        # 'schedule': crontab(hour=21, minute=20),  # Run at 8:18 PM Nicosia time (UTC+3)
        'schedule': crontab(minute='*'),  # Run every minute
    },
    'update-streaks': {
        'task': 'tasks.update_streaks',
        'schedule': crontab(hour=0, minute=5),  # Run at 00:05 UTC daily
    },
}

if __name__ == '__main__':
    app.start()