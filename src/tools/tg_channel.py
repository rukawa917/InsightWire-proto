import atexit
import streamlit as st
import time
import datetime
import logging
import os
from typing import List, Dict, Any, Optional, Tuple

from telethon.tl import types

# Import the manager
from insightwire.clients.telegram_session_manager import telegram_manager

# Set up logging
logger = logging.getLogger('telegram_channel_page')
logger.setLevel(logging.INFO)
# Add a handler if not already added
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Function to initialize or reset session state
def init_session_state():
    """Initialize or reset the session state variables"""
    logger.info("Initializing session state")
    st.session_state.auth = False
    st.session_state.api_id = ""
    st.session_state.api_hash = ""
    st.session_state.phone_number = ""
    st.session_state.auth_step = "input_credentials"
    st.session_state.tos_accepted = False
    st.session_state.tos_expires = None
    st.session_state.last_tos_check = None
    st.session_state.code_request_time = None
    st.session_state.session_error = False
    st.session_state.error_message = None

# Function to repair SQLite database
def repair_session_database(session_path):
    """
    Attempt to repair a corrupted session database by running SQLite's VACUUM command.
    This can help resolve 'database is locked' errors.
    """
    import sqlite3
    
    logger.info(f"Attempting to repair session database: {session_path}")
    
    try:
        # Try to connect with a timeout
        conn = sqlite3.connect(session_path, timeout=10.0)
        
        # Set pragma to recover from corruption
        conn.execute("PRAGMA integrity_check")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=OFF")
        
        # Run VACUUM to rebuild the database
        conn.execute("VACUUM")
        
        # Commit changes and close properly
        conn.commit()
        conn.close()
        
        logger.info(f"Successfully repaired session database: {session_path}")
        return True
    except sqlite3.Error as e:
        logger.error(f"SQLite error while repairing database {session_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while repairing database {session_path}: {e}")
        raise

# Initialize session state if needed
if "auth" not in st.session_state:
    init_session_state()

# Add a reset button in the sidebar
with st.sidebar:
    st.title("App Controls")
    if st.button("Reset Session"):
        logger.info("User requested session reset")
        # Stop the manager first to release any locks
        telegram_manager.stop()
        
        # Clean up session files if they exist
        try:
            sessions_dir = os.path.join(os.getcwd(), 'sessions')
            if os.path.exists(sessions_dir):
                # First, remove lock files
                for file in os.listdir(sessions_dir):
                    if file.endswith('.lock'):
                        lock_path = os.path.join(sessions_dir, file)
                        logger.info(f"Removing lock file: {lock_path}")
                        try:
                            os.remove(lock_path)
                        except Exception as e:
                            logger.error(f"Failed to remove lock file {lock_path}: {e}")
                
                # Then, handle session database files
                for file in os.listdir(sessions_dir):
                    if file.endswith('.session'):
                        session_path = os.path.join(sessions_dir, file)
                        try:
                            # Try to repair the session database
                            repair_session_database(session_path)
                        except Exception as e:
                            logger.error(f"Failed to repair session database {session_path}: {e}")
                            # If repair fails, rename the file to allow creating a new one
                            try:
                                backup_path = f"{session_path}.bak"
                                logger.info(f"Renaming problematic session file {session_path} to {backup_path}")
                                os.rename(session_path, backup_path)
                            except Exception as e2:
                                logger.error(f"Failed to rename session file {session_path}: {e2}")
        except Exception as e:
            logger.error(f"Error cleaning up session files: {e}")
        
        # Reset session state
        init_session_state()
        # Restart the manager
        telegram_manager.start()
        st.success("Session reset successfully!")
        st.rerun()

# Start the manager with error handling
try:
    telegram_manager.start()
    logger.info("Telegram manager started successfully")
except Exception as e:
    logger.error(f"Failed to start telegram manager: {e}")
    st.session_state.session_error = True
    st.session_state.error_message = f"Failed to start telegram manager: {e}"

st.title("Telegram Channel Scraper")

# Display error message if there was an error starting the manager
if st.session_state.session_error:
    st.error(f"Error: {st.session_state.error_message}")
    st.warning("Please try resetting the session using the button in the sidebar.")


def safe_execute(func, error_msg="Operation failed", max_retries=3, *args, **kwargs) -> Tuple[Any, Optional[str]]:
    """
    Execute a function safely with error handling and retry mechanism.
    Specifically handles 'database is locked' errors with retries.
    
    Args:
        func: The function to execute
        error_msg: Error message prefix for logging
        max_retries: Maximum number of retries for database lock errors
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Tuple of (result, error_message)
    """
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            result = func(*args, **kwargs)
            if retry_count > 0:
                logger.info(f"Operation succeeded after {retry_count} retries")
            return result, None
        except Exception as e:
            last_error = str(e)
            error_lower = last_error.lower()
            
            # Check if it's a database lock error
            if "database is locked" in error_lower:
                retry_count += 1
                logger.warning(f"Database is locked. Retry {retry_count}/{max_retries}")
                
                if retry_count < max_retries:
                    # Wait before retrying, with increasing delay
                    time.sleep(1.0 * retry_count)
                    continue
                else:
                    logger.error(f"Max retries reached for database lock error: {error_msg}: {e}")
            else:
                # For other errors, don't retry
                logger.error(f"{error_msg}: {e}")
                break
    
    return None, last_error

def login():
    """Handle the login process with improved error handling"""
    if st.session_state.auth_step == "input_credentials":
        api_id = st.text_input("Enter your API ID:")
        api_hash = st.text_input("Enter your API Hash:", type="password")
        phone_number = st.text_input("Enter your phone number (+123456789):")

        st.markdown(
            """
            ### How to get the API ID and Hash?
            1. Go to [Telegram's website](https://my.telegram.org/auth) and log in.
            2. Click on API Development Tools.
            3. Fill in the required fields.
                - App Title: Any name you want.
                - Short Name: Any name you want.
            4. Copy the `api_id` and `api_hash` to the respective fields above.
            5. Enter your phone number and click on Connect.
            """
        )

        if not api_id or not api_hash or not phone_number:
            return None

        if st.button("Connect"):
            st.session_state.api_id = api_id
            st.session_state.api_hash = api_hash
            st.session_state.phone_number = phone_number

            # Connect using the session manager with error handling
            session_name = f"session_{phone_number.replace('+', '')}"
            
            with st.spinner("Connecting to Telegram..."):
                result, error = safe_execute(
                    telegram_manager.connect,
                    "Failed to connect to Telegram",
                    3,  # max_retries
                    session_name, api_id, api_hash, phone_number
                )
                
                if error:
                    st.error(f"Connection error: {error}")
                    st.warning("Please check your credentials and try again, or reset the session.")
                    return None
                
                # Check if the user needs to comply with the terms of service
                st.session_state.auth_step = "check_connection"
                st.rerun()

    elif st.session_state.auth_step == "check_connection":
        with st.spinner("Connecting to Telegram..."):
            # Check if already authorized
            is_authorized, auth_error = safe_execute(
                telegram_manager.is_authorized,
                "Failed to check authorization status",
                3  # max_retries
            )
            
            if auth_error:
                st.error(f"Authorization check error: {auth_error}")
                st.warning("Please try again or reset the session.")
                return None
                
            if is_authorized:
                # Debug: Check for Terms of Service updates
                st.info("Checking for Terms of Service updates...")
                try:
                    tos_update, tos_error = safe_execute(
                        telegram_manager.get_terms_of_service_update,
                        "Failed to get Terms of Service update",
                        3  # max_retries
                    )
                    
                    if tos_error:
                        st.error(f"Error getting ToS update: {tos_error}")
                        # Continue with the flow even if ToS check fails
                        st.success("Authorized (but ToS check failed)")
                        st.session_state.auth = True
                        return True
                        
                    st.info(f"ToS update response type: {type(tos_update)}")
                    st.info(f"ToS update content: {tos_update}")
                    
                    if tos_update:
                        # Store ToS info in session state and move to ToS step
                        st.session_state.tos_update = tos_update
                        st.session_state.auth_step = "tos_update"
                        st.rerun()
                    else:
                        # No ToS update needed
                        st.success("Already authorized!")
                        st.session_state.auth = True
                        return True
                except Exception as e:
                    st.error(f"Error getting ToS update: {e}")
                    # Continue with the flow even if ToS check fails
                    st.success("Authorized (but ToS check failed)")
                    st.session_state.auth = True
                    return True
            else:
                # Need to request verification code with error handling
                result, error = safe_execute(
                    telegram_manager.send_code_request,
                    "Failed to send verification code",
                    3,  # max_retries
                    st.session_state.phone_number
                )
                
                if error:
                    st.error(f"Failed to send verification code: {error}")
                    st.warning("Please try again or reset the session.")
                    return None
                
                # Store the time when the code was requested
                st.session_state.code_request_time = time.time()
                st.session_state.auth_step = "enter_code"
                st.rerun()

    elif st.session_state.auth_step == "enter_code":
        verification_code = st.text_input(
            "Enter the verification code sent to your Telegram:"
        )

        # Check if 10 seconds have passed since the code was requested
        current_time = time.time()
        code_request_time = st.session_state.code_request_time or 0
        time_elapsed = current_time - code_request_time
        
        # Display a countdown or "Resend Code" button if 10 seconds have passed
        if time_elapsed < 10:
            st.info(f"You can resend the code in {int(10 - time_elapsed)} seconds")
        else:
            if st.button("Resend Code"):
                with st.spinner("Resending verification code..."):
                    result, error = safe_execute(
                        telegram_manager.send_code_request,
                        "Failed to resend verification code",
                        3,  # max_retries
                        st.session_state.phone_number
                    )
                    
                    if error:
                        st.error(f"Failed to resend verification code: {error}")
                        st.warning("Please try again or reset the session.")
                    else:
                        st.session_state.code_request_time = time.time()
                        st.success("Verification code resent!")
                        st.rerun()

        if st.button("Verify"):
            if verification_code:
                with st.spinner("Verifying..."):
                    result, error = safe_execute(
                        telegram_manager.sign_in,
                        "Failed to sign in",
                        3,  # max_retries
                        st.session_state.phone_number, verification_code
                    )
                    
                    if error:
                        st.error(f"Sign in error: {error}")
                        st.warning("Invalid code or authentication failed. Please try again.")
                    elif result:
                        st.success("Successfully connected to Telegram!")
                        st.session_state.auth_step = "tos_update"
                        st.session_state.auth = True
                        st.rerun()
                    else:
                        st.error("Invalid code or authentication failed. Please try again.")
            else:
                st.warning("Please enter the verification code.")

    return None

def check_tos_expiration():
    """
    Check if the Terms of Service update needs to be checked based on expiration time.
    Returns True if ToS needs to be updated, False otherwise.
    """
    # If we have an expiration time and it's in the past, we need to check for updates
    if st.session_state.tos_expires is not None:
        current_time = datetime.datetime.now(tz=datetime.timezone.utc)
        if current_time >= st.session_state.tos_expires:
            logger.info("ToS expired at %s, current time is %s", st.session_state.tos_expires, current_time)
            return True
    
    # If we've never checked for ToS updates, we should check
    if st.session_state.last_tos_check is None:
        logger.info("First ToS check")
        return True
        
    return False

def tos_update():
    """Display and handle Terms of Service updates"""
    # Get the latest Terms of Service update
    tos, error = safe_execute(
        telegram_manager.get_terms_of_service_update,
        "Failed to get Terms of Service update",
        3  # max_retries
    )
    
    if error:
        st.error(f"Error getting Terms of Service update: {error}")
        st.warning("Please try again or reset the session.")
        return False
    
    # Update the last check time
    st.session_state.last_tos_check = datetime.datetime.now()
    
    # Store the expiration time if available
    if tos and 'expires' in tos:
        st.session_state.tos_expires = tos['expires']
        expiry_date = tos['expires']
        logger.info("ToS expires at: %s", expiry_date)
    
    # Check the type of ToS update
    if tos and tos.get('type') == 'empty':
        logger.info("No Terms of Service update available")
        st.session_state.tos_accepted = True
        return True
    elif tos and tos.get('type') == 'update':
        logger.info("Terms of Service update available")
        # Display the ToS update to the user
        st.warning("Telegram Terms of Service Update")
        st.markdown("**Terms of Service:**")
        st.markdown(tos.get('text', 'Terms of Service text not available'))
        
        # Show expiration time if available
        if 'expires' in tos:
            expiry_date = datetime.datetime.fromtimestamp(tos['expires'])
            st.info(f"This Terms of Service will be valid until: {expiry_date}")
    
    st.write("Please review the Terms of Service and accept or decline.")
    # Show accept and decline buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Accept"):
            with st.spinner("Accepting Terms of Service..."):
                result, error = safe_execute(
                    telegram_manager.accept_terms_of_service,
                    "Failed to accept Terms of Service",
                    3,  # max_retries
                    tos.get('id')
                )
                
                if error:
                    st.error(f"Failed to accept Terms of Service: {error}")
                    st.warning("Please try again or reset the session.")
                    return False
                elif result:
                    st.success("Terms of Service accepted!")
                    st.session_state.tos_accepted = True
                    return True
                else:
                    st.error("Failed to accept Terms of Service. Please try again.")
                    return False
    
    with col2:
        if st.button("Decline"):
            if st.checkbox("I understand that declining will delete my account"):
                with st.spinner("Declining Terms of Service..."):
                    result, error = safe_execute(
                        telegram_manager.decline_terms_of_service,
                        "Failed to decline Terms of Service",
                        3,  # max_retries
                        tos.get('id')
                    )
                    
                    if error:
                        st.error(f"Failed to decline Terms of Service: {error}")
                        st.warning("Please try again or reset the session.")
                        return False
                    elif result:
                        st.error("Account has been deleted as you declined the Terms of Service.")
                        # Reset session state
                        st.session_state.auth = False
                        st.session_state.auth_step = "input_credentials"
                        st.rerun()
                    else:
                        st.error("Failed to decline Terms of Service. Please try again.")
                        return False
            else:
                st.warning("You must acknowledge that your account will be deleted if you decline.")
    
    return False

def main_flow():
    """Main application flow after authentication"""
    try:
        # Display ToS status
        if st.session_state.tos_expires:
            expiry_date = st.session_state.tos_expires
            current_time = datetime.datetime.now(datetime.timezone.utc)
            time_left = expiry_date - current_time
            
            # Create a status indicator
            status_col1, status_col2 = st.columns([1, 3])
            with status_col1:
                if time_left.total_seconds() > 0:
                    st.success("ToS Status: Valid")
                else:
                    st.error("ToS Status: Expired")
            
            with status_col2:
                if time_left.total_seconds() > 0:
                    st.info(f"Terms of Service valid until: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')} (in {time_left.days} days, {time_left.seconds//3600} hours)")
                else:
                    st.warning("Terms of Service has expired. You will be prompted to review and accept the updated terms.")
        
        # Debug info - can be removed in production
        with st.expander("Debug Info"):
            st.write(st.session_state)
        
        # Main functionality
        channels, error = safe_execute(
            telegram_manager.get_channels,
            "Failed to get channels",
            3  # max_retries
        )
        
        if error:
            if "database is locked" in error.lower():
                st.error("Database is locked. This usually happens when multiple instances are accessing the same session.")
                st.warning("Please try resetting the session using the button in the sidebar, or wait a few moments and try again.")
                
                # Add a retry button specifically for database lock errors
                if st.button("Retry Getting Channels"):
                    st.experimental_rerun()
            else:
                st.error(f"Error getting channels: {error}")
                st.warning("Please try again or reset the session.")
            return
            
        if not channels:
            channels = []
            
        sel_channels = st.multiselect("Select channels", channels)
        data = None
        
        if st.button("Scrape"):
            with st.spinner("Scraping..."):
                data, error = safe_execute(
                    telegram_manager.get_channel_data,
                    "Failed to get channel data",
                    3,  # max_retries
                    sel_channels
                )
                
                if error:
                    st.error(f"Error getting channel data: {error}")
                    st.warning("Please try again or reset the session.")
                    return

        if data is not None and not data.empty:
            st.dataframe(data, use_container_width=True)
    except Exception as e:
        logger.error(f"Error in main flow: {e}")
        st.error(f"An unexpected error occurred: {e}")
        st.warning("Please try resetting the session using the button in the sidebar.")


# Main code flow with error handling
try:
    if not st.session_state.auth:
        result = login()
        if result:
            st.rerun()  # Refresh after successful login
    elif not st.session_state.tos_accepted or check_tos_expiration():
        # If ToS is not accepted or has expired, show the ToS update
        result = tos_update()
        if result:
            st.rerun()  # Refresh after accepting ToS
    else:
        # User is already authenticated and ToS is accepted, proceed to main flow
        main_flow()
except Exception as e:
    logger.error(f"Unhandled exception in main app flow: {e}")
    st.error(f"An unexpected error occurred: {e}")
    st.warning("Please try resetting the session using the button in the sidebar.")


# Cleanup function
def cleanup():
    """Clean up resources when the app exits"""
    try:
        logger.info("Cleaning up resources...")
        telegram_manager.stop()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


# Register cleanup
atexit.register(cleanup)
