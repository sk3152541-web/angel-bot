import streamlit as st
import pandas as pd
import numpy as np
import datetime
import pyotp
import threading
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import matplotlib.pyplot as plt

st.set_page_config(page_title="Angel One Live TSL Trading Bot", layout="wide")

st.markdown("<h2 style='color: #38bdf8;'>🚀 Angel One Pro Web Trading Bot & TSL with Live Chart</h2>", unsafe_allow_html=True)

# Initialize session state variables
if "smart_session" not in st.session_state:
    st.session_state.smart_session = None
if "bot_active" not in st.session_state:
    st.session_state.bot_active = False
if "logs" not in st.session_state:
    st.session_state.logs = []
if "active_positions" not in st.session_state:
    st.session_state.active_positions = {}
if "market_data" not in st.session_state:
    st.session_state.market_data = {"2885": 1219.20, "11536": 2087.00, "1594": 1014.50}

def add_log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {msg}")

# Sidebar for Authentication
st.sidebar.header("🔐 SmartAPI Authentication")
api_key = st.sidebar.text_input("API Key", type="default")
client_id = st.sidebar.text_input("Client ID", type="default")
password = st.sidebar.text_input("Password / MPIN", type="password")
totp_key = st.sidebar.text_input("TOTP Secret Key", type="password")

if st.sidebar.button("Connect Live Feed"):
    if not all([api_key, client_id, password, totp_key]):
        st.sidebar.error("Please fill all authentication fields!")
    else:
        try:
            obj = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(totp_key).now()
            session_data = obj.generateSession(client_id, password, totp)

            if session_data and session_data.get('status'):
                jwt_token = session_data['data']['jwtToken']
                feed_token = obj.getfeedToken()
                st.session_state.smart_session = {
                    "obj": obj, "jwt": jwt_token, "feed": feed_token, "client": client_id, "key": api_key
                }
                st.sidebar.success("Connected Successfully!")
                add_log("⚡ Successfully authenticated with Angel One SmartAPI!")
            else:
                err_msg = session_data.get('message', 'Authentication failed')
                st.sidebar.error(f"Login Failed: {err_msg}")
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")

# Main Dashboard Layout
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📊 Live Market Ticks (NSE)")
    df_market = pd.DataFrame([
        {"Token & Symbol": "2885 (RELIANCE-EQ)", "Live LTP (₹)": st.session_state.market_data["2885"]},
        {"Token & Symbol": "11536 (TCS-EQ)", "Live LTP (₹)": st.session_state.market_data["11536"]},
        {"Token & Symbol": "1594 (INFY-EQ)", "Live LTP (₹)": st.session_state.market_data["1594"]}
    ])
    st.table(df_market)

with col2:
    st.subheader("⚙️ TSL & Entry Controls")
    entry_price_input = st.number_input("Entry Price (₹)", value=float(st.session_state.market_data["2885"]), step=0.5)
    tsl_gap_input = st.number_input("TSL Gap (₹)", value=5.0, step=0.5)
    qty_input = st.number_input("Quantity", value=1, step=1)

    if not st.session_state.bot_active:
        if st.button("Start Auto-Bot (TSL)", type="primary"):
            if not st.session_state.smart_session:
                st.warning("Please connect SmartAPI first from sidebar!")
            else:
                st.session_state.bot_active = True
                base_price = entry_price_input if entry_price_input > 0 else st.session_state.market_data["2885"]
                st.session_state.active_positions["2885"] = {
                    "symbol": "RELIANCE-EQ",
                    "quantity": int(qty_input),
                    "highest_price": base_price,
                    "current_sl": base_price - tsl_gap_input,
                    "tsl_value": tsl_gap_input
                }
                add_log(f"🟢 TSL Bot Activated! Base Entry Price: ₹{base_price} | Gap: ₹{tsl_gap_input}")
                st.rerun()
    else:
        if st.button("Stop Auto-Bot", type="secondary"):
            st.session_state.bot_active = False
            st.session_state.active_positions.clear()
            add_log("🔴 TSL Bot Engine Stopped.")
            st.rerun()

# Chart Section
st.subheader("📈 Live Price Chart & Dotted Line (RELIANCE-EQ)")
fig, ax = plt.subplots(figsize=(10, 4))
fig.patch.set_facecolor('#0f172a')
ax.set_facecolor('#1e293b')
ax.tick_params(colors='#f8fafc')
for spine in ax.spines.values():
    spine.set_color('#334155')

current_ltp = st.session_state.market_data["2885"]
ax.axhline(y=current_ltp, color='#facc15', linestyle='--', label=f'LTP: ₹{current_ltp}')
ax.set_title("Live Reliance Price Action", color='#38bdf8', fontsize=12, fontweight='bold')
ax.legend(facecolor='#0f172a', edgecolor='none', labelcolor='#facc15')
st.pyplot(fig)

# Execution & TSL Audit Logs
st.subheader("📜 Execution & TSL Audit Logs")
log_container = st.container(height=200)
with log_container:
    for log in reversed(st.session_state.logs):
        st.text(log)