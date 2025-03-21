import streamlit as st
import asyncio
from telethon import TelegramClient
from telethon.tl.types import InputPeerUser

st.set_page_config(layout="wide")


def home():
    st.markdown(f"Welcome!")


home_pg = st.Page(home, title="Home")
telegram_pg = st.Page("tools/tg_channel.py", title="Telegram Channel")

page_dict = {
    "Home": [home_pg],
    "Tools": [telegram_pg],
}

pg = st.navigation(page_dict)
pg.run()
