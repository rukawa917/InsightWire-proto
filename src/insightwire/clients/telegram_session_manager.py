import asyncio
import threading
import queue
import os
import time
from telethon import TelegramClient
from telethon.tl.types import Channel
from telethon.sessions import SQLiteSession, StringSession
import pandas as pd
from typing import List, Dict, Any, Optional, Callable, Union
from filelock import FileLock  # pip install filelock

class TelegramSessionManager:
    """
    Thread-safe Telegram session manager that runs in its own dedicated thread.
    This avoids event loop conflicts with Streamlit.
    """
    
    def __init__(self):
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.thread = None
        self.running = False
        self.client = None
        self.lock = None
        self.session_dir = None
        
    def start(self):
        """Start the session manager thread"""
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._run_manager)
            self.thread.daemon = True
            self.thread.start()
            
    def stop(self):
        """Stop the session manager thread"""
        if self.thread and self.thread.is_alive():
            self.running = False
            self.command_queue.put(("stop", None))
            self.thread.join(timeout=5)
            
            # Release any locks
            if self.lock and self.lock.is_locked:
                self.lock.release()
    
    def _run_manager(self):
        """Main thread function that runs the event loop"""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                # Get the next command with timeout
                command, args = self.command_queue.get(timeout=0.1)
                
                if command == "stop":
                    # Clean up before stopping
                    if self.client:
                        try:
                            loop.run_until_complete(self.client.disconnect())
                        except:
                            pass
                    break
                    
                elif command == "connect":
                    session_dir, api_id, api_hash, phone = args
                    
                    # Create session directory if it doesn't exist
                    os.makedirs(os.path.dirname(session_dir), exist_ok=True)
                    
                    # Set up file lock for this session
                    lock_file = f"{session_dir}.lock"
                    self.lock = FileLock(lock_file, timeout=30)  # 30 second timeout
                    
                    try:
                        # Acquire lock before accessing session
                        self.lock.acquire()
                        self.session_dir = session_dir
                        
                        # Create a new client with this thread's event loop
                        # Use StringSession instead of SQLiteSession to avoid database locks
                        self.client = TelegramClient(session_dir, api_id, api_hash, loop=loop)
                        result = loop.run_until_complete(self.client.connect())
                        self.result_queue.put(result)
                    except Exception as e:
                        print(f"Connection error: {e}")
                        self.result_queue.put(False)
                        # Release lock on error
                        if self.lock and self.lock.is_locked:
                            self.lock.release()
                    
                elif command == "is_authorized":
                    if self.client:
                        try:
                            result = loop.run_until_complete(self.client.is_user_authorized())
                            self.result_queue.put(result)
                        except Exception as e:
                            print(f"Authorization check error: {e}")
                            self.result_queue.put(False)
                    else:
                        self.result_queue.put(False)
                        
                elif command == "send_code":
                    phone = args
                    if self.client:
                        try:
                            loop.run_until_complete(self.client.send_code_request(phone))
                            self.result_queue.put(True)
                        except Exception as e:
                            print(f"Send code error: {e}")
                            self.result_queue.put(False)
                    else:
                        self.result_queue.put(False)
                        
                elif command == "sign_in":
                    phone, code = args
                    if self.client:
                        try:
                            loop.run_until_complete(self.client.sign_in(phone, code))
                            self.result_queue.put(True)
                        except Exception as e:
                            print(f"Sign in error: {e}")
                            self.result_queue.put(False)
                    else:
                        self.result_queue.put(False)
                        
                elif command == "get_channels":
                    if self.client and loop.run_until_complete(self.client.is_user_authorized()):
                        try:
                            # Get all dialogs and filter channels
                            channels = []
                            dialogs = loop.run_until_complete(self.client.get_dialogs())
                            for dialog in dialogs:
                                if isinstance(dialog.entity, Channel):
                                    channels.append(dialog.name)
                            self.result_queue.put(channels)
                        except Exception as e:
                            print(f"Get channels error: {e}")
                            self.result_queue.put([])
                    else:
                        self.result_queue.put([])
                        
                elif command == "get_channel_data":
                    target_channels, limit = args
                    if self.client and loop.run_until_complete(self.client.is_user_authorized()):
                        try:
                            data = []
                            dialogs = loop.run_until_complete(self.client.get_dialogs())
                            for dialog in dialogs:
                                if dialog.name in target_channels:
                                    # One message request at a time
                                    msgs = loop.run_until_complete(self.client.get_messages(dialog, limit=limit))
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
                            self.result_queue.put(pd.DataFrame(data))
                        except Exception as e:
                            print(f"Get channel data error: {e}")
                            self.result_queue.put(pd.DataFrame())
                    else:
                        self.result_queue.put(pd.DataFrame())
                        
                elif command == "disconnect":
                    if self.client:
                        try:
                            loop.run_until_complete(self.client.disconnect())
                            # Release the lock
                            if self.lock and self.lock.is_locked:
                                self.lock.release()
                            self.client = None
                        except Exception as e:
                            print(f"Disconnect error: {e}")
                    self.result_queue.put(True)
                    
            except queue.Empty:
                # No commands in queue, continue
                pass
            except Exception as e:
                print(f"Error in telegram session manager: {e}")
                self.result_queue.put(None)
                
        # Clean up
        if self.client:
            try:
                loop.run_until_complete(self.client.disconnect())
            except:
                pass
        
        # Release the lock
        if self.lock and self.lock.is_locked:
            self.lock.release()
            
        loop.close()
    
    def _execute_command(self, command, args=None):
        """Send a command to the thread and wait for the result"""
        if not self.running:
            self.start()
        self.command_queue.put((command, args))
        return self.result_queue.get()
    
    # Public API methods remain the same as before
    def connect(self, session_dir, api_id, api_hash, phone):
        """Connect to Telegram"""
        # Make sure session directory is a full path
        if not os.path.isabs(session_dir):
            session_dir = os.path.abspath(os.path.join('sessions', session_dir))
        return self._execute_command("connect", (session_dir, api_id, api_hash, phone))
    
    def is_authorized(self):
        """Check if user is authorized"""
        return self._execute_command("is_authorized")
    
    def send_code_request(self, phone):
        """Request verification code"""
        return self._execute_command("send_code", phone)
    
    def sign_in(self, phone, code):
        """Sign in with verification code"""
        return self._execute_command("sign_in", (phone, code))
    
    def get_channels(self):
        """Get list of available channels"""
        return self._execute_command("get_channels")
    
    def get_channel_data(self, target_channels, limit=100):
        """Get data from channels"""
        return self._execute_command("get_channel_data", (target_channels, limit))
    
    def disconnect(self):
        """Disconnect the client"""
        return self._execute_command("disconnect")

# Create a singleton instance
telegram_manager = TelegramSessionManager()