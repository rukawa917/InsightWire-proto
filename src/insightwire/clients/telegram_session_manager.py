"""
Thread-safe Telegram session manager that runs in its own dedicated thread.
This avoids event loop conflicts with Streamlit and other frameworks.
"""

import asyncio
import threading
import queue
import os
import logging
from typing import List, Dict, Any, Optional, Callable, Union, Tuple, TypeVar
import pandas as pd
from telethon import TelegramClient
from telethon.tl.types import Channel, Dialog
from telethon.sessions import SQLiteSession, StringSession
from filelock import FileLock

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('telegram_session_manager')

# Type variables for better type hinting
T = TypeVar('T')
CommandResult = TypeVar('CommandResult')


class TelegramSessionError(Exception):
    """Base exception for all telegram session errors"""
    pass


class ClientNotConnectedError(TelegramSessionError):
    """Raised when trying to use a client that is not connected"""
    pass


class AuthenticationError(TelegramSessionError):
    """Raised when authentication fails"""
    pass


class CommandExecutionError(TelegramSessionError):
    """Raised when a command execution fails"""
    def __init__(self, command: str, original_error: Exception):
        self.command = command
        self.original_error = original_error
        super().__init__(f"Error executing command '{command}': {original_error}")


class TelegramClientWrapper:
    """
    Wrapper around Telethon's TelegramClient that handles session management
    and provides a simplified interface for common operations.
    """
    
    def __init__(self, session_path: str, api_id: str, api_hash: str, loop: asyncio.AbstractEventLoop):
        """
        Initialize the client wrapper.
        
        Args:
            session_path: Path to the session file
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            loop: Asyncio event loop to use
        """
        self.session_path = session_path
        self.api_id = api_id
        self.api_hash = api_hash
        self.loop = loop
        self.client = TelegramClient(session_path, api_id, api_hash, loop=loop)
        self.lock: Optional[FileLock] = None
        
    async def connect(self) -> bool:
        """
        Connect to Telegram.
        
        Returns:
            bool: True if connection was successful
        """
        try:
            return await self.client.connect()
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise CommandExecutionError("connect", e)
            
    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        try:
            await self.client.disconnect()
        except Exception as e:
            logger.error(f"Failed to disconnect: {e}")
            raise CommandExecutionError("disconnect", e)
            
    async def is_authorized(self) -> bool:
        """
        Check if the user is authorized.
        
        Returns:
            bool: True if the user is authorized
        """
        try:
            return await self.client.is_user_authorized()
        except Exception as e:
            logger.error(f"Failed to check authorization: {e}")
            raise CommandExecutionError("is_authorized", e)
            
    async def send_code_request(self, phone: str) -> bool:
        """
        Send a code request to the given phone number.
        
        Args:
            phone: Phone number to send the code to
            
        Returns:
            bool: True if the code was sent successfully
        """
        try:
            await self.client.send_code_request(phone)
            return True
        except Exception as e:
            logger.error(f"Failed to send code request: {e}")
            raise CommandExecutionError("send_code_request", e)
            
    async def sign_in(self, phone: str, code: str) -> bool:
        """
        Sign in with the given phone number and code.
        
        Args:
            phone: Phone number
            code: Verification code
            
        Returns:
            bool: True if sign in was successful
        """
        try:
            await self.client.sign_in(phone, code)
            return True
        except Exception as e:
            logger.error(f"Failed to sign in: {e}")
            raise CommandExecutionError("sign_in", e)
            
    async def get_dialogs(self) -> List[Dialog]:
        """
        Get all dialogs.
        
        Returns:
            List[Dialog]: List of dialogs
        """
        try:
            return await self.client.get_dialogs()
        except Exception as e:
            logger.error(f"Failed to get dialogs: {e}")
            raise CommandExecutionError("get_dialogs", e)
            
    async def get_messages(self, dialog: Dialog, limit: int = 100):
        """
        Get messages from a dialog.
        
        Args:
            dialog: Dialog to get messages from
            limit: Maximum number of messages to get
            
        Returns:
            List of messages
        """
        try:
            return await self.client.get_messages(dialog, limit=limit)
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            raise CommandExecutionError("get_messages", e)


class CommandProcessor:
    """
    Processes commands in a separate thread with its own event loop.
    """
    
    def __init__(self, command_queue: queue.Queue, result_queue: queue.Queue):
        """
        Initialize the command processor.
        
        Args:
            command_queue: Queue for receiving commands
            result_queue: Queue for sending results
        """
        self.command_queue = command_queue
        self.result_queue = result_queue
        self.client: Optional[TelegramClientWrapper] = None
        self.running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
    def start(self) -> None:
        """Start the command processor."""
        self.running = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def stop(self) -> None:
        """Stop the command processor."""
        self.running = False
        if self.client:
            try:
                self.loop.run_until_complete(self.client.disconnect())
            except Exception as e:
                logger.error(f"Error disconnecting client during stop: {e}")
                
        if self.client and self.client.lock and self.client.lock.is_locked:
            self.client.lock.release()
            
        if self.loop:
            self.loop.close()
            
    def process_command(self, command: str, args: Any) -> Any:
        """
        Process a command.
        
        Args:
            command: Command to process
            args: Arguments for the command
            
        Returns:
            Result of the command
        """
        try:
            if command == "stop":
                return self._handle_stop()
            elif command == "connect":
                return self._handle_connect(args)
            elif command == "is_authorized":
                return self._handle_is_authorized()
            elif command == "send_code":
                return self._handle_send_code(args)
            elif command == "sign_in":
                return self._handle_sign_in(args)
            elif command == "get_channels":
                return self._handle_get_channels()
            elif command == "get_channel_data":
                return self._handle_get_channel_data(args)
            elif command == "disconnect":
                return self._handle_disconnect()
            else:
                logger.warning(f"Unknown command: {command}")
                return None
        except Exception as e:
            logger.error(f"Error processing command {command}: {e}")
            return None
            
    def _handle_stop(self) -> bool:
        """Handle the stop command."""
        self.stop()
        return True
        
    def _handle_connect(self, args: Tuple[str, str, str, str]) -> bool:
        """
        Handle the connect command.
        
        Args:
            args: Tuple of (session_dir, api_id, api_hash, phone)
            
        Returns:
            bool: True if connection was successful
        """
        session_dir, api_id, api_hash, phone = args
        
        # Create session directory if it doesn't exist
        os.makedirs(os.path.dirname(session_dir), exist_ok=True)
        
        # Set up file lock for this session
        lock_file = f"{session_dir}.lock"
        lock = FileLock(lock_file, timeout=30)  # 30 second timeout
        
        try:
            # Acquire lock before accessing session
            lock.acquire()
            
            # Create a new client with this thread's event loop
            self.client = TelegramClientWrapper(session_dir, api_id, api_hash, self.loop)
            self.client.lock = lock
            
            result = self.loop.run_until_complete(self.client.connect())
            return result
        except Exception as e:
            logger.error(f"Connection error: {e}")
            # Release lock on error
            if lock and lock.is_locked:
                lock.release()
            return False
            
    def _handle_is_authorized(self) -> bool:
        """
        Handle the is_authorized command.
        
        Returns:
            bool: True if the user is authorized
        """
        if not self.client:
            return False
            
        try:
            return self.loop.run_until_complete(self.client.is_authorized())
        except Exception as e:
            logger.error(f"Authorization check error: {e}")
            return False
            
    def _handle_send_code(self, phone: str) -> bool:
        """
        Handle the send_code command.
        
        Args:
            phone: Phone number to send the code to
            
        Returns:
            bool: True if the code was sent successfully
        """
        if not self.client:
            return False
            
        try:
            return self.loop.run_until_complete(self.client.send_code_request(phone))
        except Exception as e:
            logger.error(f"Send code error: {e}")
            return False
            
    def _handle_sign_in(self, args: Tuple[str, str]) -> bool:
        """
        Handle the sign_in command.
        
        Args:
            args: Tuple of (phone, code)
            
        Returns:
            bool: True if sign in was successful
        """
        phone, code = args
        if not self.client:
            return False
            
        try:
            return self.loop.run_until_complete(self.client.sign_in(phone, code))
        except Exception as e:
            logger.error(f"Sign in error: {e}")
            return False
            
    def _handle_get_channels(self) -> List[str]:
        """
        Handle the get_channels command.
        
        Returns:
            List[str]: List of channel names
        """
        if not self.client or not self.loop.run_until_complete(self.client.is_authorized()):
            return []
            
        try:
            # Get all dialogs and filter channels
            channels = []
            dialogs = self.loop.run_until_complete(self.client.get_dialogs())
            for dialog in dialogs:
                if isinstance(dialog.entity, Channel):
                    channels.append(dialog.name)
            return channels
        except Exception as e:
            logger.error(f"Get channels error: {e}")
            return []
            
    def _handle_get_channel_data(self, args: Tuple[List[str], int]) -> pd.DataFrame:
        """
        Handle the get_channel_data command.
        
        Args:
            args: Tuple of (target_channels, limit)
            
        Returns:
            pd.DataFrame: DataFrame with channel data
        """
        target_channels, limit = args
        if not self.client or not self.loop.run_until_complete(self.client.is_authorized()):
            return pd.DataFrame()
            
        try:
            data = []
            dialogs = self.loop.run_until_complete(self.client.get_dialogs())
            for dialog in dialogs:
                if dialog.name in target_channels:
                    # One message request at a time
                    msgs = self.loop.run_until_complete(self.client.get_messages(dialog, limit=limit))
                    for message in msgs:
                        text = message.text.strip() if message.text else ""
                        if text == "":
                            continue
                        data.append({
                            "channel": dialog.name,
                            "date": message.date,
                            "text": text,
                            "views": message.views,
                        })
            return pd.DataFrame(data)
        except Exception as e:
            logger.error(f"Get channel data error: {e}")
            return pd.DataFrame()
            
    def _handle_disconnect(self) -> bool:
        """
        Handle the disconnect command.
        
        Returns:
            bool: True if disconnection was successful
        """
        if not self.client:
            return True
            
        try:
            self.loop.run_until_complete(self.client.disconnect())
            # Release the lock
            if self.client.lock and self.client.lock.is_locked:
                self.client.lock.release()
            self.client = None
            return True
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return False


class TelegramSessionManager:
    """
    Thread-safe Telegram session manager that runs in its own dedicated thread.
    This avoids event loop conflicts with Streamlit and other frameworks.
    """
    
    def __init__(self):
        """Initialize the session manager."""
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.processor: Optional[CommandProcessor] = None
        
    def start(self) -> None:
        """Start the session manager thread."""
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._run_manager)
            self.thread.daemon = True
            self.thread.start()
            
    def stop(self) -> None:
        """Stop the session manager thread."""
        if self.thread and self.thread.is_alive():
            self.running = False
            self.command_queue.put(("stop", None))
            self.thread.join(timeout=5)
            
    def _run_manager(self) -> None:
        """Main thread function that runs the event loop."""
        self.processor = CommandProcessor(self.command_queue, self.result_queue)
        self.processor.start()
        
        while self.running:
            try:
                # Get the next command with timeout
                command, args = self.command_queue.get(timeout=0.1)
                
                # Process the command
                result = self.processor.process_command(command, args)
                self.result_queue.put(result)
                
            except queue.Empty:
                # No commands in queue, continue
                pass
            except Exception as e:
                logger.error(f"Error in telegram session manager: {e}")
                self.result_queue.put(None)
                
        # Clean up
        if self.processor:
            self.processor.stop()
            
    def _execute_command(self, command: str, args: Any = None) -> Any:
        """
        Send a command to the thread and wait for the result.
        
        Args:
            command: Command to execute
            args: Arguments for the command
            
        Returns:
            Result of the command
        """
        if not self.running:
            self.start()
        self.command_queue.put((command, args))
        return self.result_queue.get()
    
    # Public API methods
    def connect(self, session_dir: str, api_id: str, api_hash: str, phone: str) -> bool:
        """
        Connect to Telegram.
        
        Args:
            session_dir: Directory to store the session file
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone: Phone number
            
        Returns:
            bool: True if connection was successful
        """
        # Make sure session directory is a full path
        if not os.path.isabs(session_dir):
            session_dir = os.path.abspath(os.path.join('sessions', session_dir))
        return self._execute_command("connect", (session_dir, api_id, api_hash, phone))
    
    def is_authorized(self) -> bool:
        """
        Check if user is authorized.
        
        Returns:
            bool: True if the user is authorized
        """
        return self._execute_command("is_authorized")
    
    def send_code_request(self, phone: str) -> bool:
        """
        Request verification code.
        
        Args:
            phone: Phone number to send the code to
            
        Returns:
            bool: True if the code was sent successfully
        """
        return self._execute_command("send_code", phone)
    
    def sign_in(self, phone: str, code: str) -> bool:
        """
        Sign in with verification code.
        
        Args:
            phone: Phone number
            code: Verification code
            
        Returns:
            bool: True if sign in was successful
        """
        return self._execute_command("sign_in", (phone, code))
    
    def get_channels(self) -> List[str]:
        """
        Get list of available channels.
        
        Returns:
            List[str]: List of channel names
        """
        return self._execute_command("get_channels")
    
    def get_channel_data(self, target_channels: List[str], limit: int = 100) -> pd.DataFrame:
        """
        Get data from channels.
        
        Args:
            target_channels: List of channel names to get data from
            limit: Maximum number of messages to get per channel
            
        Returns:
            pd.DataFrame: DataFrame with channel data
        """
        return self._execute_command("get_channel_data", (target_channels, limit))
    
    def disconnect(self) -> bool:
        """
        Disconnect the client.
        
        Returns:
            bool: True if disconnection was successful
        """
        return self._execute_command("disconnect")


# Create a singleton instance
telegram_manager = TelegramSessionManager()
