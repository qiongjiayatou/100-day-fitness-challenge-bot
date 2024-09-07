from telebot import TeleBot, types
from telebot.types import Message, CallbackQuery
from database import get_connection, release_connection
from utils import authenticate_user, is_authenticated, register_user, logout_user
from config import BOT_TOKEN
import re
from os import getenv
import pytz
from datetime import datetime

ADMIN_PASSWORD = getenv('ADMIN_PASSWORD')
MAINTENANCE_MODE = getenv('MAINTENANCE_MODE', 'false').lower() == 'true'

# Add this constant at the top of your file
NICOSIA_TIMEZONE = pytz.timezone('Europe/Nicosia')

def create_bot():
    bot = TeleBot(BOT_TOKEN)
    register_handlers(bot)
    return bot

def check_maintenance(message: Message, bot: TeleBot):
    if MAINTENANCE_MODE:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT is_admin FROM users WHERE telegram_id = %s", (message.from_user.id,))
                result = cursor.fetchone()
                is_admin = result[0] if result else False
                
            if not is_admin:
                bot.reply_to(message, "The bot is currently under maintenance. Please try again later.")
                return True
        finally:
            release_connection(conn)
    return False

def register_handlers(bot: TeleBot):
    @bot.message_handler(commands=['start'])
    def start(message: Message):
        if check_maintenance(message, bot):
            return
        welcome_text = """
🏅 Welcome to the 100-Day Fitness Challenge Bot! 🏅

This challenge is simple:
Choose one or more activities (e.g., walk 5,000 steps, do 50 push-ups, hold a 1-minute plank) 
and do them every day for 100 days straight.

Rules:
• Choose any activity each day—steps, push-ups, squats, planks, anything goes!
• No skipping! If you miss a day, the challenge resets to Day 1.
• Even if you do fewer reps, it counts as long as you stay active.
• Track your progress and stay motivated!

To get started:
• Register with /register <password>
• Or authenticate with /auth <password>

Let's achieve our fitness goals together! 💪
"""
        bot.reply_to(message, welcome_text)

    @bot.message_handler(commands=['help'])
    def help(message: Message):
        if check_maintenance(message, bot):
            return
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
        
        Reference activities:
        /addref - Add a new reference activity
        /listref - List all reference activities
        /updateref - Update an existing reference activity
        /deleteref - Delete a reference activity

        Other commands:
        /exit - Cancel the current operation (can be used during multi-step commands)
        """
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['register'])
    def register(message: Message):
        if check_maintenance(message, bot):
            return
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
        if check_maintenance(message, bot):
            return
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
        if check_maintenance(message, bot):
            return
        if logout_user(message.from_user.id):
            bot.reply_to(message, "You have been successfully logged out.")
        else:
            bot.reply_to(message, "An error occurred while logging out.")

    @bot.message_handler(commands=['add'])
    @is_authenticated(bot)
    def add_activity(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute("SELECT id, activity_name FROM reference_activities WHERE user_id = %s ORDER BY id", (user_id,))
                activities = cursor.fetchall()
                
                if activities:
                    keyboard = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                    for activity in activities:
                        keyboard.add(f"{activity[0]}: {activity[1]}")
                    keyboard.add("Other")
                    bot.reply_to(message, "Please choose an activity or select 'Other' to enter a new one:", reply_markup=keyboard)
                    bot.register_next_step_handler(message, process_add_activity_choice, activities)
                else:
                    bot.reply_to(message, "You don't have any reference activities. Please add one first using /addref")
        finally:
            release_connection(conn)

    def process_add_activity_choice(message: Message, valid_activities):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        choice = message.text.strip()
        
        if choice == "Other":
            bot.reply_to(message, "Please enter the new activity name (or /exit to cancel):", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, process_add_activity_name)
        else:
            try:
                reference_activity_id = int(choice.split(":")[0])
                activity_name = next(activity[1] for activity in valid_activities if activity[0] == reference_activity_id)
                bot.reply_to(message, f"Adding activity: {activity_name}\nPlease enter the reps or duration (e.g., 1 minute 30 seconds, 50 reps):", reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, process_add_activity_reps_or_duration, reference_activity_id)
            except (ValueError, StopIteration):
                bot.reply_to(message, "Invalid choice. Please select an activity from the list or 'Other'.")
                return add_activity(message)

    def process_add_activity_name(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        activity_name = message.text.strip().lower()
        telegram_id = message.from_user.id
        
        # List of commands to check against
        commands = ['start', 'help', 'register', 'auth', 'add', 'update', 'delete', 'list', 'stats', 'logout', 'addref', 'listref', 'updateref', 'deleteref', 'exit']
        
        # Check if the activity name is a command
        if activity_name.startswith('/') or activity_name in commands:
            bot.reply_to(message, "You cannot use a command as an activity name. Please choose a different name.")
            return add_activity(message)

        # Add the new activity to the reference list
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO reference_activities (user_id, activity_name) VALUES (%s, %s) RETURNING id",
                    (user_id, activity_name)
                )
                new_reference_id = cursor.fetchone()[0]
                conn.commit()
                bot.reply_to(message, f"New activity '{activity_name}' has been added to your reference list.")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while adding the new activity: {str(e)}")
            return add_activity(message)
        finally:
            release_connection(conn)

        # Proceed to add the activity
        bot.reply_to(message, f"Adding activity: {activity_name}\nPlease enter the reps or duration (e.g., 1 minute 30 seconds, 50 reps):")
        bot.register_next_step_handler(message, process_add_activity_reps_or_duration, new_reference_id)

    def process_add_activity_reps_or_duration(message: Message, reference_activity_id):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        reps_or_duration = message.text.strip()
        telegram_id = message.from_user.id
        
        # Get current time in Nicosia
        nicosia_time = datetime.now(NICOSIA_TIMEZONE)
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO activities (user_id, reference_activity_id, reps_or_duration, created_at) VALUES (%s, %s, %s, %s)",
                    (user_id, reference_activity_id, reps_or_duration, nicosia_time)
                )
                conn.commit()
                bot.reply_to(message, f"Activity added successfully! Recorded at {nicosia_time.strftime('%Y-%m-%d %H:%M:%S')} Nicosia time.")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while adding the activity: {str(e)}")
        finally:
            release_connection(conn)

    @bot.message_handler(commands=['update'])
    @is_authenticated(bot)
    def update_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the activity ID and updated reps or duration in the following format:\n"
                              "activity_id, new_reps_or_duration\n"
                              "For example: 1, 60 reps or 2, 45 minutes")
        bot.register_next_step_handler(message, process_update_activity)

    def process_update_activity(message: Message):
        if check_maintenance(message, bot):
            return
        try:
            activity_id, new_reps_or_duration = map(str.strip, message.text.split(','))
            activity_id = int(activity_id)
            telegram_id = message.from_user.id
            
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                    user_id = cursor.fetchone()[0]
                    cursor.execute("UPDATE activities SET reps_or_duration = %s WHERE id = %s AND user_id = %s",
                                (new_reps_or_duration, activity_id, user_id))
                    if cursor.rowcount == 0:
                        bot.reply_to(message, "Activity not found or you don't have permission to update it.")
                    else:
                        conn.commit()
                        bot.reply_to(message, f"Activity with ID {activity_id} has been updated successfully!")
            finally:
                release_connection(conn)
        except ValueError:
            bot.reply_to(message, "Invalid format. Please use: activity_id, new_reps_or_duration")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while updating the activity: {str(e)}")

    @bot.message_handler(commands=['delete'])
    @is_authenticated(bot)
    def delete_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the activity ID you want to delete:")
        bot.register_next_step_handler(message, process_delete_activity)

    def process_delete_activity(message: Message):
        if check_maintenance(message, bot):
            return
        try:
            activity_id = int(message.text.strip())
            telegram_id = message.from_user.id
            
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                    user_id = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM activities WHERE id = %s AND user_id = %s", (activity_id, user_id))
                    if cursor.rowcount == 0:
                        bot.reply_to(message, "Activity not found or you don't have permission to delete it.")
                    else:
                        conn.commit()
                        bot.reply_to(message, f"Activity with ID {activity_id} has been deleted successfully!")
            finally:
                release_connection(conn)
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while deleting the activity: {str(e)}")

    @bot.message_handler(commands=['list'])
    @is_authenticated(bot)
    def list_activities(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute("""
                    SELECT a.id, r.activity_name, a.reps_or_duration, a.created_at
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE a.user_id = %s
                    ORDER BY a.created_at DESC
                    LIMIT 10
                """, (user_id,))
                activities = cursor.fetchall()
                
                if activities:
                    response = "Your recent activities:\n\n"
                    for activity in activities:
                        response += f"ID: {activity[0]}, Activity: {activity[1]}, Reps/Duration: {activity[2]}, Date: {activity[3].strftime('%Y-%m-%d %H:%M')}\n"
                else:
                    response = "You haven't added any activities yet."
                
                bot.reply_to(message, response)
        finally:
            release_connection(conn)

    @bot.message_handler(commands=['stats'])
    @is_authenticated(bot)
    def get_stats(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                
                # Get total activities count
                cursor.execute("SELECT COUNT(*) FROM activities WHERE user_id = %s", (user_id,))
                result = cursor.fetchone()
                total_activities = result[0] if result else 0

                # Get unique activities count
                cursor.execute("SELECT COUNT(DISTINCT reference_activity_id) FROM activities WHERE user_id = %s", (user_id,))
                result = cursor.fetchone()
                unique_activities = result[0] if result else 0

                # Get most frequent activity
                cursor.execute("""
                    SELECT r.activity_name, COUNT(*) as frequency
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE a.user_id = %s
                    GROUP BY r.activity_name
                    ORDER BY frequency DESC
                    LIMIT 1
                """, (user_id,))
                most_frequent = cursor.fetchone()

                # Get all activities with correct Nicosia time
                cursor.execute("""
                    SELECT r.activity_name, a.reps_or_duration, a.created_at
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE a.user_id = %s
                    ORDER BY a.created_at DESC
                """, (user_id,))
                activities = cursor.fetchall()

                # Calculate total reps and duration for each activity
                activity_totals = {}
                total_reps = 0
                total_duration = 0
                for activity_name, reps_or_duration, created_at in activities:
                    value, unit = parse_reps_or_duration(reps_or_duration)
                    if activity_name not in activity_totals:
                        activity_totals[activity_name] = {'reps': 0, 'duration': 0}
                    if unit == 'reps':
                        activity_totals[activity_name]['reps'] += value
                        total_reps += value
                    else:
                        activity_totals[activity_name]['duration'] += value
                        total_duration += value

                # Format the response
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

                stats_message += "\nRecent activities:\n"
                for activity in activities[:5]:  # Show only the 5 most recent activities
                    nicosia_time = activity[2].astimezone(NICOSIA_TIMEZONE)
                    stats_message += f"- {activity[0]}: {activity[1]} ({nicosia_time.strftime('%Y-%m-%d %H:%M:%S')})\n"

                bot.reply_to(message, stats_message)
        except Exception as e:
            print(f"Error in get_stats: {str(e)}")
            bot.reply_to(message, "An error occurred while fetching your statistics. Please try again later.")
        finally:
            release_connection(conn)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("daily_check_"))
    def handle_daily_check(call: CallbackQuery):
        if check_maintenance(call.message, bot):
            return
        user_id = call.from_user.id
        response = call.data.split("_")[-1]
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (user_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM activities WHERE user_id = %s AND created_at::date = CURRENT_DATE", (user_id,))
                activities_count = cursor.fetchone()[0]
                
                if response == "yes":
                    if activities_count > 0:
                        message = "🎉 Great job! Keep up the good work! 💪"
                    else:
                        message = "🌟 That's great! Don't forget to log your activities using the /add command. 📝"
                else:
                    if activities_count > 0:
                        message = "👀 It looks like you've already logged some activities today. Keep going! 🏃‍♂️"
                    else:
                        message = "😊 No worries! There's still time to get active. Remember, consistency is key! 🔑"
                
                bot.answer_callback_query(call.id, "Thanks for your response!")
                bot.send_message(user_id, message)
        finally:
            release_connection(conn)

    @bot.message_handler(commands=['addref'])
    @is_authenticated(bot)
    def add_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the name of the activity you want to add to your reference list (or /exit to cancel):")
        bot.register_next_step_handler(message, process_add_reference_activity)

    def process_add_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        activity_name = message.text.strip()  # Remove leading/trailing whitespace, but keep original case
        telegram_id = message.from_user.id
        
        # List of commands to check against
        commands = ['start', 'help', 'register', 'auth', 'add', 'update', 'delete', 'list', 'stats', 'logout', 'addref', 'listref', 'updateref', 'deleteref', 'exit']
        
        # Check if the activity name is a command (case-insensitive)
        if activity_name.lower().startswith('/') or activity_name.lower() in commands:
            bot.reply_to(message, "You cannot use a command as an activity name. Please choose a different name.")
            return

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO reference_activities (user_id, activity_name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (user_id, activity_name)
                )
                conn.commit()
                bot.reply_to(message, f"Activity '{activity_name}' has been added to your reference list!")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while adding the reference activity: {str(e)}")
        finally:
            release_connection(conn)

    @bot.message_handler(commands=['listref'])
    @is_authenticated(bot)
    def list_reference_activities(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute("SELECT id, activity_name FROM reference_activities WHERE user_id = %s ORDER BY id", (user_id,))
                activities = cursor.fetchall()
                
                if activities:
                    response = "Your reference activities:\n\n"
                    for activity in activities:
                        response += f"ID: {activity[0]}, Activity: {activity[1]}\n"
                else:
                    response = "You haven't added any reference activities yet."
                
                bot.reply_to(message, response)
        finally:
            release_connection(conn)

    @bot.message_handler(commands=['updateref'])
    @is_authenticated(bot)
    def update_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the ID of the reference activity you want to update:")
        bot.register_next_step_handler(message, process_update_reference_activity_id)

    def process_update_reference_activity_id(message: Message):
        if check_maintenance(message, bot):
            return
        try:
            activity_id = int(message.text.strip())
            bot.reply_to(message, "Now, please enter the new name for this reference activity:")
            bot.register_next_step_handler(message, process_update_reference_activity_name, activity_id)
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")

    def process_update_reference_activity_name(message: Message, activity_id):
        if check_maintenance(message, bot):
            return
        new_activity_name = message.text.strip()
        telegram_id = message.from_user.id
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute(
                    "UPDATE reference_activities SET activity_name = %s WHERE id = %s AND user_id = %s",
                    (new_activity_name, activity_id, user_id)
                )
                if cursor.rowcount == 0:
                    bot.reply_to(message, "Reference activity not found or you don't have permission to update it.")
                else:
                    conn.commit()
                    bot.reply_to(message, f"Reference activity with ID {activity_id} has been updated to '{new_activity_name}'.")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while updating the reference activity: {str(e)}")
        finally:
            release_connection(conn)

    @bot.message_handler(commands=['deleteref'])
    @is_authenticated(bot)
    def delete_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the ID of the reference activity you want to delete:")
        bot.register_next_step_handler(message, process_delete_reference_activity)

    def process_delete_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        try:
            activity_id = int(message.text.strip())
            telegram_id = message.from_user.id
            
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                    user_id = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM reference_activities WHERE id = %s AND user_id = %s", (activity_id, user_id))
                    if cursor.rowcount == 0:
                        bot.reply_to(message, "Reference activity not found or you don't have permission to delete it.")
                    else:
                        conn.commit()
                        bot.reply_to(message, f"Reference activity with ID {activity_id} has been deleted successfully!")
            finally:
                release_connection(conn)
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while deleting the reference activity: {str(e)}")

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

    def check_exit(message: Message, bot: TeleBot):
        if message.text.lower() == '/exit':
            bot.reply_to(message, "Operation cancelled.", reply_markup=types.ReplyKeyboardRemove())
            return True
        return False

# Initialize the bot
bot = create_bot()

# Add this at the end of the file
if __name__ == '__main__':
    bot.polling(none_stop=True)