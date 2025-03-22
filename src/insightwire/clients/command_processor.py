import logging
import asyncio
import queue
from typing import Any, Tuple, List, Dict, Optional
import os
from filelock import FileLock

import pandas as pd
from telethon.tl.types import Channel

from insightwire.clients.telegram_client_wrapper import TelegramClientWrapper

logger = logging.getLogger('command_processor')
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
                logger.error("Error disconnecting client during stop: %s", e)
                
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
            elif command == "get_terms_of_service_update":
                return self._handle_get_terms_of_service_update()
            elif command == "accept_terms_of_service":
                return self._handle_accept_terms_of_service(args)
            elif command == "decline_terms_of_service":
                return self._handle_decline_terms_of_service(args)
            else:
                logger.warning("Unknown command: %s", command)
                return None
        except Exception as e:
            logger.error("Error processing command %s: %s", command, e)
            return None
    
    def _handle_get_terms_of_service_update(self) -> Dict[str, Any]:
        """
        Handle the get_terms_of_service_update command.
        
        Returns:
            Dict[str, Any]: Dictionary with terms of service update info
        """
        if not self.client:
            return None
        
        try:
            return self.loop.run_until_complete(self.client.get_terms_of_service_update())
        except Exception as e:
            logger.error("Terms of service update error: %s", e)
            return None
            
    def _handle_accept_terms_of_service(self, tos_id: str) -> bool:
        """
        Handle the accept_terms_of_service command.
        
        Args:
            tos_id: ID of the terms of service to accept
            
        Returns:
            bool: True if terms were accepted successfully
        """
        if not self.client:
            return False
        
        try:
            return self.loop.run_until_complete(self.client.accept_terms_of_service(tos_id))
        except Exception as e:
            logger.error("Accept terms of service error: %s", e)
            return False
            
    def _handle_decline_terms_of_service(self, tos_id: str) -> bool:
        """
        Handle the decline_terms_of_service command.
        
        Args:
            tos_id: ID of the terms of service to decline
            
        Returns:
            bool: True if account was deleted successfully
        """
        if not self.client:
            return False
        
        try:
            return self.loop.run_until_complete(self.client.decline_terms_of_service(tos_id))
        except Exception as e:
            logger.error("Decline terms of service error: %s", e)
            return False
            
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
            logger.error("Connection error: %s", e)
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
            logger.error("Authorization check error: %s", e)
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
            logger.error("Send code error: %s", e)
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
            logger.error("Sign in error: %s", e)
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
            logger.error("Get channels error: %s", e)
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
            logger.error("Disconnect error: %s", e)
            return False