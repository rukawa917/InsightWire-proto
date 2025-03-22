
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