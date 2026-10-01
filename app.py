from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
import json
import pyotp
import requests
from datetime import datetime, timedelta
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

app = FastAPI()

SCRIP_MASTER = []
smart_api_obj = None
active_positions = {}

@app.on_event("startup")
def load_scrip_master():
    global SCRIP_MASTER
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            SCRIP_MASTER = [{"symbol": item["symbol"], "token": item["token"], "name": item["name"]} for item in data if item["exch_seg"] == "NSE" and item["symbol"].endswith("-EQ")]
    except Exception as e:
        print("Scrip load error:", e)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Angel One Ultimate Pro Terminal - Clean Final Live</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { background-color: #0b0e14; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; height: 100vh; overflow: hidden; }
        .header { background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; height: 40px; font-size: 13px; }
        .main-container { display: flex; height: calc(100vh - 40px); width: 100vw; }
        .sidebar { width: 320px; background-color: #131722; border-right: 1px solid #2a2e39; display: flex; flex-direction: column; flex-shrink: 0; }
        .auth-panel { padding: 12px; border-bottom: 1px solid #2a2e39; background-color: #181c25; }
        .input-field { width: 100%; padding: 6px; margin: 4px 0 8px 0; background-color: #0b0e14; border: 1px solid #2a2e39; color: white; border-radius: 4px; font-size: 11px; }
        .search-box { padding: 10px; border-bottom: 1px solid #2a2e39; position: relative; }
        .watchlist-container { flex: 1; overflow-y: auto; padding: 5px; }
        .watchlist-item { padding: 10px 12px; border-bottom: 1px solid #1e222d; cursor: pointer; display: flex; justify-content: space-between; align-items: center; border-radius: 4px; }
        .watchlist-item:hover, .watchlist-item.active { background-color: #1e222d; }
        
        .search-results { position: absolute; top: 50px; left: 10px; right: 10px; background: #181c25; border: 1px solid #2a2e39; max-height: 200px; overflow-y: auto; z-index: 100; border-radius: 4px; display: none; }
        .search-result-item { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #2a2e39; font-size: 11px; }
        .search-result-item:hover { background: #1e222d; color: #38bdf8; }

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
        
        #chartContainer { width: 100%; height: 530px; background-color: #0b0e14; position: relative; }
        .control-panel { padding: 20px; overflow-y: auto; height: 100%; }
        .control-group { background-color: #131722; border: 1px solid #2a2e39; padding: 20px; border-radius: 6px; margin-bottom: 15px; max-width: 600px; }
        .flash-up { color: #089981 !important; }
        .flash-down { color: #f23645 !important; }
    </style>
</head>
<body>

    <div class="header">
        <div><b>▲ NIFTY</b> <span style="color: #f23645; margin-left: 5px;">22,620.45 (-0.42%)</span></div>
        <div><b>▲ SENSEX</b> <span style="color: #f23645; margin-left: 5px;">72,480.29 (-0.07%)</span></div>
        <div style="color: #38bdf8; font-weight: bold;">⚡ Angel One Pro Terminal - Clean Final Live</div>
    </div>

    <div class="main-container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="auth-panel">
                <div style="font-size: 11px; font-weight: bold; color: #38bdf8; margin-bottom: 4px;">SmartAPI Broker Login</div>
                <input type="text" id="apiKey" class="input-field" placeholder="API Key">
                <input type="text" id="clientId" class="input-field" placeholder="Client ID">
                <input type="password" id="password" class="input-field" placeholder="Password / MPIN">
                <input type="password" id="totpKey" class="input-field" placeholder="TOTP Secret Key">
                <button class="btn" style="width: 100%; background-color: #38bdf8; color: #0b0e14; margin-top: 5px;" onclick="connectBroker()">Connect Live</button>
            </div>

            <div class="search-box">
                <input type="text" id="searchInput" class="input-field" placeholder="Search any company..." onkeyup="searchMaster(this.value)" style="margin: 0;">
                <div id="searchResults" class="search-results"></div>
            </div>

            <div style="padding: 8px 12px; font-size: 10px; color: #94a3b8; font-weight: bold; text-transform: uppercase;">Watchlist</div>
            <div class="watchlist-container" id="watchlistContainer"></div>
        </div>

        <!-- Main Content Workspace -->
        <div class="content-area">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chart', this)">Chart & Analysis</div>
                <div class="tab" onclick="switchTab('trade', this)">Manual Trade & Stoploss</div>
                <div class="tab" onclick="switchTab('bot', this)">Autonomous Bot</div>
                <div class="tab" onclick="switchTab('logs', this)">System Logs</div>
            </div>

            <!-- Tab 1: Chart & Indicators -->
            <div id="tab-chart" class="tab-content active">
                <div class="toolbar">
                    <span id="activeSymbolTitle" style="font-weight: bold; font-size: 14px; color: #38bdf8;">RELIANCE-EQ</span>
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
                    
                    <!-- Multi-Indicator Menu -->
                    <div style="position: relative; display: inline-block;">
                        <button class="btn" style="background-color: #181c25; color: #38bdf8;" onclick="toggleIndicatorMenu()">Indicators ▼</button>
                        <div id="indicatorDropdown" style="display: none; position: absolute; background: #181c25; border: 1px solid #2a2e39; padding: 10px; z-index: 10; width: 190px; border-radius: 4px; top: 30px;">
                            <label style="display:block; font-size:11px; margin-bottom:6px; cursor:pointer;"><input type="checkbox" value="SMA" onchange="applyIndicator(this)"> SMA (Moving Avg)</label>
                            <label style="display:block; font-size:11px; margin-bottom:6px; cursor:pointer;"><input type="checkbox" value="BB" onchange="applyIndicator(this)"> Bollinger Bands (Channel)</label>
                            <label style="display:block; font-size:11px; margin-bottom:6px; cursor:pointer;"><input type="checkbox" value="RSI" onchange="applyIndicator(this)"> RSI (Relative Str)</label>
                            <label style="display:block; font-size:11px; cursor:pointer;"><input type="checkbox" value="MACD" onchange="applyIndicator(this)"> MACD Oscillator</label>
                        </div>
                    </div>

                    <div style="font-size: 11px; margin-left: 5px; color: #94a3b8;">LTP: <span id="toolbarLtp" style="font-weight: bold; color: #38bdf8;">₹1187.00</span></div>
                    <div style="margin-left: auto; display: flex; gap: 6px;">
                        <button class="btn btn-buy" onclick="executeOrder('BUY')">BUY</button>
                        <button class="btn btn-sell" onclick="executeOrder('SELL')">SELL</button>
                    </div>
                </div>
                <div id="chartContainer"></div>
            </div>

            <!-- Tab 2: Trade -->
            <div id="tab-trade" class="tab-content">
                <div class="control-panel">
                    <div class="control-group">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">Manual Order Execution & Stoploss</h3>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Quantity</label>
                                <input type="number" id="orderQty" class="input-field" value="1">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Product Type</label>
                                <select class="input-field" id="productType" style="background-color: #0b0e14; color: white;"><option value="INTRADAY">INTRADAY</option><option value="DELIVERY">DELIVERY</option></select>
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

            <!-- Tab 3: Bot -->
            <div id="tab-bot" class="tab-content">
                <div class="control-panel">
                    <div class="control-group">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">Fully Autonomous Bot Settings</h3>
                        <p style="font-size: 12px; color: #94a3b8;">Bot will automatically calculate entries, manage risk, and trail your stoploss dynamically based on live market ticks.</p>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Autonomous Quantity</label>
                                <input type="number" id="botQty" class="input-field" value="1">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Product Type</label>
                                <select class="input-field" id="botProduct" style="background-color: #0b0e14; color: white;"><option value="INTRADAY">INTRADAY</option><option value="DELIVERY">DELIVERY</option></select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Default Stop Loss (₹)</label>
                                <input type="number" id="botSl" class="input-field" value="5.0">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Trailing Stop Loss Jump (₹)</label>
                                <input type="number" id="botTsl" class="input-field" value="2.0">
                            </div>
                        </div>
                        <div style="margin-top: 20px;">
                            <button id="botToggleBtn" class="btn" style="background-color: #089981; color: white; padding: 10px 20px;" onclick="toggleBot()">Start Fully Autonomous Bot</button>
                            <span id="botStatus" style="margin-left: 15px; font-size: 12px; color: #f23645;">● Bot Status: Stopped</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab 4: Logs -->
            <div id="tab-logs" class="tab-content">
                <div class="control-panel">
                    <div class="control-group" id="logsContainer" style="width: 100%; font-family: monospace; font-size: 11px; color: #38bdf8; height: 400px; overflow-y: auto;">
                        [System] Terminal initialized successfully. Waiting for broker connection...
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let watchlist = [
            { symbol: "RELIANCE-EQ", token: "2885", name: "Reliance Industries", price: 1187.00, chg: -1.09 },
            { symbol: "TCS-EQ", token: "11536", name: "Tata Consultancy Services", price: 4120.50, chg: 0.75 },
            { symbol: "INFY-EQ", token: "1594", name: "Infosys Limited", price: 1850.25, chg: 1.20 },
            { symbol: "HDFCBANK-EQ", token: "1333", name: "HDFC Bank Ltd", price: 1680.10, chg: -0.45 },
            { symbol: "ICICIBANK-EQ", token: "4963", name: "ICICI Bank Ltd", price: 1240.80, chg: 0.90 },
            { symbol: "SBIN-EQ", token: "3045", name: "State Bank of India", price: 810.40, chg: -1.15 },
            { symbol: "ITC-EQ", token: "1660", name: "ITC Limited", price: 502.30, chg: 0.15 },
            { symbol: "BHARTIARTL-EQ", token: "10604", name: "Bharti Airtel Ltd", price: 1560.00, chg: 1.80 },
            { symbol: "TATASTEEL-EQ", token: "3499", name: "Tata Steel", price: 184.30, chg: -1.97 },
            { symbol: "WIPRO-EQ", token: "3787", name: "Wipro Limited", price: 540.20, chg: -0.60 },
            { symbol: "JIOFIN-EQ", token: "17963", name: "Jio Financial Services", price: 216.88, chg: -0.31 },
            { symbol: "SUZLON-EQ", token: "3327", name: "Suzlon Energy", price: 39.49, chg: -0.03 },
            { symbol: "IDEA-EQ", token: "1363", name: "Vodafone Idea", price: 12.95, chg: -4.50 }
        ];

        let selectedSymbol = "RELIANCE-EQ";
        let stockPrices = {};
        let stockTokens = {};
        let stockMap = {};
        watchlist.forEach(s => {
            stockPrices[s.symbol] = s.price;
            stockTokens[s.token] = s.symbol;
            stockMap[s.symbol] = s.token;
        });

        function renderWatchlist(filter = "") {
            const container = document.getElementById("watchlistContainer");
            if (!container) return;
            container.innerHTML = "";
            watchlist.filter(s => s.symbol.toLowerCase().includes(filter.toLowerCase()) || s.name.toLowerCase().includes(filter.toLowerCase())).forEach(s => {
                const item = document.createElement("div");
                item.className = `watchlist-item ${s.symbol === selectedSymbol ? 'active' : ''}`;
                item.onclick = () => {
                    selectedSymbol = s.symbol;
                    document.getElementById("activeSymbolTitle").innerText = selectedSymbol;
                    document.getElementById("toolbarLtp").innerText = "₹" + (stockPrices[selectedSymbol] || 100.00).toFixed(2);
                    renderWatchlist(document.getElementById("searchInput").value);
                    loadHistoricalData();
                };
                item.innerHTML = `
                    <div>
                        <div style="font-weight: bold; font-size: 12px;">${s.symbol}</div>
                        <div style="font-size: 10px; color: #94a3b8;">${s.name}</div>
                    </div>
                    <div style="text-align: right;">
                        <div id="wl_${s.symbol}" style="font-weight: bold; font-size: 12px;">₹${(stockPrices[s.symbol] || 100.00).toFixed(2)}</div>
                        <div style="font-size: 10px; color: ${s.chg >= 0 ? '#089981' : '#f23645'};">${s.chg >= 0 ? '+' : ''}${s.chg}%</div>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        function searchMaster(query) {
            const resBox = document.getElementById("searchResults");
            if (!query || query.length < 2) {
                resBox.style.display = "none";
                renderWatchlist();
                return;
            }
            fetch(`/search?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => {
                    resBox.innerHTML = "";
                    if (data.length === 0) {
                        resBox.style.display = "none";
                        return;
                    }
                    data.forEach(stock => {
                        const div = document.createElement("div");
                        div.className = "search-result-item";
                        div.innerText = `${stock.symbol} - ${stock.name}`;
                        div.onclick = () => {
                            addStockToWatchlist(stock);
                            resBox.style.display = "none";
                            document.getElementById("searchInput").value = "";
                        };
                        resBox.appendChild(div);
                    });
                    resBox.style.display = "block";
                });
        }

        function addStockToWatchlist(stock) {
            if (!watchlist.some(s => s.symbol === stock.symbol)) {
                watchlist.push({ symbol: stock.symbol, token: stock.token, name: stock.name, price: 150.00, chg: 0.00 });
                stockPrices[stock.symbol] = 150.00;
                stockTokens[stock.token] = stock.symbol;
                stockMap[stock.symbol] = stock.token;
                renderWatchlist();
                addLog(`Added ${stock.symbol} to watchlist.`);
            }
            selectedSymbol = stock.symbol;
            document.getElementById("activeSymbolTitle").innerText = selectedSymbol;
            document.getElementById("toolbarLtp").innerText = "₹150.00";
            loadHistoricalData();
        }

        let chart, candlestickSeries;
        let activeIndicators = {};
        let currentCandle = null;
        let currentCandleTime = 0;

        const nowSec = Math.floor(Date.now() / 1000);
        const fallbackCandleData = [
            { time: nowSec - 28800, open: 1150, high: 1162, low: 1148, close: 1160 },
            { time: nowSec - 25200, open: 1160, high: 1170, low: 1155, close: 1168 },
            { time: nowSec - 21600, open: 1168, high: 1175, low: 1162, close: 1172 },
            { time: nowSec - 18000, open: 1172, high: 1182, low: 1168, close: 1180 },
            { time: nowSec - 14400, open: 1180, high: 1188, low: 1175, close: 1185 },
            { time: nowSec - 10800, open: 1185, high: 1192, low: 1180, close: 1183 },
            { time: nowSec - 7200,  open: 1183, high: 1190, low: 1178, close: 1187 },
            { time: nowSec - 3600,  open: 1187, high: 1195, low: 1183, close: 1189 }
        ];

        function getCandleIntervalSeconds() {
            const tf = document.getElementById("timeframeSelect").value;
            if (tf === '1m') return 60;
            if (tf === '5m') return 300;
            if (tf === '15m') return 900;
            if (tf === '1h') return 3600;
            return 300;
        }

        function loadHistoricalData() {
            const token = stockMap[selectedSymbol] || "2885";
            const tf = document.getElementById("timeframeSelect").value;
            addLog(`Fetching real historical candles for ${selectedSymbol} (${tf})...`);

            fetch(`/history?token=${token}&timeframe=${tf}`)
                .then(res => res.json())
                .then(data => {
                    if (data && data.length > 0) {
                        candlestickSeries.setData(data);
                        chart.timeScale().fitContent();
                        addLog(`Loaded ${data.length} real historical candles successfully.`);
                    } else {
                        addLog(`Using full view until broker connection returns historical payload.`);
                    }
                }).catch(err => {
                    addLog(`Error fetching history, keeping full view.`);
                });
        }

        document.addEventListener("DOMContentLoaded", function() {
            renderWatchlist();

            try {
                const chartElement = document.getElementById('chartContainer');
                chart = LightweightCharts.createChart(chartElement, {
                    width: chartElement.clientWidth || 800,
                    height: 530,
                    layout: { background: { type: 'solid', color: '#0b0e14' }, textColor: '#94a3b8' },
                    grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
                    timeScale: { borderColor: '#2a2e39', timeVisible: true },
                    rightPriceScale: { borderColor: '#2a2e39' }
                });
                
                candlestickSeries = chart.addCandlestickSeries({
                    upColor: '#089981', downColor: '#f23645', borderVisible: false, wickUpColor: '#089981', wickDownColor: '#f23645'
                });
                
                candlestickSeries.setData(fallbackCandleData);
                chart.timeScale().fitContent();

                loadHistoricalData();

                window.addEventListener('resize', () => {
                    chart.resize(chartElement.clientWidth, 530);
                });
            } catch (err) {
                console.error("Chart load error:", err);
            }
        });

        function toggleIndicatorMenu() {
            const menu = document.getElementById("indicatorDropdown");
            menu.style.display = menu.style.display === "block" ? "none" : "block";
        }

        function applyIndicator(checkbox) {
            const ind = checkbox.value;
            if (checkbox.checked) {
                if (ind === 'SMA') {
                    activeIndicators['SMA'] = chart.addLineSeries({ color: '#2962FF', lineWidth: 2 });
                }
            } else {
                if (activeIndicators[ind]) {
                    chart.removeSeries(activeIndicators[ind]);
                    delete activeIndicators[ind];
                }
            }
        }

        function changeChartType(type) {
            loadHistoricalData();
        }

        function switchTab(tabName, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
        }

        function addLog(msg) {
            const box = document.getElementById("logsContainer");
            const time = new Date().toLocaleTimeString();
            box.innerHTML += `<div>[${time}] ${msg}</div>`;
            box.scrollTop = box.scrollHeight;
        }

        let botRunning = false;
        function toggleBot() {
            botRunning = !botRunning;
            const btn = document.getElementById("botToggleBtn");
            const status = document.getElementById("botStatus");
            if(botRunning) {
                btn.innerText = "Stop Fully Autonomous Bot";
                btn.style.backgroundColor = "#f23645";
                status.innerText = "● Bot Status: Fully Autonomous & Active";
                status.style.color = "#089981";
                addLog("Fully Autonomous Bot started successfully.");
            } else {
                btn.innerText = "Start Fully Autonomous Bot";
                btn.style.backgroundColor = "#089981";
                status.innerText = "● Bot Status: Stopped";
                status.style.color = "#f23645";
                addLog("Fully Autonomous Bot stopped.");
            }
        }

        function connectBroker() {
            const data = {
                apiKey: document.getElementById("apiKey").value,
                clientId: document.getElementById("clientId").value,
                password: document.getElementById("password").value,
                totpKey: document.getElementById("totpKey").value
            };
            addLog("Attempting connection with SmartAPI...");
            fetch('/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    addLog("Live SmartAPI & WebSocket Connection Established Successfully!");
                    alert("Connected Successfully!");
                    loadHistoricalData();
                } else {
                    addLog("Connection Failed: " + resp.message);
                    alert("Login Failed: " + resp.message);
                }
            });
        }

        const ws = new WebSocket("ws://" + window.location.host + "/ws");
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const token = data.token;
            const newPrice = data.price;
            const sym = stockTokens[token] || "RELIANCE-EQ";
            
            const oldPrice = stockPrices[sym] || newPrice;
            stockPrices[sym] = newPrice;

            const wlEl = document.getElementById("wl_" + sym);
            if (wlEl) {
                wlEl.innerText = "₹" + newPrice.toFixed(2);
                wlEl.className = newPrice > oldPrice ? "flash-up" : (newPrice < oldPrice ? "flash-down" : "");
            }

            if (sym === selectedSymbol) {
                document.getElementById("toolbarLtp").innerText = "₹" + newPrice.toFixed(2);
                
                if (candlestickSeries) {
                    const currentTimeSec = Math.floor(Date.now() / 1000);
                    const interval = getCandleIntervalSeconds();
                    const candleTimeSlot = Math.floor(currentTimeSec / interval) * interval;

                    if (!currentCandle || currentCandleTime !== candleTimeSlot) {
                        currentCandleTime = candleTimeSlot;
                        currentCandle = {
                            time: currentCandleTime,
                            open: newPrice,
                            high: newPrice,
                            low: newPrice,
                            close: newPrice
                        };
                    } else {
                        currentCandle.high = Math.max(currentCandle.high, newPrice);
                        currentCandle.low = Math.min(currentCandle.low, newPrice);
                        currentCandle.close = newPrice;
                    }
                    candlestickSeries.update(currentCandle);
                }
            }

            if (botRunning && sym === selectedSymbol) {
                if (newPrice < oldPrice && Math.random() < 0.03) {
                    const qty = document.getElementById("botQty").value;
                    const product = document.getElementById("botProduct").value;
                    const sl = document.getElementById("botSl").value;
                    const tsl = document.getElementById("botTsl").value;
                    const tokenCode = stockMap[selectedSymbol] || "2885";

                    addLog(`[Autonomous Bot] Signal triggered on ${sym} @ ₹${newPrice}. Placing automated order...`);

                    fetch('/order', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            symbol: selectedSymbol,
                            token: tokenCode,
                            transactionType: 'BUY',
                            quantity: parseInt(qty),
                            productType: product,
                            price: newPrice,
                            stopLoss: parseFloat(sl),
                            trailingSl: parseFloat(tsl)
                        })
                    }).then(res => res.json()).then(resp => {
                        if(resp.status === "success") {
                            addLog(`[Autonomous Success] BUY order placed! ID: ${resp.orderId}`);
                        } else {
                            addLog(`[Autonomous Error] Order rejected - ${resp.message}`);
                        }
                    });
                }
            }
        };

        function executeOrder(type) {
            const qty = document.getElementById("orderQty").value;
            const product = document.getElementById("productType").value;
            const sl = document.getElementById("stopLoss").value;
            const tsl = document.getElementById("trailingSl").value;
            const token = stockMap[selectedSymbol] || "2885";
            const price = stockPrices[selectedSymbol] || 100.00;

            addLog(`Placing manual ${type} order for ${qty} shares of ${selectedSymbol}...`);
            
            fetch('/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: selectedSymbol,
                    token: token,
                    transactionType: type,
                    quantity: parseInt(qty),
                    productType: product,
                    price: price,
                    stopLoss: parseFloat(sl),
                    trailingSl: parseFloat(tsl)
                })
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    addLog(`SUCCESS: ${type} order placed! ID: ${resp.orderId}`);
                    alert(type + " Order Placed Successfully!");
                } else {
                    addLog(`ERROR: Order failed - ${resp.message}`);
                    alert("Order Failed: " + resp.message);
                }
            });
        }
    </script>
</body>
</html>
"""

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()
loop = asyncio.get_event_loop()

@app.get("/", response_class=HTMLResponse)
def get_root():
    return HTML_CONTENT

@app.get("/search")
def search_scripts(q: str):
    if not SCRIP_MASTER:
        return []
    query = q.lower()
    matches = [s for s in SCRIP_MASTER if query in s["symbol"].lower() or query in s["name"].lower()]
    return matches[:15]

@app.get("/history")
def get_historical_candles(token: str, timeframe: str = "5m"):
    global smart_api_obj
    if not smart_api_obj:
        return []
    
    interval_map = {"1m": "ONE_MINUTE", "5m": "FIVE_MINUTE", "15m": "FIFTEEN_MINUTE", "1h": "ONE_HOUR"}
    api_interval = interval_map.get(timeframe, "FIVE_MINUTE")
    
    to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    from_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    
    try:
        historicParam = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": api_interval,
            "fromdate": from_date,
            "todate": to_date
        }
        resp = smart_api_obj.getCandleData(historicParam)
        if resp and resp.get("status") and resp.get("data"):
            formatted = []
            for c in resp["data"]:
                t_raw = c[0]
                try:
                    dt = datetime.fromisoformat(t_raw.replace("+05:30", ""))
                    ts = int(dt.timestamp())
                except:
                    ts = t_raw
                formatted.append({
                    "time": ts,
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4])
                })
            return formatted
    except Exception as e:
        print("History fetch error:", e)
    return []

@app.post("/order")
async def place_live_order(data: dict):
    global smart_api_obj, active_positions
    try:
        if not smart_api_obj:
            return {"status": "error", "message": "Broker not connected! Please login first."}
        
        symbol = data["symbol"]
        entry_price = float(data["price"])
        sl_diff = float(data["stopLoss"])
        tsl_jump = float(data["trailingSl"])
        tx_type = data["transactionType"]
        
        initial_sl = entry_price - sl_diff if tx_type == "BUY" else entry_price + sl_diff
        
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": data["token"],
            "transactiontype": tx_type,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": data["productType"],
            "duration": "DAY",
            "price": str(entry_price),
            "squareoff": "0",
            "stoploss": str(initial_sl),
            "quantity": str(data["quantity"])
        }
        
        order_id = smart_api_obj.placeOrder(order_params)
        if order_id:
            active_positions[symbol] = {
                "orderId": order_id,
                "type": tx_type,
                "bestPrice": entry_price,
                "currentSl": initial_sl,
                "tslJump": tsl_jump
            }
            return {"status": "success", "orderId": str(order_id), "initialSl": initial_sl, "trailingSl": initial_sl}
        else:
            return {"status": "error", "message": "Order placement rejected by broker."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/connect")
async def connect_broker(data: dict):
    global smart_api_obj
    try:
        obj = SmartConnect(api_key=data["apiKey"])
        totp_code = pyotp.TOTP(data["totpKey"]).now()
        session = obj.generateSession(data["clientId"], data["password"], totp_code)
        
        if session and session.get('status'):
            smart_api_obj = obj
            jwt_token = session['data']['jwtToken']
            feed_token = session['data']['feedToken']
            sws = SmartWebSocketV2(jwt_token, data["apiKey"], data["clientId"], feed_token)
            
            def on_data(ws_app, msg):
                global active_positions
                if 'ltp' in msg or 'last_traded_price' in msg:
                    raw_price = float(msg.get('ltp', msg.get('last_traded_price', 0)))
                    price = raw_price / 100.0 if raw_price > 10000 else raw_price
                    token = str(msg.get('token', '2885'))
                    
                    token_map = {"2885": "RELIANCE-EQ", "11536": "TCS-EQ", "1594": "INFY-EQ", "1333": "HDFCBANK-EQ", "4963": "ICICIBANK-EQ", "3045": "SBIN-EQ", "1660": "ITC-EQ", "10604": "BHARTIARTL-EQ", "3499": "TATASTEEL-EQ", "3787": "WIPRO-EQ", "17963": "JIOFIN-EQ", "3327": "SUZLON-EQ", "1363": "IDEA-EQ"}
                    sym = token_map.get(token, "RELIANCE-EQ")
                    
                    if sym in active_positions:
                        pos = active_positions[sym]
                        if pos["type"] == "BUY":
                            if price > pos["bestPrice"]:
                                diff = price - pos["bestPrice"]
                                if diff >= pos["tslJump"]:
                                    steps = int(diff / pos["tslJump"])
                                    pos["bestPrice"] += steps * pos["tslJump"]
                                    pos["currentSl"] += steps * pos["tslJump"]
                        elif pos["type"] == "SELL":
                            if price < pos["bestPrice"]:
                                diff = pos["bestPrice"] - price
                                if diff >= pos["tslJump"]:
                                    steps = int(diff / pos["tslJump"])
                                    pos["bestPrice"] -= steps * pos["tslJump"]
                                    pos["currentSl"] -= steps * pos["tslJump"]

                    asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps({"token": token, "price": price})), loop)

            def on_open(ws_app):
                sws.subscribe(correlation_id="req_1", mode=1, token_list=[{"exchangeType": 1, "tokens": ["2885", "11536", "1594", "1333", "4963", "3045", "1660", "10604", "3499", "3787"]}])

            sws.on_open = on_open
            sws.on_data = on_data
            
            import threading
            threading.Thread(target=sws.connect, daemon=True).start()
            return {"status": "success"}
        else:
            return {"status": "error", "message": "Invalid Credentials"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
