import telebot
from telebot.types import Message, CallbackQuery
from database import Database  # Import the Database class
from config import BOT_TOKEN, MAINTENANCE_MODE
import pytz
from datetime import datetime
import logging
from tasks import send_encouragement_and_quote

# Add this constant at the top of your file
NICOSIA_TIMEZONE = pytz.timezone('Europe/Nicosia')

# Create a Database instance
db = Database()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_bot():
    bot = telebot.TeleBot(BOT_TOKEN)
    register_handlers(bot)
    return bot

def check_maintenance(message: Message, bot: telebot.TeleBot):
    if MAINTENANCE_MODE:
        user = db.get_user(message.from_user.id)
        if not user or not user[5]:  # user[5] is the is_admin flag
            bot.reply_to(message, "The bot is currently under maintenance. Please try again later.")
            return True
    return False

def register_handlers(bot: telebot.TeleBot):
    @bot.message_handler(commands=['start'])
    def start(message: Message):
        if check_maintenance(message, bot):
            return
        
        telegram_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        try:
            user = db.get_user(telegram_id)
            
            if user:
                # Update user information
                db.update_user(telegram_id, username, first_name, last_name)
                bot.reply_to(message, "Welcome back! Your information has been updated.")
            else:
                # Insert new user
                db.add_user(telegram_id, username, first_name, last_name)
                bot.reply_to(message, "Welcome! You've been successfully registered.")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while processing your request: {str(e)}")

    @bot.message_handler(commands=['help'])
    def help(message: Message):
        if check_maintenance(message, bot):
            return
        help_text = """
        Available commands:
        /start - Start the bot
        /help - Show this help message            

        Activity commands:
        /add - Add a new activity
        /update - Update an existing activity
        /delete - Delete an activity
        /list - List all activities
        /stats - Get activity statistics
        
        Reference activities:
        /addref - Add a new reference activity
        /listref - List all reference activities
        /updateref - Update an existing reference activity
        /deleteref - Delete a reference activity

        Other commands:
        /exit - Cancel the current operation (can be used during multi-step commands)
        """
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['add'])
    def add_activity(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            logger.debug(f"User: {user}")
            
            activities = db.get_reference_activities(user[0])  # user[0] is the user_id
            logger.debug(f"Reference activities: {activities}")
            
            if activities:
                keyboard = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                for activity in activities:
                    activity_id, activity_name, activity_type = activity  # Unpack 3 values
                    keyboard.add(f"{activity_id}: {activity_name} ({activity_type})")
                bot.reply_to(message, "Please choose an activity:", reply_markup=keyboard)
                bot.register_next_step_handler(message, process_add_activity_choice, activities)
            else:
                bot.reply_to(message, "You don't have any reference activities. Please add one first using /addref")
        except Exception as e:
            logger.exception("Error in add_activity")
            bot.reply_to(message, f"An error occurred: {str(e)}")
            logger.error(f"Error occurred on line {sys.exc_info()[2].tb_lineno}")

    def process_add_activity_choice(message: Message, valid_activities):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        choice = message.text.strip()
        logger.debug(f"User choice: {choice}")
        
        try:
            reference_activity_id = int(choice.split(":")[0])
            activity = next((act for act in valid_activities if act[0] == reference_activity_id), None)
            
            if not activity:
                raise ValueError("Invalid activity selection")
            
            activity_id, activity_name, activity_type = activity  # Unpack 3 values
            
            if activity_type == 'time':
                bot.reply_to(message, f"Adding activity: {activity_name}\nPlease enter the duration in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds):", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.reply_to(message, f"Adding activity: {activity_name}\nPlease enter the number of reps:", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, process_add_activity_value, reference_activity_id, activity_type)
        except Exception as e:
            logger.exception("Error in process_add_activity_choice")
            bot.reply_to(message, f"An error occurred while processing your choice: {str(e)}")
            return add_activity(message)

    def process_add_activity_value(message: Message, reference_activity_id, activity_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        value_input = message.text.strip()
        telegram_id = message.from_user.id
        
        try:
            value = parse_activity_value(value_input, activity_type)
            
            user = db.get_user(telegram_id)
            db.add_activity(user[0], reference_activity_id, value)
            
            # Get current time in Nicosia (for display purposes only)
            nicosia_time = datetime.now(NICOSIA_TIMEZONE)
            
            value_str = format_activity_value(value, activity_type)
            bot.reply_to(message, f"Activity added successfully! Recorded {value_str} at {nicosia_time.strftime('%Y-%m-%d %H:%M:%S')} Nicosia time.")
        except ValueError as e:
            bot.reply_to(message, str(e))
            if activity_type == 'time':
                bot.reply_to(message, "Please enter a valid time in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds):")
            else:
                bot.reply_to(message, "Please enter a valid number of reps:")
            bot.register_next_step_handler(message, process_add_activity_value, reference_activity_id, activity_type)
        except Exception as e:
            logger.exception("Error in process_add_activity_value")
            bot.reply_to(message, f"An error occurred while adding the activity: {str(e)}")

    def parse_activity_value(value_input, activity_type):
        if activity_type == 'time':
            try:
                hours, minutes, seconds = map(int, value_input.split(':'))
                total_seconds = hours * 3600 + minutes * 60 + seconds
                if total_seconds <= 0:
                    raise ValueError("Duration must be positive")
                return total_seconds
            except ValueError:
                raise ValueError("Invalid time format. Please use HH:MM:SS.")
        else:  # reps
            try:
                value = int(value_input)
                if value <= 0:
                    raise ValueError("Number of reps must be positive")
                return value
            except ValueError:
                raise ValueError("Invalid input. Please enter a positive integer for reps.")

    def format_activity_value(value, activity_type):
        if activity_type == 'time':
            return format_duration(value)
        else:
            return f"{value} reps"

    def format_duration(seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @bot.message_handler(commands=['update'])
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
            
            user = db.get_user(telegram_id)
            activity = db.get_activity(activity_id, user[0])
            if activity:
                reference_activity = db.get_reference_activity(activity[1], user[0])
                if reference_activity:
                    activity_name, activity_type = reference_activity[1], reference_activity[2]
                    current_value = format_activity_value(activity[2], activity_type)
                    if activity_type == 'time':
                        bot.reply_to(message, f"Updating activity: {activity_name}\nCurrent value: {current_value}\nPlease enter the new duration in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds):")
                    else:
                        bot.reply_to(message, f"Updating activity: {activity_name}\nCurrent value: {current_value}\nPlease enter the new number of reps:")
                    bot.register_next_step_handler(message, process_update_activity_value, activity_id, activity_type)
                else:
                    bot.reply_to(message, "Error: Reference activity not found.")
            else:
                bot.reply_to(message, "Activity not found or you don't have permission to update it.")
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
            new_value = parse_activity_value(new_value, activity_type)
            
            user = db.get_user(telegram_id)
            db.update_activity(activity_id, user[0], new_value)
            
            value_str = format_activity_value(new_value, activity_type)
            bot.reply_to(message, f"Activity with ID {activity_id} has been updated successfully! New value: {value_str}")
        except ValueError as e:
            bot.reply_to(message, str(e))
            bot.register_next_step_handler(message, process_update_activity_value, activity_id, activity_type)
        except Exception as e:
            bot.reply_to(message, f"An error occurred while updating the activity: {str(e)}")

    @bot.message_handler(commands=['delete'])
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
            
            user = db.get_user(telegram_id)
            db.delete_activity(activity_id, user[0])
            bot.reply_to(message, f"Activity with ID {activity_id} has been deleted successfully!")
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while deleting the activity: {str(e)}")

    @bot.message_handler(commands=['list'])
    
    def list_activities(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_recent_activities(user[0])  # user[0] is the user_id
            
            if activities:
                response = "Your recent activities:\n\n"
                for activity in activities:
                    try:
                        activity_id, activity_name, value, activity_type, created_at = activity
                        value_str = format_activity_value(value, activity_type)
                        nicosia_time = created_at.astimezone(NICOSIA_TIMEZONE)
                        response += f"ID: {activity_id}, Activity: {activity_name}, Value: {value_str}, Date: {nicosia_time.strftime('%Y-%m-%d %H:%M')}\n"
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

    @bot.message_handler(commands=['stats'])
    
    def get_stats(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        try:
            user = db.get_user(telegram_id)
            
            total_activities = db.get_total_activities_count(user[0])
            unique_activities = db.get_unique_activities_count(user[0])
            most_frequent = db.get_most_frequent_activity(user[0])
            activities = db.get_all_activities(user[0])

            logger.debug(f"Total activities: {total_activities}")
            logger.debug(f"Unique activities: {unique_activities}")
            logger.debug(f"Most frequent activity: {most_frequent}")
            logger.debug(f"All activities: {activities}")

            # Calculate totals
            activity_totals, total_reps, total_duration = calculate_activity_totals(activities)

            # Format the response
            stats_message = format_stats_message(total_activities, unique_activities, most_frequent, 
                                                 total_reps, total_duration, activity_totals)

            bot.reply_to(message, stats_message)
        except Exception as e:
            error_message = f"An error occurred while fetching your statistics: {str(e)}\n"
            error_message += f"Error type: {type(e).__name__}\n"
            error_message += f"Error details: {str(e.args)}"
            bot.reply_to(message, error_message)
            logger.exception("Error in get_stats")

    def calculate_activity_totals(activities):
        activity_totals = {}
        total_reps = 0
        total_duration = 0
        for activity in activities:
            activity_id, activity_name, value, activity_type, created_at = activity
            
            if activity_type == 'reps':
                total_reps += value
            else:  # 'time'
                total_duration += value

            if activity_name not in activity_totals:
                activity_totals[activity_name] = {'reps': 0, 'time': 0}
            activity_totals[activity_name][activity_type] += value
        
        return activity_totals, total_reps, total_duration

    def format_stats_message(total_activities, unique_activities, most_frequent, total_reps, total_duration, activity_totals):
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
            
            last_activity = db.get_last_activity(activity)
            if last_activity:
                nicosia_time = last_activity[2].astimezone(NICOSIA_TIMEZONE)
                stats_message += f"  Last performed: {nicosia_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            stats_message += "\n"
        
        return stats_message

    @bot.message_handler(commands=['addref'])
    def add_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the name of the reference activity:")
        bot.register_next_step_handler(message, process_add_reference_activity_name)

    def process_add_reference_activity_name(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        activity_name = message.text.strip()
        bot.reply_to(message, "Please enter the type of the reference activity (time or reps):")
        bot.register_next_step_handler(message, process_add_reference_activity_type, activity_name)

    def process_add_reference_activity_type(message: Message, activity_name):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        activity_type = message.text.strip().lower()
        if activity_type not in ['time', 'reps']:
            bot.reply_to(message, "Invalid activity type. Please enter 'time' or 'reps'.")
            return add_reference_activity(message)
        
        try:
            db.add_reference_activity(activity_name, activity_type)
            bot.reply_to(message, f"Reference activity '{activity_name}' ({activity_type}) added successfully!")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while adding the reference activity: {str(e)}")

    @bot.message_handler(commands=['listref'])
    def list_reference_activities(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_reference_activities(user[0])
            
            if activities:
                response = "Your reference activities:\n\n"
                for activity in activities:
                    activity_id, activity_name, activity_type = activity  # Unpack 3 values
                    response += f"ID: {activity_id}, Activity: {activity_name} ({activity_type})\n"
            else:
                response = "You haven't added any reference activities yet."
            
            bot.reply_to(message, response)
        except Exception as e:
            bot.reply_to(message, f"An error occurred while fetching your reference activities: {str(e)}")

    @bot.message_handler(commands=['updateref'])
    def update_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the ID of the reference activity you want to update:")
        bot.register_next_step_handler(message, process_update_reference_activity_id)

    def process_update_reference_activity_id(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        try:
            activity_id = int(message.text.strip())
            activity = db.get_reference_activity(activity_id)
            if activity:
                bot.reply_to(message, f"Current name: {activity[1]}, Current type: {activity[2]}\nPlease enter the new name (or leave blank to keep current):")
                bot.register_next_step_handler(message, process_update_reference_activity_name, activity_id)
            else:
                bot.reply_to(message, "Reference activity not found.")
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid reference activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while processing the reference activity ID: {str(e)}")

    def process_update_reference_activity_name(message: Message, activity_id):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_name = message.text.strip()
        bot.reply_to(message, "Please enter the new type (time or reps, or leave blank to keep current):")
        bot.register_next_step_handler(message, process_update_reference_activity_type, activity_id, new_name)

    def process_update_reference_activity_type(message: Message, activity_id, new_name):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_type = message.text.strip().lower()
        if new_type not in ['time', 'reps', '']:
            bot.reply_to(message, "Invalid activity type. Please enter 'time' or 'reps'.")
            return update_reference_activity(message)
        
        try:
            db.update_reference_activity(activity_id, new_name, new_type)
            bot.reply_to(message, f"Reference activity with ID {activity_id} has been updated successfully!")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while updating the reference activity: {str(e)}")

    @bot.message_handler(commands=['deleteref'])
    def delete_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the ID of the reference activity you want to delete:")
        bot.register_next_step_handler(message, process_delete_reference_activity_check)

    def process_delete_reference_activity_check(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        try:
            activity_id = int(message.text.strip())
            telegram_id = message.from_user.id
            
            user = db.get_user(telegram_id)
            reference_activity = db.get_reference_activity(activity_id, user[0])
            
            if not reference_activity:
                bot.reply_to(message, f"Reference activity with ID {activity_id} not found or you don't have permission to delete it.")
                return
            
            activity_count = db.get_activity_count_for_reference(activity_id, user[0])
            
            if activity_count > 0:
                keyboard = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                keyboard.add("Yes", "No")
                bot.reply_to(message, 
                             f"Warning: The reference activity '{reference_activity[1]}' has {activity_count} recorded activities. "
                             f"Deleting this reference will also delete all associated activities. "
                             f"Are you sure you want to proceed?",
                             reply_markup=keyboard)
                bot.register_next_step_handler(message, process_delete_reference_activity_confirm, activity_id)
            else:
                process_delete_reference_activity(message, activity_id)
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while processing the reference activity: {str(e)}")

    def process_delete_reference_activity_confirm(message: Message, activity_id):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        confirmation = message.text.strip().lower()
        if confirmation == 'yes':
            process_delete_reference_activity(message, activity_id)
        else:
            bot.reply_to(message, "Deletion cancelled.", reply_markup=types.ReplyKeyboardRemove())

    def process_delete_reference_activity(message: Message, activity_id):
        try:
            telegram_id = message.from_user.id
            user = db.get_user(telegram_id)
            success = db.delete_reference_activity(activity_id, user[0])
            if success:
                bot.reply_to(message, f"Reference activity with ID {activity_id} has been deleted successfully!", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.reply_to(message, f"Failed to delete reference activity with ID {activity_id}. It may not exist or you don't have permission to delete it.", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.reply_to(message, f"An error occurred while deleting the reference activity: {str(e)}", reply_markup=types.ReplyKeyboardRemove())

    @bot.message_handler(commands=['exit'])
    def exit_command(message: Message):
        bot.reply_to(message, "Exiting the current operation.")

    @bot.message_handler(func=lambda message: True)
    def handle_unknown_command(message: Message):
        bot.reply_to(message, "Unknown command. Please use /help to see available commands.")

def check_exit(message: Message, bot: telebot.TeleBot):
    if message.text.strip().lower() == '/exit':
        bot.reply_to(message, "Exiting the current operation.")
        return True
    return False

def register_handlers(bot: telebot.TeleBot):
    @bot.message_handler(commands=['start'])
    def start(message: Message):
        if check_maintenance(message, bot):
            return
        
        telegram_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        try:
            user = db.get_user(telegram_id)
            
            if user:
                # Update user information
                db.update_user(telegram_id, username, first_name, last_name)
                bot.reply_to(message, "Welcome back! Your information has been updated.")
            else:
                # Insert new user
                db.add_user(telegram_id, username, first_name, last_name)
                bot.reply_to(message, "Welcome! You've been successfully registered.")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while processing your request: {str(e)}")

    @bot.message_handler(commands=['help'])
    def help(message: Message):
        if check_maintenance(message, bot):
            return
        help_text = """
        Available commands:
        /start - Start the bot
        /help - Show this help message            

        Activity commands:
        /add - Add a new activity
        /update - Update an existing activity
        /delete - Delete an activity
        /list - List all activities
        /stats - Get activity statistics
        
        Reference activities:
        /addref - Add a new reference activity
        /listref - List all reference activities
        /updateref - Update an existing reference activity
        /deleteref - Delete a reference activity

        Other commands:
        /exit - Cancel the current operation (can be used during multi-step commands)
        """
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['add'])
    def add_activity(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_reference_activities(user[0])  # user[0] is the user_id
            
            if activities:
                keyboard = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                for activity in activities:
                    activity_id, activity_name, activity_type = activity  # Unpack 3 values
                    keyboard.add(f"{activity_id}: {activity_name} ({activity_type})")
                bot.reply_to(message, "Please choose an activity:", reply_markup=keyboard)
                bot.register_next_step_handler(message, process_add_activity_choice, activities)
            else:
                bot.reply_to(message, "You don't have any reference activities. Please add one first using /addref")
        except Exception as e:
            logger.exception("Error in add_activity")
            bot.reply_to(message, f"An error occurred: {str(e)}")

    def process_add_activity_choice(message: Message, valid_activities):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        choice = message.text.strip()
        logger.debug(f"User choice: {choice}")
        
        try:
            reference_activity_id = int(choice.split(":")[0])
            activity = next((act for act in valid_activities if act[0] == reference_activity_id), None)
            
            if not activity:
                raise ValueError("Invalid activity selection")
            
            activity_id, activity_name, activity_type = activity  # Unpack 3 values
            
            if activity_type == 'time':
                bot.reply_to(message, f"Adding activity: {activity_name}\nPlease enter the duration in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds):", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.reply_to(message, f"Adding activity: {activity_name}\nPlease enter the number of reps:", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, process_add_activity_value, reference_activity_id, activity_type)
        except Exception as e:
            logger.exception("Error in process_add_activity_choice")
            bot.reply_to(message, f"An error occurred while processing your choice: {str(e)}")
            return add_activity(message)

    def process_add_activity_value(message: Message, reference_activity_id, activity_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        value_input = message.text.strip()
        telegram_id = message.from_user.id
        
        try:
            value = parse_activity_value(value_input, activity_type)
            
            user = db.get_user(telegram_id)
            db.add_activity(user[0], reference_activity_id, value)
            
            # Get current time in Nicosia (for display purposes only)
            nicosia_time = datetime.now(NICOSIA_TIMEZONE)
            
            value_str = format_activity_value(value, activity_type)
            bot.reply_to(message, f"Activity added successfully! Recorded {value_str} at {nicosia_time.strftime('%Y-%m-%d %H:%M:%S')} Nicosia time.")
        except ValueError as e:
            bot.reply_to(message, str(e))
            if activity_type == 'time':
                bot.reply_to(message, "Please enter a valid time in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds):")
            else:
                bot.reply_to(message, "Please enter a valid number of reps:")
            bot.register_next_step_handler(message, process_add_activity_value, reference_activity_id, activity_type)
        except Exception as e:
            logger.exception("Error in process_add_activity_value")
            bot.reply_to(message, f"An error occurred while adding the activity: {str(e)}")

    def parse_activity_value(value_input, activity_type):
        if activity_type == 'time':
            try:
                hours, minutes, seconds = map(int, value_input.split(':'))
                total_seconds = hours * 3600 + minutes * 60 + seconds
                if total_seconds <= 0:
                    raise ValueError("Duration must be positive")
                return total_seconds
            except ValueError:
                raise ValueError("Invalid time format. Please use HH:MM:SS.")
        else:  # reps
            try:
                value = int(value_input)
                if value <= 0:
                    raise ValueError("Number of reps must be positive")
                return value
            except ValueError:
                raise ValueError("Invalid input. Please enter a positive integer for reps.")

    def format_activity_value(value, activity_type):
        if activity_type == 'time':
            return format_duration(value)
        else:
            return f"{value} reps"

    def format_duration(seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @bot.message_handler(commands=['update'])
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
            
            user = db.get_user(telegram_id)
            activity = db.get_activity(activity_id, user[0])
            if activity:
                reference_activity = db.get_reference_activity(activity[1], user[0])
                if reference_activity:
                    activity_name, activity_type = reference_activity[1], reference_activity[2]
                    current_value = format_activity_value(activity[2], activity_type)
                    if activity_type == 'time':
                        bot.reply_to(message, f"Updating activity: {activity_name}\nCurrent value: {current_value}\nPlease enter the new duration in the format HH:MM:SS (e.g., 00:01:30 for 1 minute 30 seconds):")
                    else:
                        bot.reply_to(message, f"Updating activity: {activity_name}\nCurrent value: {current_value}\nPlease enter the new number of reps:")
                    bot.register_next_step_handler(message, process_update_activity_value, activity_id, activity_type)
                else:
                    bot.reply_to(message, "Error: Reference activity not found.")
            else:
                bot.reply_to(message, "Activity not found or you don't have permission to update it.")
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
            new_value = parse_activity_value(new_value, activity_type)
            
            user = db.get_user(telegram_id)
            db.update_activity(activity_id, user[0], new_value)
            
            value_str = format_activity_value(new_value, activity_type)
            bot.reply_to(message, f"Activity with ID {activity_id} has been updated successfully! New value: {value_str}")
        except ValueError as e:
            bot.reply_to(message, str(e))
            bot.register_next_step_handler(message, process_update_activity_value, activity_id, activity_type)
        except Exception as e:
            bot.reply_to(message, f"An error occurred while updating the activity: {str(e)}")

    @bot.message_handler(commands=['delete'])
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
            
            user = db.get_user(telegram_id)
            db.delete_activity(activity_id, user[0])
            bot.reply_to(message, f"Activity with ID {activity_id} has been deleted successfully!")
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while deleting the activity: {str(e)}")

    @bot.message_handler(commands=['list'])
    
    def list_activities(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_recent_activities(user[0])  # user[0] is the user_id
            
            if activities:
                response = "Your recent activities:\n\n"
                for activity in activities:
                    try:
                        activity_id, activity_name, value, activity_type, created_at = activity
                        value_str = format_activity_value(value, activity_type)
                        nicosia_time = created_at.astimezone(NICOSIA_TIMEZONE)
                        response += f"ID: {activity_id}, Activity: {activity_name}, Value: {value_str}, Date: {nicosia_time.strftime('%Y-%m-%d %H:%M')}\n"
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

    @bot.message_handler(commands=['stats'])
    
    def get_stats(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        try:
            user = db.get_user(telegram_id)
            
            total_activities = db.get_total_activities_count(user[0])
            unique_activities = db.get_unique_activities_count(user[0])
            most_frequent = db.get_most_frequent_activity(user[0])
            activities = db.get_all_activities(user[0])

            logger.debug(f"Total activities: {total_activities}")
            logger.debug(f"Unique activities: {unique_activities}")
            logger.debug(f"Most frequent activity: {most_frequent}")
            logger.debug(f"All activities: {activities}")

            # Calculate totals
            activity_totals, total_reps, total_duration = calculate_activity_totals(activities)

            # Format the response
            stats_message = format_stats_message(total_activities, unique_activities, most_frequent, 
                                                 total_reps, total_duration, activity_totals)

            bot.reply_to(message, stats_message)
        except Exception as e:
            error_message = f"An error occurred while fetching your statistics: {str(e)}\n"
            error_message += f"Error type: {type(e).__name__}\n"
            error_message += f"Error details: {str(e.args)}"
            bot.reply_to(message, error_message)
            logger.exception("Error in get_stats")

    def calculate_activity_totals(activities):
        activity_totals = {}
        total_reps = 0
        total_duration = 0
        for activity in activities:
            activity_id, activity_name, value, activity_type, created_at = activity
            
            if activity_type == 'reps':
                total_reps += value
            else:  # 'time'
                total_duration += value

            if activity_name not in activity_totals:
                activity_totals[activity_name] = {'reps': 0, 'time': 0}
            activity_totals[activity_name][activity_type] += value
        
        return activity_totals, total_reps, total_duration

    def format_stats_message(total_activities, unique_activities, most_frequent, total_reps, total_duration, activity_totals):
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
            
            last_activity = db.get_last_activity(activity)
            if last_activity:
                nicosia_time = last_activity[2].astimezone(NICOSIA_TIMEZONE)
                stats_message += f"  Last performed: {nicosia_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            stats_message += "\n"
        
        return stats_message

    @bot.callback_query_handler(func=lambda call: call.data.startswith("daily_check_"))
    def handle_daily_check(call: CallbackQuery):
        if check_maintenance(call.message, bot):
            return
        user_id = call.from_user.id
        response = call.data.split("_")[-1]
        
        try:
            user = db.get_user(user_id)
            activities_count = db.get_activities_count_for_today(user[0])
            
            was_active = response == "yes"
            
            # Send encouragement and quote
            send_encouragement_and_quote.delay(user_id, was_active)
            
            # Optionally, you can add a reminder to log activities if the user was active but hasn't logged any
            if was_active and activities_count == 0:
                bot.send_message(user_id, "Don't forget to log your activities using the /add command! 📝")
        
        except Exception as e:
            bot.reply_to(call.message, f"An error occurred while processing your response: {str(e)}")

    @bot.message_handler(commands=['addref'])
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
        commands = ['start', 'help', 'add', 'update', 'delete', 'list', 'stats', 'addref', 'listref', 'updateref', 'deleteref', 'exit']
        
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
        try:
            user = db.get_user(telegram_id)
            db.add_reference_activity(user[0], activity_name, activity_type)
            bot.reply_to(message, f"Activity '{activity_name}' ({activity_type}) has been added to your reference list!", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.reply_to(message, f"An error occurred while adding the reference activity: {str(e)}")

    @bot.message_handler(commands=['listref'])
    def list_reference_activities(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_reference_activities(user[0])
            
            if activities:
                response = "Your reference activities:\n\n"
                for activity in activities:
                    activity_id, activity_name, activity_type = activity  # Unpack 3 values
                    response += f"ID: {activity_id}, Activity: {activity_name} ({activity_type})\n"
            else:
                response = "You haven't added any reference activities yet."
            
            bot.reply_to(message, response)
        except Exception as e:
            bot.reply_to(message, f"An error occurred while fetching your reference activities: {str(e)}")

    @bot.message_handler(commands=['updateref'])
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
            
            user = db.get_user(telegram_id)
            activity = db.get_reference_activity(activity_id, user[0])
            if activity:
                current_name, current_type = activity[1], activity[2]
                bot.reply_to(message, f"Current name: {current_name}\nCurrent type: {current_type}\nPlease enter the new name for this activity (or 'skip' to keep the current name):")
                bot.register_next_step_handler(message, process_update_reference_activity_name, activity_id, current_name, current_type)
            else:
                bot.reply_to(message, "Reference activity not found or you don't have permission to update it.")
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
        try:
            user = db.get_user(telegram_id)
            success = db.update_reference_activity(activity_id, user[0], new_name, new_type)
            if success:
                bot.reply_to(message, f"Reference activity updated successfully!\nNew name: {new_name}\nNew type: {new_type}", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.reply_to(message, "Failed to update the reference activity. It may not exist or you don't have permission to update it.", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.reply_to(message, f"An error occurred while updating the reference activity: {str(e)}", reply_markup=types.ReplyKeyboardRemove())

    @bot.message_handler(commands=['deleteref'])
    def delete_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        bot.reply_to(message, "Please enter the ID of the reference activity you want to delete:")
        bot.register_next_step_handler(message, process_delete_reference_activity_check)

    def process_delete_reference_activity_check(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        try:
            activity_id = int(message.text.strip())
            telegram_id = message.from_user.id
            
            user = db.get_user(telegram_id)
            reference_activity = db.get_reference_activity(activity_id, user[0])
            
            if not reference_activity:
                bot.reply_to(message, f"Reference activity with ID {activity_id} not found or you don't have permission to delete it.")
                return
            
            activity_count = db.get_activity_count_for_reference(activity_id, user[0])
            
            if activity_count > 0:
                keyboard = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                keyboard.add("Yes", "No")
                bot.reply_to(message, 
                             f"Warning: The reference activity '{reference_activity[1]}' has {activity_count} recorded activities. "
                             f"Deleting this reference will also delete all associated activities. "
                             f"Are you sure you want to proceed?",
                             reply_markup=keyboard)
                bot.register_next_step_handler(message, process_delete_reference_activity_confirm, activity_id)
            else:
                process_delete_reference_activity(message, activity_id)
        except ValueError:
            bot.reply_to(message, "Invalid input. Please enter a valid activity ID (number).")
        except Exception as e:
            bot.reply_to(message, f"An error occurred while processing the reference activity: {str(e)}")

    def process_delete_reference_activity_confirm(message: Message, activity_id):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        confirmation = message.text.strip().lower()
        if confirmation == 'yes':
            process_delete_reference_activity(message, activity_id)
        else:
            bot.reply_to(message, "Deletion cancelled.", reply_markup=types.ReplyKeyboardRemove())

    def process_delete_reference_activity(message: Message, activity_id):
        try:
            telegram_id = message.from_user.id
            user = db.get_user(telegram_id)
            success = db.delete_reference_activity(activity_id, user[0])
            if success:
                bot.reply_to(message, f"Reference activity with ID {activity_id} has been deleted successfully!", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.reply_to(message, f"Failed to delete reference activity with ID {activity_id}. It may not exist or you don't have permission to delete it.", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.reply_to(message, f"An error occurred while deleting the reference activity: {str(e)}", reply_markup=types.ReplyKeyboardRemove())

    @bot.message_handler(commands=['exit'])
    def exit_command(message: Message):
        bot.reply_to(message, "Exiting the current operation.")
        return True

    def check_exit(message: Message, bot: telebot.TeleBot):
        if message.text.lower() == '/exit':
            bot.reply_to(message, "Operation cancelled.", reply_markup=types.ReplyKeyboardRemove())
            return True
        return False

# Initialize the bot
bot = create_bot()

# Add this at the end of the file
if __name__ == '__main__':
    bot.polling(none_stop=True)