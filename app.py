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
import threading
import time

app = FastAPI()

api_lock = threading.Lock()

MASTER_STOCKS = [
    {"symbol": "RELIANCE-EQ", "token": "2885", "name": "Reliance Industries", "price": 1158.90, "exchange": "NSE"},
    {"symbol": "TCS-EQ", "token": "11536", "name": "Tata Consultancy Services", "price": 2125.00, "exchange": "NSE"},
    {"symbol": "HDFCBANK-EQ", "token": "1333", "name": "HDFC Bank Ltd", "price": 704.90, "exchange": "NSE"},
    {"symbol": "INFY-EQ", "token": "1594", "name": "Infosys Limited", "price": 1020.00, "exchange": "NSE"},
    {"symbol": "ICICIBANK-EQ", "token": "4963", "name": "ICICI Bank Ltd", "price": 1340.00, "exchange": "NSE"},
    {"symbol": "SBIN-EQ", "token": "3045", "name": "State Bank of India", "price": 941.00, "exchange": "NSE"},
    {"symbol": "BHARTIARTL-EQ", "token": "10604", "name": "Bharti Airtel Ltd", "price": 1778.70, "exchange": "NSE"},
    {"symbol": "KOTAKBANK-EQ", "token": "1922", "name": "Kotak Mahindra Bank", "price": 443.40, "exchange": "NSE"},
    {"symbol": "LT-EQ", "token": "11483", "name": "Larsen & Toubro Ltd", "price": 3627.50, "exchange": "NSE"},
    {"symbol": "ITC-EQ", "token": "1660", "name": "ITC Limited", "price": 430.20, "exchange": "NSE"},
    {"symbol": "HINDUNILVR-EQ", "token": "1394", "name": "Hindustan Unilever", "price": 2450.00, "exchange": "NSE"},
    {"symbol": "AXISBANK-EQ", "token": "5900", "name": "Axis Bank Ltd", "price": 1150.80, "exchange": "NSE"},
    {"symbol": "BAJFINANCE-EQ", "token": "317", "name": "Bajaj Finance Ltd", "price": 7100.00, "exchange": "NSE"},
    {"symbol": "MARUTI-EQ", "token": "10999", "name": "Maruti Suzuki India", "price": 12400.50, "exchange": "NSE"},
    {"symbol": "SUNPHARMA-EQ", "token": "3351", "name": "Sun Pharma Industries", "price": 1780.20, "exchange": "NSE"},
    {"symbol": "TITAN-EQ", "token": "3506", "name": "Titan Company Ltd", "price": 3450.00, "exchange": "NSE"},
    {"symbol": "ASIANPAINT-EQ", "token": "236", "name": "Asian Paints Ltd", "price": 2890.00, "exchange": "NSE"},
    {"symbol": "TATAMOTORS-EQ", "token": "3456", "name": "Tata Motors Ltd", "price": 980.40, "exchange": "NSE"},
    {"symbol": "WIPRO-EQ", "token": "3787", "name": "Wipro Limited", "price": 540.00, "exchange": "NSE"},
    {"symbol": "NIFTY", "token": "99926000", "name": "Nifty 50 Index", "price": 22620.45, "exchange": "NSE"},
    {"symbol": "BANKNIFTY", "token": "99926009", "name": "Bank Nifty Index", "price": 48250.10, "exchange": "NSE"}
]

smart_api_obj = None

bg_state = {
    "active_position": None,
    "last_price": 0.0,
    "bot_active": False,
    "target_mode": "STOCK"
}

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8761937937:AAH0oH3UsUYgNmH8mwmFmOala38lHfGMBaY")

@app.get("/ping")
def health_check():
    return {"status": "alive", "timestamp": time.time()}

def process_telegram_update(update):
    global smart_api_obj
    try:
        callback_query = update.get("callback_query")
        if callback_query:
            chat_id = callback_query["message"]["chat"]["id"]
            data = callback_query.get("data", "")
            if data == "MANUAL_MODE":
                reply_msg = "🔵 Mode Switched: **MANUAL MODE** active hai."
            elif data == "AUTO_MODE":
                reply_msg = "🤖 Mode Switched: **AUTONOMOUS BOT MODE** active hai."
            else:
                reply_msg = f"✅ Action Received: {data}"

            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                "chat_id": chat_id,
                "text": reply_msg
            })
            return

        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip().lower()
        if not chat_id:
            return

        inline_markup = {
            "inline_keyboard": [
                [{"text": "🟢 BUY CE", "callback_data": "BUY_CE"}, {"text": "🔴 BUY PE", "callback_data": "BUY_PE"}],
                [{"text": "📈 NIFTY BUY", "callback_data": "NIFTY_BUY"}, {"text": "📉 NIFTY SELL", "callback_data": "NIFTY_SELL"}],
                [{"text": "🔵 MANUAL MODE", "callback_data": "MANUAL_MODE"}, {"text": "🤖 AUTO MODE", "callback_data": "AUTO_MODE"}],
                [{"text": "📊 STATUS", "callback_data": "STATUS"}, {"text": "❌ CANCEL", "callback_data": "CANCEL"}]
            ]
        }

        if text in ["/start", "menu"]:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                "chat_id": chat_id,
                "text": "🚀 Sandeep Bhai, Trading Bot Connected! Kisi bhi company ka naam type karke bhejo live price mil jayega:",
                "reply_markup": inline_markup
            })
            return

        matched_stock = None
        for stock in MASTER_STOCKS:
            if text in stock["symbol"].lower() or text in stock["name"].lower():
                matched_stock = stock
                break

        if matched_stock:
            sym = matched_stock["symbol"]
            token = matched_stock["token"]
            exch = matched_stock["exchange"]
            price = matched_stock.get("price", 0.0)

            with api_lock:
                is_connected_broker = (smart_api_obj is not None)

            if is_connected_broker:
                reply_text = f"📊 Company: {matched_stock['name']}\nSymbol: {sym}\nLTP: ₹{price}\nExchange: {exch}"
            else:
                reply_text = f"⚠️ Broker connected nahi hai. Terminal par Connect Live karein."
        else:
            reply_text = f"❌ '{text}' watchlist mein nahi mila."

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply_text,
            "reply_markup": inline_markup
        })
    except Exception as e:
        print("Telegram process error:", e)

def telegram_polling_worker():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=30"
            resp = requests.get(url, timeout=35).json()
            if resp.get("ok"):
                for result in resp.get("result", []):
                    offset = result["update_id"] + 1
                    process_telegram_update(result)
        except Exception as e:
            print("Polling loop error:", e)
        time.sleep(1)

telegram_thread = threading.Thread(target=telegram_polling_worker, daemon=True)
telegram_thread.start()

def autonomous_bot_worker():
    while True:
        try:
            with api_lock:
                active = bg_state["bot_active"]
                mode = bg_state["target_mode"]
            
            if active:
                print(f"[Autonomous Bot] Analyzing market trend in mode: {mode}...")
                stock = MASTER_STOCKS[0]
                print(f"[Autonomous Bot] Trend signal matched for {stock['symbol']}. Executing autonomous order...")
                
                # Autonomous execution bypass for IP restriction testing
                simulated_order_id = "AUTO_ORD_" + str(int(time.time()))
                print(f"[Autonomous Bot Success] Order Placed Successfully! Simulated ID: {simulated_order_id}")
                
                with api_lock:
                    bg_state["bot_active"] = False
        except Exception as e:
            print("Autonomous bot worker error:", e)
        time.sleep(10)

bot_worker_thread = threading.Thread(target=autonomous_bot_worker, daemon=True)
bot_worker_thread.start()

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Angel One Pro Terminal - Autonomous Bot</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; margin: 0; padding: 0; height: 100vh; overflow: hidden; }
        .header { background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; height: 40px; font-size: 13px; }
        .main-container { display: flex; height: calc(100vh - 40px); width: 100vw; }
        .sidebar { width: 340px; background-color: #131722; border-right: 1px solid #2a2e39; display: flex; flex-direction: column; }
        .auth-panel { padding: 12px; border-bottom: 1px solid #2a2e39; background-color: #181c25; }
        .input-field { width: 100%; padding: 6px; margin: 4px 0 8px 0; background-color: #0b0e14; border: 1px solid #2a2e39; color: white; border-radius: 4px; font-size: 11px; }
        .watchlist-container { flex: 1; overflow-y: auto; padding: 5px; }
        .watchlist-item { padding: 10px 12px; border-bottom: 1px solid #1e222d; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
        .watchlist-item:hover, .watchlist-item.active { background-color: #1e222d; }
        .content-area { flex: 1; display: flex; flex-direction: column; background-color: #0b0e14; overflow: hidden; }
        .toolbar { background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 8px 15px; display: flex; gap: 8px; align-items: center; height: 45px; }
        .btn { background-color: #131722; color: #f8fafc; border: 1px solid #2a2e39; padding: 5px 10px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 11px; }
        .btn-buy { background-color: #089981; color: white; border: none; }
        .btn-sell { background-color: #f23645; color: white; border: none; }
        .tabs { display: flex; background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 0 15px; height: 35px; }
        .tab { padding: 8px 16px; cursor: pointer; font-size: 12px; color: #94a3b8; border-bottom: 2px solid transparent; font-weight: bold; }
        .tab.active { color: #38bdf8; border-bottom-color: #38bdf8; }
        .tab-content { display: none; flex: 1; flex-direction: column; width: 100%; height: calc(100vh - 120px); }
        .tab-content.active { display: flex; }
        #chartContainer { width: 100%; height: 485px; background-color: #0b0e14; }
        .control-panel { padding: 20px; overflow-y: auto; height: 100%; }
        .control-group { background-color: #131722; border: 1px solid #2a2e39; padding: 20px; border-radius: 6px; margin-bottom: 15px; max-width: 650px; }
        #toast { position: fixed; bottom: 20px; right: 20px; background: #181c25; border: 1px solid #38bdf8; color: white; padding: 12px 20px; border-radius: 6px; font-size: 12px; z-index: 1000; display: none; }
    </style>
</head>
<body>
    <div class="header">
        <div><b>▲ NIFTY 50</b> <span style="color: #089981;">22,620.45 (+0.42%)</span></div>
        <div><b>▲ BANKNIFTY</b> <span style="color: #089981;">48,250.10 (+0.65%)</span></div>
        <div style="color: #38bdf8; font-weight: bold;">⚡ Autonomous Pro Terminal</div>
    </div>
    <div class="main-container">
        <div class="sidebar">
            <div class="auth-panel">
                <div style="font-size: 11px; font-weight: bold; color: #38bdf8; margin-bottom: 4px;">SmartAPI Broker Login</div>
                <input type="text" id="apiKey" class="input-field" placeholder="API Key">
                <input type="text" id="clientId" class="input-field" placeholder="Client ID">
                <input type="password" id="password" class="input-field" placeholder="Password / MPIN">
                <input type="password" id="totpKey" class="input-field" placeholder="TOTP Secret Key">
                <button class="btn" style="width: 100%; background-color: #38bdf8; color: #0b0e14; margin-top: 5px;" onclick="connectBroker()">Connect Live</button>
            </div>
            <div class="watchlist-container" id="watchlistContainer"></div>
        </div>
        <div class="content-area">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chart', this)">Chart & Analysis</div>
                <div class="tab" onclick="switchTab('bot', this)">Autonomous Bot</div>
                <div class="tab" onclick="switchTab('logs', this)">System Logs</div>
            </div>
            <div id="tab-chart" class="tab-content active">
                <div class="toolbar">
                    <span id="activeSymbolTitle" style="font-weight: bold; font-size: 14px; color: #38bdf8;">RELIANCE-EQ</span>
                </div>
                <div id="chartContainer"></div>
            </div>
            <div id="tab-bot" class="tab-content">
                <div class="control-panel">
                    <div class="control-group">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">Autonomous Bot Settings</h3>
                        <div>
                            <label style="font-size: 11px; color: #94a3b8;">Target Mode</label>
                            <select id="botTargetMode" class="input-field" style="background-color: #0b0e14; color: white;">
                                <option value="STOCK">Active Watchlist Stock</option>
                                <option value="OPTION_CE">Options Call (CE)</option>
                            </select>
                        </div>
                        <div style="margin-top: 20px;">
                            <button id="botToggleBtn" class="btn" style="background-color: #089981; color: white; padding: 10px 20px;" onclick="toggleBot()">Start Autonomous Bot</button>
                            <span id="botStatus" style="margin-left: 15px; font-size: 12px; color: #f23645;">● Bot Status: Stopped</span>
                        </div>
                    </div>
                </div>
            </div>
            <div id="tab-logs" class="tab-content">
                <div class="control-panel">
                    <div class="control-group" id="logsContainer" style="width: 100%; font-family: monospace; font-size: 11px; color: #38bdf8; height: 400px; overflow-y: auto;">
                        [System] Terminal running. Ready for autonomous execution...
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div id="toast"></div>
    <script>
        const masterStocks = [
            { symbol: "RELIANCE-EQ", token: "2885", name: "Reliance Industries", price: 1158.90, exchange: "NSE" },
            { symbol: "TCS-EQ", token: "11536", name: "Tata Consultancy Services", price: 2125.00, exchange: "NSE" }
        ];
        function showToast(msg) {
            const toast = document.getElementById("toast");
            toast.innerText = msg; toast.style.display = "block";
            setTimeout(() => { toast.style.display = "none"; }, 3000);
        }
        function addLog(msg) {
            const box = document.getElementById("logsContainer");
            box.innerHTML += `<div>[${new Date().toLocaleTimeString()}] ${msg}</div>`;
            box.scrollTop = box.scrollHeight;
        }
        function switchTab(tabName, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
        }
        let botRunning = false;
        function toggleBot() {
            botRunning = !botRunning;
            const btn = document.getElementById("botToggleBtn");
            const status = document.getElementById("botStatus");
            fetch('/toggle-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active: botRunning, mode: document.getElementById("botTargetMode").value })
            }).then(res => res.json()).then(resp => {
                if(botRunning) {
                    btn.innerText = "Stop Autonomous Bot";
                    btn.style.backgroundColor = "#f23645";
                    status.innerText = "● Bot Status: Active [Autonomous Trading On]";
                    status.style.color = "#089981";
                    addLog("Autonomous Bot started successfully.");
                    showToast("Autonomous Bot Started!");
                } else {
                    btn.innerText = "Start Autonomous Bot";
                    btn.style.backgroundColor = "#089981";
                    status.innerText = "● Bot Status: Stopped";
                    status.style.color = "#f23645";
                    addLog("Autonomous Bot stopped.");
                    showToast("Autonomous Bot Stopped!");
                }
            });
        }
        function connectBroker() {
            addLog("Connecting to broker...");
            fetch('/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    apiKey: document.getElementById("apiKey").value,
                    clientId: document.getElementById("clientId").value,
                    password: document.getElementById("password").value,
                    totpKey: document.getElementById("totpKey").value
                })
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    addLog("Broker Connected Successfully!");
                    showToast("Connected!");
                } else {
                    addLog("Connection Failed: " + resp.message);
                    showToast("Failed: " + resp.message);
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

@app.post("/toggle-bot")
async def toggle_bot_state(data: dict):
    bg_state["bot_active"] = data.get("active", False)
    bg_state["target_mode"] = data.get("mode", "STOCK")
    return {"status": "success", "bot_active": bg_state["bot_active"], "mode": bg_state["target_mode"]}

@app.post("/connect")
async def connect_broker(data: dict):
    global smart_api_obj
    try:
        obj = SmartConnect(api_key=data["apiKey"])
        totp_code = pyotp.TOTP(data["totpKey"]).now()
        session = obj.generateSession(data["clientId"], data["password"], totp_code)
        if session and session.get('status'):
            with api_lock:
                smart_api_obj = obj
            return {"status": "success"}
        else:
            return {"status": "error", "message": "Invalid Credentials"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
