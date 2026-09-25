import datetime
import threading
import pyotp
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

app = FastAPI()

# Global variables for session and bot state
smart_session = None
bot_active = False
active_positions = {}
latest_ticks = {
    "2885": {"symbol": "RELIANCE-EQ", "ltp": "-", "time": "-"},
    "11536": {"symbol": "TCS-EQ", "ltp": "-", "time": "-"},
    "1594": {"symbol": "INFY-EQ", "ltp": "-", "time": "-"}
}
bot_logs = []
tsl_gap_val = 5.0
qty_val = 1

def add_log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {msg}"
    bot_logs.append(log_entry)
    if len(bot_logs) > 50:
        bot_logs.pop(0)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    global bot_active, latest_ticks, bot_logs, tsl_gap_val, qty_val
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cloud Trading Bot Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ background-color: #0f172a; color: #f8fafc; font-family: Arial, sans-serif; margin: 0; padding: 15px; }}
            h2 {{ color: #38bdf8; text-align: center; }}
            .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 15px; margin-bottom: 15px; }}
            input, button {{ width: 100%; padding: 10px; margin: 5px 0; background: #334155; color: #fff; border: 1px solid #475569; border-radius: 4px; box-sizing: border-box; }}
            .btn-connect {{ background: #0284c7; font-weight: bold; cursor: pointer; }}
            .btn-start {{ background: #16a34a; font-weight: bold; cursor: pointer; }}
            .btn-stop {{ background: #dc2626; font-weight: bold; cursor: pointer; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #334155; padding: 8px; text-align: center; font-size: 14px; }}
            th {{ background: #334155; color: #38bdf8; }}
            .logs {{ background: #090d16; color: #38bdf8; padding: 10px; font-family: monospace; font-size: 11px; height: 150px; overflow-y: scroll; border: 1px solid #334155; }}
            .status {{ font-weight: bold; color: {'#4ade80' if smart_session else '#facc15'}; }}
        </style>
    </head>
    <body>
        <h2>🚀 Cloud Trading Bot Dashboard</h2>
        <div class="card">
            <p>Status: <span class="status">{'Connected & Running' if smart_session else 'Disconnected'}</span></p>
            <form action="/login" method="post">
                <input type="text" name="api_key" placeholder="API Key" required>
                <input type="text" name="client_id" placeholder="Client ID" required>
                <input type="password" name="password" placeholder="Password / MPIN" required>
                <input type="password" name="totp_key" placeholder="TOTP Secret Key" required>
                <button type="submit" class="btn-connect">Connect Live Feed</button>
            </form>
        </div>

        <div class="card">
            <h3>Trailing Stop Loss (TSL) Control</h3>
            <form action="/toggle_bot" method="post">
                <label>TSL Gap (₹):</label>
                <input type="text" name="tsl_gap" value="{tsl_gap_val}">
                <label>Quantity:</label>
                <input type="text" name="qty" value="{qty_val}">
                <button type="submit" class="{'btn-stop' if bot_active else 'btn-start'}">
                    {'Stop TSL Bot' if bot_active else 'Activate TSL Bot'}
                </button>
            </form>
        </div>

        <div class="card">
            <h3>Live Market Ticks (NSE)</h3>
            <table>
                <tr><th>Symbol</th><th>Live LTP (₹)</th><th>Last Updated</th></tr>
    """
    for token, data in latest_ticks.items():
        html_content += f"<tr><td>{data['symbol']}</td><td>₹{data['ltp']}</td><td>{data['time']}</td></tr>"

    html_content += f"""
            </table>
        </div>

        <div class="card">
            <h3>Execution & Bot Logs</h3>
            <div class="logs">
    """
    for log in reversed(bot_logs):
        html_content += f"{log}<br>"

    html_content += f"""
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.post("/login")
def login_route(api_key: str = Form(...), client_id: str = Form(...), password: str = Form(...), totp_key: str = Form(...)):
    global smart_session
    try:
        obj = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_key).now()
        session_data = obj.generateSession(client_id, password, totp)

        if session_data and session_data.get('status'):
            jwt_token = session_data['data']['jwtToken']
            feed_token = obj.getfeedToken()
            smart_session = {"obj": obj, "jwt": jwt_token, "feed": feed_token, "client": client_id, "key": api_key}
            add_log("⚡ Successfully authenticated with Angel One SmartAPI!")
            
            # Fetch real LTP via REST API immediately
            fetch_real_ltp_rest()

            # Start WebSocket in background thread for live streaming
            threading.Thread(target=start_angel_websocket, daemon=True).start()
        else:
            add_log(f"❌ Login Failed: {session_data.get('message', 'Unknown error')}")
    except Exception as e:
        add_log(f"❌ Login Error: {str(e)}")
    
    return HTMLResponse("<script>window.location='/';</script>")

def fetch_real_ltp_rest():
    global smart_session, latest_ticks
    if not smart_session:
        return
    try:
        obj = smart_session["obj"]
        symbols_to_fetch = [
            {"exchange": "NSE", "tradingsymbol": "RELIANCE-EQ", "symboltoken": "2885"},
            {"exchange": "NSE", "tradingsymbol": "TCS-EQ", "symboltoken": "11536"},
            {"exchange": "NSE", "tradingsymbol": "INFY-EQ", "symboltoken": "1594"}
        ]
        
        for item in symbols_to_fetch:
            res = obj.ltpData(item["exchange"], item["tradingsymbol"], item["symboltoken"])
            if res and res.get('status') and 'data' in res:
                ltp_val = res['data'].get('ltp')
                token = item["symboltoken"]
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                if ltp_val:
                    latest_ticks[token]["ltp"] = str(ltp_val)
                    latest_ticks[token]["time"] = current_time
        add_log("📊 Real LTP fetched successfully via Angel One REST API!")
    except Exception as e:
        add_log(f"❌ REST LTP Fetch Error: {str(e)}")

@app.post("/toggle_bot")
def toggle_bot_route(tsl_gap: float = Form(5.0), qty: int = Form(1)):
    global bot_active, smart_session, active_positions, tsl_gap_val, qty_val
    tsl_gap_val = tsl_gap
    qty_val = qty

    if not smart_session:
        add_log("⚠️ Cannot start bot: SmartAPI not connected!")
        return HTMLResponse("<script>window.location='/';</script>")

    if not bot_active:
        bot_active = True
        add_log("🟢 TSL Bot Engine Activated via Cloud Dashboard!")
        active_positions["2885"] = {
            "symbol": "RELIANCE-EQ",
            "quantity": qty_val,
            "highest_price": 1240.0,
            "current_sl": 1240.0 - tsl_gap_val,
            "tsl_value": tsl_gap_val
        }
    else:
        bot_active = False
        add_log("🔴 TSL Bot Engine Stopped.")
        active_positions.clear()

    return HTMLResponse("<script>window.location='/';</script>")

def start_angel_websocket():
    global smart_session
    if not smart_session:
        return
    try:
        sws = SmartWebSocketV2(
            smart_session["jwt"], 
            smart_session["key"], 
            smart_session["client"], 
            smart_session["feed"]
        )
        
        def on_open(ws):
            token_list = [{"exchangeType": 1, "tokens": ["2885", "11536", "1594"]}]
            sws.subscribe(correlation_id="cloud_bot", mode=1, token_list=token_list)
            add_log("📡 Subscribed to live market data feed (NSE) on Cloud.")
            
        def on_data(ws, message):
            token = str(message.get('token'))
            ltp = message.get('last_traded_price')
            
            if token and ltp:
                actual_ltp = float(ltp) / 100.0 if float(ltp) > 100000 else float(ltp)
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                if token in latest_ticks:
                    latest_ticks[token]["ltp"] = str(actual_ltp)
                    latest_ticks[token]["time"] = current_time

                if bot_active:
                    process_trailing_stop_loss(token, actual_ltp)

        sws.on_open = on_open
        sws.on_data = on_data
        sws.connect()
    except Exception as e:
        add_log(f"❌ WebSocket Error: {str(e)}")

def process_trailing_stop_loss(token, current_ltp):
    global active_positions
    if token in active_positions:
        pos = active_positions[token]
        if current_ltp > pos["highest_price"]:
            active_positions[token]["highest_price"] = current_ltp
            active_positions[token]["current_sl"] = current_ltp - pos["tsl_value"]
            add_log(f"📈 TSL Trail [{token}]: Peak ₹{current_ltp} | New SL: ₹{active_positions[token]['current_sl']}")

        if current_ltp <= active_positions[token]["current_sl"]:
            add_log(f"🚨 TSL HIT [{token}] at ₹{current_ltp}! Executing Real Exit Order...")
            execute_real_order(pos["symbol"], token, "SELL", pos["quantity"])
            del active_positions[token]

def execute_real_order(symbol, token, transaction_type, quantity):
    global smart_session
    if not smart_session:
        return
    try:
        obj = smart_session["obj"]
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": transaction_type,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "DELIVERY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(quantity)
        }
        order_id = obj.placeOrder(orderparams)
        add_log(f"⚡ REAL {transaction_type} ORDER PLACED! ID: {order_id}")
    except Exception as e:
        add_log(f"❌ Order Execution Failed: {str(e)}")
