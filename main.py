from bot_handlers import create_bot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    bot = create_bot()
    logger.info("Bot started. Polling for updates...")
    bot.polling(none_stop=True)