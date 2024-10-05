from telebot import TeleBot
from telebot.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from database import Database  # Import the Database class
from config import *
import pytz
from datetime import datetime, timedelta
from tasks import send_encouragement_and_quote
from logger import logger, log_error, log_info
from tabulate import tabulate
from error_messages import *

# Add this constant at the top of your file
NICOSIA_TIMEZONE = pytz.timezone('Europe/Nicosia')

# Create a Database instance
db = Database()

def create_bot():
    bot = TeleBot(BOT_TOKEN)
    register_handlers(bot)
    return bot

def check_maintenance(message: Message, bot: TeleBot):
    if MAINTENANCE_MODE:
        user = db.get_user(message.from_user.id)
        if not user or not user[5]:  # user[5] is the is_admin flag
            bot.reply_to(message, MAINTENANCE_MODE_MESSAGE)
            return True
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
        
        try:
            user = db.get_user(telegram_id)
            
            message_text = "Hey there! 👋 Are you ready for a challenge? 💪 I bet you do! 🎉"
            if user:
                db.update_user(telegram_id, username, first_name, last_name)
                bot.reply_to(message, message_text)
                log_info(f"User {telegram_id} information updated")
            else:
                db.add_user(telegram_id, username, first_name, last_name)
                bot.reply_to(message, message_text)
                log_info(f"New user {telegram_id} registered")
        except Exception as e:
            log_error(f"Error in start command: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

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
        """
        bot.reply_to(message, help_text)
        log_info(f"Help command used by user {message.from_user.id}")

    @bot.message_handler(commands=['add'])
    def add_activity(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_reference_activities(user[0])  # user[0] is the user_id
            
            if activities:
                keyboard = ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                for activity in activities:
                    activity_id, activity_name, activity_type = activity  # Unpack 3 values
                    keyboard.add(f"{activity_id}: {activity_name} ({activity_type})")
                keyboard.add("Cancel")  # Add Cancel button
                bot.reply_to(message, "Please choose an activity or press 'Cancel' to abort:", reply_markup=keyboard)
                bot.register_next_step_handler(message, process_add_activity_choice, activities)
                log_info(f"User {telegram_id} started adding an activity")
            else:
                bot.reply_to(message, NO_REFERENCE_ACTIVITIES_MESSAGE)
                log_info(f"User {telegram_id} attempted to add activity but has no reference activities")
        except Exception as e:
            log_error(f"Error in add_activity for user {telegram_id}: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    def process_add_activity_choice(message: Message, valid_activities):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        choice = message.text.strip()
        log_info(f"User choice: {choice}")
        
        if choice.lower() == "cancel":
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        
        try:
            reference_activity_id = int(choice.split(":")[0])
            activity = next((act for act in valid_activities if act[0] == reference_activity_id), None)
            
            if not activity:
                raise ValueError(INVALID_ACTIVITY_SELECTION_MESSAGE)
            
            activity_id, activity_name, activity_type = activity  # Unpack 3 values
            
            keyboard = ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True, resize_keyboard=True)
            keyboard.add("Cancel")
            
            if activity_type == 'time':
                bot.reply_to(message, f"How long was it? (enter in HH:MM:SS format)\nOr press 'Cancel' to abort.", reply_markup=keyboard)
            else:
                bot.reply_to(message, f"How many reps did you do?\nOr press 'Cancel' to abort.", reply_markup=keyboard)
            bot.register_next_step_handler(message, process_add_activity_value, reference_activity_id, activity_type)
        except Exception as e:
            log_error(f"Error in process_add_activity_choice: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)
            return add_activity(message)

    def process_add_activity_value(message: Message, reference_activity_id, activity_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        value_input = message.text.strip()
        telegram_id = message.from_user.id
        
        if value_input.lower() == "cancel":
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        
        try:
            value = parse_activity_value(value_input, activity_type)
            
            user = db.get_user(telegram_id)
            activity_id = db.add_activity(user[0], reference_activity_id, value)
            
            # Get the activity name
            activity = db.get_reference_activity(reference_activity_id, user[0])
            activity_name = activity[0] if activity else "Unknown"
            
            # Get current time in Nicosia
            nicosia_time = datetime.now(NICOSIA_TIMEZONE)
            
            value_str = format_activity_value(value, activity_type)
            date_str = nicosia_time.strftime('%b %d %H:%M')
            
            bot.reply_to(message, f"Added: {activity_name} | {value_str} | {date_str}", reply_markup=ReplyKeyboardRemove())
        except ValueError as e:
            bot.reply_to(message, str(e))
            keyboard = ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True, resize_keyboard=True)
            keyboard.add("Cancel")
            if activity_type == 'time':
                bot.reply_to(message, "Enter valid time (HH:MM:SS) or press 'Cancel' to abort:", reply_markup=keyboard)
            else:
                bot.reply_to(message, "Enter valid number of reps or press 'Cancel' to abort:", reply_markup=keyboard)
            bot.register_next_step_handler(message, process_add_activity_value, reference_activity_id, activity_type)
        except Exception as e:
            log_error(f"Error in process_add_activity_value: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE, reply_markup=ReplyKeyboardRemove())

    def parse_activity_value(value_input, activity_type):
        if activity_type == 'time':
            try:
                hours, minutes, seconds = map(int, value_input.split(':'))
                total_seconds = hours * 3600 + minutes * 60 + seconds
                if total_seconds <= 0:
                    raise ValueError("Duration must be positive")
                return total_seconds
            except ValueError:
                raise ValueError(INVALID_TIME_FORMAT_MESSAGE)
        else:  # reps
            try:
                value = int(value_input)
                if value <= 0:
                    raise ValueError("Number of reps must be positive")
                return value
            except ValueError:
                raise ValueError(INVALID_REPS_FORMAT_MESSAGE)

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
        
        telegram_id = message.from_user.id  # Use from_user.id as it corresponds to telegram_id
        
        try:
            user = db.get_user(telegram_id)
            if not user:
                bot.reply_to(message, "User not found. Please start the bot with /start command.")
                return

            user_id = user[0]  # Assuming the first element of the user tuple is the user_id
            activities = db.get_recent_activities(user_id, limit=ACTIVITY_LIMIT)
            
            if activities:
                keyboard = ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True, resize_keyboard=True)
                for activity in activities:
                    activity_id, activity_name, value, activity_type, created_at = activity
                    value_str = format_activity_value(value, activity_type)
                    nicosia_time = created_at.astimezone(NICOSIA_TIMEZONE)
                    date_str = nicosia_time.strftime('%b %d %H:%M')
                    keyboard.add(f"{activity_id}: {activity_name}: {value_str} | {date_str}")
                keyboard.add("Cancel")
                bot.reply_to(message, "Choose an activity to update or press 'Cancel' to abort:", reply_markup=keyboard)
                bot.register_next_step_handler(message, process_update_activity_choice, activities)
            else:
                bot.reply_to(message, NO_ACTIVITIES_MESSAGE)
        except Exception as e:
            log_error(f"Error in update_activity: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    def process_update_activity_choice(message: Message, activities):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return

        choice = message.text.strip()
        if choice.lower() == "cancel":
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        
        try:
            activity_id = int(choice.split(":")[0])
            chosen_activity = next((act for act in activities if act[0] == activity_id), None)
            
            if not chosen_activity:
                raise ValueError(INVALID_ACTIVITY_SELECTION_MESSAGE)
            
            activity_id, activity_name, current_value, activity_type, created_at = chosen_activity
            
            keyboard = ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
            keyboard.add("Skip", "Cancel")
            
            if activity_type == 'time':
                bot.reply_to(message, f"Updating: {activity_name}\nCurrent: {format_activity_value(current_value, activity_type)}\nEnter new time (HH:MM:SS), press 'Skip' to keep current, or 'Cancel' to abort:", reply_markup=keyboard)
            else:
                bot.reply_to(message, f"Updating: {activity_name}\nCurrent: {current_value} reps\nEnter new number of reps, press 'Skip' to keep current, or 'Cancel' to abort:", reply_markup=keyboard)
            bot.register_next_step_handler(message, process_update_activity_value, activity_id, activity_type, current_value, created_at)
        except ValueError as e:
            log_error(f"Error in process_update_activity_choice: {str(e)}")
            bot.reply_to(message, INVALID_ACTIVITY_SELECTION_MESSAGE)
            return update_activity(message)
        except Exception as e:
            log_error(f"Error in process_update_activity_choice: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    def process_update_activity_value(message: Message, activity_id, activity_type, current_value, created_at):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_value = message.text.strip()
        telegram_id = message.from_user.id
        
        if new_value.lower() == "cancel":
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        elif new_value.lower() == "skip":
            new_value = current_value
        else:
            try:
                new_value = parse_activity_value(new_value, activity_type)
            except ValueError as e:
                log_error(f"Error in process_update_activity_value: {str(e)}")
                bot.reply_to(message, INVALID_INPUT_MESSAGE)
                keyboard = ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                keyboard.add("Skip", "Cancel")
                if activity_type == 'time':
                    bot.reply_to(message, "Enter valid time (HH:MM:SS), press 'Skip' to keep current, or 'Cancel' to abort:", reply_markup=keyboard)
                else:
                    bot.reply_to(message, "Enter valid number of reps, press 'Skip' to keep current, or 'Cancel' to abort:", reply_markup=keyboard)
                return bot.register_next_step_handler(message, process_update_activity_value, activity_id, activity_type, current_value, created_at)
        
        # Move to updating the datetime
        keyboard = ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
        keyboard.add("Skip", "Cancel")
        bot.reply_to(message, "Enter new date and time (YYYY-MM-DD HH:MM:SS), press 'Skip' to keep current, or 'Cancel' to abort:", reply_markup=keyboard)
        bot.register_next_step_handler(message, process_update_activity_datetime, activity_id, activity_type, new_value, created_at)

    def process_update_activity_datetime(message: Message, activity_id, activity_type, new_value, current_datetime):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_datetime_str = message.text.strip()
        telegram_id = message.from_user.id
        
        if new_datetime_str.lower() == "cancel":
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        elif new_datetime_str.lower() == "skip":
            new_datetime = current_datetime  # Keep the original datetime            
        else:
            try:
                new_datetime = datetime.strptime(new_datetime_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                log_error(f"Error parsing datetime: {new_datetime_str}")
                bot.reply_to(message, "Invalid date format. Please use YYYY-MM-DD HH:MM:SS.")
                return bot.register_next_step_handler(message, process_update_activity_datetime, activity_id, activity_type, new_value, current_datetime)
        
        try:
            user = db.get_user(telegram_id)
            success = db.update_activity(activity_id, user[0], new_value, new_datetime)
            
            if success:
                value_str = format_activity_value(new_value, activity_type)
                localized_datetime = new_datetime.astimezone(NICOSIA_TIMEZONE)
                date_str = localized_datetime.strftime('%Y-%m-%d %H:%M:%S')
                update_message = f"Updated: Value: {value_str}, Date/Time: {date_str}"
                log_info(f"Activity updated successfully: {update_message}")
                bot.reply_to(message, update_message, reply_markup=ReplyKeyboardRemove())
            else:
                log_error(f"Failed to update activity. activity_id: {activity_id}, user_id: {user[0]}, new_value: {new_value}, new_datetime: {new_datetime}")
                bot.reply_to(message, FAILED_TO_UPDATE_ACTIVITY_MESSAGE, reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            log_error(f"Error in process_update_activity_datetime: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE, reply_markup=ReplyKeyboardRemove())

    @bot.message_handler(commands=['delete'])
    def delete_activity(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_recent_activities(user[0], limit=10)  # Get last 5 activities
            
            if activities:
                keyboard = ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True, resize_keyboard=True)
                for activity in activities:
                    activity_id, activity_name, value, activity_type, created_at = activity
                    value_str = format_activity_value(value, activity_type)
                    nicosia_time = created_at.astimezone(NICOSIA_TIMEZONE)
                    date_str = nicosia_time.strftime('%b %d %H:%M')
                    keyboard.add(f"{activity_id}: {activity_name}: {value_str} | {date_str}")
                keyboard.add("Cancel")
                bot.reply_to(message, "Choose an activity to delete:", reply_markup=keyboard)
                bot.register_next_step_handler(message, process_delete_activity_choice, activities)
            else:
                bot.reply_to(message, NO_ACTIVITIES_MESSAGE)
        except Exception as e:
            log_error(f"Error in delete_activity: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    def process_delete_activity_choice(message: Message, activities):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        choice = message.text.strip()
        if choice == "Cancel":
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        
        try:
            activity_id = int(choice.split(":")[0])
            chosen_activity = next((act for act in activities if act[0] == activity_id), None)
            
            if not chosen_activity:
                raise ValueError(INVALID_ACTIVITY_SELECTION_MESSAGE)
            
            activity_id, activity_name, value, activity_type, created_at = chosen_activity
            
            # Ask for confirmation
            keyboard = ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
            keyboard.add("Yes", "No")
            bot.reply_to(message, f"Are you sure you want to delete the activity '{activity_name}'?", reply_markup=keyboard)
            bot.register_next_step_handler(message, confirm_delete_activity, activity_id, activity_name)
        except ValueError as e:
            log_error(f"Error in process_delete_activity_choice: {str(e)}")
            bot.reply_to(message, INVALID_ACTIVITY_SELECTION_MESSAGE)
            return delete_activity(message)
        except Exception as e:
            log_error(f"Error in process_delete_activity_choice: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    def confirm_delete_activity(message: Message, activity_id: int, activity_name: str):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        confirmation = message.text.strip().lower()
        if confirmation == 'yes':
            try:
                log_info(f"Attempting to delete activity {activity_id} for user {message.from_user.id}")
                user = db.get_user(message.from_user.id)
                success = db.delete_activity(activity_id, user[0])
                if success:
                    log_info(f"Successfully deleted activity {activity_id} for user {message.from_user.id}")
                    bot.reply_to(message, f"Activity '{activity_name}' has been deleted successfully!", reply_markup=ReplyKeyboardRemove())
                else:
                    log_error(f"Failed to delete activity {activity_id} for user {message.from_user.id}")
                    bot.reply_to(message, FAILED_TO_DELETE_ACTIVITY_MESSAGE, reply_markup=ReplyKeyboardRemove())
            except Exception as e:
                log_error(f"Error in confirm_delete_activity: {str(e)}")
                bot.reply_to(message, GENERAL_ERROR_MESSAGE, reply_markup=ReplyKeyboardRemove())
        else:
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())

    @bot.message_handler(commands=['list'])
    def list_activities(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_recent_activities(user[0], limit=10)  # Get recent activities
            
            if activities:
                table_data = []
                headers = ["Activity", "Value", "Date"]
                
                for activity in activities:
                    try:
                        activity_id, activity_name, value, activity_type, created_at = activity
                        value_str = format_activity_value(value, activity_type)
                        nicosia_time = created_at.astimezone(NICOSIA_TIMEZONE)
                        date_str = nicosia_time.strftime('%b %d %H:%M')
                        
                        table_data.append([activity_name, value_str, date_str])
                    except Exception as e:
                        log_error(f"Error formatting activity {activity[0]}: {str(e)}")
                
                table = tabulate(table_data, headers=headers, tablefmt="pipe")
                response = "Recent activities:\n\n" + table
            else:
                response = "No activities logged yet."
            
            bot.reply_to(message, f"```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            log_error(f"Error in list_activities: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

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
            activity_streaks = db.get_activity_streaks(user[0])

            log_info(f"Total activities: {total_activities}")
            log_info(f"Unique activities: {unique_activities}")
            log_info(f"Most frequent activity: {most_frequent}")
            log_info(f"All activities: {activities}")
            log_info(f"Activity streaks: {activity_streaks}")

            # Calculate totals
            activity_totals, total_reps, total_duration = calculate_activity_totals(activities)

            # Format the response
            stats_message = format_stats_message(total_activities, unique_activities, most_frequent, 
                                                 total_reps, total_duration, activity_totals, activity_streaks)

            bot.reply_to(message, stats_message)
            log_info(f"Stats retrieved for user {telegram_id}")
        except Exception as e:
            log_error(f"Error in get_stats for user {telegram_id}: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

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

    def format_stats_message(total_activities, unique_activities, most_frequent, total_reps, total_duration, activity_totals, activity_streaks):
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
                stats_message += f"  Total duration: {format_duration(totals['time'])}\n"
            
            # Add streak information with correct grammatical agreement
            streak = next((s for s in activity_streaks if s[3] == activity), None)
            if streak:
                days = streak[4]
                if days == 1:
                    streak_text = "1 day"
                else:
                    streak_text = f"{days} days"
                stats_message += f"  Current streak: {streak_text}\n"
            
            last_activity = db.get_last_activity(activity)
            if last_activity:
                nicosia_time = last_activity[2].astimezone(NICOSIA_TIMEZONE)
                stats_message += f"  Last performed: {nicosia_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            stats_message += "\n"
        
        return stats_message

    @bot.message_handler(commands=['addref'])
    def add_reference_activity(message: Message):
        try:
            if check_maintenance(message, bot):
                return
            bot.reply_to(message, "Please enter the name of an activity:")
            bot.register_next_step_handler(message, process_add_reference_activity_name)
            log_info(f"Started add reference activity process for user {message.from_user.id}")
        except Exception as e:
            log_error(f"Error in add_reference_activity: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    def process_add_reference_activity_name(message: Message):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        activity_name = message.text.strip()
        
        # Create a keyboard with two buttons: "Reps" and "Time"
        keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        keyboard.add(KeyboardButton("Reps"), KeyboardButton("Time"))
        
        bot.send_message(message.chat.id, "Please select the type of the reference activity:", reply_markup=keyboard)
        bot.register_next_step_handler(message, process_add_reference_activity_type, activity_name)

        # Log the action for debugging
        log_info(f"Sent keyboard for activity type selection to user {message.from_user.id}")

    def process_add_reference_activity_type(message: Message, activity_name):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        activity_type = message.text.strip().lower()
        if activity_type not in ['reps', 'time']:
            bot.reply_to(message, "Invalid activity type. Please select either 'Reps' or 'Time'.")
            log_error(f"Invalid activity type '{activity_type}' selected by user {message.from_user.id}")
            return process_add_reference_activity_name(message)
        
        try:
            user = db.get_user(message.from_user.id)
            db.add_reference_activity(user[0], activity_name, activity_type)
            bot.reply_to(message, f"Reference activity '{activity_name}' ({activity_type}) added successfully!", reply_markup=ReplyKeyboardRemove())
            log_info(f"Reference activity '{activity_name}' ({activity_type}) added successfully by user {message.from_user.id}")
        except Exception as e:
            error_message = f"Error in process_add_reference_activity_type for user {message.from_user.id}: {str(e)}"
            log_error(error_message)
            bot.reply_to(message, GENERAL_ERROR_MESSAGE, reply_markup=ReplyKeyboardRemove())

    @bot.message_handler(commands=['listref'])
    def list_reference_activities(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            activities = db.get_reference_activities(user[0])
            
            if activities:
                table_data = []
                headers = ["ID", "Activity", "Type"]
                
                for activity in activities:
                    activity_id, activity_name, activity_type = activity
                    table_data.append([activity_id, activity_name, activity_type])
                
                table = tabulate(table_data, headers=headers, tablefmt="pipe")
                response = "Your reference activities:\n\n" + table
            else:
                response = "You haven't added any reference activities yet."
            
            bot.reply_to(message, f"```\n{response}\n```", parse_mode='MarkdownV2')
        except Exception as e:
            log_error(f"Error in list_reference_activities: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    @bot.message_handler(commands=['updateref'])
    def update_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            reference_activities = db.get_reference_activities_without_activities(user[0])  # Get all reference activities
            
            if reference_activities:
                keyboard = ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True, resize_keyboard=True)
                for reference_activity in reference_activities:
                    activity_id, activity_name, activity_type = reference_activity
                    keyboard.add(f"{activity_id}: {activity_name} ({activity_type})")
                keyboard.add("Cancel")
                bot.reply_to(message, "Choose a reference activity to update or press 'Cancel' to exit:", reply_markup=keyboard)
                bot.register_next_step_handler(message, process_update_reference_activity_choice, reference_activities)
            else:
                bot.reply_to(message, "You don't have any reference activities to update.")
        except Exception as e:
            log_error(f"Error in update_reference_activity: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    def process_update_reference_activity_choice(message: Message, reference_activities):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        choice = message.text.strip()
        if choice.lower() == "cancel":
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        
        try:
            activity_id = int(choice.split(":")[0])
            reference_activity = next((act for act in reference_activities if act[0] == activity_id), None)
            
            if not reference_activity:
                raise ValueError(INVALID_ACTIVITY_SELECTION_MESSAGE)
            
            activity_id, current_name, current_type = reference_activity
            
            keyboard = ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
            keyboard.add("Skip", "Cancel")
            bot.reply_to(message, f"Updating reference activity: {current_name}\nCurrent type: {current_type}\nEnter new name, press 'Skip' to keep current, or 'Cancel' to exit:", reply_markup=keyboard)
            bot.register_next_step_handler(message, process_update_reference_activity_name, activity_id, current_name, current_type)
        except Exception as e:
            log_error(f"Error in process_update_reference_activity_choice: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)
            return update_reference_activity(message)

    def process_update_reference_activity_name(message: Message, activity_id, current_name, current_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_name = message.text.strip()
        if new_name.lower() == 'cancel':
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        if new_name.lower() == 'skip':
            new_name = current_name
        
        keyboard = ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
        keyboard.add("Time", "Reps", "Skip", "Cancel")
        bot.reply_to(message, f"Current type: {current_type}\nSelect new type, press 'Skip' to keep current, or 'Cancel' to exit:", reply_markup=keyboard)
        bot.register_next_step_handler(message, process_update_reference_activity_type, activity_id, new_name, current_type)

    def process_update_reference_activity_type(message: Message, activity_id, new_name, current_type):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        new_type = message.text.strip().lower()
        if new_type == 'cancel':
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        if new_type not in ['time', 'reps', 'skip']:
            bot.reply_to(message, "Invalid type. Please select either 'time', 'reps', 'Skip' to keep the current type, or 'Cancel' to exit.")
            return process_update_reference_activity_name(message, activity_id, new_name, current_type)
        
        if new_type == 'skip':
            new_type = current_type
        
        telegram_id = message.from_user.id
        try:
            user = db.get_user(telegram_id)
            success = db.update_reference_activity(activity_id, user[0], new_name, new_type)
            if success:
                bot.reply_to(message, f"Updated: {new_name}\nNew type: {new_type}", reply_markup=ReplyKeyboardRemove())
            else:
                bot.reply_to(message, FAILED_TO_UPDATE_ACTIVITY_MESSAGE, reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            log_error(f"Error in process_update_reference_activity_type: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    @bot.message_handler(commands=['deleteref'])
    def delete_reference_activity(message: Message):
        if check_maintenance(message, bot):
            return
        telegram_id = message.from_user.id
        
        try:
            user = db.get_user(telegram_id)
            reference_activities = db.get_reference_activities_without_activities(user[0])  # Get all reference activities
            
            if reference_activities:
                keyboard = ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True, resize_keyboard=True)
                for activity in reference_activities:
                    activity_id, activity_name, activity_type = activity
                    keyboard.add(f"{activity_name} ({activity_type})")
                keyboard.add("Cancel")
                bot.reply_to(message, "Choose a reference activity to delete:", reply_markup=keyboard)
                bot.register_next_step_handler(message, process_delete_reference_activity_choice, reference_activities)
            else:
                bot.reply_to(message, "You don't have any recent reference activities to delete.")
        except Exception as e:
            log_error(f"Error in delete_reference_activity: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    def process_delete_reference_activity_choice(message: Message, reference_activities):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        choice = message.text.strip()
        if choice.lower() == "cancel":
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return
        
        try:
            activity_name, activity_type = choice.split(" (")
            activity_type = activity_type.rstrip(")")
            reference_activity = next((act for act in reference_activities if act[1] == activity_name and act[2] == activity_type), None)
            
            if not reference_activity:
                raise ValueError(INVALID_ACTIVITY_SELECTION_MESSAGE)
            
            activity_id, activity_name, activity_type = reference_activity
            
            activity_count = db.get_activity_count_for_reference(activity_id, message.from_user.id)
            
            if activity_count > 0:
                keyboard = ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
                keyboard.add("Yes", "No")
                bot.reply_to(message, 
                             f"Warning: The reference activity '{activity_name}' has {activity_count} recorded activities. "
                             f"Deleting this reference will also delete all associated activities. "
                             f"Are you sure you want to proceed?",
                             reply_markup=keyboard)
                bot.register_next_step_handler(message, process_delete_reference_activity_confirm, activity_id)
            else:
                process_delete_reference_activity(message, activity_id)
        except Exception as e:
            log_error(f"Error in process_delete_reference_activity_choice: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)
            return delete_reference_activity(message)

    def process_delete_reference_activity_confirm(message: Message, activity_id):
        if check_maintenance(message, bot):
            return
        if check_exit(message, bot):
            return
        
        confirmation = message.text.strip().lower()
        if confirmation == 'yes':
            process_delete_reference_activity(message, activity_id)
        else:
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())

    def process_delete_reference_activity(message: Message, activity_id):
        try:
            telegram_id = message.from_user.id
            user = db.get_user(telegram_id)
            success = db.delete_reference_activity(activity_id, user[0])
            if success:
                bot.reply_to(message, f"Reference activity with ID {activity_id} has been deleted successfully!", reply_markup=ReplyKeyboardRemove())
            else:
                bot.reply_to(message, FAILED_TO_DELETE_ACTIVITY_MESSAGE, reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            log_error(f"Error in process_delete_reference_activity: {str(e)}")
            bot.reply_to(message, GENERAL_ERROR_MESSAGE)

    @bot.message_handler(commands=['exit'])
    def exit_command(message: Message):
        bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())

    def check_exit(message: Message, bot: TeleBot):
        if message.text.strip().lower() == '/exit':
            bot.reply_to(message, OPERATION_CANCELLED_MESSAGE, reply_markup=ReplyKeyboardRemove())
            return True
        return False
