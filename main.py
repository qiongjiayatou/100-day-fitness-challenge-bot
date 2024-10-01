from bot_handlers import create_bot
from logger import log_error, log_info
import pytz
from datetime import datetime

if __name__ == "__main__":
    try:
        # Set the default timezone to Nicosia
        nicosia_tz = pytz.timezone('Europe/Nicosia')
        now = datetime.now(nicosia_tz)
        log_info(f"Starting the bot at {now}")
        
        bot = create_bot()
        bot.polling(none_stop=True)
    except Exception as e:
        log_error(f"An error occurred while running the bot: {str(e)}")