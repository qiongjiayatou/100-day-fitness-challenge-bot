from bot_handlers import create_bot
from logger import logger, log_error, log_info

if __name__ == "__main__":
    try:
        log_info("Starting the bot...")
        bot = create_bot()
        bot.polling(none_stop=True)
    except Exception as e:
        log_error(f"An error occurred while running the bot: {str(e)}")