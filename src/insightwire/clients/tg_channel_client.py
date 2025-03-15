"""
Telegram Channel Client Module

This module provides functionality for interacting with Telegram channels programmatically.
It wraps the Telethon library to offer an easy-to-use interface for scraping and analyzing
content from Telegram channels.

The module contains the TelegramChannelClient class which handles authentication,
channel retrieval, and message scraping. The data is returned as pandas DataFrames
for convenient analysis and processing.

Dependencies:
    - telethon: For Telegram API interaction
    - pandas: For data handling and organization
    - asyncio: For asynchronous operations

Example:
    Basic usage of the TelegramChannelClient:

    ```python
    # Initialize the client
    client = TelegramChannelClient(
        session_dir="session_name",
        api_id="your_api_id",
        api_hash="your_api_hash",
        target_channels=["channel1", "channel2"]
    )
    
    # Retrieve available channels
    available_channels = client.get_channels("+1234567890")
    
    # Scrape data from target channels
    channel_data = client.get_channel_data("+1234567890", limit=100)
    ```

Note:
    To use this module, you need to register your application on
    https://my.telegram.org to get the API ID and hash.
"""
import asyncio
from typing import List

import pandas as pd
import streamlit as st
from telethon import TelegramClient
from telethon.tl.types import Channel, Message


class TelegramChannelClient:
    """
    A client for interacting with Telegram channels.
    This class provides functionality to connect to Telegram, retrieve available channels, 
    and scrape messages from specific channels.
    Attributes:
        session_dir (str): Directory where the Telegram session will be stored.
        api_id (int): Telegram API ID obtained from https://my.telegram.org.
        api_hash (str): Telegram API hash obtained from https://my.telegram.org.
        client (TelegramClient): Telethon client instance used for Telegram operations.
    Examples:
        >>> client = TelegramChannelClient("session_name", api_id, api_hash)
        >>> channels = client.get_channels("+1234567890")
        >>> data = client.get_channel_data("+1234567890", limit=50)
    """
    def __init__(self, session_dir: str, api_id: str, api_hash: str, phone_number: str):
        self.session_dir = session_dir
        self.api_id = api_id
        self.api_hash = api_hash
        self.client = None
        self.phone_number = phone_number
    
    async def __aenter__(self):
        self.client = TelegramClient(self.session_dir, self.api_id, self.api_hash)
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.disconnect()

    async def __get_available_channels(self):
        """
        Retrieves a list of available Telegram channels for a given phone number.

        This asynchronous method connects to Telegram using the provided phone number
        and iterates through all dialogs, filtering for only Channel entities.

        Returns:
        -------
        list of str
            A list of channel names that the authenticated user has access to.

        Notes:
        -----
        This method uses a context manager to handle the client session automatically.
        The user will need to complete the authentication process if prompted.
        """
        async with self as client:
            await client.start(phone=self.phone_number)
            return [
                dialog.name
                async for dialog in client.iter_dialogs()
                if isinstance(dialog.entity, Channel)
            ]

    async def __scrape_channels(self, target_channels: List[str], limit=100):
        """
        Scrapes messages from target Telegram channels.

        This method connects to Telegram using the provided phone number, iterates through 
        the user's dialogs (chats), and collects messages from channels specified in 
        self.target_channels.

        Parameters:
            limit (int, optional): Maximum number of messages to retrieve from each channel. 
                                  Defaults to 100.

        Returns:
            pandas.DataFrame: A DataFrame containing the scraped messages with columns:
                - channel: Name of the Telegram channel
                - date: Date and time when the message was posted
                - text: Content of the message
                - views: Number of views for the message
                - forwards: Number of times the message was forwarded

        Note:
            This method uses an async context manager to handle the Telegram client session.
        """
        async with self as client:
            await client.start(phone=self.phone_number)


            data = []
            async for dialog in client.iter_dialogs():
                if dialog.name not in target_channels:
                    continue
                msgs:List[Message] = await client.get_messages(dialog, limit=limit)

                for message in msgs:
                    text = message.text.strip() if message.text else ""
                    if text == "":
                        continue
                    data.append(
                        {
                            "channel": dialog.name,
                            "date": message.date,
                            "text": text,
                            "views": message.views,
                            # "forwards": message.forwards,
                        }
                    )

            return pd.DataFrame(data)

    def get_channel_data(self, target_channels: List[str], limit=100):
        """
        Retrieves data from Telegram channels for a specific phone number.

        This method serves as a synchronous wrapper for the asynchronous scrape_channels method,
        using asyncio.run to handle the execution of the coroutine.

        Parameters
        ----------
        limit : int, optional
            Maximum number of messages to retrieve per channel. Defaults to 100.

        Returns
        -------
        dict
            A dictionary containing the scraped channel data organized by channel.
        """
        return asyncio.run(self.__scrape_channels(target_channels=target_channels, limit=limit))

    @st.cache_data(ttl = 60 * 10)
    def get_channels(_self):
        """
        Retrieve all accessible channels for a given phone number.

        This method is a synchronous wrapper around the asynchronous `get_available_channels` 
        method, making it easier to use in non-asynchronous contexts by automatically handling
        the event loop execution.

        Returns:
            list: A list of channel objects that are accessible with the provided phone number.

        Example:
            >>> client = TelegramChannelClient()
            >>> channels = client.get_channels('+1234567890')
            >>> print(channels)
            [Channel(id=123, title='Channel 1'), Channel(id=456, title='Channel 2')]
        """
        return asyncio.run(_self.__get_available_channels())