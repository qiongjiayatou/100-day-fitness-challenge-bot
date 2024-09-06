import telebot
import time
from config import BOT_TOKEN
from bot_handlers import register_handlers
from database import init_db
# from utils import authenticate_user


def main():
    init_db()

    bot = telebot.TeleBot(BOT_TOKEN)
    register_handlers(bot)
    # Start the bot polling
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()