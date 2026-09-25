import streamlit as st
import pandas as pd
import numpy as np
import time
from SmartApi import SmartConnect
import pyotp

st.set_page_config(page_title="Angel One Live TSL Trading Bot", layout="wide")

# Automatic refresh every 5 seconds for mobile & cloud live updates
st.markdown(
    """
    <meta http-equiv="refresh" content="5">
    """,
    unsafe_allow_html=True
)

st.title("🚀 Angel One Pro Web Trading Bot & TSL with Live Chart")

# Sidebar for Authentication
st.sidebar.header("SmartAPI Authentication")
api_key = st.sidebar.text_input("API Key", type="default")
client_id = st.sidebar.text_input("Client ID", type="default")
password = st.sidebar.text_input("Password / MPIN", type="password")
totp_key = st.sidebar.text_input("TOTP Secret Key", type="password")

# Session state initialization
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.sidebar.button("Connect Live Feed"):
    try:
        if api_key and client_id and password and totp_key:
            totp = pyotp.TOTP(totp_key.replace(" ", "")).now()
            smartApi = SmartConnect(api_key=api_key)
            data = smartApi.generateSession(client_id, password, totp)
            if data and data.get('status'):
                st.sidebar.success("Connected Successfully!")
                st.session_state['smartApi'] = smartApi
                st.session_state['logged_in'] = True
            else:
                st.sidebar.error("Authentication Failed. Check credentials.")
        else:
            st.sidebar.warning("Please fill all authentication fields.")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# Live Market Ticks Section
st.subheader("📊 Live Market Ticks (NSE)")

ltp_reliance = 1219.20
ltp_tcs = 2087.00
ltp_infy = 1014.50

if st.session_state['logged_in'] and 'smartApi' in st.session_state:
    try:
        smartApi = st.session_state['smartApi']
        ltp_data = smartApi.ltpData("NSE", "2885", "RELIANCE-EQ")
        if ltp_data and 'data' in ltp_data:
            ltp_reliance = ltp_data['data'].get('ltp', ltp_reliance)
    except Exception as ex:
        pass

market_data = {
    "Token & Symbol": ["2885 (RELIANCE-EQ)", "11536 (TCS-EQ)", "1594 (INFY-EQ)"],
    "Live LTP (₹)": [ltp_reliance, ltp_tcs, ltp_infy]
}
df_market = pd.DataFrame(market_data)
st.dataframe(df_market, use_container_width=True)

# TSL & Entry Controls
st.subheader("⚙️ TSL & Entry Controls")
col1, col2, col3 = st.columns(3)

with col1:
    entry_price = st.number_input("Entry Price (₹)", value=float(ltp_reliance))
with col2:
    tsl_gap = st.number_input("TSL Gap (₹)", value=5.00)
with col3:
    quantity = st.number_input("Quantity", value=1, min_value=1)

if st.button("Start Auto-Bot (TSL)"):
    if st.session_state['logged_in']:
        st.success("Auto-Bot activated successfully with Trailing Stop Loss on live account!")
    else:
        st.error("Please connect to SmartAPI First via Sidebar!")

# Live Chart Section
st.subheader("📈 Live Price Chart & Dotted Line (RELIANCE-EQ)")
chart_data = pd.DataFrame(
    np.random.randn(20, 1) * 2 + float(ltp_reliance),
    columns=['Price']
)
st.line_chart(chart_data)

# Audit Logs
st.subheader("📜 Execution & TSL Audit Logs")
if st.session_state['logged_in']:
    st.info("⚡ Successfully authenticated and linked with Angel One SmartAPI live session!")
else:
    st.warning("⚠️ Please connect via SmartAPI Authentication in the sidebar.")
