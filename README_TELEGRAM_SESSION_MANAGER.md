# Telegram Session Manager Refactoring

## Overview

The Telegram Session Manager has been refactored to improve code organization, error handling, and maintainability. This document explains the changes made and the new structure.

## Key Changes

1. **Separation of Concerns**
   - Split the monolithic class into three distinct classes:
     - `TelegramSessionManager`: Main class that orchestrates everything
     - `TelegramClientWrapper`: Wraps the Telethon client and provides a simplified interface
     - `CommandProcessor`: Handles command execution in the thread

2. **Improved Error Handling**
   - Added custom exceptions for better error handling:
     - `TelegramSessionError`: Base exception for all telegram session errors
     - `ClientNotConnectedError`: Raised when trying to use a client that is not connected
     - `AuthenticationError`: Raised when authentication fails
     - `CommandExecutionError`: Raised when a command execution fails

3. **Better Logging**
   - Replaced print statements with proper logging
   - Added more detailed error messages

4. **Enhanced Type Hints and Documentation**
   - Added comprehensive type hints for better IDE support and code understanding
   - Improved docstrings with parameter and return type descriptions

5. **Reduced Code Duplication**
   - Extracted common patterns into reusable methods
   - Centralized error handling

6. **Added Unit Tests**
   - Created a test suite to verify the functionality of the refactored code

## Class Structure

### TelegramSessionManager

The main class that provides the public API for interacting with Telegram. It manages the thread and delegates commands to the CommandProcessor.

```python
class TelegramSessionManager:
    def __init__(self)
    def start(self) -> None
    def stop(self) -> None
    def _run_manager(self) -> None
    def _execute_command(self, command: str, args: Any = None) -> Any
    
    # Public API methods
    def connect(self, session_dir: str, api_id: str, api_hash: str, phone: str) -> bool
    def is_authorized(self) -> bool
    def send_code_request(self, phone: str) -> bool
    def sign_in(self, phone: str, code: str) -> bool
    def get_channels(self) -> List[str]
    def get_channel_data(self, target_channels: List[str], limit: int = 100) -> pd.DataFrame
    def disconnect(self) -> bool
```

### TelegramClientWrapper

Wraps the Telethon client and provides a simplified interface for common operations.

```python
class TelegramClientWrapper:
    def __init__(self, session_path: str, api_id: str, api_hash: str, loop: asyncio.AbstractEventLoop)
    async def connect(self) -> bool
    async def disconnect(self) -> None
    async def is_authorized(self) -> bool
    async def send_code_request(self, phone: str) -> bool
    async def sign_in(self, phone: str, code: str) -> bool
    async def get_dialogs(self) -> List[Dialog]
    async def get_messages(self, dialog: Dialog, limit: int = 100)
```

### CommandProcessor

Processes commands in a separate thread with its own event loop.

```python
class CommandProcessor:
    def __init__(self, command_queue: queue.Queue, result_queue: queue.Queue)
    def start(self) -> None
    def stop(self) -> None
    def process_command(self, command: str, args: Any) -> Any
    
    # Command handlers
    def _handle_stop(self) -> bool
    def _handle_connect(self, args: Tuple[str, str, str, str]) -> bool
    def _handle_is_authorized(self) -> bool
    def _handle_send_code(self, phone: str) -> bool
    def _handle_sign_in(self, args: Tuple[str, str]) -> bool
    def _handle_get_channels(self) -> List[str]
    def _handle_get_channel_data(self, args: Tuple[List[str], int]) -> pd.DataFrame
    def _handle_disconnect(self) -> bool
```

## Usage

The usage of the Telegram Session Manager remains the same as before. The refactoring was done in a way that maintains backward compatibility with existing code.

```python
from insightwire.clients.telegram_session_manager import telegram_manager

# Start the manager
telegram_manager.start()

# Connect to Telegram
telegram_manager.connect(session_dir, api_id, api_hash, phone)

# Check if authorized
if telegram_manager.is_authorized():
    # Get channels
    channels = telegram_manager.get_channels()
    
    # Get channel data
    data = telegram_manager.get_channel_data(channels, limit=100)
else:
    # Send code request
    telegram_manager.send_code_request(phone)
    
    # Sign in
    telegram_manager.sign_in(phone, code)

# Disconnect
telegram_manager.disconnect()

# Stop the manager
telegram_manager.stop()
```

## Testing

A test suite has been added to verify the functionality of the refactored code. The tests can be run with:

```bash
cd tests
python -m unittest test_telegram_session_manager.py
```

The tests use mocking to avoid the need for actual Telegram credentials.
