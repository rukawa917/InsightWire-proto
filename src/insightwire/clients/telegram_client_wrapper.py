from typing import Optional, List, Dict, Any
import logging
import asyncio
from telethon import TelegramClient
from telethon import functions, types
from filelock import FileLock

from insightwire.clients.exec_errors import CommandExecutionError
from telethon.tl.types import Dialog

logger = logging.getLogger('telegram_client_wrapper')

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
            logger.error("Failed to connect: %s", e)
            raise CommandExecutionError("connect", e) from e
            
    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        try:
            await self.client.disconnect()
        except Exception as e:
            logger.error("Failed to disconnect: %s", e)
            raise CommandExecutionError("disconnect", e) from e
            
    async def is_authorized(self) -> bool:
        """
        Check if the user is authorized.
        
        Returns:
            bool: True if the user is authorized
        """
        try:
            return await self.client.is_user_authorized()
        except Exception as e:
            logger.error("Failed to check authorization: %s", e)
            raise CommandExecutionError("is_authorized", e) from e
            
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
            logger.error("Failed to send code request: %s", e)
            raise CommandExecutionError("send_code_request", e) from e
            
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
            logger.error("Failed to sign in: %s", e)
            raise CommandExecutionError("sign_in", e) from e
            
    async def get_dialogs(self) -> List[Dialog]:
        """
        Get all dialogs.
        
        Returns:
            List[Dialog]: List of dialogs
        """
        try:
            return await self.client.get_dialogs()
        except Exception as e:
            logger.error("Failed to get dialogs: %s", e)
            raise CommandExecutionError("get_dialogs", e) from e
            
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
            logger.error("Failed to get messages: %s", e)
            raise CommandExecutionError("get_messages", e) from e

    async def get_terms_of_service_update(self) -> Dict[str, Any]:
        """
        Get the latest terms of service update.
        
        Returns:
            Dict[str, Any]: Dictionary with terms of service update info or None if no update
        """
        try:
            result = await self.client(functions.help.GetTermsOfServiceUpdateRequest())
            if isinstance(result, types.help.TermsOfServiceUpdateEmpty):
                logger.info("No Terms of Service update available")
                return {
                    "type": "empty",
                    "expires": result.expires
                }
            elif isinstance(result, types.help.TermsOfServiceUpdate):
                logger.info("Terms of Service update available")
                return {
                    "type": "update",
                    "id": result.id.decode('utf-8') if hasattr(result.id, 'decode') else result.id,
                    "text": result.terms_of_service.text,
                    "entities": [e.to_dict() for e in result.terms_of_service.entities] if hasattr(result.terms_of_service, 'entities') else [],
                    "min_age": result.terms_of_service.min_age_confirm if hasattr(result.terms_of_service, 'min_age_confirm') else None,
                    "popup": result.terms_of_service.popup if hasattr(result.terms_of_service, 'popup') else False,
                    "expires": result.expires
                }
            logger.warning("Unknown result type: %s", type(result))
            return {
                "type": "unknown",
                "raw_result": str(result)
            }
        except Exception as e:
            logger.error("Failed to get terms of service update: %s", e)
            raise CommandExecutionError("get_terms_of_service_update", e) from e
            
    async def accept_terms_of_service(self, tos_id: str) -> bool:
        """
        Accept the terms of service.
        
        Args:
            tos_id: ID of the terms of service to accept
            
        Returns:
            bool: True if terms were accepted successfully
        """
        try:
            result = await self.client(functions.help.AcceptTermsOfServiceRequest(
                id=types.DataJSON(
                    data=tos_id.encode('utf-8') if hasattr(tos_id, 'encode') else tos_id
                )
            ))
            return result
        except Exception as e:
            logger.error("Failed to accept terms of service: %s", e)
            raise CommandExecutionError("accept_terms_of_service", e) from e
            
    async def decline_terms_of_service(self, tos_id: str = None) -> bool:
        """
        Decline the terms of service by deleting the account.
        
        Args:
            tos_id: ID of the terms of service that was declined (not used in API call but kept for consistency)
            
        Returns:
            bool: True if account was deleted successfully
        """
        try:
            # The tos_id is not actually used in the DeleteAccountRequest, but we keep it as a parameter
            # for consistency with the accept_terms_of_service method
            result = await self.client(functions.account.DeleteAccountRequest(
                reason="Decline ToS update"
            ))
            return result
        except Exception as e:
            logger.error("Failed to decline terms of service: %s", e)
            raise CommandExecutionError("decline_terms_of_service", e) from e
