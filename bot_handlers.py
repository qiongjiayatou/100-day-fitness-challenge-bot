from telebot import TeleBot
from telebot.types import Message
from database import get_connection, release_connection
from utils import authenticate_user, is_authenticated, register_user, logout_user
from config import BOT_TOKEN
import re

def create_bot():
    bot = TeleBot(BOT_TOKEN)
    register_handlers(bot)
    return bot

def register_handlers(bot: TeleBot):
    @bot.message_handler(commands=['start'])
    def start(message: Message):
        welcome_text = """
            Welcome to the 100-Day Fitness Challenge Bot! 🏅

            This challenge is simple: choose one or more activities (e.g., walk 5,000 steps, do 50 push-ups, hold a 1-minute plank) and do them every day for 100 days straight.

            Rules:
            • Choose any activity each day—steps, push-ups, squats, planks, anything goes!
            • No skipping! If you miss a day, the challenge resets to Day 1.
            • Even if you do fewer reps, it counts as long as you stay active.
            • Track your progress and stay motivated!

            To get started, please register with /register <password> or authenticate with /auth <password>

            Let's achieve our fitness goals together! 💪
        """
        bot.reply_to(message, welcome_text)

    @bot.message_handler(commands=['help'])
    def help(message: Message):
        help_text = """
            Available commands:
            /start - Start the bot
            /register <password> - Register as a new user
            /auth <password> - Authenticate yourself        
            /help - Show this help message            

            Authenticated users only:
            /add - Add a new activity
            /update - Update an existing activity
            /delete - Delete an activity
            /list - List all activities
            /stats - Get activity statistics
            /logout - Log out from the current session
        """
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['register'])
    def register(message: Message):
        try:
            _, password = message.text.split(maxsplit=1)
            if register_user(message.from_user.id, password):
                bot.reply_to(message, "Registration successful! You are now authenticated.")
            else:
                bot.reply_to(message, "Registration failed. User already exists.")
        except ValueError:
            bot.reply_to(message, "Please provide a password. Usage: /register <password>")

    @bot.message_handler(commands=['auth'])
    def auth(message: Message):
        try:
            _, password = message.text.split(maxsplit=1)
            if authenticate_user(message.from_user.id, password):
                bot.reply_to(message, "Authentication successful!")
            else:
                bot.reply_to(message, "Authentication failed. Wrong password or user not registered.")
        except ValueError:
            bot.reply_to(message, "Please provide a password. Usage: /auth <password>")

    @bot.message_handler(commands=['logout'])
    def logout(message: Message):
        if logout_user(message.from_user.id):
            bot.reply_to(message, "You have been successfully logged out.")
        else:
            bot.reply_to(message, "An error occurred while logging out.")

    @bot.message_handler(commands=['add'])    
    @is_authenticated
    def add_activity(message: Message):
        bot.reply_to(message, "Please enter the activity name:")
        bot.register_next_step_handler(message, process_add_activity_name)

    def process_add_activity_name(message: Message):
        activity_name = message.text.strip()
        bot.reply_to(message, "Please enter the reps or duration (e.g., 1 minute 30 seconds, 50 reps):")
        bot.register_next_step_handler(message, process_add_activity_reps_or_duration, activity_name)

    def process_add_activity_reps_or_duration(message: Message, activity_name):
        try:
            reps_or_duration = message.text.strip()
            
            # Validate reps_or_duration format
            if reps_or_duration.endswith('reps'):
                # Handle reps format
                parts = reps_or_duration.split()
                if len(parts) != 2 or not parts[0].isdigit():
                    raise ValueError("Invalid format for reps")
            else:
                # Handle duration format
                duration_pattern = r'(\d+)\s*(hour|minute|second)s?'
                matches = re.findall(duration_pattern, reps_or_duration, re.IGNORECASE)
                if not matches:
                    raise ValueError("Invalid format for duration")
                
                # Convert duration to a standard format (e.g., total seconds)
                total_seconds = 0
                for value, unit in matches:
                    if unit.lower().startswith('hour'):
                        total_seconds += int(value) * 3600
                    elif unit.lower().startswith('minute'):
                        total_seconds += int(value) * 60
                    elif unit.lower().startswith('second'):
                        total_seconds += int(value)
                
                reps_or_duration = f"{total_seconds} seconds"

            telegram_id = message.from_user.id
            
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    # Insert the activity using telegram_id
                    cursor.execute("INSERT INTO activities (telegram_id, activity_name, reps_or_duration) VALUES (%s, %s, %s)",
                                   (telegram_id, activity_name, reps_or_duration))
                conn.commit()
                bot.reply_to(message, f"Activity '{activity_name}' with {reps_or_duration} has been added successfully!")
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                release_connection(conn)
        except ValueError as ve:
            bot.reply_to(message, f"Invalid input: {str(ve)}. Please use the format: activity_name, duration (e.g., 1 minute 30 seconds, 50 reps)")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while adding the activity: {str(e)}")

    @bot.message_handler(commands=['update'])
    @is_authenticated
    def update_activity(message: Message):
        bot.reply_to(message, "Please enter the activity ID and updated details in the following format:\n"
                              "activity_id, new_activity_name, new_reps_or_duration\n"
                              "For example: 1, Push-ups, 60 or 2, Running, 45 minutes")
        bot.register_next_step_handler(message, process_update_activity)

    def process_update_activity(message: Message):
        try:
            activity_id, new_activity_name, new_reps_or_duration = map(str.strip, message.text.split(','))
            telegram_id = message.from_user.id
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE activities SET activity_name = %s, reps_or_duration = %s WHERE id = %s AND telegram_id = %s",
                           (new_activity_name, new_reps_or_duration, activity_id, telegram_id))
            if cursor.rowcount == 0:
                bot.reply_to(message, "Activity not found or you don't have permission to update it.")
            else:
                conn.commit()
                bot.reply_to(message, f"Activity with ID {activity_id} has been updated successfully!")
            conn.close()
        except ValueError:
            bot.reply_to(message, "Invalid format. Please use: activity_id, new_activity_name, new_reps_or_duration")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while updating the activity: {str(e)}")

    @bot.message_handler(commands=['delete'])
    @is_authenticated
    def delete_activity(message: Message):
        bot.reply_to(message, "Please enter the activity ID you want to delete:")
        bot.register_next_step_handler(message, process_delete_activity)

    def process_delete_activity(message: Message):
        try:
            activity_id = int(message.text.strip())
            telegram_id = message.from_user.id
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM activities WHERE id = %s AND telegram_id = %s", (activity_id, telegram_id))
            if cursor.rowcount == 0:
                bot.reply_to(message, "Activity not found or you don't have permission to delete it.")
            else:
                conn.commit()
                bot.reply_to(message, f"Activity with ID {activity_id} has been deleted successfully!")
            conn.close()
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while deleting the activity: {str(e)}")

    @bot.message_handler(commands=['list'])
    @is_authenticated
    def list_activities(message: Message):
        telegram_id = message.from_user.id
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, activity_name, reps_or_duration FROM activities WHERE telegram_id = %s", (telegram_id,))
        activities = cursor.fetchall()
        conn.close()
        
        if activities:
            response = "Your activities:\n\n"
            for activity in activities:
                response += f"ID: {activity[0]}, Activity: {activity[1]}, Reps/Duration: {activity[2]}\n"
        else:
            response = "You haven't added any activities yet."
        
        bot.reply_to(message, response)

    @bot.message_handler(commands=['stats'])
    @is_authenticated
    def get_stats(message: Message):
        telegram_id = message.from_user.id
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Get total activities count
                cursor.execute("SELECT COUNT(*) FROM activities WHERE telegram_id = %s", (telegram_id,))
                result = cursor.fetchone()
                total_activities = result[0] if result else 0

                # Get unique activities count
                cursor.execute("SELECT COUNT(DISTINCT activity_name) FROM activities WHERE telegram_id = %s", (telegram_id,))
                result = cursor.fetchone()
                unique_activities = result[0] if result else 0

                # Get most frequent activity
                cursor.execute("""
                    SELECT activity_name, COUNT(*) as frequency
                    FROM activities
                    WHERE telegram_id = %s
                    GROUP BY activity_name
                    ORDER BY frequency DESC
                    LIMIT 1
                """, (telegram_id,))
                most_frequent = cursor.fetchone()

                # Get all activities
                cursor.execute("SELECT activity_name, reps_or_duration FROM activities WHERE telegram_id = %s", (telegram_id,))
                activities = cursor.fetchall()

                # Calculate total reps and duration for each activity
                activity_totals = {}
                total_reps = 0
                total_duration = 0
                for activity_name, reps_or_duration in activities:
                    value, unit = parse_reps_or_duration(reps_or_duration)
                    if activity_name not in activity_totals:
                        activity_totals[activity_name] = {'reps': 0, 'duration': 0}
                    if unit == 'reps':
                        activity_totals[activity_name]['reps'] += value
                        total_reps += value
                    else:
                        activity_totals[activity_name]['duration'] += value
                        total_duration += value

            stats_message = f"📊 Your Fitness Challenge Statistics:\n\n"
            stats_message += f"Total activities logged: {total_activities}\n"
            stats_message += f"Unique activities: {unique_activities}\n"
            if most_frequent:
                stats_message += f"Most frequent activity: {most_frequent[0]} (done {most_frequent[1]} times)\n"
            stats_message += f"Total reps across all activities: {total_reps}\n"
            stats_message += f"Total duration across all activities: {format_duration(total_duration)}\n\n"
            
            stats_message += "Activity Totals:\n"
            for activity, totals in activity_totals.items():
                stats_message += f"{activity}:\n"
                if totals['reps'] > 0:
                    stats_message += f"  Total reps: {totals['reps']}\n"
                if totals['duration'] > 0:
                    stats_message += f"  Total duration: {format_duration(totals['duration'])}\n"

            bot.reply_to(message, stats_message)
        except Exception as e:
            print(f"Error in get_stats: {str(e)}")
            bot.reply_to(message, "An error occurred while fetching your statistics. Please try again later.")
        finally:
            release_connection(conn)

def parse_reps_or_duration(reps_or_duration):
    if reps_or_duration.endswith('reps'):
        return int(reps_or_duration.split()[0]), 'reps'
    else:
        duration_pattern = r'(\d+)\s*(hour|minute|second)s?'
        matches = re.findall(duration_pattern, reps_or_duration, re.IGNORECASE)
        total_seconds = 0
        for value, unit in matches:
            if unit.lower().startswith('hour'):
                total_seconds += int(value) * 3600
            elif unit.lower().startswith('minute'):
                total_seconds += int(value) * 60
            elif unit.lower().startswith('second'):
                total_seconds += int(value)
        return total_seconds, 'seconds'

def format_duration(seconds):
    if seconds == 0:
        return "0 seconds"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return " ".join(parts)

# Initialize the bot
bot = create_bot()

# Add this at the end of the file
if __name__ == '__main__':
    bot.polling(none_stop=True)