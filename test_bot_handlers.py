import pytest
from unittest.mock import Mock, patch
from telebot import TeleBot
from telebot.types import Message, User, Chat, CallbackQuery
from bot_handlers import register_handlers, check_maintenance, is_authenticated

@pytest.fixture
def bot():
    bot = Mock(spec=TeleBot)
    bot.message_handler = Mock()
    bot.message_handler.side_effect = lambda **kwargs: lambda func: setattr(bot, f"handler_{kwargs.get('commands', [''])[0]}", func)
    with patch('bot_handlers.is_authenticated', lambda f: f):  # Mock is_authenticated globally
        register_handlers(bot)
    return bot

@pytest.fixture
def message():
    message = Mock(spec=Message)
    message.from_user = Mock(spec=User)
    message.from_user.id = 12345
    message.chat = Mock(spec=Chat)
    message.chat.id = 67890
    return message

@pytest.fixture
def mock_db_connection():
    with patch('bot_handlers.get_connection') as mock_conn:
        mock_cursor = Mock()
        mock_conn.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        yield mock_cursor

def find_handler(bot, command):
    return getattr(bot, f"handler_{command}", None)

@patch('bot_handlers.check_maintenance')
def test_start_command(mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    handler = find_handler(bot, 'start')
    assert handler is not None, "start command handler not found"
    handler(message)
    bot.reply_to.assert_called_once()
    assert "Welcome to the 100-Day Fitness Challenge Bot!" in bot.reply_to.call_args[0][1]

@patch('bot_handlers.check_maintenance')
def test_help_command(mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    handler = find_handler(bot, 'help')
    assert handler is not None, "help command handler not found"
    handler(message)
    bot.reply_to.assert_called_once()
    assert "Available commands:" in bot.reply_to.call_args[0][1]

@patch('bot_handlers.check_maintenance')
@patch('bot_handlers.register_user')
def test_register_command(mock_register_user, mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    mock_register_user.return_value = True
    message.text = "/register password123"
    handler = find_handler(bot, 'register')
    assert handler is not None, "register command handler not found"
    handler(message)
    mock_register_user.assert_called_once_with(12345, "password123")
    bot.reply_to.assert_called_once_with(message, "Registration successful! You are now authenticated.")

@patch('bot_handlers.check_maintenance')
@patch('bot_handlers.authenticate_user')
def test_auth_command(mock_authenticate_user, mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    mock_authenticate_user.return_value = True
    message.text = "/auth password123"
    handler = find_handler(bot, 'auth')
    assert handler is not None, "auth command handler not found"
    handler(message)
    mock_authenticate_user.assert_called_once_with(12345, "password123")
    bot.reply_to.assert_called_once_with(message, "Authentication successful!")

@patch('bot_handlers.check_maintenance')
@patch('bot_handlers.logout_user')
def test_logout_command(mock_logout_user, mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    mock_logout_user.return_value = True
    handler = find_handler(bot, 'logout')
    assert handler is not None, "logout command handler not found"
    handler(message)
    bot.reply_to.assert_called_once_with(message, "You have been successfully logged out.")

@patch('bot_handlers.check_maintenance')
@patch('bot_handlers.get_connection')
def test_add_activity_command(mock_get_connection, mock_check_maintenance, bot, message, mock_db_connection):
    mock_check_maintenance.return_value = False
    mock_db_connection.fetchall.return_value = [(1, "Running", "time")]
    handler = find_handler(bot, 'add')
    assert handler is not None, "add command handler not found"
    handler(message)
    bot.reply_to.assert_called_once()
    assert "Please choose an activity:" in bot.reply_to.call_args[0][1]

@patch('bot_handlers.check_maintenance')
def test_update_activity_command(mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    handler = find_handler(bot, 'update')
    assert handler is not None, "update command handler not found"
    handler(message)
    bot.reply_to.assert_called_once()
    assert "Please enter the activity ID and updated value" in bot.reply_to.call_args[0][1]

@patch('bot_handlers.check_maintenance')
def test_delete_activity_command(mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    handler = find_handler(bot, 'delete')
    assert handler is not None, "delete command handler not found"
    handler(message)
    bot.reply_to.assert_called_once_with(message, "Please enter the activity ID you want to delete:")

@patch('bot_handlers.check_maintenance')
@patch('bot_handlers.get_connection')
def test_list_activities_command(mock_get_connection, mock_check_maintenance, bot, message, mock_db_connection):
    mock_check_maintenance.return_value = False
    mock_db_connection.fetchall.return_value = []
    handler = find_handler(bot, 'list')
    assert handler is not None, "list command handler not found"
    handler(message)
    bot.reply_to.assert_called_once_with(message, "You haven't added any activities yet.")

@patch('bot_handlers.check_maintenance')
@patch('bot_handlers.get_connection')
def test_stats_command(mock_get_connection, mock_check_maintenance, bot, message, mock_db_connection):
    mock_check_maintenance.return_value = False
    mock_db_connection.fetchone.side_effect = [(1,), (0,), (0,), None]
    mock_db_connection.fetchall.return_value = []
    handler = find_handler(bot, 'stats')
    assert handler is not None, "stats command handler not found"
    handler(message)
    bot.reply_to.assert_called_once()
    assert "Your Fitness Challenge Statistics:" in bot.reply_to.call_args[0][1]

@patch('bot_handlers.check_maintenance')
def test_addref_command(mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    handler = find_handler(bot, 'addref')
    assert handler is not None, "addref command handler not found"
    handler(message)
    bot.reply_to.assert_called_once()
    assert "Please enter the name of the activity you want to add to your reference list" in bot.reply_to.call_args[0][1]

@patch('bot_handlers.check_maintenance')
@patch('bot_handlers.get_connection')
def test_listref_command(mock_get_connection, mock_check_maintenance, bot, message, mock_db_connection):
    mock_check_maintenance.return_value = False
    mock_db_connection.fetchall.return_value = []
    handler = find_handler(bot, 'listref')
    assert handler is not None, "listref command handler not found"
    handler(message)
    bot.reply_to.assert_called_once_with(message, "You haven't added any reference activities yet.")

@patch('bot_handlers.check_maintenance')
def test_updateref_command(mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    handler = find_handler(bot, 'updateref')
    assert handler is not None, "updateref command handler not found"
    handler(message)
    bot.reply_to.assert_called_once()
    assert "Please enter the ID of the reference activity you want to update:" in bot.reply_to.call_args[0][1]

@patch('bot_handlers.check_maintenance')
def test_deleteref_command(mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    handler = find_handler(bot, 'deleteref')
    assert handler is not None, "deleteref command handler not found"
    handler(message)
    bot.reply_to.assert_called_once_with(message, "Please enter the ID of the reference activity you want to delete:")

@patch('bot_handlers.check_maintenance')
@patch('bot_handlers.is_authenticated')
def test_addref_command(mock_is_authenticated, mock_check_maintenance, bot, message):
    mock_check_maintenance.return_value = False
    mock_is_authenticated.return_value = True
    bot.message_handler(commands=['addref'])(message)
    
    print(f"bot.reply_to.call_count: {bot.reply_to.call_count}")
    print(f"bot.reply_to.call_args: {bot.reply_to.call_args}")
    
    bot.reply_to.assert_called_once()
    assert "Please enter the name of the activity you want to add to your reference list" in bot.reply_to.call_args[0][1]