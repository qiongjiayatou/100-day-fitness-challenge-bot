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
        
        telegram_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    # Update user information
                    cursor.execute(
                        "UPDATE users SET username = %s, first_name = %s, last_name = %s WHERE telegram_id = %s",
                        (username, first_name, last_name, telegram_id)
                    )
                    conn.commit()
                    bot.reply_to(message, "Welcome back! Your information has been updated.")
                else:
                    # Insert new user
                    cursor.execute(
                        "INSERT INTO users (telegram_id, username, first_name, last_name) VALUES (%s, %s, %s, %s)",
                        (telegram_id, username, first_name, last_name)
                    )
                    conn.commit()
                    bot.reply_to(message, "Welcome! You've been successfully registered.")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while processing your request: {str(e)}")
        finally:
            release_connection(conn)

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
                cursor.execute("SELECT id, activity_name, activity_type FROM reference_activities WHERE user_id = %s ORDER BY id", (user_id,))
                activities = cursor.fetchall()
                
                if activities:
                    keyboard = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                    for activity in activities:
                        keyboard.add(f"{activity[0]}: {activity[1]} ({activity[2]})")
                    bot.reply_to(message, "Please choose an activity:", reply_markup=keyboard)
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
        
        try:
            reference_activity_id = int(choice.split(":")[0])
            activity = next(activity for activity in valid_activities if activity[0] == reference_activity_id)
            activity_name, activity_type = activity[1], activity[2]
            if activity_type == 'time':
                bot.reply_to(message, f"Adding activity: {activity_name}\nPlease enter the duration in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds):", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.reply_to(message, f"Adding activity: {activity_name}\nPlease enter the number of reps:", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, process_add_activity_value, reference_activity_id, activity_type)
        except (ValueError, StopIteration):
            bot.reply_to(message, "Invalid choice. Please select an activity from the list.")
            return add_activity(message)

    def process_add_activity_value(message: Message, reference_activity_id, activity_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        value_input = message.text.strip()
        telegram_id = message.from_user.id
        
        if activity_type == 'time':
            try:
                value = parse_time_to_seconds(value_input)
                if value <= 0:
                    raise ValueError("Duration must be positive")
            except ValueError as e:
                bot.reply_to(message, f"Invalid input: {str(e)}. Please enter a valid time in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds).")
                return add_activity(message)
        else:  # reps
            try:
                value = int(value_input)
                if value <= 0:
                    raise ValueError("Number of reps must be positive")
            except ValueError:
                bot.reply_to(message, "Invalid input. Please enter a positive integer for reps.")
                return add_activity(message)
        
        # Get current time in Nicosia
        nicosia_time = datetime.now(NICOSIA_TIMEZONE)
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO activities (user_id, reference_activity_id, value, created_at) VALUES (%s, %s, %s, %s)",
                    (user_id, reference_activity_id, value, nicosia_time)
                )
                conn.commit()
                value_str = format_duration(value) if activity_type == 'time' else f"{value} reps"
                bot.reply_to(message, f"Activity added successfully! Recorded {value_str} at {nicosia_time.strftime('%Y-%m-%d %H:%M:%S')} Nicosia time.")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while adding the activity: {str(e)}")
        finally:
            release_connection(conn)

    def parse_time_to_seconds(time_str):
        try:
            hours, minutes, seconds = map(int, time_str.split(':'))
            total_seconds = hours * 3600 + minutes * 60 + seconds
            if total_seconds <= 0:
                raise ValueError("Duration must be positive")
            return total_seconds
        except ValueError:
            raise ValueError("Invalid time format")

    def format_duration(seconds):
        try:
            seconds = int(seconds)
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except ValueError:
            return "Invalid duration"

    @bot.message_handler(commands=['update'])
    @is_authenticated(bot)
    def update_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the activity ID you want to update:")
        bot.register_next_step_handler(message, process_update_activity_id)

    def process_update_activity_id(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        try:
            activity_id = int(message.text.strip())
            telegram_id = message.from_user.id
            
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                    user_id = cursor.fetchone()[0]
                    
                    # Get the activity type from reference_activities
                    cursor.execute("""
                        SELECT r.activity_type 
                        FROM activities a 
                        JOIN reference_activities r ON a.reference_activity_id = r.id 
                        WHERE a.id = %s AND a.user_id = %s
                    """, (activity_id, user_id))
                    result = cursor.fetchone()
                    if result:
                        activity_type = result[0]
                        if activity_type == 'time':
                            bot.reply_to(message, "Please enter the new duration in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds):")
                        else:
                            bot.reply_to(message, "Please enter the new number of reps:")
                        bot.register_next_step_handler(message, process_update_activity_value, activity_id, activity_type)
                    else:
                        bot.reply_to(message, "Activity not found or you don't have permission to update it.")
            finally:
                release_connection(conn)
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while processing the activity ID: {str(e)}")

    def process_update_activity_value(message: Message, activity_id, activity_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_value = message.text.strip()
        telegram_id = message.from_user.id
        
        try:
            if activity_type == 'time':
                new_value = parse_time_to_seconds(new_value)
                if new_value <= 0:
                    raise ValueError("Duration must be positive")
            else:
                new_value = int(new_value)
                if new_value <= 0:
                    raise ValueError("Number of reps must be positive")
            
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                    user_id = cursor.fetchone()[0]
                    cursor.execute("UPDATE activities SET value = %s WHERE id = %s AND user_id = %s",
                                (new_value, activity_id, user_id))
                    if cursor.rowcount == 0:
                        bot.reply_to(message, "Activity not found or you don't have permission to update it.")
                    else:
                        conn.commit()
                        bot.reply_to(message, f"Activity with ID {activity_id} has been updated successfully!")
            finally:
                release_connection(conn)
        except ValueError as e:
            if activity_type == 'time':
                bot.reply_to(message, f"Invalid input: {str(e)}. Please enter a valid time in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds).")
            else:
                bot.reply_to(message, "Invalid input. Please enter a positive integer for reps.")
            bot.register_next_step_handler(message, process_update_activity_value, activity_id, activity_type)
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
                user_result = cursor.fetchone()
                if not user_result:
                    bot.reply_to(message, "Error: User not found in database.")
                    return
                user_id = user_result[0]
                
                cursor.execute("""
                    SELECT a.id, r.activity_name, a.value, r.activity_type, a.created_at
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
                        try:
                            value_str = format_activity_value(activity[2], activity[3])
                            nicosia_time = activity[4].astimezone(NICOSIA_TIMEZONE)
                            response += f"ID: {activity[0]}, Activity: {activity[1]}, Value: {value_str}, Date: {nicosia_time.strftime('%Y-%m-%d %H:%M')}\n"
                        except Exception as e:
                            response += f"Error formatting activity {activity[0]}: {str(e)}\n"
                else:
                    response = "You haven't added any activities yet."
                
                bot.reply_to(message, response)
        except Exception as e:
            error_message = f"An error occurred while fetching your activities: {str(e)}\n"
            error_message += f"Error type: {type(e).__name__}\n"
            error_message += f"Error details: {str(e.args)}"
            bot.reply_to(message, error_message)
            print(error_message)  # Log the error to the console
        finally:
            release_connection(conn)

    def format_activity_value(value, activity_type):
        try:
            value = int(value)
            if activity_type == 'time':
                return format_duration(value)
            else:
                return f"{value} reps"
        except ValueError:
            return f"Error: Invalid value format for {activity_type}"

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
                user_result = cursor.fetchone()
                if not user_result:
                    bot.reply_to(message, "Error: User not found in database.")
                    return
                user_id = user_result[0]
                
                # Get total activities count
                cursor.execute("SELECT COUNT(*) FROM activities WHERE user_id = %s", (user_id,))
                total_activities = cursor.fetchone()[0]

                # Get unique activities count
                cursor.execute("SELECT COUNT(DISTINCT reference_activity_id) FROM activities WHERE user_id = %s", (user_id,))
                unique_activities = cursor.fetchone()[0]

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
                    SELECT r.activity_name, a.value, r.activity_type, a.created_at
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
                for activity_name, value, activity_type, created_at in activities:
                    try:
                        value = int(value)
                        if activity_type == 'reps':
                            total_reps += value
                        else:  # 'time'
                            total_duration += value

                        if activity_name not in activity_totals:
                            activity_totals[activity_name] = {'reps': 0, 'time': 0}
                        activity_totals[activity_name][activity_type] += value
                    except ValueError as e:
                        print(f"Error processing activity: {activity_name}, value: {value}, type: {activity_type}")
                        print(f"Error details: {str(e)}")

                # Format the response
                stats_message = f"📊 Your Fitness Challenge Statistics:\n\n"
                stats_message += f"Total activities logged: {total_activities}\n"
                stats_message += f"Unique activities: {unique_activities}\n"
                if most_frequent:
                    stats_message += f"Most frequent activity: {most_frequent[0]} (done {most_frequent[1]} times)\n"
                stats_message += f"Total reps across all activities: {total_reps}\n"
                stats_message += f"Total duration across all activities: {format_duration(total_duration)}\n\n"
                
                stats_message += "Activity Statistics:\n"
                for activity, totals in activity_totals.items():
                    stats_message += f"{activity}:\n"
                    if totals['reps'] > 0:
                        stats_message += f"  Total reps: {totals['reps']}\n"
                    if totals['time'] > 0:
                        stats_message += f"  Total duration: {format_duration(totals['time'])}\n"
                    
                    # Get the last activity date for this reference activity
                    cursor.execute("""
                        SELECT MAX(a.created_at)
                        FROM activities a
                        JOIN reference_activities r ON a.reference_activity_id = r.id
                        WHERE a.user_id = %s AND r.activity_name = %s
                    """, (user_id, activity))
                    last_activity_date = cursor.fetchone()[0]
                    if last_activity_date:
                        nicosia_time = last_activity_date.astimezone(NICOSIA_TIMEZONE)
                        stats_message += f"  Last performed: {nicosia_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    
                    stats_message += "\n"

                bot.reply_to(message, stats_message)
        except Exception as e:
            error_message = f"An error occurred while fetching your statistics: {str(e)}\n"
            error_message += f"Error type: {type(e).__name__}\n"
            error_message += f"Error details: {str(e.args)}"
            bot.reply_to(message, error_message)
            print(error_message)  # Log the error to the console
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
                        message = "😊 No worries! There's still time to get active. Remember, consistency is key! "
                
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
        bot.register_next_step_handler(message, process_add_reference_activity_name)

    def process_add_reference_activity_name(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        activity_name = message.text.strip()
        
        # List of commands to check against
        commands = ['start', 'help', 'register', 'auth', 'add', 'update', 'delete', 'list', 'stats', 'logout', 'addref', 'listref', 'updateref', 'deleteref', 'exit']
        
        # Check if the activity name is a command (case-insensitive)
        if activity_name.lower().startswith('/') or activity_name.lower() in commands:
            bot.reply_to(message, "You cannot use a command as an activity name. Please choose a different name.")
            return add_reference_activity(message)

        keyboard = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
        keyboard.add("time", "reps")
        bot.reply_to(message, "Please select the type of activity:", reply_markup=keyboard)
        bot.register_next_step_handler(message, process_add_reference_activity_type, activity_name)

    def process_add_reference_activity_type(message: Message, activity_name):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        activity_type = message.text.strip().lower()
        if activity_type not in ["time", "reps"]:
            bot.reply_to(message, "Invalid type. Please select either 'time' or 'reps'.")
            return add_reference_activity(message)

        telegram_id = message.from_user.id
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO reference_activities (user_id, activity_name, activity_type) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (user_id, activity_name, activity_type)
                )
                conn.commit()
                bot.reply_to(message, f"Activity '{activity_name}' ({activity_type}) has been added to your reference list!", reply_markup=types.ReplyKeyboardRemove())
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
                cursor.execute("SELECT id, activity_name, activity_type FROM reference_activities WHERE user_id = %s ORDER BY id", (user_id,))
                activities = cursor.fetchall()
                
                if activities:
                    response = "Your reference activities:\n\n"
                    for activity in activities:
                        response += f"ID: {activity[0]}, Activity: {activity[1]} ({activity[2]})\n"
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
        bot.reply_to(message, "Please enter the ID of the reference activity you want to update:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, process_update_reference_activity_id)

    def process_update_reference_activity_id(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        try:
            activity_id = int(message.text.strip())
            telegram_id = message.from_user.id
            
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                    user_id = cursor.fetchone()[0]
                    cursor.execute("SELECT activity_name, activity_type FROM reference_activities WHERE id = %s AND user_id = %s", (activity_id, user_id))
                    result = cursor.fetchone()
                    if result:
                        current_name, current_type = result
                        bot.reply_to(message, f"Current name: {current_name}\nCurrent type: {current_type}\nPlease enter the new name for this activity (or 'skip' to keep the current name):")
                        bot.register_next_step_handler(message, process_update_reference_activity_name, activity_id, current_name, current_type)
                    else:
                        bot.reply_to(message, "Reference activity not found or you don't have permission to update it.")
            finally:
                release_connection(conn)
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while processing the activity ID: {str(e)}")

    def process_update_reference_activity_name(message: Message, activity_id, current_name, current_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_name = message.text.strip()
        if new_name.lower() == 'skip':
            new_name = current_name
        
        keyboard = types.ReplyKeyboardMarkup(row_width=3, one_time_keyboard=True, resize_keyboard=True)
        keyboard.add("time", "reps", "skip")
        bot.reply_to(message, f"Current type: {current_type}\nPlease select the new type for this activity:", reply_markup=keyboard)
        bot.register_next_step_handler(message, process_update_reference_activity_type_keyboard, activity_id, new_name, current_type)

    def process_update_reference_activity_type_keyboard(message: Message, activity_id, new_name, current_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_type = message.text.strip().lower()
        if new_type not in ['time', 'reps', 'skip']:
            bot.reply_to(message, "Invalid type. Please select either 'time', 'reps', or 'skip' to keep the current type.")
            keyboard = types.ReplyKeyboardMarkup(row_width=3, one_time_keyboard=True, resize_keyboard=True)
            keyboard.add("time", "reps", "skip")
            bot.reply_to(message, f"Please select the new type for this activity:", reply_markup=keyboard)
            return bot.register_next_step_handler(message, process_update_reference_activity_type_keyboard, activity_id, new_name, current_type)
        
        if new_type == 'skip':
            new_type = current_type
        
        telegram_id = message.from_user.id
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user_id = cursor.fetchone()[0]
                cursor.execute(
                    "UPDATE reference_activities SET activity_name = %s, activity_type = %s WHERE id = %s AND user_id = %s",
                    (new_name, new_type, activity_id, user_id)
                )
                conn.commit()
                bot.reply_to(message, f"Reference activity updated successfully!\nNew name: {new_name}\nNew type: {new_type}", reply_markup=types.ReplyKeyboardRemove())
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