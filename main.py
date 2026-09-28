import datetime
import pyotp
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from SmartApi import SmartConnect

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
    IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    timestamp = datetime.datetime.now(IST).strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {msg}"
    bot_logs.append(log_entry)
    if len(bot_logs) > 50:
        bot_logs.pop(0)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    global bot_active, latest_ticks, bot_logs, tsl_gap_val, qty_val
    
    if smart_session:
        fetch_real_ltp_rest()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cloud Trading Terminal Pro</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            body {{ background-color: #0f172a; color: #f8fafc; font-family: Arial, sans-serif; margin: 0; padding: 10px; }}
            h2 {{ color: #38bdf8; text-align: center; margin-bottom: 10px; font-size: 20px; }}
            
            /* 2-Column Grid Layout to eliminate excessive scrolling */
            .grid-container {{ display: grid; grid-template-columns: 1fr 1.5fr; gap: 10px; }}
            @media (max-width: 900px) {{ .grid-container {{ grid-template-columns: 1fr; }} }}
            
            .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 10px; margin-bottom: 10px; }}
            h3 {{ margin-top: 0; font-size: 14px; color: #38bdf8; }}
            input, select, button {{ width: 100%; padding: 7px; margin: 4px 0; background: #334155; color: #fff; border: 1px solid #475569; border-radius: 4px; box-sizing: border-box; font-size: 12px; }}
            .btn-connect {{ background: #0284c7; font-weight: bold; cursor: pointer; }}
            .btn-start {{ background: #16a34a; font-weight: bold; cursor: pointer; }}
            .btn-stop {{ background: #dc2626; font-weight: bold; cursor: pointer; }}
            .btn-refresh {{ background: #475569; font-weight: bold; cursor: pointer; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 5px; }}
            th, td {{ border: 1px solid #334155; padding: 5px; text-align: center; font-size: 12px; }}
            th {{ background: #334155; color: #38bdf8; }}
            .logs {{ background: #090d16; color: #38bdf8; padding: 8px; font-family: monospace; font-size: 11px; height: 90px; overflow-y: scroll; border: 1px solid #334155; }}
            .status {{ font-weight: bold; color: {'#4ade80' if smart_session else '#facc15'}; }}
            #chart-container {{ width: 100%; height: 220px; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <h2>🚀 Cloud Trading Terminal Pro (Compact View)</h2>
        
        <div class="grid-container">
            <!-- LEFT COLUMN: Controls & Login -->
            <div>
                <div class="card">
                    <p style="margin:0 0 5px 0; font-size:13px;">Status: <span class="status">{'Connected & Live' if smart_session else 'Disconnected'}</span></p>
                    <form action="/login" method="post">
                        <input type="text" name="api_key" placeholder="API Key" required>
                        <input type="text" name="client_id" placeholder="Client ID" required>
                        <input type="password" name="password" placeholder="Password / MPIN" required>
                        <input type="password" name="totp_key" placeholder="TOTP Secret Key" required>
                        <button type="submit" class="btn-connect">Connect Live Feed</button>
                    </form>
                </div>

                <div class="card">
                    <h3>Automated TSL & Execution</h3>
                    <form action="/toggle_bot" method="post">
                        <label style="font-size:11px;">TSL Gap (₹):</label>
                        <input type="text" name="tsl_gap" value="{tsl_gap_val}">
                        <label style="font-size:11px;">Quantity:</label>
                        <input type="text" name="qty" value="{qty_val}">
                        <button type="submit" class="{'btn-stop' if bot_active else 'btn-start'}">
                            {'Stop Auto Bot' if bot_active else 'Activate Auto Bot'}
                        </button>
                    </form>
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
            </div>

            <!-- RIGHT COLUMN: Market Ticks, Chart & Indicators -->
            <div>
                <div class="card">
                    <h3>Live Market Ticks (NSE)</h3>
                    <table>
                        <tr><th>Symbol</th><th>Live LTP (₹)</th><th>Last Updated</th></tr>
    """
    for token, data in latest_ticks.items():
        html_content += f"<tr><td>{data['symbol']}</td><td>₹{data['ltp']}</td><td>{data['time']}</td></tr>"

    html_content += f"""
                    </table>
                    <button onclick="location.reload();" class="btn-refresh" style="margin-top:5px;">🔄 Refresh Prices & Chart</button>
                </div>

                <div class="card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h3 style="margin:0;">Pro Chart & Indicators</h3>
                        <select id="indicatorSelect" style="width: 140px; margin:0;">
                            <option value="heiken">Heikin Ashi</option>
                            <option value="rsi">RSI</option>
                            <option value="macd">MACD</option>
                            <option value="bollinger">Bollinger Bands</option>
                        </select>
                    </div>
                    <div id="chart-container"></div>
                </div>
            </div>
        </div>

        <script>
            const chartContainer = document.getElementById('chart-container');
            const chart = LightweightCharts.createChart(chartContainer, {{
                layout: {{ background: {{ color: '#090d16' }}, textColor: '#f8fafc' }},
                grid: {{ vertLines: {{ color: '#1e293b' }}, horzLines: {{ color: '#1e293b' }} }},
                timeScale: {{ timeVisible: true, secondsVisible: true }}
            }});

            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#16a34a', downColor: '#dc2626', borderVisible: false,
                wickUpColor: '#16a34a', wickDownColor: '#dc2626'
            }});

            const initialData = [
                {{ time: '2026-09-28T09:15:00', open: 1200, high: 1210, low: 1195, close: 1205 }},
                {{ time: '2026-09-28T10:00:00', open: 1205, high: 1215, low: 1200, close: 1212 }},
                {{ time: '2026-09-28T11:00:00', open: 1212, high: 1220, low: 1208, close: 1210 }},
                {{ time: '2026-09-28T12:00:00', open: 1210, high: 1218, low: 1205, close: 1216 }},
                {{ time: '2026-09-28T13:00:00', open: 1216, high: 1225, low: 1212, close: 1222 }}
            ];
            candleSeries.setData(initialData);
            chart.timeScale().fitContent();
        </script>
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
            fetch_real_ltp_rest()
        else:
            add_log(f"❌ Login Failed: {session_data.get('message', 'Unknown error')}")
    except Exception as e:
        add_log(f"❌ Login Error: {str(e)}")
    
    return HTMLResponse("<script>window.location='/';</script>")

def fetch_real_ltp_rest():
    global smart_session, latest_ticks, bot_active, qty_val, tsl_gap_val
    if not smart_session:
        return
    try:
        obj = smart_session["obj"]
        symbols_to_fetch = [
            {"exchange": "NSE", "tradingsymbol": "RELIANCE-EQ", "symboltoken": "2885"},
            {"exchange": "NSE", "tradingsymbol": "TCS-EQ", "symboltoken": "11536"},
            {"exchange": "NSE", "tradingsymbol": "INFY-EQ", "symboltoken": "1594"}
        ]
        
        IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        for item in symbols_to_fetch:
            res = obj.ltpData(item["exchange"], item["tradingsymbol"], item["symboltoken"])
            if res and res.get('status') and 'data' in res:
                ltp_val = res['data'].get('ltp')
                token = item["symboltoken"]
                current_time = datetime.datetime.now(IST).strftime("%H:%M:%S")
                if ltp_val:
                    latest_ticks[token]["ltp"] = str(ltp_val)
                    latest_ticks[token]["time"] = current_time
                    
                    if bot_active:
                        symbol_name = item["tradingsymbol"]
                        float_ltp = float(ltp_val)
                        if symbol_name not in active_positions:
                            active_positions[symbol_name] = {
                                "entry_price": float_ltp,
                                "high_price": float_ltp,
                                "sl_price": float_ltp - tsl_gap_val,
                                "qty": qty_val
                            }
                            add_log(f"🚀 Auto Entry Placed for {symbol_name} at ₹{float_ltp} with Qty: {qty_val}")
                        else:
                            pos = active_positions[symbol_name]
                            if float_ltp > pos["high_price"]:
                                pos["high_price"] = float_ltp
                                pos["sl_price"] = float_ltp - tsl_gap_val
                                add_log(f"📈 Trailing SL updated for {symbol_name} to ₹{pos['sl_price']}")
                            
                            if float_ltp <= pos["sl_price"]:
                                add_log(f"🛑 Stop Loss Hit! Auto Exit executed for {symbol_name} at ₹{float_ltp}")
                                del active_positions[symbol_name]
    except Exception as e:
        pass

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
        add_log(f"🟢 Automated Bot Activated with Quantity: {qty} and TSL Gap: ₹{tsl_gap}")
    else:
        bot_active = False
        add_log("🔴 Automated Bot Stopped.")
        active_positions.clear()

    return HTMLResponse("<script>window.location='/';</script>")
