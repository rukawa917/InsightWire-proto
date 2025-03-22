"""
Thread-safe Telegram session manager that runs in its own dedicated thread.
This avoids event loop conflicts with Streamlit and other frameworks.
"""

import threading
import queue
import os
import logging
from typing import List, Dict, Any, Optional, TypeVar
import pandas as pd

from insightwire.clients.exec_errors import *
from insightwire.clients.telegram_client_wrapper import TelegramClientWrapper
from insightwire.clients.command_processor import CommandProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('telegram_session_manager')

# Type variables for better type hinting
T = TypeVar('T')
CommandResult = TypeVar('CommandResult')


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
                logger.error("Error in telegram session manager: %s", e)
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

    def get_terms_of_service_update(self) -> Dict[str, Any]:
        """
        Get the latest terms of service update.
        
        Returns:
            Dict[str, Any]: Dictionary with terms of service update info or None if no update
        """
        return self._execute_command("get_terms_of_service_update")
        
    def accept_terms_of_service(self, tos_id: str) -> bool:
        """
        Accept the terms of service.
        
        Args:
            tos_id: ID of the terms of service to accept
            
        Returns:
            bool: True if terms were accepted successfully
        """
        return self._execute_command("accept_terms_of_service", tos_id)
        
    def decline_terms_of_service(self, tos_id: str) -> bool:
        """
        Decline the terms of service by deleting the account.
        
        Args:
            tos_id: ID of the terms of service to decline
            
        Returns:
            bool: True if account was deleted successfully
        """
        return self._execute_command("decline_terms_of_service", tos_id)


# Create a singleton instance
telegram_manager = TelegramSessionManager()
