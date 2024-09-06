from unittest.mock import patch
from tasks import send_daily_reminder, update_streaks

@patch('tasks.bot.send_message')
def test_send_daily_reminder(mock_send_message):
    send_daily_reminder()
    mock_send_message.assert_called()  # Check if bot.send_message was called

@patch('tasks.get_connection')
def test_update_streaks(mock_get_connection):
    update_streaks()
    mock_get_connection.assert_called()  # Check if database connection was established