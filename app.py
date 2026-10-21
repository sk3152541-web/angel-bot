import asyncio
from datetime import datetime, timedelta
import json
import os
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import pyotp
import requests
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import uvicorn

app = FastAPI()

smart_api_obj = None
sws = None
live_prices = {}
prev_closes = {}
stockTokens = {}
stockMap = {}
stockExchanges = {}
scrip_master_cache = []
loop = None

saved_credentials = {
    "api_key": "",
    "client_id": "",
    "password": "",
    "totp_key": "",
}

last_login_time = 0

bg_state = {
    "bot_active": False,
    "target_mode": "STOCK",
    "bot_qty": 1,
    "bot_product": "INTRADAY",
    "leverage": 1,
    "symbol": "",
    "token": "",
    "exchange": "NSE"
}

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Angel One Fully Autonomous Pro Terminal</title>
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
        .btn:hover { border-color: #38bdf8; }
        .tabs { display: flex; background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 0 15px; height: 35px; flex-shrink: 0; }
        .tab { padding: 8px 16px; cursor: pointer; font-size: 12px; color: #94a3b8; border-bottom: 2px solid transparent; font-weight: bold; line-height: 19px; }
        .tab.active { color: #38bdf8; border-bottom-color: #38bdf8; }
        .tab-content { display: none; flex: 1; flex-direction: column; width: 100%; height: calc(100vh - 120px); position: relative; }
        .tab-content.active { display: flex; }
        #chartContainer { width: 100%; height: 485px; background-color: #0b0e14; position: relative; }
        .control-panel { padding: 20px; overflow-y: auto; height: 100%; }
        .control-group { background-color: #131722; border: 1px solid #2a2e39; padding: 20px; border-radius: 6px; margin-bottom: 15px; max-width: 900px; }
        .flash-up { color: #089981 !important; }
        .flash-down { color: #f23645 !important; }
        .chart-ohlc-bar { background-color: #131722; border-bottom: 1px solid #2a2e39; padding: 8px 15px; display: flex; align-items: center; gap: 15px; font-size: 11px; flex-shrink: 0; }
        .ohlc-item { display: flex; gap: 4px; }
        .ohlc-label { color: #94a3b8; }
        .opt-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
        .opt-table th, .opt-table td { border: 1px solid #2a2e39; padding: 8px; text-align: center; }
        .opt-table th { background-color: #181c25; color: #38bdf8; }
        .opt-table tr { cursor: pointer; }
        .opt-table tr:hover { background-color: #1e222d; }
        #toast { position: fixed; bottom: 20px; right: 20px; background: #181c25; border: 1px solid #38bdf8; color: white; padding: 12px 20px; border-radius: 6px; font-size: 12px; z-index: 1000; display: none; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        .status-badge { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: #f23645; margin-right: 5px; }
        .status-badge.connected { background-color: #089981; }
    </style>
</head>
<body>
    <div class="header">
        <div><b>▲ NIFTY 50</b> <span style="color: #089981; margin-left: 5px;" id="niftyHeader">22,620.45</span></div>
        <div><b>▲ BANKNIFTY</b> <span style="color: #089981; margin-left: 5px;" id="bankniftyHeader">48,250.10</span></div>
        <div style="display: flex; gap: 15px; align-items: center;">
            <div style="font-size: 11px;"><span id="connBadge" class="status-badge"></span><span id="connStatusText">Disconnected</span></div>
            <div style="color: #38bdf8; font-weight: bold;">⚡ Fully Autonomous Bot Terminal</div>
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
                <input type="text" id="searchInput" class="input-field" placeholder="Search Stock (e.g. HDFC, RELIANCE)..." oninput="searchSymbol()" style="margin: 0 0 6px 0;">
                <div style="display: flex; gap: 6px; margin-top: 4px;">
                    <div style="flex: 1;">
                        <label style="font-size: 9px; color: #94a3b8;">Min Price (₹)</label>
                        <input type="number" id="minPriceFilter" class="input-field" value="0" oninput="renderWatchlistUI(masterWatchlist)" style="margin: 2px 0 0 0;">
                    </div>
                    <div style="flex: 1;">
                        <label style="font-size: 9px; color: #94a3b8;">Max Price (₹)</label>
                        <input type="number" id="maxPriceFilter" class="input-field" value="50000" oninput="renderWatchlistUI(masterWatchlist)" style="margin: 2px 0 0 0;">
                    </div>
                </div>
            </div>
            <div style="padding: 8px 12px; font-size: 10px; color: #94a3b8; font-weight: bold; text-transform: uppercase; display: flex; justify-content: space-between;">
                <span>Pro Live Watchlist</span>
                <span style="color: #38bdf8; cursor: pointer; font-weight: bold;" onclick="loadMarketStatus()">REFRESH</span>
            </div>
            <div class="watchlist-container" id="watchlistContainer">
                <div style="padding: 15px; color: #94a3b8; text-align: center; font-size: 11px;">Connect broker to load live market feed</div>
            </div>
        </div>
        <div class="content-area">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chart', this)">Chart & Monitoring</div>
                <div class="tab" onclick="switchTab('options', this)">Options Chain & Autonomous Bot</div>
                <div class="tab" onclick="switchTab('positions', this)">Positions & P&L</div>
                <div class="tab" onclick="switchTab('logs', this)">System Logs</div>
            </div>
            <div id="tab-chart" class="tab-content active">
                <div class="toolbar">
                    <span id="activeSymbolTitle" style="font-weight: bold; font-size: 14px; color: #38bdf8;">SELECT A STOCK / OPTION</span>
                    <select id="timeframeSelect" class="btn" style="background-color: #181c25;" onchange="loadHistoricalData()">
                        <option value="1m">1m</option>
                        <option value="5m" selected>5m</option>
                        <option value="15m">15m</option>
                        <option value="1h">1h</option>
                    </select>
                    <button class="btn" style="background-color: #181c25; color: #38bdf8;" onclick="manualRefreshChart()">🔄 Refresh Chart</button>
                </div>
                <div class="chart-ohlc-bar">
                    <div><b id="barSymbol" style="color: #38bdf8;">--</b> • <span id="barTf">5m</span> • NSE/NFO</div>
                    <div class="ohlc-item"><span class="ohlc-label">O</span><span id="ohlcO" style="color: #089981;">0.00</span></div>
                    <div class="ohlc-item"><span class="ohlc-label">H</span><span id="ohlcH" style="color: #089981;">0.00</span></div>
                    <div class="ohlc-item"><span class="ohlc-label">L</span><span id="ohlcL" style="color: #f23645;">0.00</span></div>
                    <div class="ohlc-item"><span class="ohlc-label">C</span><span id="ohlcC" style="color: #089981;">0.00</span></div>
                    <div id="ohlcChg" style="color: #089981; font-weight: bold;">+0.00 (+0.00%)</div>
                </div>
                <div id="chartContainer"></div>
            </div>
            <div id="tab-options" class="tab-content">
                <div class="control-panel">
                    <div class="control-group">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">Nifty & Bank Nifty Options Chain (CE / PE) - Click row to select strike</h3>
                        <div style="display: flex; gap: 15px; align-items: center; margin-bottom: 10px;">
                            <button class="btn" style="background-color: #38bdf8; color: #0b0e14; height: 30px;" onclick="loadOptionsChain()">Fetch Chain Range</button>
                        </div>
                        <table class="opt-table">
                            <thead>
                                <tr>
                                    <th>CALLS LTP</th>
                                    <th>Volume</th>
                                    <th>STRIKE</th>
                                    <th>Volume</th>
                                    <th>PUTS LTP</th>
                                </tr>
                            </thead>
                            <tbody id="optionsChainBody">
                                <tr><td colspan="5" style="color: #94a3b8; text-align: center; padding: 20px;">Click 'Fetch Chain Range' to load filtered Option strikes.</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div class="control-group" style="border-color: #38bdf8;">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">⚡ Fully Autonomous Bot (Dynamic Symbol Match)</h3>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Select Target Mode</label>
                                <select id="botTargetMode" class="input-field" style="background-color: #0b0e14; color: white;">
                                    <option value="STOCK">Active Watchlist Stock / Option</option>
                                    <option value="NIFTY">Nifty 50 Index</option>
                                    <option value="OPTION_CE">Options Call (CE)</option>
                                    <option value="OPTION_PE">Options Put (PE)</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Autonomous Base Quantity / Lots</label>
                                <input type="number" id="botQty" class="input-field" value="1">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Product Type</label>
                                <select class="input-field" id="botProduct" style="background-color: #0b0e14; color: white;">
                                    <option value="INTRADAY">INTRADAY (MIS)</option>
                                    <option value="CARRYFORWARD">CARRYFORWARD (CNC/NRML)</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #94a3b8;">Margin / Leverage Multiplier</label>
                                <select class="input-field" id="botLeverage" style="background-color: #0b0e14; color: white;">
                                    <option value="1">1x (Normal)</option>
                                    <option value="2">2x Leverage</option>
                                    <option value="3">3x Leverage</option>
                                    <option value="4">4x Leverage</option>
                                    <option value="5" selected>5x Leverage (Intraday Max)</option>
                                    <option value="10">10x Leverage</option>
                                </select>
                            </div>
                        </div>
                        <div style="margin-top: 20px; display: flex; align-items: center; gap: 15px;">
                            <button id="botToggleBtn" class="btn" style="background-color: #089981; color: white; padding: 10px 20px;" onclick="toggleBot()">Start Fully Autonomous Bot</button>
                            <span id="botStatus" style="font-size: 12px; color: #f23645; font-weight: bold;">● Bot Status: Stopped</span>
                        </div>
                    </div>
                </div>
            </div>
            <div id="tab-positions" class="tab-content">
                <div class="control-panel">
                    <div class="control-group" style="width: 100%;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <h3 style="margin: 0; color: #38bdf8; font-size: 14px;">Live Orders, Positions &amp; Cancellation</h3>
                            <button class="btn" style="background-color: #38bdf8; color: #0b0e14;" onclick="loadOrderBook()">🔄 Refresh Orders &amp; Positions</button>
                        </div>
                        <h4 style="color: #38bdf8; font-size: 12px; margin-bottom: 5px;">Open / Pending Orders</h4>
                        <table class="opt-table" style="margin-bottom: 20px;">
                            <thead>
                                <tr>
                                    <th>Order ID</th>
                                    <th>Symbol</th>
                                    <th>Type</th>
                                    <th>Qty</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="ordersTableBody">
                                <tr><td colspan="6" style="color: #94a3b8; text-align: center; padding: 15px;">Loading open orders...</td></tr>
                            </tbody>
                        </table>
                        <h4 style="color: #38bdf8; font-size: 12px; margin-bottom: 5px;">Active Positions &amp; P&amp;L</h4>
                        <table class="opt-table">
                            <thead>
                                <tr>
                                    <th>Symbol</th>
                                    <th>Exchange</th>
                                    <th>Product</th>
                                    <th>Qty</th>
                                    <th>Buy/Sell Avg</th>
                                    <th>LTP</th>
                                    <th>P&amp;L (₹)</th>
                                </tr>
                            </thead>
                            <tbody id="positionsTableBody">
                                <tr><td colspan="7" style="color: #94a3b8; text-align: center; padding: 15px;">Connect broker to load live positions &amp; P&amp;L.</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            <div id="tab-logs" class="tab-content">
                <div class="control-panel">
                    <div class="control-group" id="logsContainer" style="width: 100%; font-family: monospace; font-size: 11px; color: #38bdf8; height: 400px; overflow-y: auto;">
                        [System] Autonomous Bot Terminal ready. Connect broker to begin...
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div id="toast"></div>
    <script>
        let masterWatchlist = [];
        let selectedSymbol = "";
        let selectedToken = "";
        let selectedExchange = "NSE";
        let stockPrices = {}, stockPrevCloses = {}, stockTokens = {}, stockMap = {}, stockExchanges = {};
        let isConnected = false, ws = null;

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
        document.addEventListener("DOMContentLoaded", function() {
            loadCredentials();
            initChart();
            initWebSocket();
        });

        function updateConnectionUI(connected) {
            isConnected = connected;
            const badge = document.getElementById("connBadge");
            const text = document.getElementById("connStatusText");
            if (connected) {
                badge.className = "status-badge connected";
                text.innerText = "Connected Live";
            } else {
                badge.className = "status-badge";
                text.innerText = "Disconnected";
            }
        }

        function initWebSocket() {
            const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${proto}//${window.location.host}/ws`);
            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data && data.symbol && data.ltp) {
                        const sym = data.symbol;
                        const newPrice = parseFloat(data.ltp);
                        stockPrices[sym] = newPrice;
                        const wlEl = document.getElementById("wl_" + sym);
                        if (wlEl) {
                            wlEl.innerText = "₹" + newPrice.toFixed(2);
                            const prevClose = stockPrevCloses[sym] || newPrice;
                            wlEl.className = newPrice >= prevClose ? "flash-up" : "flash-down";
                        }
                        if (sym === selectedSymbol && candlestickSeries) {
                            const currentTimeSec = Math.floor(Date.now() / 1000);
                            const interval = 300;
                            const candleTimeSlot = Math.floor(currentTimeSec / interval) * interval;
                            if (!currentCandle || currentCandleTime !== candleTimeSlot) {
                                currentCandleTime = candleTimeSlot;
                                currentCandle = { time: currentCandleTime, open: newPrice, high: newPrice, low: newPrice, close: newPrice };
                            } else {
                                currentCandle.high = Math.max(currentCandle.high, newPrice);
                                currentCandle.low = Math.min(currentCandle.low, newPrice);
                                currentCandle.close = newPrice;
                            }
                            candlestickSeries.update(currentCandle);
                            updateOhlcBar(currentCandle);
                        }
                    }
                } catch(e) {}
            };
        }

        let currentCandle = null, currentCandleTime = 0;
        function updateOhlcBar(candle) {
            if (!candle) return;
            document.getElementById("ohlcO").innerText = candle.open.toFixed(2);
            document.getElementById("ohlcH").innerText = candle.high.toFixed(2);
            document.getElementById("ohlcL").innerText = candle.low.toFixed(2);
            document.getElementById("ohlcC").innerText = candle.close.toFixed(2);
            const diff = candle.close - candle.open;
            const pct = candle.open > 0 ? (diff / candle.open) * 100 : 0;
            const chgEl = document.getElementById("ohlcChg");
            chgEl.innerText = `${diff >= 0 ? '+' : ''}${diff.toFixed(2)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`;
            chgEl.style.color = diff >= 0 ? '#089981' : '#f23645';
        }

        function loadMarketStatus() {
            const container = document.getElementById("watchlistContainer");
            container.innerHTML = `<div style="padding: 15px; color: #38bdf8; text-align: center; font-size: 11px;">Loading Pro Watchlist & Caching Scrip Master...</div>`;

            fetch('/market-status').then(res => res.json()).then(data => {
                if(data && data.stocks) {
                    masterWatchlist = data.stocks;
                    masterWatchlist.forEach(s => {
                        stockPrices[s.symbol] = s.price;
                        stockPrevCloses[s.symbol] = s.prev_close;
                        stockTokens[s.token] = s.symbol;
                        stockMap[s.symbol] = s.token;
                        stockExchanges[s.symbol] = s.exchange;
                    });
                    renderWatchlistUI(masterWatchlist);
                    showToast("Watchlist & Scrip Master Ready!");
                }
            });
        }

        let searchTimeout = null;
        function searchSymbol() {
            const query = document.getElementById("searchInput").value.trim();
            if(query.length < 2) return;
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                fetch(`/search-symbol?q=${encodeURIComponent(query)}`).then(res => res.json()).then(data => {
                    if(data && data.length > 0) {
                        data.forEach(newItem => {
                            if (!masterWatchlist.some(x => x.symbol === newItem.symbol)) {
                                masterWatchlist.push(newItem);
                            }
                            stockPrices[newItem.symbol] = newItem.price;
                            stockPrevCloses[newItem.symbol] = newItem.prev_close;
                            stockTokens[newItem.token] = newItem.symbol;
                            stockMap[newItem.symbol] = newItem.token;
                            stockExchanges[newItem.symbol] = newItem.exchange;
                        });
                        renderWatchlistUI(masterWatchlist);
                        showToast(`Stock added successfully!`);
                    } else {
                        showToast("Stock not found in local cache.");
                    }
                });
            }, 300);
        }

        function renderWatchlistUI(items) {
            const container = document.getElementById("watchlistContainer");
            if (!container) return;
            container.innerHTML = "";
            const minP = parseFloat(document.getElementById("minPriceFilter").value) || 0;
            const maxP = parseFloat(document.getElementById("maxPriceFilter").value) || 50000;
            
            const filteredItems = items.filter(s => {
                const currentP = stockPrices[s.symbol] || s.price || 0.0;
                return currentP >= minP && currentP <= maxP;
            });

            if(filteredItems.length === 0) {
                container.innerHTML = `<div style="padding: 15px; color: #94a3b8; text-align: center; font-size: 11px;">No matching stocks in range (₹${minP} - ₹${maxP})</div>`;
                return;
            }

            filteredItems.forEach(s => {
                const item = document.createElement("div");
                item.className = `watchlist-item ${s.symbol === selectedSymbol ? 'active' : ''}`;
                item.onclick = () => {
                    selectedSymbol = s.symbol;
                    selectedToken = s.token;
                    selectedExchange = s.exchange || "NSE";
                    document.getElementById("activeSymbolTitle").innerText = selectedSymbol;
                    document.getElementById("barSymbol").innerText = selectedSymbol;
                    renderWatchlistUI(masterWatchlist);
                    loadHistoricalData();
                };
                const currentP = stockPrices[s.symbol] || s.price || 0.0;
                const prevClose = stockPrevCloses[s.symbol] || s.prev_close || currentP;
                let colorClass = currentP >= prevClose ? "flash-up" : "flash-down";
                
                item.innerHTML = `
                    <div>
                        <div style="font-weight: bold; font-size: 12px;">${s.symbol}</div>
                        <div style="font-size: 10px; color: #94a3b8;">${s.exchange}</div>
                    </div>
                    <div style="text-align: right;">
                        <div id="wl_${s.symbol}" class="${colorClass}" style="font-weight: bold; font-size: 12px;">₹${currentP.toFixed(2)}</div>
                        <div style="font-size: 10px; color: #089981;">${isConnected ? 'LIVE' : 'READY'}</div>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        function loadOrderBook() {
            fetch('/order-book').then(res => res.json()).then(data => {
                const tbody = document.getElementById("ordersTableBody");
                tbody.innerHTML = "";
                if(!data.success || !data.orders || data.orders.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="6" style="color: #94a3b8; text-align: center; padding: 15px;">No open/pending orders found.</td></tr>`;
                } else {
                    data.orders.forEach(o => {
                        const tr = document.createElement("tr");
                        tr.innerHTML = `
                            <td>${o.orderid}</td>
                            <td style="font-weight: bold; color: #38bdf8;">${o.symbol}</td>
                            <td>${o.transactiontype}</td>
                            <td>${o.qty}</td>
                            <td>${o.status}</td>
                            <td><button class="btn" style="background-color: #f23645; color: white; padding: 3px 8px;" onclick="cancelOrder('${o.orderid}')">Cancel</button></td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            });

            fetch('/positions').then(res => res.json()).then(data => {
                const tbody = document.getElementById("positionsTableBody");
                tbody.innerHTML = "";
                if(!data.success || !data.positions || data.positions.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="7" style="color: #94a3b8; text-align: center; padding: 15px;">No open positions found.</td></tr>`;
                    return;
                }
                data.positions.forEach(p => {
                    const pnlClass = p.pnl >= 0 ? "flash-up" : "flash-down";
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td style="font-weight: bold; color: #38bdf8;">${p.symbol}</td>
                        <td>${p.exchange}</td>
                        <td>${p.product}</td>
                        <td>${p.qty}</td>
                        <td>₹${p.avgPrice.toFixed(2)}</td>
                        <td>₹${p.ltp.toFixed(2)}</td>
                        <td class="${pnlClass}" style="font-weight: bold;">₹${p.pnl.toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
                showToast("Orders & Positions Updated!");
            });
        }

        function cancelOrder(orderId) {
            fetch('/cancel-order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ orderid: orderId })
            }).then(res => res.json()).then(resp => {
                if(resp.success) {
                    showToast("Order Cancelled Successfully!");
                    loadOrderBook();
                } else {
                    showToast("Failed to cancel: " + resp.message);
                }
            });
        }

        let chart, candlestickSeries;
        function loadHistoricalData() {
            if (!isConnected || !selectedToken) return;
            fetch(`/history?token=${selectedToken}&exchange=${selectedExchange}`).then(res => res.json()).then(data => {
                if (data && data.length > 0) {
                    candlestickSeries.setData(data);
                    chart.timeScale().fitContent();
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
                grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
                timeScale: { borderColor: '#2a2e39', timeVisible: true }
            });
            candlestickSeries = chart.addCandlestickSeries({ upColor: '#089981', downColor: '#f23645' });
        }
        function switchTab(tabName, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
            if(tabName === 'positions') {
                loadOrderBook();
            }
        }
        function addLog(msg) {
            const box = document.getElementById("logsContainer");
            box.innerHTML += `<div>[${new Date().toLocaleTimeString()}] ${msg}</div>`;
            box.scrollTop = box.scrollHeight;
        }

        function loadOptionsChain() {
            const minPrice = parseFloat(document.getElementById("minPriceFilter").value) || 0;
            const maxPrice = parseFloat(document.getElementById("maxPriceFilter").value) || 50000;
            fetch(`/options-chain?min_price=${minPrice}&max_price=${maxPrice}`).then(res => res.json()).then(data => {
                const tbody = document.getElementById("optionsChainBody");
                tbody.innerHTML = "";
                if(data.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="5" style="color: #94a3b8; text-align: center; padding: 20px;">No strikes found in range</td></tr>`;
                    return;
                }
                data.forEach(row => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td style="color: #089981;">₹${row.ceLtp.toFixed(2)}</td>
                        <td>${row.ceVol}</td>
                        <td style="font-weight: bold; color: #38bdf8;">${row.strike}</td>
                        <td>${row.peVol}</td>
                        <td style="color: #f23645;">₹${row.peLtp.toFixed(2)}</td>
                    `;
                    tr.onclick = () => {
                        selectedSymbol = `NIFTY_${row.strike}_STRIKE`;
                        selectedToken = "NIFTY";
                        selectedExchange = "NFO";
                        document.getElementById("activeSymbolTitle").innerText = `Selected Strike: NIFTY ${row.strike}`;
                        showToast(`Strike ${row.strike} Selected for Autonomous Bot!`);
                        addLog(`User selected Strike ${row.strike} (CE LTP: ₹${row.ceLtp}, PE LTP: ₹${row.peLtp}) from Options Chain.`);
                    };
                    tbody.appendChild(tr);
                });
                showToast("Options Chain Range Loaded! Click any row to select strike.");
            });
        }

        let botRunning = false;
        function toggleBot() {
            botRunning = !botRunning;
            const btn = document.getElementById("botToggleBtn");
            const status = document.getElementById("botStatus");
            const targetMode = document.getElementById("botTargetMode").value;
            const qty = document.getElementById("botQty").value;
            const product = document.getElementById("botProduct").value;
            const leverage = document.getElementById("botLeverage").value;

            fetch('/toggle-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    active: botRunning,
                    mode: targetMode,
                    qty: parseInt(qty),
                    product: product,
                    leverage: parseInt(leverage),
                    symbol: selectedSymbol,
                    token: selectedToken,
                    exchange: selectedExchange
                })
            }).then(res => res.json()).then(resp => {
                if(botRunning) {
                    btn.innerText = "Stop Fully Autonomous Bot";
                    btn.style.backgroundColor = "#f23645";
                    status.innerText = `● Bot Status: Active (${leverage}x Leverage)`;
                    status.style.color = "#089981";
                    addLog(`Fully Autonomous Bot started with ${leverage}x leverage for ${selectedSymbol || 'Index/Option'}.`);
                    showToast("Fully Autonomous Bot Started!");
                } else {
                    btn.innerText = "Start Fully Autonomous Bot";
                    btn.style.backgroundColor = "#089981";
                    status.innerText = "● Bot Status: Stopped";
                    status.style.color = "#f23645";
                    addLog("Autonomous Bot stopped.");
                    showToast("Autonomous Bot Stopped!");
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
            fetch('/connect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
            .then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    updateConnectionUI(true);
                    showToast("Connected to SmartAPI successfully!");
                    addLog("Connected to SmartAPI feed successfully.");
                    loadMarketStatus();
                } else {
                    updateConnectionUI(false);
                    showToast("Login Failed: " + resp.message);
                    addLog("Connection failed: " + resp.message);
                }
            });
        }
        function manualRefreshChart() { loadHistoricalData(); showToast("Chart Refreshed!"); }
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
            try: await connection.send_text(message)
            except: pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def ensure_smart_api_session():
    global smart_api_obj, last_login_time
    if not saved_credentials["api_key"] or not saved_credentials["client_id"]:
        return smart_api_obj
    if smart_api_obj:
        return smart_api_obj
    current_time = time.time()
    if current_time - last_login_time < 60:
        return smart_api_obj
    try:
        last_login_time = current_time
        print("[System] Generating fresh session to SmartAPI...")
        obj = SmartConnect(api_key=saved_credentials["api_key"])
        totp_code = pyotp.TOTP(saved_credentials["totp_key"]).now()
        session = obj.generateSession(saved_credentials["client_id"], saved_credentials["password"], totp_code)
        if session and session.get('status'):
            smart_api_obj = obj
            print("[System] Successfully logged in with fresh session!")
            return smart_api_obj
    except Exception as e:
        print("[System] Session generation failed:", e)
    return smart_api_obj

def start_smart_websocket(auth_token, api_key, client_code, feed_token):
    global sws
    try:
        sws = SmartWebSocketV2(auth_token, api_key, client_code, feed_token)
        def on_data(ws_app, message):
            try:
                token = str(message.get("token"))
                ltp = float(message.get("last_traded_price", 0)) / 100.0
                symbol = stockTokens.get(token)
                if symbol and ltp > 0:
                    live_prices[symbol] = ltp
                    asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps({"symbol": symbol, "ltp": ltp})), loop)
            except: pass
        def on_open(ws_app):
            tokens_to_sub = [t for t in stockTokens.keys() if t.isdigit()]
            if tokens_to_sub:
                token_list = [{"exchangeType": 1, "tokens": tokens_to_sub}]
                sws.subscribe("corridor", 1, token_list)
        sws.on_data = on_data
        sws.on_open = on_open
        sws.connect()
    except Exception as e:
        print("SWS Error:", e)

@app.on_event("startup")
async def startup_event():
    global loop, scrip_master_cache
    loop = asyncio.get_event_loop()
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            scrip_master_cache = res.json()
            print(f"[System] Scrip Master successfully cached locally. Total items: {len(scrip_master_cache)}")
        else:
            raise Exception("Non-200 response")
    except Exception as e:
        print("[System] Failed to download Scrip Master online. Loading fallback backup items:", e)
        # Fallback default items to prevent blank watchlist if offline/timeout on startup
        scrip_master_cache = [
            {"symbol": "RELIANCE-EQ", "token": "2885", "exchange": "NSE", "name": "RELIANCE"},
            {"symbol": "TCS-EQ", "token": "11536", "exchange": "NSE", "name": "TCS"},
            {"symbol": "INFY-EQ", "token": "1594", "exchange": "NSE", "name": "INFY"},
            {"symbol": "SBIN-EQ", "token": "3045", "exchange": "NSE", "name": "SBIN"},
            {"symbol": "ITC-EQ", "token": "1660", "exchange": "NSE", "name": "ITC"}
        ]

@app.get("/", response_class=HTMLResponse)
def get_root():
    return HTML_CONTENT

@app.get("/market-status")
def get_market_status():
    global stockTokens, stockMap, stockExchanges
    active_api = ensure_smart_api_session()
    stocks_list = []
    master_symbols = ["RELIANCE", "TCS", "INFY", "SBIN", "ITC"]
    raw_watchlist_items = []
    for sym in master_symbols:
        matched = [item for item in scrip_master_cache if item.get("symbol") == f"{sym}-EQ" or item.get("symbol") == sym]
        if matched:
            raw_watchlist_items.append(matched[0])
    
    for item in raw_watchlist_items:
        sym = item.get("symbol")
        tok = item.get("token")
        exch = item.get("exchange", "NSE")
        if not sym or not tok: continue
        price = 0.0
        close_price = 0.0
        if active_api:
            try:
                resp = active_api.ltpData(exch, sym, str(tok))
                if resp and resp.get("status") and resp.get("data"):
                    price = float(resp["data"].get("ltp", 0.0))
                    close_price = float(resp["data"].get("close", price))
                time.sleep(0.3)
            except: pass
        stocks_list.append({
            "symbol": sym,
            "token": str(tok),
            "exchange": exch,
            "price": price,
            "prev_close": close_price if close_price > 0 else price
        })
        stockTokens[str(tok)] = sym
        stockMap[sym] = str(tok)
        stockExchanges[sym] = exch
        live_prices[sym] = price
    return {"stocks": stocks_list}

@app.get("/search-symbol")
def search_symbol(q: str):
    results = []
    query_upper = q.upper()
    active_api = ensure_smart_api_session()
    try:
        matched_items = [item for item in scrip_master_cache if query_upper in item.get("symbol", "").upper() or query_upper in item.get("name", "").upper()]
        for item in matched_items[:5]:
            sym = item.get("symbol")
            tok = item.get("token")
            exch = item.get("exchange", "NSE")
            price = 0.0
            close_price = 0.0
            if active_api:
                try:
                    ltp_resp = active_api.ltpData(exch, sym, str(tok))
                    if ltp_resp and ltp_resp.get("status") and ltp_resp.get("data"):
                        price = float(ltp_resp["data"].get("ltp", 0.0))
                        close_price = float(ltp_resp["data"].get("close", price))
                    time.sleep(0.3)
                except: pass
            results.append({
                "symbol": sym,
                "token": str(tok),
                "exchange": exch,
                "price": price,
                "prev_close": close_price if close_price > 0 else price
            })
            stockTokens[str(tok)] = sym
            stockMap[sym] = str(tok)
            stockExchanges[sym] = exch
    except Exception as e:
        print("Search error:", e)
    return results

@app.get("/order-book")
def get_order_book():
    active_api = ensure_smart_api_session()
    if not active_api: return {"success": False, "orders": []}
    try:
        resp = active_api.orderBook()
        formatted_orders = []
        if resp and resp.get("status") and resp.get("data"):
            for order in resp["data"]:
                status = order.get("status", "").upper()
                if status in ["OPEN", "PENDING", "TRIGGER PENDING"]:
                    formatted_orders.append({
                        "orderid": order.get("orderid"),
                        "symbol": order.get("tradingsymbol"),
                        "transactiontype": order.get("transactiontype"),
                        "qty": order.get("quantity"),
                        "status": status
                    })
        return {"success": True, "orders": formatted_orders}
    except Exception as e:
        return {"success": False, "orders": []}

@app.post("/cancel-order")
def cancel_order(data: dict):
    active_api = ensure_smart_api_session()
    if not active_api: return {"success": False, "message": "Broker not connected"}
    try:
        resp = active_api.cancelOrder(orderid=data.get("orderid"), variety=data.get("variety", "NORMAL"))
        if resp and resp.get("status"): return {"success": True}
        return {"success": False, "message": resp.get("message", "Cancellation failed")}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/positions")
def get_positions():
    active_api = ensure_smart_api_session()
    if not active_api: return {"success": False, "positions": []}
    try:
        resp = active_api.position()
        formatted_positions = []
        if resp and resp.get("status") and resp.get("data"):
            for pos in resp["data"]:
                sym = pos.get("tradingsymbol")
                exch = pos.get("exchange")
                prod = pos.get("producttype")
                qty = float(pos.get("netqty", 0))
                avg_price = float(pos.get("averageprice", 0))
                ltp = float(pos.get("ltp", avg_price))
                pnl = float(pos.get("pnl", (ltp - avg_price) * qty if qty > 0 else 0))
                formatted_positions.append({"symbol": sym, "exchange": exch, "product": prod, "qty": qty, "avgPrice": avg_price, "ltp": ltp, "pnl": pnl})
        return {"success": True, "positions": formatted_positions}
    except Exception as e:
        return {"success": False, "positions": []}

@app.get("/options-chain")
def get_options_chain(min_price: float = 0.0, max_price: float = 50000.0):
    base_price = live_prices.get("NIFTY", 22620.0)
    chain = []
    for i in range(-20, 21):
        strike = int(base_price + (i * 50))
        ce_ltp = round(max(1.0, 250.0 - (i * 12.0)), 2)
        pe_ltp = round(max(1.0, 250.0 + (i * 12.0)), 2)
        if (min_price <= ce_ltp <= max_price) or (min_price <= pe_ltp <= max_price):
            chain.append({"strike": strike, "ceLtp": ce_ltp, "ceVol": 12500 + abs(i) * 1500, "peLtp": pe_ltp, "peVol": 14000 + abs(i) * 1200})
    return chain

@app.get("/history")
def get_historical_candles(token: str, exchange: str = "NSE"):
    active_api = ensure_smart_api_session()
    if not active_api: return []
    try:
        historicParam = {
            "exchange": exchange, 
            "symboltoken": token, 
            "interval": "FIVE_MINUTE", 
            "fromdate": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), 
            "todate": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        time.sleep(1)
        resp = active_api.getCandleData(historicParam)
        if resp and resp.get("status") and resp.get("data"):
            return [{"time": int(datetime.fromisoformat(c[0].replace("+05:30", "")).timestamp()), "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4])} for c in resp["data"]]
    except: pass
    return []

def autonomous_bot_background_worker():
    time.sleep(10)
    order_placed_flag = False
    while True:
        time.sleep(30)
        if not bg_state["bot_active"] or order_placed_flag: continue
        try:
            active_api = ensure_smart_api_session()
            if not active_api: continue
            target_symbol = bg_state.get("symbol", "RELIANCE-EQ")
            target_token = bg_state.get("token", "2885")
            target_exch = bg_state.get("exchange", "NSE")
            final_qty = bg_state.get("bot_qty", 1) * bg_state.get("leverage", 1)
            
            order_params = {
                "variety": "NORMAL", "tradingsymbol": target_symbol, "symboltoken": str(target_token),
                "transactiontype": "BUY", "exchange": target_exch, "ordertype": "MARKET",
                "producttype": bg_state.get("bot_product", "INTRADAY"), "duration": "DAY", "price": "0", "quantity": str(final_qty)
            }
            response = active_api.placeOrder(order_params)
            if response:
                order_placed_flag = True
                bg_state["bot_active"] = False
                break
        except Exception as e:
            print("Autonomous Bot Error:", e)

threading.Thread(target=autonomous_bot_background_worker, daemon=True).start()

@app.post("/toggle-bot")
async def toggle_bot_state(data: dict):
    bg_state["bot_active"] = data.get("active", False)
    bg_state["target_mode"] = data.get("mode", "STOCK")
    bg_state["bot_qty"] = int(data.get("qty", 1))
    bg_state["bot_product"] = data.get("product", "INTRADAY")
    bg_state["leverage"] = int(data.get("leverage", 1))
    bg_state["symbol"] = data.get("symbol", "")
    bg_state["token"] = data.get("token", "")
    bg_state["exchange"] = data.get("exchange", "NSE")
    return {"status": "success", "bot_active": bg_state["bot_active"]}

@app.post("/connect")
async def connect_broker(data: dict):
    global smart_api_obj, last_login_time
    try:
        saved_credentials["api_key"] = data["apiKey"]
        saved_credentials["client_id"] = data["clientId"]
        saved_credentials["password"] = data["password"]
        saved_credentials["totp_key"] = data["totpKey"]
        last_login_time = time.time()
        obj = SmartConnect(api_key=data["apiKey"])
        totp_code = pyotp.TOTP(data["totpKey"]).now()
        session = obj.generateSession(data["clientId"], data["password"], totp_code)
        if session and session.get('status'):
            smart_api_obj = obj
            threading.Thread(target=start_smart_websocket, args=(session['data']['jwtToken'], data["apiKey"], data["clientId"], session['data'].get('feedToken') or getattr(obj, 'feedToken', None)), daemon=True).start()
            return {"status": "success"}
        return {"status": "error", "message": "Invalid Credentials"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
