import streamlit as st
from typing import List

from insightwire.clients.tg_channel_client import TelegramChannelClient


st.title("Telegram Channel Scraper")

api_id = st.text_input("Input API ID")
api_hash = st.text_input("Input API Hash")
phone_number = st.text_input("Input Phone Number used in Telegram")

# api_id = st.secrets["telegram"]["api_id"]
# api_hash = st.secrets["telegram"]["api_hash"]
# phone_number = st.secrets["telegram"]["phone_number"]
if not api_id or not api_hash or not phone_number:
    st.stop()

cli = TelegramChannelClient(
    session_dir="session",
    api_id=api_id,
    api_hash=api_hash,
    phone_number=phone_number,
)

# target_channels = ["The Barbarian 해외주식", "SeungHee KANG"]
with st.spinner("Retrieving channels..."):
    channels: List[str] = cli.get_channels()

sel_channels: List[str] = st.multiselect("Select channels", channels)
if st.button("Scrape"):
    with st.spinner("Scraping..."):
        data = cli.get_channel_data(sel_channels)
        st.write(data)

        