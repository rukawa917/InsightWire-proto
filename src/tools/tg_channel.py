import atexit
import streamlit as st
from typing import List

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

# Start the manager
telegram_manager.start()

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

            st.session_state.auth_step = "check_connection"
            st.rerun()

    elif st.session_state.auth_step == "check_connection":
        with st.spinner("Connecting to Telegram..."):
            # Check if already authorized
            if telegram_manager.is_authorized():
                st.success("Already authorized!")
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
                        st.session_state.auth = True
                        return True
                    else:
                        st.error(
                            "Invalid code or authentication failed. Please try again."
                        )
                        # Keep in the same state to allow retrying
            else:
                st.warning("Please enter the verification code.")

    return None


def main_flow():
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
else:
    # User is already authenticated, proceed to main flow
    main_flow()


# Cleanup function
def cleanup():
    telegram_manager.stop()


# Register cleanup
atexit.register(cleanup)
