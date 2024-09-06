# 100-Day Fitness Challenge Bot

This is a Telegram bot designed to help users achieve their fitness goals by completing daily challenges. The bot uses a combination of Telegram's Bot API, PostgreSQL, Redis, and Celery to manage user data, send daily reminders, and update streaks.

## Features

- **User Authentication:** Users can register and authenticate using a password.
- **Activity Tracking:** Users can add, update, delete, and list their activities.
- **Streak Management:** The bot keeps track of the user's streak for each activity.
- **Daily Reminders:** The bot sends daily reminders to users to complete their activities.

## Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/100-day-fitness-challenge-bot.git
cd 100-day-fitness-challenge-bot
```

2. Create a `.env` file in the project root directory and add the following environment variables:

   ```
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_PASSWORD=your_admin_password
   DB_NAME=your_database_name
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_HOST=postgres
   DB_PORT=5432
   REDIS_URL=redis://redis:6379/0
   ```

   Replace the placeholder values with your actual configuration.

3. Build and start the Docker containers:

   ```bash
   docker-compose up --build
   ```

   This command will build the Docker images and start the containers for the bot, PostgreSQL database, Redis, and Celery worker.

4. The bot should now be running and ready to use. You can interact with it through Telegram.

## Usage

1. Start a chat with your bot on Telegram.
2. Use the `/start` command to get an introduction to the bot.
3. Register using `/register <password>` or authenticate using `/auth <password>`.
4. Once authenticated, you can use commands like `/add`, `/update`, `/delete`, `/list`, and `/stats` to manage your activities.

## Development

To make changes to the bot:

1. Modify the code as needed.
2. Rebuild and restart the Docker containers:

   ```bash
   docker-compose down
   docker-compose up --build
   ```

3. For running tests:

   ```bash
   docker-compose run --rm bot pytest
   ```

