import atexit
import streamlit as st
import time
import datetime
import logging
from typing import List, Dict, Any, Optional

from telethon.tl import types

# Import the manager
from insightwire.clients.telegram_session_manager import telegram_manager

# Initialize session state
if "auth" not in st.session_state:
    st.session_state.auth = False
if "api_id" not in st.session_state:
    st.session_state.api_id = ""
if "api_hash" not in st.session_state:
    st.session_state.api_hash = ""
if "phone_number" not in st.session_state:
    st.session_state.phone_number = ""
if "auth_step" not in st.session_state:
    st.session_state.auth_step = "input_credentials"
if "tos_accepted" not in st.session_state:
    st.session_state.tos_accepted = False
if "tos_expires" not in st.session_state:
    st.session_state.tos_expires = None
if "last_tos_check" not in st.session_state:
    st.session_state.last_tos_check = None
    
# Start the manager
telegram_manager.start()
logger = logging.getLogger('telegram_channel_page')

st.title("Telegram Channel Scraper")

def login():
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

            # Connect using the session manager
            session_name = f"session_{phone_number.replace('+', '')}"
            telegram_manager.connect(session_name, api_id, api_hash, phone_number)

            # Check if the user needs to comply with the terms of service
            st.session_state.auth_step = "check_connection"
            st.rerun()

    elif st.session_state.auth_step == "check_connection":
        with st.spinner("Connecting to Telegram..."):
        # Check if already authorized
            if telegram_manager.is_authorized():
            # Debug: Check for Terms of Service updates
                st.info("Checking for Terms of Service updates...")
                try:
                    tos_update = telegram_manager.get_terms_of_service_update()
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
                # Need to request verification code
                telegram_manager.send_code_request(st.session_state.phone_number)
                st.session_state.auth_step = "enter_code"
                st.rerun()

    elif st.session_state.auth_step == "enter_code":
        verification_code = st.text_input(
            "Enter the verification code sent to your Telegram:"
        )

        if st.button("Verify"):
            if verification_code:
                with st.spinner("Verifying..."):
                    if telegram_manager.sign_in(
                        st.session_state.phone_number, verification_code
                    ):
                        st.success("Successfully connected to Telegram!")
                        st.session_state.auth_step = "tos_update"
                        st.session_state.auth = True
                        st.rerun()
                    else:
                        st.error(
                            "Invalid code or authentication failed. Please try again."
                        )
                        # Keep in the same state to allow retrying
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
    tos = telegram_manager.get_terms_of_service_update()
    
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
                if telegram_manager.accept_terms_of_service(tos.get('id')):
                    st.success("Terms of Service accepted!")
                    st.session_state.tos_accepted = True
                    return True
                else:
                    st.error("Failed to accept Terms of Service. Please try again.")
    
    with col2:
        if st.button("Decline"):
            if st.checkbox("I understand that declining will delete my account"):
                with st.spinner("Declining Terms of Service..."):
                    if telegram_manager.decline_terms_of_service(tos.get('id')):
                        st.error("Account has been deleted as you declined the Terms of Service.")
                        # Reset session state
                        st.session_state.auth = False
                        st.session_state.auth_step = "input_credentials"
                        st.rerun()
                    else:
                        st.error("Failed to decline Terms of Service. Please try again.")
            else:
                st.warning("You must acknowledge that your account will be deleted if you decline.")
    


def main_flow():
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
    channels = telegram_manager.get_channels()
    sel_channels = st.multiselect("Select channels", channels)
    data = None
    if st.button("Scrape"):
        with st.spinner("Scraping..."):
            data = telegram_manager.get_channel_data(sel_channels)

    if data is not None and not data.empty:
        st.dataframe(data, use_container_width=True)


# Main code flow
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


# Cleanup function
def cleanup():
    telegram_manager.stop()


# Register cleanup
atexit.register(cleanup)
