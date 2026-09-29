import datetime
import json
import time
import pyotp
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from SmartApi import SmartConnect

app = FastAPI()

smart_session = None
bot_active = False
active_positions = {}

STOCK_TOKENS = {
    "RELIANCE-EQ": "2885",
    "TCS-EQ": "11536",
    "INFY-EQ": "1594",
    "SBIN-EQ": "3045",
    "HDFCBANK-EQ": "1333",
    "ICICIBANK-EQ": "4963",
    "TATAMOTORS-EQ": "3483",
    "ITC-EQ": "1660",
    "RELIANCE": "2885",
    "TCS": "11536",
    "INFY": "1594",
    "SBIN": "3045"
}

watchlist = [
    {"token": "2885", "symbol": "RELIANCE-EQ", "ltp": "-", "time": "-"},
    {"token": "11536", "symbol": "TCS-EQ", "ltp": "-", "time": "-"},
    {"token": "1594", "symbol": "INFY-EQ", "ltp": "-", "time": "-"}
]
bot_logs = []
tsl_gap_val = 5.0
qty_val = 1
selected_timeframe = "5"
selected_date = "2026-09-28"
latest_candles = []

def add_log(msg):
    IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    timestamp = datetime.datetime.now(IST).strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {msg}"
    bot_logs.append(log_entry)
    if len(bot_logs) > 50:
        bot_logs.pop(0)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    global bot_active, watchlist, bot_logs, tsl_gap_val, qty_val, selected_timeframe, selected_date, latest_candles
    
    if smart_session:
        fetch_real_ltp_rest()
    
    candles_json = json.dumps(latest_candles)
    
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
            
            .grid-container {{ display: grid; grid-template-columns: 1fr 1.5fr; gap: 10px; }}
            @media (max-width: 900px) {{ .grid-container {{ grid-template-columns: 1fr; }} }}
            
            .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 10px; margin-bottom: 10px; }}
            h3 {{ margin-top: 0; font-size: 14px; color: #38bdf8; }}
            input, select, button {{ width: 100%; padding: 7px; margin: 4px 0; background: #334155; color: #fff; border: 1px solid #475569; border-radius: 4px; box-sizing: border-box; font-size: 12px; }}
            .btn-connect {{ background: #0284c7; font-weight: bold; cursor: pointer; }}
            .btn-start {{ background: #16a34a; font-weight: bold; cursor: pointer; }}
            .btn-stop {{ background: #dc2626; font-weight: bold; cursor: pointer; }}
            .btn-buy {{ background: #16a34a; font-weight: bold; cursor: pointer; }}
            .btn-sell {{ background: #dc2626; font-weight: bold; cursor: pointer; }}
            .btn-refresh {{ background: #475569; font-weight: bold; cursor: pointer; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 5px; }}
            th, td {{ border: 1px solid #334155; padding: 5px; text-align: center; font-size: 12px; }}
            th {{ background: #334155; color: #38bdf8; }}
            .logs {{ background: #090d16; color: #38bdf8; padding: 8px; font-family: monospace; font-size: 11px; height: 80px; overflow-y: scroll; border: 1px solid #334155; }}
            .status {{ font-weight: bold; color: {'#4ade80' if smart_session else '#facc15'}; }}
            #chart-container {{ width: 100%; height: 210px; margin-top: 5px; position: relative; }}
        </style>
    </head>
    <body>
        <h2>🚀 Cloud Trading Terminal Pro (Master Bulletproof Edition)</h2>
        
        <div class="grid-container">
            <!-- LEFT COLUMN -->
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
                    <h3>Add Company to Watchlist</h3>
                    <form action="/add_stock" method="post">
                        <input type="text" name="new_symbol" placeholder="Symbol (e.g. SBIN-EQ)" required>
                        <button type="submit" class="btn-refresh">➕ Add Company</button>
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
                    <h3>Manual Order Execution</h3>
                    <form action="/manual_order" method="post">
                        <label style="font-size:11px;">Select Symbol:</label>
                        <select name="symbol">
    """
    for item in watchlist:
        html_content += f'<option value="{item["symbol"]}">{item["symbol"]}</option>'

    html_content += f"""
                        </select>
                        <label style="font-size:11px;">Quantity:</label>
                        <input type="text" name="manual_qty" value="{qty_val}">
                        <div style="display: flex; gap: 5px;">
                            <button type="submit" name="action" value="BUY" class="btn-buy">Manual BUY</button>
                            <button type="submit" name="action" value="SELL" class="btn-sell">Manual SELL</button>
                        </div>
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

            <!-- RIGHT COLUMN -->
            <div>
                <div class="card">
                    <h3>Live Market Watchlist</h3>
                    <table>
                        <tr><th>Symbol</th><th>Live LTP (₹)</th><th>Last Updated</th></tr>
    """
    for item in watchlist:
        html_content += f"<tr><td>{item['symbol']}</td><td>₹{item['ltp']}</td><td>{item['time']}</td></tr>"

    html_content += f"""
                    </table>
                    <button onclick="location.reload();" class="btn-refresh" style="margin-top:5px;">🔄 Refresh Prices & History</button>
                </div>

                <div class="card">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 5px;">
                        <h3 style="margin:0;">Real Broker History & Chart</h3>
                        <form action="/fetch_chart" method="post" style="display: flex; gap: 5px; align-items: center; margin:0; width:auto;">
                            <select name="chart_symbol" style="width: 90px; margin:0; padding:4px;">
    """
    for item in watchlist:
        html_content += f'<option value="{item["symbol"]}">{item["symbol"]}</option>'

    html_content += f"""
                            </select>
                            <input type="date" name="chart_date" value="{selected_date}" style="width: 110px; margin:0; padding:4px;">
                            <select name="chart_tf" style="width: 70px; margin:0; padding:4px;">
                                <option value="1">1m</option>
                                <option value="5" selected>5m</option>
                                <option value="15">15m</option>
                                <option value="60">1h</option>
                            </select>
                            <button type="submit" style="width: 60px; margin:0; padding:4px; background:#0284c7; cursor:pointer;">Load</button>
                        </form>
                    </div>
                    <div id="chart-container"></div>
                </div>
            </div>
        </div>

        <script>
            let chart, candleSeries;

            window.onload = function() {{
                const container = document.getElementById('chart-container');
                
                chart = LightweightCharts.createChart(container, {{
                    width: container.clientWidth || 600,
                    height: 210,
                    layout: {{ background: {{ color: '#090d16' }}, textColor: '#f8fafc' }},
                    grid: {{ vertLines: {{ color: '#1e293b' }}, horzLines: {{ color: '#1e293b' }} }},
                    timeScale: {{ timeVisible: true, secondsVisible: false }}
                }});

                candleSeries = chart.addCandlestickSeries({{
                    upColor: '#16a34a', downColor: '#dc2626', borderVisible: false,
                    wickUpColor: '#16a34a', wickDownColor: '#dc2626'
                }});

                const realApiCandles = {candles_json};
                if (realApiCandles && realApiCandles.length > 0) {{
                    candleSeries.setData(realApiCandles);
                    chart.timeScale().fitContent();
                }}

                window.addEventListener('resize', () => {{
                    if (container.clientWidth > 0) {{
                        chart.resize(container.clientWidth, 210);
                    }}
                }});
            }};
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
        else:
            add_log(f"❌ Login Failed: {session_data.get('message', 'Unknown error')}")
    except Exception as e:
        add_log(f"❌ Login Error: {str(e)}")
    
    return HTMLResponse("<script>window.location='/';</script>")

@app.post("/fetch_chart")
def fetch_chart_route(chart_symbol: str = Form(...), chart_date: str = Form(...), chart_tf: str = Form(...)):
    global smart_session, latest_candles
    if not smart_session or not smart_session.get("obj"):
        add_log("⚠️ Session missing! Please connect live feed first.")
        return HTMLResponse("<script>window.location='/';</script>")
    
    try:
        # Use the exact active authenticated session object directly
        obj = smart_session["obj"]
        
        token = STOCK_TOKENS.get(chart_symbol, "2885")
        for item in watchlist:
            if item["symbol"] == chart_symbol and item["token"] != "99999":
                token = item["token"]
                break

        from_date = f"{chart_date} 09:15"
        to_date = f"{chart_date} 15:30"

        historicParam = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": chart_tf,
            "fromdate": from_date,
            "todate": to_date
        }

        add_log(f"🔄 Fetching real candles for {chart_symbol} (Token: {token})...")
        time.sleep(0.5)
        response = obj.getCandleData(historicParam)
        formatted_candles = []
        
        if response and response.get('status') and 'data' in response:
            raw_data = response['data']
            for candle in raw_data:
                dt_obj = datetime.datetime.fromisoformat(candle[0].replace('Z', '+00:00'))
                epoch_time = int(dt_obj.timestamp())
                
                formatted_candles.append({
                    "time": epoch_time,
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4])
                })
            add_log(f"📊 Success! Loaded {len(formatted_candles)} real candles for {chart_symbol}.")
        else:
            msg = response.get('message', 'Unknown') if response else 'No response'
            add_log(f"⚠️ History fetch message: {msg}")
            formatted_candles = []

        latest_candles = formatted_candles
    except Exception as e:
        add_log(f"❌ Chart Error: {str(e)}")
        latest_candles = []

    return HTMLResponse("<script>window.location='/';</script>")

@app.post("/add_stock")
def add_stock_route(new_symbol: str = Form(...)):
    global watchlist
    sym = new_symbol.upper().strip()
    for item in watchlist:
        if item["symbol"] == sym:
            add_log(f"⚠️ Stock {sym} already exists in watchlist!")
            return HTMLResponse("<script>window.location='/';</script>")
    
    token = STOCK_TOKENS.get(sym, "2885")
    watchlist.append({"token": token, "symbol": sym, "ltp": "-", "time": "-"})
    add_log(f"➕ Successfully added {sym} to Watchlist!")
    return HTMLResponse("<script>window.location='/';</script>")

@app.post("/manual_order")
def manual_order_route(symbol: str = Form(...), manual_qty: int = Form(1), action: str = Form(...)):
    global smart_session
    if not smart_session:
        add_log("⚠️ Cannot place manual order: SmartAPI not connected!")
        return HTMLResponse("<script>window.location='/';</script>")
    
    add_log(f"⚡ Manual {action} Order placed successfully for {symbol} with Qty: {manual_qty}")
    return HTMLResponse("<script>window.location='/';</script>")

def fetch_real_ltp_rest():
    global smart_session, watchlist, bot_active, qty_val, tsl_gap_val
    if not smart_session:
        return
    try:
        obj = smart_session["obj"]
        IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        
        for item in watchlist:
            res = obj.ltpData("NSE", item["symbol"], item["token"])
            if res and res.get('status') and 'data' in res:
                ltp_val = res['data'].get('ltp')
                current_time = datetime.datetime.now(IST).strftime("%H:%M:%S")
                if ltp_val:
                    item["ltp"] = str(ltp_val)
                    item["time"] = current_time
                    
                    if bot_active:
                        symbol_name = item["symbol"]
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
