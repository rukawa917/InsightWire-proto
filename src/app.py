import streamlit as st

from insightwire.clients.tg_channel_client import TelegramChannelClient

def home():
    st.write("Welcome to InsightWire!")

    

home_pg = st.Page(home, title="Home")
telegram_pg = st.Page("tools/tg_channel.py", title="Telegram Channel")

page_dict = {
    "Home": [home_pg],
    "Tools": [telegram_pg],
}

pg = st.navigation(page_dict)
pg.run()

