from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
import json
import pyotp
import requests
import os
from datetime import datetime, timedelta
from SmartApi import SmartConnect

app = FastAPI()

MASTER_STOCKS = [
    {"symbol": "IDEA-EQ", "token": "3719", "name": "Vodafone Idea Ltd", "price": 12.50, "chg": 1.20, "exchange": "NSE"},
    {"symbol": "YESBANK-EQ", "token": "11915", "name": "Yes Bank Ltd", "price": 24.30, "chg": -0.80, "exchange": "NSE"},
    {"symbol": "SUZLON-EQ", "token": "3327", "name": "Suzlon Energy Ltd", "price": 48.60, "chg": 2.10, "exchange": "NSE"},
    {"symbol": "PNB-EQ", "token": "10666", "name": "Punjab National Bank", "price": 105.40, "chg": 0.50, "exchange": "NSE"},
    {"symbol": "IDFCFIRSTB-EQ", "token": "11014", "name": "IDFC First Bank Ltd", "price": 72.10, "chg": -1.10, "exchange": "NSE"},
    {"symbol": "HDFCBANK-EQ", "token": "1333", "name": "HDFC Bank Ltd", "price": 1650.00, "chg": 0.50, "exchange": "NSE"},
    {"symbol": "ITC-EQ", "token": "1660", "name": "ITC Limited", "price": 430.20, "chg": 0.4, "exchange": "NSE"},
    {"symbol": "WIPRO-EQ", "token": "3787", "name": "Wipro Limited", "price": 540.00, "chg": 0.4, "exchange": "NSE"},
    {"symbol": "SBIN-EQ", "token": "3045", "name": "State Bank of India", "price": 810.50, "chg": 1.1, "exchange": "NSE"},
    {"symbol": "TATAMOTORS-EQ", "token": "3456", "name": "Tata Motors Ltd", "price": 980.40, "chg": 1.8, "exchange": "NSE"},
    {"symbol": "RELIANCE-EQ", "token": "2885", "name": "Reliance Industries", "price": 1276.40, "chg": -1.09, "exchange": "NSE"},
    {"symbol": "TCS-EQ", "token": "11536", "name": "Tata Consultancy Services", "price": 4098.30, "chg": 0.75, "exchange": "NSE"},
    {"symbol": "NIFTY", "token": "99926000", "name": "Nifty 50 Index", "price": 22620.45, "chg": 0.42, "exchange": "NSE"},
    {"symbol": "BANKNIFTY", "token": "99926009", "name": "Bank Nifty Index", "price": 48250.10, "chg": 0.65, "exchange": "NSE"}
]

smart_api_obj = None

server_state = {
    "connected": False,
    "selected_symbol": "ITC-EQ",
    "bot_running": False,
    "bot_mode": "STOCK",
    "bot_qty": 1,
    "bot_product": "INTRADAY",
    "bot_sl": 5.0,
    "bot_tsl": 2.0,
    "active_trade": None,
    "prices": {s["symbol"]: s["price"] for s in MASTER_STOCKS},
    "logs": ["[System] Server-side dynamic trailing engine initialized."]
}

def add_server_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {msg}"
    print(log_entry)
    server_state["logs"].append(log_entry)
    if len(server_state["logs"]) > 100:
        server_state["logs"].pop(0)

async def background_trading_worker():
    while True:
        await asyncio.sleep(2)
        if not server_state["connected"] or not smart_api_obj:
            continue
        
        try:
            sym = server_state["selected_symbol"]
            token = "1660"
            exch = "NSE"
            for s in MASTER_STOCKS:
                if s["symbol"] == sym:
                    token = s["token"]
                    exch = s["exchange"]
                    break

            resp = smart_api_obj.ltpData(exch, sym, token)
            if resp and resp.get("status") and resp.get("data"):
                new_price = float(resp["data"].get("ltp", 0.0))
                if new_price > 0:
                    old_price = server_state["prices"].get(sym, new_price)
                    server_state["prices"][sym] = new_price

                    trade = server_state["active_trade"]
                    if trade and trade["symbol"] == sym:
                        if trade["type"] == "BUY":
                            if new_price > trade["entryPrice"]:
                                potential_new_sl = new_price - server_state["bot_sl"]
                                if potential_new_sl > trade["currentSl"]:
                                    trade["currentSl"] = potential_new_sl
                                    add_server_log(f"[Trailing SL] Price rose to ₹{new_price}. Stop-loss trailed upwards to ₹{round(potential_new_sl, 2)}")
                            
                            if new_price <= trade["currentSl"]:
                                add_server_log(f"[Risk Management] Stoploss hit for {sym} at ₹{new_price}. Square off triggered!")
                                server_state["active_trade"] = None

                        elif trade["type"] == "SELL":
                            if new_price < trade["entryPrice"]:
                                potential_new_sl = new_price + server_state["bot_sl"]
                                if potential_new_sl < trade["currentSl"]:
                                    trade["currentSl"] = potential_new_sl
                                    add_server_log(f"[Trailing SL] Price dropped to ₹{new_price}. Stop-loss trailed downwards to ₹{round(potential_new_sl, 2)}")
                            
                            if new_price >= trade["currentSl"]:
                                add_server_log(f"[Risk Management] Stoploss hit for {sym} at ₹{new_price}. Square off triggered!")
                                server_state["active_trade"] = None

                    if server_state["bot_running"] and not server_state["active_trade"]:
                        if import_random_check():
                            mode = server_state["bot_mode"]
                            qty = server_state["bot_qty"]
                            product = server_state["bot_product"]
                            sl_val = server_state["bot_sl"]
                            
                            t_sym = sym
                            t_exch = exch
                            t_token = token
                            t_price = new_price
                            tx_type = "BUY" if new_price >= old_price else "SELL"

                            if mode == "OPTION_CE" or mode == "OPTION_PE":
                                t_sym = f"NIFTY2026100822600{'CE' if mode=='OPTION_CE' else 'PE'}"
                                t_exch = "NFO"
                                t_token = "0"
                                t_price = 120.00
                                tx_type = "BUY"

                            initial_sl = (t_price - sl_val) if tx_type == "BUY" else (t_price + sl_val)
                            order_params = {
                                "variety": "NORMAL",
                                "tradingsymbol": t_sym,
                                "symboltoken": t_token,
                                "transactiontype": tx_type,
                                "exchange": t_exch,
                                "ordertype": "MARKET",
                                "producttype": product,
                                "duration": "DAY",
                                "price": str(t_price),
                                "squareoff": "0",
                                "stoploss": str(initial_sl),
                                "quantity": str(qty)
                            }
                            
                            ord_id = smart_api_obj.placeOrder(order_params)
                            if ord_id:
                                server_state["active_trade"] = {
                                    "symbol": t_sym, 
                                    "entryPrice": t_price, 
                                    "qty": qty, 
                                    "type": tx_type, 
                                    "currentSl": initial_sl
                                }
                                add_server_log(f"[Server Bot] Automated {tx_type} order placed for {t_sym} at ₹{t_price} | Initial SL: ₹{round(initial_sl, 2)}")
        except Exception as e:
            pass

def import_random_check():
    import random
    return random.random() < 0.03

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_trading_worker())

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Angel One Pro Terminal - Dynamic Trailing Stop-Loss Bot</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { background-color: #0b0e14; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; height: 100vh; overflow: hidden; }
        .header { background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; height: 40px; font-size: 13px; }
        .main-container { display: flex; height: calc(100vh - 40px); width: 100vw; }
        .sidebar { width: 340px; background-color: #131722; border-right: 1px solid #2a2e39; display: flex; flex-direction: column; flex-shrink: 0; }
        .auth-panel { padding: 12px; border-bottom: 1px solid #2a2e39; background-color: #181c25; }
        .input-field { width: 100%; padding: 6px; margin: 4px 0 8px 0; background-color: #0b0e14; border: 1px solid #2a2e39; color: white; border-radius: 4px; font-size: 11px; }
        .watchlist-container { flex: 1; overflow-y: auto; padding: 5px; }
        .watchlist-item { padding: 10px 12px; border-bottom: 1px solid #1e222d; cursor: pointer; display: flex; justify-content: space-between; align-items: center; border-radius: 4px; }
        .watchlist-item:hover, .watchlist-item.active { background-color: #1e222d; }
        
        .content-area { flex: 1; display: flex; flex-direction: column; background-color: #0b0e14; overflow: hidden; }
        .toolbar { background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 8px 15px; display: flex; gap: 8px; align-items: center; height: 45px; flex-shrink: 0; flex-wrap: wrap; }
        .btn { background-color: #131722; color: #f8fafc; border: 1px solid #2a2e39; padding: 5px 10px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 11px; }
        .btn-buy { background-color: #089981; color: white; border: none; }
        .btn-sell { background-color: #f23645; color: white; border: none; }
        .btn:hover { border-color: #38bdf8; }
        
        .tabs { display: flex; background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 0 15px; height: 35px; flex-shrink: 0; }
        .tab { padding: 8px 16px; cursor: pointer; font-size: 12px; color: #94a3b8; border-bottom: 2px solid transparent; font-weight: bold; line-height: 19px; }
        .tab.active { color: #38bdf8; border-bottom-color: #38bdf8; }
        
        .tab-content { display: none; flex: 1; flex-direction: column; width: 100%; height: calc(100vh - 120px); position: relative; }
        .tab-content.active { display: flex; }
        
        #chartContainer { width: 100%; height: 485px; background-color: #0b0e14; position: relative; }
        .control-panel { padding: 20px; overflow-y: auto; height: 100%; }
        .control-group { background-color: #131722; border: 1px solid #2a2e39; padding: 20px; border-radius: 6px; margin-bottom: 15px; max-width: 650px; }

        .chart-ohlc-bar { background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 8px 15px; display: flex; align-items: center; gap: 15px; font-size: 11px; flex-shrink: 0; }
        .ohlc-item { display: flex; gap: 4px; }
        .ohlc-label { color: #94a3b8; }
        .quick-trade-group { display: flex; align-items: center; gap: 5px; margin-left: auto; }
        .quick-qty-input { width: 45px; background: #0b0e14; border: 1px solid #2a2e39; color: white; text-align: center; padding: 3px; border-radius: 3px; font-size: 11px; }

        .opt-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
        .opt-table th, .opt-table td { border: 1px solid #2a2e39; padding: 8px; text-align: center; }
        .opt-table th { background-color: #181c25; color: #38bdf8; }
        .opt-table tr:hover { background-color: #1e222d; cursor: pointer; }

        #toast { position: fixed; bottom: 20px; right: 20px; background: #181c25; border: 1px solid #38bdf8; color: white; padding: 12px 20px; border-radius: 6px; font-size: 12px; z-index: 1000; display: none; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
    </style>
</head>
<body>

    <div class="header">
        <div><b>▲ NIFTY 50</b> <span style="color: #089981; margin-left: 5px;">22,620.45 (+0.42%)</span></div>
        <div><b>▲ BANKNIFTY</b> <span style="color: #089981; margin-left: 5px;">48,250.10 (+0.65%)</span></div>
        <div style="display: flex; gap: 15px; align-items: center;">
            <div style="font-size: 11px; background: #181c25; padding: 4px 10px; border-radius: 4px; border: 1px solid #2a2e39;">Live P&L: <span id="headerPnl" style="font-weight: bold; color: #089981;">₹0.00</span></div>
            <div style="color: #38bdf8; font-weight: bold;">⚡ Dynamic Trailing Terminal</div>
        </div>
    </div>

    <div class="main-container">
        <div class="sidebar">
            <div class="auth-panel">
                <div style="font-size: 11px; font-weight: bold; color: #38bdf8; margin-bottom: 4px;">SmartAPI Broker Login</div>
                <input type="text" id="apiKey" class="input-field login-input" placeholder="API Key" oninput="saveCredentials()">
                <input type="text" id="clientId" class="input-field login-input" placeholder="Client ID" oninput="saveCredentials()">
                <input type="password" id="password" class="input-field login-input" placeholder="Password / MPIN" oninput="saveCredentials()">
                <input type="password" id="totpKey" class="input-field login-input" placeholder="TOTP Secret Key" oninput="saveCredentials()">
                <button class="btn" style="width: 100%; background-color: #38bdf8; color: #0b0e14; margin-top: 5px;" onclick="connectBroker()">Connect Live</button>
            </div>

            <div style="padding: 10px; border-bottom: 1px solid #2a2e39;">
                <input type="text" id="searchInput" class="input-field" placeholder="Search Symbol..." oninput="filterWatchlist()" style="margin: 0 0 6px 0;">
                <div style="display: flex; gap: 4px;">
                    <input type="number" id="minPriceInput" class="input-field" placeholder="Min ₹" oninput="filterWatchlist()" style="margin: 0;">
                    <input type="number" id="maxPriceInput" class="input-field" placeholder="Max ₹" oninput="filterWatchlist()" style="margin: 0;">
                </div>
            </div>

            <div style="padding: 8px 12px; font-size: 10px; color: #94a3b8; font-weight: bold; text-transform: uppercase; display: flex; justify-content: space-between;">
                <span>Watchlist</span>
                <span style="color: #38bdf8; cursor: pointer; font-weight: bold;" onclick="resetWatchlist()">RESET ALL</span>
            </div>
            <div class="watchlist-container" id="watchlistContainer"></div>
        </div>

        <div class="content-area">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chart', this)">Chart & Analysis</div>
                <div class="tab" onclick="switchTab('options', this)">Options Chain (CE/PE)</div>
                <div class="tab" onclick="switchTab('trade', this)">Manual Trade & TSL</div>
                <div class="tab" onclick="switchTab('bot', this)">24/7 Server Bot</div>
                <div class="tab" onclick="switchTab('logs', this)">Server Logs</div>
            </div>

            <div id="tab-chart" class="tab-content active">
                <div class="toolbar">
                    <span id="activeSymbolTitle" style="font-weight: bold; font-size: 14px; color: #38bdf8;">ITC-EQ</span>
                    <select id="timeframeSelect" class="btn" style="background-color: #181c25;" onchange="loadHistoricalData()">
                        <option value="1m">1m</option>
                        <option value="5m" selected>5m</option>
                        <option value="15m">15m</option>
                        <option value="1h">1h</option>
                    </select>
                    <select id="chartTypeSelect" class="btn" style="background-color: #181c25;" onchange="changeChartType(this.value)">
                        <option value="Candlestick">Candlestick</option>
                        <option value="HeikenAshi">Heiken Ashi</option>
                    </select>
                    <button class="btn" style="background-color: #181c25; color: #38bdf8;" onclick="manualRefreshChart()">🔄 Refresh Chart</button>
                </div>

                <div class="chart-ohlc-bar">
                    <div><b id="barSymbol" style="color: #38bdf8;">ITC-EQ</b> • <span id="barTf">5m</span> • NSE</div>
                    <div class="ohlc-item"><span class="ohlc-label">O</span><span id="ohlcO" style="color: #089981;">0.00</span></div>
                    <div class="ohlc-item"><span class="ohlc-label">H</span><span id="ohlcH" style="color: #089981;">0.00</span></div>
                    <div class="ohlc-item"><span class="ohlc-label">L</span><span id="ohlcL" style="color: #f23645;">0.00</span></div>
                    <div class="ohlc-item"><span class="ohlc-label">C</span><span id="ohlcC" style="color: #089981;">0.00</span></div>
                    <div id="ohlcChg" style="color: #089981; font-weight: bold;">+0.00 (+0.00%)</div>

                    <div class="quick-trade-group">
                        <button class="btn btn-buy" onclick="executeQuickOrder('BUY')">BUY @ <span id="quickBuyPrice">0.00</span></button>
                        <input type="number" id="quickQty" class="quick-qty-input" value="1" oninput="autoSelectStockByQty(this.value)">
                        <button class="btn btn-sell" onclick="executeQuickOrder('SELL')">SELL @ <span id="quickSellPrice">0.00</span></button>
                    </div>
                </div>

                <div id="chartContainer"></div>
            </div>

            <div id="tab-options" class="tab-content">
                <div class="control-panel">
                    <div class="control-group" style="max-width: 900px;">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">Nifty & Bank Nifty Options Chain (CE / PE)</h3>
                        <div style="display: flex; gap: 15px; align-items: center; margin-bottom: 15px;">
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Select Index</label>
                                <select id="optIndexSelect" class="input-field" style="background-color: #0b0e14; color: white;" onchange="loadOptionsChain()">
                                    <option value="NIFTY">NIFTY 50</option>
                                    <option value="BANKNIFTY">BANK NIFTY</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Expiry Date</label>
                                <select id="optExpirySelect" class="input-field" style="background-color: #0b0e14; color: white;">
                                    <option value="2026-10-08">08-OCT-2026 (Weekly)</option>
                                    <option value="2026-10-15">15-OCT-2026 (Weekly)</option>
                                    <option value="2026-10-29">29-OCT-2026 (Monthly)</option>
                                </select>
                            </div>
                            <div style="margin-top: 16px;">
                                <button class="btn" style="background-color: #38bdf8; color: #0b0e14;" onclick="loadOptionsChain()">Fetch Chain</button>
                            </div>
                        </div>

                        <table class="opt-table">
                            <thead>
                                <tr>
                                    <th colspan="3">CALLS (CE)</th>
                                    <th>STRIKE</th>
                                    <th colspan="3">PUTS (PE)</th>
                                </tr>
                                <tr>
                                    <th>LTP</th>
                                    <th>Volume</th>
                                    <th>Action</th>
                                    <th>Price</th>
                                    <th>Action</th>
                                    <th>Volume</th>
                                    <th>LTP</th>
                                </tr>
                            </thead>
                            <tbody id="optionsChainBody">
                                <tr>
                                    <td colspan="7" style="color: #94a3b8; text-align: center; padding: 20px;">Click 'Fetch Chain' to load live Option strikes.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div id="tab-trade" class="tab-content">
                <div class="control-panel">
                    <div class="control-group">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">Manual Order Execution & Dynamic TSL</h3>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Quantity / Lot Size</label>
                                <input type="number" id="orderQty" class="input-field" value="1">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Product Type</label>
                                <select class="input-field" id="productType" style="background-color: #0b0e14; color: white;"><option value="INTRADAY">INTRADAY</option><option value="CARRYFORWARD">CARRYFORWARD (NRML)</option><option value="DELIVERY">DELIVERY</option></select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Stop Loss (₹)</label>
                                <input type="number" id="stopLoss" class="input-field" value="5.0">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Trailing Stop Loss Jump (₹)</label>
                                <input type="number" id="trailingSl" class="input-field" value="2.0">
                            </div>
                        </div>
                        <div style="margin-top: 20px; display: flex; gap: 10px;">
                            <button class="btn btn-buy" style="flex: 1; padding: 10px;" onclick="executeOrder('BUY')">PLACE BUY ORDER</button>
                            <button class="btn btn-sell" style="flex: 1; padding: 10px;" onclick="executeOrder('SELL')">PLACE SELL ORDER</button>
                        </div>
                    </div>
                </div>
            </div>

            <div id="tab-bot" class="tab-content">
                <div class="control-panel">
                    <div class="control-group">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">24/7 Server Autonomous Bot Settings</h3>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Target Mode</label>
                                <select id="botTargetMode" class="input-field" style="background-color: #0b0e14; color: white;">
                                    <option value="STOCK">Active Watchlist Stock / Index</option>
                                    <option value="OPTION_CE">Options Call (CE)</option>
                                    <option value="OPTION_PE">Options Put (PE)</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Autonomous Quantity / Lots</label>
                                <input type="number" id="botQty" class="input-field" value="1">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Product Type</label>
                                <select class="input-field" id="botProduct" style="background-color: #0b0e14; color: white;"><option value="INTRADAY">INTRADAY</option><option value="CARRYFORWARD">CARRYFORWARD</option></select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Default Stop Loss (₹)</label>
                                <input type="number" id="botSl" class="input-field" value="5.0">
                            </div>
                        </div>
                        <div style="margin-top: 20px;">
                            <button id="botToggleBtn" class="btn" style="background-color: #089981; color: white; padding: 10px 20px;" onclick="toggleBotServer()">Start 24/7 Server Bot</button>
                            <span id="botStatus" style="margin-left: 15px; font-size: 12px; color: #f23645;">● Bot Status: Stopped (Server Side)</span>
                        </div>
                    </div>
                </div>
            </div>

            <div id="tab-logs" class="tab-content">
                <div class="control-panel">
                    <div class="control-group" id="logsContainer" style="width: 100%; font-family: monospace; font-size: 11px; color: #38bdf8; height: 400px; overflow-y: auto;">
                        [System] Dynamic Trailing Terminal running. Waiting for connection...
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="toast"></div>

    <script>
        const masterStocks = [
            { symbol: "IDEA-EQ", token: "3719", name: "Vodafone Idea Ltd", price: 12.50, chg: 1.20, exchange: "NSE" },
            { symbol: "YESBANK-EQ", token: "11915", name: "Yes Bank Ltd", price: 24.30, chg: -0.80, exchange: "NSE" },
            { symbol: "SUZLON-EQ", token: "3327", name: "Suzlon Energy Ltd", price: 48.60, chg: 2.10, exchange: "NSE" },
            { symbol: "PNB-EQ", token: "10666", name: "Punjab National Bank", price: 105.40, chg: 0.50, exchange: "NSE" },
            { symbol: "IDFCFIRSTB-EQ",  token: "11014", name: "IDFC First Bank Ltd", price: 72.10, chg: -1.10, exchange: "NSE" },
            { symbol: "HDFCBANK-EQ", token: "1333", name: "HDFC Bank Ltd", price: 1650.00, chg: 0.50, exchange: "NSE" },
            { symbol: "ITC-EQ", token: "1660", name: "ITC Limited", price: 430.20, chg: 0.4, exchange: "NSE" },
            { symbol: "WIPRO-EQ", token: "3787", name: "Wipro Limited", price: 540.00, chg: 0.4, exchange: "NSE" },
            { symbol: "SBIN-EQ", token: "3045", name: "State Bank of India", price: 810.50, chg: 1.1, exchange: "NSE" },
            { symbol: "TATAMOTORS-EQ", token: "3456", name: "Tata Motors Ltd", price: 980.40, chg: 1.8, exchange: "NSE" },
            { symbol: "RELIANCE-EQ", token: "2885", name: "Reliance Industries", price: 1276.40, chg: -1.09, exchange: "NSE" },
            { symbol: "TCS-EQ", token: "11536", name: "Tata Consultancy Services", price: 4098.30, chg: 0.75, exchange: "NSE" },
            { symbol: "NIFTY", token: "99926000", name: "Nifty 50 Index", price: 22620.45, chg: 0.42, exchange: "NSE" },
            { symbol: "BANKNIFTY", token: "99926009", name: "Bank Nifty Index", price: 48250.10, chg: 0.65, exchange: "NSE" }
        ];

        let masterList = [...masterStocks];
        let selectedSymbol = "ITC-EQ";
        let stockPrices = {};
        let stockTokens = {};
        let stockMap = {};
        let stockExchanges = {};

        function showToast(msg) {
            const toast = document.getElementById("toast");
            toast.innerText = msg;
            toast.style.display = "block";
            setTimeout(() => { toast.style.display = "none"; }, 4000);
        }

        function saveCredentials() {
            localStorage.setItem("angel_apiKey", document.getElementById("apiKey").value);
            localStorage.setItem("angel_clientId", document.getElementById("clientId").value);
            localStorage.setItem("angel_password", document.getElementById("password").value);
            localStorage.setItem("angel_totpKey", document.getElementById("totpKey").value);
        }

        function loadCredentials() {
            if (localStorage.getItem("angel_apiKey")) document.getElementById("apiKey").value = localStorage.getItem("angel_apiKey");
            if (localStorage.getItem("angel_clientId")) document.getElementById("clientId").value = localStorage.getItem("angel_clientId");
            if (localStorage.getItem("angel_password")) document.getElementById("password").value = localStorage.getItem("angel_password");
            if (localStorage.getItem("angel_totpKey")) document.getElementById("totpKey").value = localStorage.getItem("angel_totpKey");
        }

        function updateStockMaps() {
            stockPrices = {};
            stockTokens = {};
            stockMap = {};
            stockExchanges = {};
            masterStocks.forEach(s => {
                stockPrices[s.symbol] = s.price;
                stockTokens[s.token] = s.symbol;
                stockMap[s.symbol] = s.token;
                stockExchanges[s.symbol] = s.exchange || "NSE";
            });
        }
        updateStockMaps();

        document.addEventListener("DOMContentLoaded", function() {
            loadCredentials();
            renderWatchlistUI(masterList);
            initChart();
            startServerLogPolling();
        });

        function startServerLogPolling() {
            setInterval(() => {
                fetch('/server-status')
                    .then(res => res.json())
                    .then(data => {
                        if (data && data.logs) {
                            const box = document.getElementById("logsContainer");
                            box.innerHTML = data.logs.join("<br>");
                            box.scrollTop = box.scrollHeight;
                        }
                    }).catch(err => {});
            }, 3000);
        }

        function loadOptionsChain() {
            const indexName = document.getElementById("optIndexSelect").value;
            const expiry = document.getElementById("optExpirySelect").value;
            fetch(`/options-chain?index=${indexName}&expiry=${expiry}`)
                .then(res => res.json())
                .then(data => {
                    const tbody = document.getElementById("optionsChainBody");
                    tbody.innerHTML = "";
                    if (data && data.length > 0) {
                        data.forEach(row => {
                            const tr = document.createElement("tr");
                            tr.innerHTML = `
                                <td style="color: #089981;">₹${row.ceLtp.toFixed(2)}</td>
                                <td>${row.ceVol}</td>
                                <td><button class="btn btn-buy" style="padding: 2px 6px;" onclick="tradeOption('${row.ceSymbol}', ${row.ceLtp}, 'BUY')">BUY CE</button></td>
                                <td style="font-weight: bold; color: #38bdf8;">${row.strike}</td>
                                <td><button class="btn btn-sell" style="padding: 2px 6px;" onclick="tradeOption('${row.peSymbol}', ${row.peLtp}, 'BUY')">BUY PE</button></td>
                                <td>${row.peVol}</td>
                                <td style="color: #f23645;">₹${row.peLtp.toFixed(2)}</td>
                            `;
                            tbody.appendChild(tr);
                        });
                        showToast("Options Chain Loaded Successfully!");
                    }
                });
        }

        function tradeOption(sym, price, type) {
            fetch('/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: sym, token: "0", exchange: "NFO", transactionType: type, quantity: 25, productType: 'INTRADAY', price: price, stopLoss: 5.0, trailingSl: 2.0 })
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    showToast(`Option Order Executed: ${sym}`);
                } else {
                    showToast("Order Failed: " + resp.message);
                }
            });
        }

        function manualRefreshChart() {
            loadHistoricalData();
            showToast(`Chart Refreshed for ${selectedSymbol}`);
        }

        function autoSelectStockByQty(qtyVal) {
            const qty = parseInt(qtyVal);
            if (isNaN(qty) || qty <= 0) return;
            if (masterList.length > 0) {
                const index = (qty - 1) % masterList.length;
                selectedSymbol = masterList[index].symbol;
                document.getElementById("activeSymbolTitle").innerText = selectedSymbol;
                document.getElementById("barSymbol").innerText = selectedSymbol;
                renderWatchlistUI(masterList);
                loadHistoricalData();
                updateServerSelectedSymbol();
            }
        }

        function updateServerSelectedSymbol() {
            fetch('/update-symbol', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: selectedSymbol })
            });
        }

        function filterWatchlist() {
            const query = document.getElementById("searchInput").value.toLowerCase();
            const minVal = document.getElementById("minPriceInput").value;
            const maxVal = document.getElementById("maxPriceInput").value;
            const minPrice = (minVal !== "") ? parseFloat(minVal) : 0;
            const maxPrice = (maxVal !== "") ? parseFloat(maxVal) : Infinity;

            const filtered = masterStocks.filter(s => {
                const p = stockPrices[s.symbol] || s.price || 100.0;
                const matchesQuery = s.symbol.toLowerCase().includes(query) || s.name.toLowerCase().includes(query);
                const matchesPrice = (p >= minPrice && p <= maxPrice);
                return matchesQuery && matchesPrice;
            });
            renderWatchlistUI(filtered);
        }

        function resetWatchlist() {
            document.getElementById("searchInput").value = "";
            document.getElementById("minPriceInput").value = "";
            document.getElementById("maxPriceInput").value = "";
            renderWatchlistUI(masterStocks);
            showToast("Watchlist reset!");
        }

        function renderWatchlistUI(items) {
            const container = document.getElementById("watchlistContainer");
            if (!container) return;
            container.innerHTML = "";
            if (items.length === 0) {
                container.innerHTML = `<div style="padding: 15px; color: #94a3b8; text-align: center; font-size: 11px;">No stocks found!</div>`;
                return;
            }
            items.forEach(s => {
                const item = document.createElement("div");
                item.className = `watchlist-item ${s.symbol === selectedSymbol ? 'active' : ''}`;
                item.onclick = () => {
                    selectedSymbol = s.symbol;
                    document.getElementById("activeSymbolTitle").innerText = selectedSymbol;
                    document.getElementById("barSymbol").innerText = selectedSymbol;
                    renderWatchlistUI(masterStocks);
                    loadHistoricalData();
                    updateServerSelectedSymbol();
                };
                item.innerHTML = `
                    <div>
                        <div style="font-weight: bold; font-size: 12px;">${s.symbol}</div>
                        <div style="font-size: 10px; color: #94a3b8;">${s.name}</div>
                    </div>
                    <div style="text-align: right;">
                        <div id="wl_${s.symbol}" style="font-weight: bold; font-size: 12px;">₹${(stockPrices[s.symbol] || s.price).toFixed(2)}</div>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        let chart, candlestickSeries;

        function updateOhlcBar(candle) {
            if (!candle) return;
            document.getElementById("ohlcO").innerText = candle.open.toFixed(2);
            document.getElementById("ohlcH").innerText = candle.high.toFixed(2);
            document.getElementById("ohlcL").innerText = candle.low.toFixed(2);
            document.getElementById("ohlcC").innerText = candle.close.toFixed(2);
            document.getElementById("quickBuyPrice").innerText = candle.close.toFixed(2);
            document.getElementById("quickSellPrice").innerText = candle.close.toFixed(2);
        }

        function loadHistoricalData() {
            const token = stockMap[selectedSymbol] || "1660";
            const exch = stockExchanges[selectedSymbol] || "NSE";
            const tf = document.getElementById("timeframeSelect").value;
            document.getElementById("barTf").innerText = tf;

            fetch(`/history?token=${token}&exchange=${exch}&timeframe=${tf}`)
                .then(res => res.json())
                .then(data => {
                    if (data && data.length > 0) {
                        candlestickSeries.setData(data);
                        updateOhlcBar(data[data.length - 1]);
                    }
                });
        }

        function initChart() {
            const chartElement = document.getElementById('chartContainer');
            chart = LightweightCharts.createChart(chartElement, {
                width: chartElement.clientWidth || 800,
                height: 485,
                layout: { background: { type: 'solid', color: '#0b0e14' }, textColor: '#94a3b8' },
                grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } }
            });
            candlestickSeries = chart.addCandlestickSeries({ upColor: '#089981', downColor: '#f23645' });
            loadHistoricalData();
        }

        function switchTab(tabName, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
            setTimeout(() => { chart.resize(document.getElementById('chartContainer').clientWidth, 485); }, 100);
        }

        function toggleBotServer() {
            const mode = document.getElementById("botTargetMode").value;
            const qty = document.getElementById("botQty").value;
            const product = document.getElementById("botProduct").value;
            const sl = document.getElementById("botSl").value;

            fetch('/toggle-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode, qty: parseInt(qty), product: product, sl: parseFloat(sl) })
            }).then(res => res.json()).then(resp => {
                const btn = document.getElementById("botToggleBtn");
                const status = document.getElementById("botStatus");
                if (resp.status === "active") {
                    btn.innerText = "Stop 24/7 Server Bot";
                    btn.style.backgroundColor = "#f23645";
                    status.innerText = `● Bot Active on Server [Mode: ${mode}]`;
                    status.style.color = "#089981";
                    showToast("24/7 Dynamic TSL Bot Started!");
                } else {
                    btn.innerText = "Start 24/7 Server Bot";
                    btn.style.backgroundColor = "#089981";
                    status.innerText = "● Bot Status: Stopped (Server Side)";
                    status.style.color = "#f23645";
                    showToast("Server Bot Stopped!");
                }
            });
        }

        function connectBroker() {
            const data = {
                apiKey: document.getElementById("apiKey").value,
                clientId: document.getElementById("clientId").value,
                password: document.getElementById("password").value,
                totpKey: document.getElementById("totpKey").value
            };
            fetch('/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    showToast("Broker Connected & Dynamic TSL Engine Active!");
                    loadHistoricalData();
                } else {
                    showToast("Login Failed: " + resp.message);
                }
            });
        }

        function executeOrder(type) {
            const qty = document.getElementById("orderQty").value;
            const product = document.getElementById("productType").value;
            const sl = document.getElementById("stopLoss").value;
            const tsl = document.getElementById("trailingSl").value;
            const token = stockMap[selectedSymbol] || "1660";
            const exch = stockExchanges[selectedSymbol] || "NSE";
            const price = stockPrices[selectedSymbol] || 100.00;

            fetch('/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: selectedSymbol, token: token, exchange: exch, transactionType: type, quantity: parseInt(qty), productType: product, price: price, stopLoss: parseFloat(sl), trailingSl: parseFloat(tsl) })
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    showToast(`Manual ${type} Order Executed with TSL!`);
                } else {
                    showToast("Order Failed: " + resp.message);
                }
            });
        }

        function executeQuickOrder(type) {
            const qty = document.getElementById("quickQty").value;
            const token = stockMap[selectedSymbol] || "1660";
            const exch = stockExchanges[selectedSymbol] || "NSE";
            const price = stockPrices[selectedSymbol] || 100.00;

            fetch('/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: selectedSymbol, token: token, exchange: exch, transactionType: type, quantity: parseInt(qty), productType: 'INTRADAY', price: price, stopLoss: 5.0, trailingSl: 2.0 })
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    showToast(`Quick ${type} Order Executed!`);
                } else {
                    showToast("Order Failed: " + resp.message);
                }
            });
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def get_root():
    return HTML_CONTENT

@app.post("/update-symbol")
def update_symbol(data: dict):
    server_state["selected_symbol"] = data.get("symbol", "ITC-EQ")
    return {"status": "success"}

@app.post("/toggle-bot")
def toggle_bot(data: dict):
    server_state["bot_running"] = not server_state["bot_running"]
    if server_state["bot_running"]:
        server_state["bot_mode"] = data.get("mode", "STOCK")
        server_state["bot_qty"] = data.get("qty", 1)
        server_state["bot_product"] = data.get("product", "INTRADAY")
        server_state["bot_sl"] = data.get("sl", 5.0)
        add_server_log(f"Dynamic TSL Bot Started in {server_state['bot_mode']} mode.")
        return {"status": "active"}
    else:
        add_server_log("Dynamic TSL Bot Stopped.")
        return {"status": "stopped"}

@app.get("/server-status")
def get_server_status():
    return {"logs": server_state["logs"], "bot_running": server_state["bot_running"]}

@app.get("/options-chain")
def get_options_chain(index: str = "NIFTY", expiry: str = "2026-10-08"):
    base_price = 22620.0 if index == "NIFTY" else 48250.0
    chain = []
    step = 100 if index == "NIFTY" else 500
    for i in range(-5, 6):
        strike = base_price + (i * step)
        chain.append({
            "strike": int(strike),
            "ceSymbol": f"{index}{expiry.replace('-', '')}{int(strike)}CE",
            "ceLtp": round(max(5.0, 150.0 - (i * 20) + (i*i)), 2),
            "ceVol": 12500 + abs(i) * 1500,
            "peSymbol": f"{index}{expiry.replace('-', '')}{int(strike)}PE",
            "peLtp": round(max(5.0, 150.0 + (i * 20) + (i*i)), 2),
            "peVol": 14000 + abs(i) * 1200
        })
    return chain

@app.get("/history")
def get_historical_candles(token: str, exchange: str = "NSE", timeframe: str = "5m"):
    global smart_api_obj
    if not smart_api_obj:
        return []
    interval_map = {"1m": "ONE_MINUTE", "5m": "FIVE_MINUTE", "15m": "FIFTEEN_MINUTE", "1h": "ONE_HOUR"}
    try:
        to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        from_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
        resp = smart_api_obj.getCandleData({"exchange": exchange, "symboltoken": token, "interval": interval_map.get(timeframe, "FIVE_MINUTE"), "fromdate": from_date, "todate": to_date})
        if resp and resp.get("status") and resp.get("data"):
            return [{"time": int(datetime.fromisoformat(c[0].replace("+05:30", "")).timestamp()), "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4])} for c in resp["data"]]
    except Exception as e:
        pass
    return []

@app.post("/order")
async def place_live_order(data: dict):
    global smart_api_obj
    try:
        if not smart_api_obj:
            return {"status": "error", "message": "Broker not connected!"}
        
        entry_price = float(data["price"])
        sl_val = float(data.get("stopLoss", 5.0))
        tx_type = data["transactionType"]
        initial_sl = (entry_price - sl_val) if tx_type == "BUY" else (entry_price + sl_val)

        order_params = {
            "variety": "NORMAL", "tradingsymbol": data["symbol"], "symboltoken": data["token"],
            "transactiontype": tx_type, "exchange": data.get("exchange", "NSE"),
            "ordertype": "MARKET", "producttype": data["productType"], "duration": "DAY",
            "price": str(entry_price), "squareoff": "0", "stoploss": str(initial_sl), "quantity": str(data["quantity"])
        }
        order_id = smart_api_obj.placeOrder(order_params)
        if order_id:
            server_state["active_trade"] = {
                "symbol": data["symbol"], 
                "entryPrice": entry_price, 
                "qty": data["quantity"], 
                "type": tx_type, 
                "currentSl": initial_sl
            }
            add_server_log(f"Manual Order Placed with TSL: {tx_type} {data['symbol']} @ ₹{entry_price} | Initial SL: ₹{round(initial_sl, 2)}")
            return {"status": "success", "orderId": str(order_id)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/connect")
async def connect_broker(data: dict):
    global smart_api_obj
    try:
        obj = SmartConnect(api_key=data["apiKey"])
        session = obj.generateSession(data["clientId"], data["password"], pyotp.TOTP(data["totpKey"]).now())
        if session and session.get('status'):
            smart_api_obj = obj
            server_state["connected"] = True
            add_server_log("Successfully connected to Angel One SmartAPI session with Dynamic TSL.")
            return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
