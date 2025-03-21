"""
Test script for the TelegramSessionManager.

This script tests the basic functionality of the TelegramSessionManager
without requiring actual Telegram credentials.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

# Add the src directory to the path so we can import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from insightwire.clients.telegram_session_manager import (
    TelegramSessionManager,
    TelegramClientWrapper,
    CommandProcessor,
    TelegramSessionError,
    ClientNotConnectedError,
    AuthenticationError,
    CommandExecutionError
)


class TestTelegramSessionManager(unittest.TestCase):
    """Test cases for the TelegramSessionManager."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock for the TelegramClient
        self.client_patcher = patch('insightwire.clients.telegram_session_manager.TelegramClient')
        self.mock_client = self.client_patcher.start()
        
        # Create a mock for the FileLock
        self.lock_patcher = patch('insightwire.clients.telegram_session_manager.FileLock')
        self.mock_lock = self.lock_patcher.start()
        
        # Create a session manager
        self.manager = TelegramSessionManager()
        
    def tearDown(self):
        """Tear down test fixtures."""
        self.client_patcher.stop()
        self.lock_patcher.stop()
        
        # Stop the session manager
        self.manager.stop()
        
    def test_connect(self):
        """Test connecting to Telegram."""
        # Mock the _execute_command method
        self.manager._execute_command = MagicMock(return_value=True)
        
        # Call connect
        result = self.manager.connect('test_session', '12345', 'abcdef', '+1234567890')
        
        # Check that _execute_command was called with the right arguments
        self.manager._execute_command.assert_called_once_with(
            'connect', 
            (os.path.abspath(os.path.join('sessions', 'test_session')), '12345', 'abcdef', '+1234567890')
        )
        
        # Check the result
        self.assertTrue(result)
        
    def test_is_authorized(self):
        """Test checking if the user is authorized."""
        # Mock the _execute_command method
        self.manager._execute_command = MagicMock(return_value=True)
        
        # Call is_authorized
        result = self.manager.is_authorized()
        
        # Check that _execute_command was called with the right arguments
        self.manager._execute_command.assert_called_once_with('is_authorized')
        
        # Check the result
        self.assertTrue(result)
        
    def test_send_code_request(self):
        """Test sending a code request."""
        # Mock the _execute_command method
        self.manager._execute_command = MagicMock(return_value=True)
        
        # Call send_code_request
        result = self.manager.send_code_request('+1234567890')
        
        # Check that _execute_command was called with the right arguments
        self.manager._execute_command.assert_called_once_with('send_code', '+1234567890')
        
        # Check the result
        self.assertTrue(result)
        
    def test_sign_in(self):
        """Test signing in."""
        # Mock the _execute_command method
        self.manager._execute_command = MagicMock(return_value=True)
        
        # Call sign_in
        result = self.manager.sign_in('+1234567890', '12345')
        
        # Check that _execute_command was called with the right arguments
        self.manager._execute_command.assert_called_once_with('sign_in', ('+1234567890', '12345'))
        
        # Check the result
        self.assertTrue(result)
        
    def test_get_channels(self):
        """Test getting channels."""
        # Mock the _execute_command method
        self.manager._execute_command = MagicMock(return_value=['channel1', 'channel2'])
        
        # Call get_channels
        result = self.manager.get_channels()
        
        # Check that _execute_command was called with the right arguments
        self.manager._execute_command.assert_called_once_with('get_channels')
        
        # Check the result
        self.assertEqual(result, ['channel1', 'channel2'])
        
    def test_get_channel_data(self):
        """Test getting channel data."""
        # Create a mock DataFrame
        mock_df = pd.DataFrame({
            'channel': ['channel1', 'channel1'],
            'date': ['2021-01-01', '2021-01-02'],
            'text': ['text1', 'text2'],
            'views': [10, 20]
        })
        
        # Mock the _execute_command method
        self.manager._execute_command = MagicMock(return_value=mock_df)
        
        # Call get_channel_data
        result = self.manager.get_channel_data(['channel1'], 10)
        
        # Check that _execute_command was called with the right arguments
        self.manager._execute_command.assert_called_once_with('get_channel_data', (['channel1'], 10))
        
        # Check the result
        pd.testing.assert_frame_equal(result, mock_df)
        
    def test_disconnect(self):
        """Test disconnecting."""
        # Mock the _execute_command method
        self.manager._execute_command = MagicMock(return_value=True)
        
        # Call disconnect
        result = self.manager.disconnect()
        
        # Check that _execute_command was called with the right arguments
        self.manager._execute_command.assert_called_once_with('disconnect')
        
        # Check the result
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
