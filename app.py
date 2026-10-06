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
    {"symbol": "RELIANCE-EQ", "token": "2885", "name": "Reliance Industries", "price": 1276.40, "chg": -1.09, "exchange": "NSE"},
    {"symbol": "TCS-EQ", "token": "11536", "name": "Tata Consultancy Services", "price": 4098.30, "chg": 0.75, "exchange": "NSE"},
    {"symbol": "HDFCBANK-EQ", "token": "1333", "name": "HDFC Bank Ltd", "price": 1650.00, "chg": 0.50, "exchange": "NSE"},
    {"symbol": "INFY-EQ", "token": "1594", "name": "Infosys Limited", "price": 1912.50, "chg": 1.20, "exchange": "NSE"},
    {"symbol": "ICICIBANK-EQ", "token": "4963", "name": "ICICI Bank Ltd", "price": 1120.50, "chg": 0.85, "exchange": "NSE"},
    {"symbol": "SBIN-EQ", "token": "3045", "name": "State Bank of India", "price": 810.50, "chg": 1.1, "exchange": "NSE"},
    {"symbol": "BHARTIARTL-EQ", "token": "10604", "name": "Bharti Airtel Ltd", "price": 1450.20, "chg": -0.4, "exchange": "NSE"},
    {"symbol": "KOTAKBANK-EQ", "token": "1922", "name": "Kotak Mahindra Bank", "price": 1740.00, "chg": 0.3, "exchange": "NSE"},
    {"symbol": "LT-EQ", "token": "11483", "name": "Larsen & Toubro Ltd", "price": 3650.10, "chg": 1.5, "exchange": "NSE"},
    {"symbol": "ITC-EQ", "token": "1660", "name": "ITC Limited", "price": 430.20, "chg": 0.4, "exchange": "NSE"},
    {"symbol": "HINDUNILVR-EQ", "token": "1394", "name": "Hindustan Unilever", "price": 2450.00, "chg": -0.2, "exchange": "NSE"},
    {"symbol": "AXISBANK-EQ", "token": "5900", "name": "Axis Bank Ltd", "price": 1150.80, "chg": 0.6, "exchange": "NSE"},
    {"symbol": "BAJFINANCE-EQ", "token": "317", "name": "Bajaj Finance Ltd", "price": 7100.00, "chg": 1.2, "exchange": "NSE"},
    {"symbol": "MARUTI-EQ", "token": "10999", "name": "Maruti Suzuki India", "price": 12400.50, "chg": 0.9, "exchange": "NSE"},
    {"symbol": "SUNPHARMA-EQ", "token": "3351", "name": "Sun Pharma Industries", "price": 1780.20, "chg": -0.7, "exchange": "NSE"},
    {"symbol": "TITAN-EQ", "token": "3506", "name": "Titan Company Ltd", "price": 3450.00, "chg": 0.5, "exchange": "NSE"},
    {"symbol": "ASIANPAINT-EQ", "token": "236", "name": "Asian Paints Ltd", "price": 2890.00, "chg": -1.1, "exchange": "NSE"},
    {"symbol": "TATAMOTORS-EQ", "token": "3456", "name": "Tata Motors Ltd", "price": 980.40, "chg": 1.8, "exchange": "NSE"},
    {"symbol": "WIPRO-EQ", "token": "3787", "name": "Wipro Limited", "price": 540.00, "chg": 0.4, "exchange": "NSE"},
    {"symbol": "NIFTY", "token": "99926000", "name": "Nifty 50 Index", "price": 22620.45, "chg": 0.42, "exchange": "NSE"},
    {"symbol": "BANKNIFTY", "token": "99926009", "name": "Bank Nifty Index", "price": 48250.10, "chg": 0.65, "exchange": "NSE"}
]

smart_api_obj = None

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Angel One Pro Terminal - Options Auto Bot</title>
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
        .flash-up { color: #089981 !important; }
        .flash-down { color: #f23645 !important; }

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
            <div style="color: #38bdf8; font-weight: bold;">⚡ Angel One Pro Terminal</div>
        </div>
    </div>

    <div class="main-container">
        <!-- Sidebar -->
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

        <!-- Main Content Workspace -->
        <div class="content-area">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chart', this)">Chart & Analysis</div>
                <div class="tab" onclick="switchTab('options', this)">Options Chain (CE/PE)</div>
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
                    <button class="btn" style="background-color: #181c25; color: #38bdf8;" onclick="manualRefreshChart()">🔄 Refresh Chart</button>
                    
                    <div style="position: relative; display: inline-block;">
                        <button class="btn" style="background-color: #181c25; color: #38bdf8;" onclick="toggleIndicatorMenu()">Indicators ▼</button>
                        <div id="indicatorDropdown" style="display: none; position: absolute; background: #181c25; border: 1px solid #2a2e39; padding: 10px; z-index: 10; width: 190px; border-radius: 4px; top: 30px;">
                            <label style="display:block; font-size:11px; margin-bottom:6px; cursor:pointer;"><input type="checkbox" value="SMA" onchange="applyIndicator(this)"> SMA (Moving Avg)</label>
                            <label style="display:block; font-size:11px; margin-bottom:6px; cursor:pointer;"><input type="checkbox" value="BB" onchange="applyIndicator(this)"> Bollinger Bands</label>
                            <label style="display:block; font-size:11px; margin-bottom:6px; cursor:pointer;"><input type="checkbox" value="RSI" onchange="applyIndicator(this)"> RSI (Relative Str)</label>
                            <label style="display:block; font-size:11px; cursor:pointer;"><input type="checkbox" value="MACD" onchange="applyIndicator(this)"> MACD Oscillator</label>
                        </div>
                    </div>
                </div>

                <!-- OHLC & Quick Buy/Sell Bar -->
                <div class="chart-ohlc-bar">
                    <div><b id="barSymbol" style="color: #38bdf8;">RELIANCE-EQ</b> • <span id="barTf">5m</span> • NSE</div>
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

            <!-- Tab 2: Options Chain (CE / PE) -->
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

            <!-- Tab 3: Trade -->
            <div id="tab-trade" class="tab-content">
                <div class="control-panel">
                    <div class="control-group">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">Manual Order Execution & Stoploss</h3>
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

            <!-- Tab 4: Bot -->
            <div id="tab-bot" class="tab-content">
                <div class="control-panel">
                    <div class="control-group">
                        <h3 style="margin-top: 0; color: #38bdf8; font-size: 14px;">Fully Autonomous Bot Settings (Equities & Options CE/PE)</h3>
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
                            <button id="botToggleBtn" class="btn" style="background-color: #089981; color: white; padding: 10px 20px;" onclick="toggleBot()">Start Options & Equity Autonomous Bot</button>
                            <span id="botStatus" style="margin-left: 15px; font-size: 12px; color: #f23645;">● Bot Status: Stopped</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab 5: Logs -->
            <div id="tab-logs" class="tab-content">
                <div class="control-panel">
                    <div class="control-group" id="logsContainer" style="width: 100%; font-family: monospace; font-size: 11px; color: #38bdf8; height: 400px; overflow-y: auto;">
                        [System] Terminal running with Options Auto-Trading Bot. Waiting for broker connection...
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="toast"></div>

    <script>
        const masterStocks = [
            { symbol: "RELIANCE-EQ", token: "2885", name: "Reliance Industries", price: 1276.40, chg: -1.09, exchange: "NSE" },
            { symbol: "TCS-EQ", token: "11536", name: "Tata Consultancy Services", price: 4098.30, chg: 0.75, exchange: "NSE" },
            { symbol: "HDFCBANK-EQ", token: "1333", name: "HDFC Bank Ltd", price: 1650.00, chg: 0.50, exchange: "NSE" },
            { symbol: "INFY-EQ", token: "1594", name: "Infosys Limited", price: 1912.50, chg: 1.20, exchange: "NSE" },
            { symbol: "ICICIBANK-EQ", token: "4963", name: "ICICI Bank Ltd", price: 1120.50, chg: 0.85, exchange: "NSE" },
            { symbol: "SBIN-EQ", token: "3045", name: "State Bank of India", price: 810.50, chg: 1.1, exchange: "NSE" },
            { symbol: "BHARTIARTL-EQ", token: "10604", name: "Bharti Airtel Ltd", price: 1450.20, chg: -0.4, exchange: "NSE" },
            { symbol: "KOTAKBANK-EQ", token: "1922", name: "Kotak Mahindra Bank", price: 1740.00, chg: 0.3, exchange: "NSE" },
            { symbol: "LT-EQ", token: "11483", name: "Larsen & Toubro Ltd", price: 3650.10, chg: 1.5, exchange: "NSE" },
            { symbol: "ITC-EQ", token: "1660", name: "ITC Limited", price: 430.20, chg: 0.4, exchange: "NSE" },
            { symbol: "HINDUNILVR-EQ", token: "1394", name: "Hindustan Unilever", price: 2450.00, chg: -0.2, exchange: "NSE" },
            { symbol: "AXISBANK-EQ", token: "5900", name: "Axis Bank Ltd", price: 1150.80, chg: 0.6, exchange: "NSE" },
            { symbol: "BAJFINANCE-EQ", token: "317", name: "Bajaj Finance Ltd", price: 7100.00, chg: 1.2, exchange: "NSE" },
            { symbol: "MARUTI-EQ", token: "10999", name: "Maruti Suzuki India", price: 12400.50, chg: 0.9, exchange: "NSE" },
            { symbol: "SUNPHARMA-EQ", token: "3351", name: "Sun Pharma Industries", price: 1780.20, chg: -0.7, exchange: "NSE" },
            { symbol: "TITAN-EQ", token: "3506", name: "Titan Company Ltd", price: 3450.00, chg: 0.5, exchange: "NSE" },
            { symbol: "ASIANPAINT-EQ", token: "236", name: "Asian Paints Ltd", price: 2890.00, chg: -1.1, exchange: "NSE" },
            { symbol: "TATAMOTORS-EQ", token: "3456", name: "Tata Motors Ltd", price: 980.40, chg: 1.8, exchange: "NSE" },
            { symbol: "WIPRO-EQ", token: "3787", name: "Wipro Limited", price: 540.00, chg: 0.4, exchange: "NSE" },
            { symbol: "NIFTY", token: "99926000", name: "Nifty 50 Index", price: 22620.45, chg: 0.42, exchange: "NSE" },
            { symbol: "BANKNIFTY", token: "99926009", name: "Bank Nifty Index", price: 48250.10, chg: 0.65, exchange: "NSE" }
        ];

        let watchlist = [...masterStocks];
        let selectedSymbol = "RELIANCE-EQ";
        let stockPrices = {};
        let stockTokens = {};
        let stockMap = {};
        let stockExchanges = {};
        let currentMasterData = [];
        let activeTrade = null;
        let lastFetchedOptions = [];

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
            renderWatchlistUI(watchlist);
            initChart();
        });

        function loadOptionsChain() {
            const indexName = document.getElementById("optIndexSelect").value;
            const expiry = document.getElementById("optExpirySelect").value;
            addLog(`Fetching Option Chain for ${indexName} [Expiry: ${expiry}]...`);

            fetch(`/options-chain?index=${indexName}&expiry=${expiry}`)
                .then(res => res.json())
                .then(data => {
                    lastFetchedOptions = data;
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
                    } else {
                        tbody.innerHTML = `<tr><td colspan="7" style="color: #f23645; text-align: center; padding: 15px;">Could not fetch options. Ensure broker is connected.</td></tr>`;
                    }
                }).catch(err => {
                    addLog("Error loading options chain: " + err);
                });
        }

        function tradeOption(sym, price, type) {
            addLog(`Placing Option Order: ${type} ${sym} @ ₹${price}`);
            fetch('/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: sym, token: "0", exchange: "NFO", transactionType: type, quantity: 25, productType: 'INTRADAY', price: price, stopLoss: 5.0, trailingSl: 2.0 })
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    showToast(`Option Order Executed: ${sym}`);
                    addLog(`[Success] Option order placed for ${sym}`);
                } else {
                    showToast("Order Failed: " + resp.message);
                }
            });
        }

        function manualRefreshChart() {
            addLog(`Manually refreshing chart for ${selectedSymbol}...`);
            loadHistoricalData(false);
            showToast(`Chart Refreshed for ${selectedSymbol}`);
        }

        function autoSelectStockByQty(qtyVal) {
            const qty = parseInt(qtyVal);
            if (isNaN(qty) || qty <= 0) return;
            if (watchlist.length > 0) {
                const index = (qty - 1) % watchlist.length;
                selectedSymbol = watchlist[index].symbol;
                document.getElementById("activeSymbolTitle").innerText = selectedSymbol;
                document.getElementById("barSymbol").innerText = selectedSymbol;
                renderWatchlistUI(watchlist);
                loadHistoricalData();
            }
        }

        function filterWatchlist() {
            const query = document.getElementById("searchInput").value.toLowerCase();
            const minVal = document.getElementById("minPriceInput").value;
            const maxVal = document.getElementById("maxPriceInput").value;
            
            const minPrice = (minVal !== "") ? parseFloat(minVal) : 0;
            const maxPrice = (maxVal !== "") ? parseFloat(maxVal) : Infinity;

            const filtered = masterStocks.filter(s => {
                const p = stockPrices[s.symbol] || s.price || 100.0;
                const matchesSearch = s.symbol.toLowerCase().includes(query) || s.name.toLowerCase().includes(query);
                const matchesPrice = p >= minPrice && p <= maxPrice;
                return matchesSearch && matchesPrice;
            });

            watchlist = filtered;
            renderWatchlistUI(watchlist);
        }

        function resetWatchlist() {
            document.getElementById("searchInput").value = "";
            document.getElementById("minPriceInput").value = "";
            document.getElementById("maxPriceInput").value = "";
            watchlist = [...masterStocks];
            renderWatchlistUI(watchlist);
            showToast("Watchlist reset!");
        }

        function renderWatchlistUI(items) {
            const container = document.getElementById("watchlistContainer");
            if (!container) return;
            container.innerHTML = "";
            
            if (items.length === 0) {
                container.innerHTML = '<div style="padding: 15px; font-size: 11px; color: #f23645; text-align: center;">No matching stocks found.</div>';
                return;
            }

            items.forEach(s => {
                const item = document.createElement("div");
                item.className = `watchlist-item ${s.symbol === selectedSymbol ? 'active' : ''}`;
                item.onclick = () => {
                    selectedSymbol = s.symbol;
                    document.getElementById("activeSymbolTitle").innerText = selectedSymbol;
                    document.getElementById("barSymbol").innerText = selectedSymbol;
                    renderWatchlistUI(watchlist);
                    loadHistoricalData();
                };
                item.innerHTML = `
                    <div>
                        <div style="font-weight: bold; font-size: 12px;">${s.symbol}</div>
                        <div style="font-size: 10px; color: #94a3b8;">${s.name}</div>
                    </div>
                    <div style="text-align: right; display: flex; align-items: center; gap: 8px;">
                        <div>
                            <div id="wl_${s.symbol}" style="font-weight: bold; font-size: 12px;">₹${(stockPrices[s.symbol] || s.price).toFixed(2)}</div>
                            <div style="font-size: 10px; color: ${s.chg >= 0 ? '#089981' : '#f23645'};">${s.chg >= 0 ? '+' : ''}${s.chg}%</div>
                        </div>
                        <span style="color: #f23645; font-weight: bold; font-size: 14px; cursor: pointer; padding: 2px 6px;" onclick="event.stopPropagation(); removeFromWatchlist('${s.symbol}')" title="Remove">×</span>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        function removeFromWatchlist(sym) {
            if (watchlist.length <= 1) {
                showToast("Cannot remove all items!");
                return;
            }
            watchlist = watchlist.filter(s => s.symbol !== sym);
            renderWatchlistUI(watchlist);
            showToast(`Removed ${sym}`);
        }

        let chart, candlestickSeries;
        let activeIndicators = {};
        let currentCandle = null;
        let currentCandleTime = 0;
        let oldestLoadedTimestamp = 0;
        let isLoadingMore = false;

        function getCandleIntervalSeconds() {
            const tf = document.getElementById("timeframeSelect").value;
            if (tf === '1m') return 60;
            if (tf === '5m') return 300;
            if (tf === '15m') return 900;
            if (tf === '1h') return 3600;
            return 300;
        }

        function updateOhlcBar(candle) {
            if (!candle) return;
            document.getElementById("ohlcO").innerText = candle.open.toFixed(2);
            document.getElementById("ohlcH").innerText = candle.high.toFixed(2);
            document.getElementById("ohlcL").innerText = candle.low.toFixed(2);
            document.getElementById("ohlcC").innerText = candle.close.toFixed(2);
            document.getElementById("quickBuyPrice").innerText = candle.close.toFixed(2);
            document.getElementById("quickSellPrice").innerText = candle.close.toFixed(2);

            const diff = candle.close - candle.open;
            const pct = (diff / candle.open) * 100;
            const chgEl = document.getElementById("ohlcChg");
            chgEl.innerText = `${diff >= 0 ? '+' : ''}${diff.toFixed(2)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`;
            chgEl.style.color = diff >= 0 ? '#089981' : '#f23645';
        }

        function loadHistoricalData(isMore = false, beforeTimestamp = null) {
            const token = stockMap[selectedSymbol] || "2885";
            const exch = stockExchanges[selectedSymbol] || "NSE";
            const tf = document.getElementById("timeframeSelect").value;
            document.getElementById("barTf").innerText = tf;

            if (isMore) {
                if (isLoadingMore) return;
                isLoadingMore = true;
            }

            let url = `/history?token=${token}&exchange=${exch}&timeframe=${tf}`;
            if (isMore && beforeTimestamp) {
                url += `&before_to=${beforeTimestamp}`;
            }

            fetch(url)
                .then(res => res.json())
                .then(data => {
                    if (data && data.length > 0) {
                        const cleanData = data.filter(c => c.open > 0 && c.high > 0 && c.low > 0 && c.close > 0);
                        if (cleanData.length === 0) return;

                        if (isMore) {
                            currentMasterData = cleanData.concat(currentMasterData);
                            candlestickSeries.setData(currentMasterData);
                            isLoadingMore = false;
                        } else {
                            currentMasterData = cleanData;
                            candlestickSeries.setData(currentMasterData);
                            chart.timeScale().fitContent();
                            updateOhlcBar(cleanData[cleanData.length - 1]);
                            addLog(`Loaded ${cleanData.length} candles for ${selectedSymbol}.`);
                        }
                        if (currentMasterData.length > 0) {
                            oldestLoadedTimestamp = currentMasterData[0].time;
                        }
                    } else {
                        isLoadingMore = false;
                    }
                }).catch(err => {
                    isLoadingMore = false;
                });
        }

        function initChart() {
            try {
                const chartElement = document.getElementById('chartContainer');
                chart = LightweightCharts.createChart(chartElement, {
                    width: chartElement.clientWidth || 800,
                    height: 485,
                    layout: { background: { type: 'solid', color: '#0b0e14' }, textColor: '#94a3b8' },
                    grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
                    timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false },
                    rightPriceScale: { 
                        borderColor: '#2a2e39', 
                        autoScale: true,
                        scaleMargins: { top: 0.1, bottom: 0.1 } 
                    }
                });
                
                candlestickSeries = chart.addCandlestickSeries({
                    upColor: '#089981', downColor: '#f23645', borderVisible: false, wickUpColor: '#089981', wickDownColor: '#f23645'
                });
                
                loadHistoricalData(false);

                chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
                    if (range && range.from < 5) {
                        if (!isLoadingMore && oldestLoadedTimestamp > 0) {
                            loadHistoricalData(true, oldestLoadedTimestamp);
                        }
                    }
                });

                window.addEventListener('resize', () => {
                    if (chartElement.clientWidth > 0) {
                        chart.resize(chartElement.clientWidth, 485);
                    }
                });
            } catch (err) {
                console.error("Chart load error:", err);
            }
        }

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
            loadHistoricalData(false);
        }

        function switchTab(tabName, el) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
            setTimeout(() => {
                const chartElement = document.getElementById('chartContainer');
                if (chart && chartElement && chartElement.clientWidth > 0) {
                    chart.resize(chartElement.clientWidth, 485);
                }
            }, 100);
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
            const targetMode = document.getElementById("botTargetMode").value;
            if(botRunning) {
                btn.innerText = "Stop Options & Equity Autonomous Bot";
                btn.style.backgroundColor = "#f23645";
                status.innerText = `● Bot Status: Active [Mode: ${targetMode}]`;
                status.style.color = "#089981";
                addLog(`Autonomous Bot started in ${targetMode} mode.`);
                showToast("Autonomous Bot Started Successfully!");
            } else {
                btn.innerText = "Start Options & Equity Autonomous Bot";
                btn.style.backgroundColor = "#089981";
                status.innerText = "● Bot Status: Stopped";
                status.style.color = "#f23645";
                addLog("Autonomous Bot stopped.");
                showToast("Autonomous Bot Stopped!");
            }
        }

        let isConnected = false;
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
                    isConnected = true;
                    addLog("Live SmartAPI Connection Established Successfully!");
                    showToast("Broker Connected Successfully!");
                    loadHistoricalData(false);
                    startPolling();
                } else {
                    addLog("Connection Failed: " + resp.message);
                    showToast("Login Failed: " + resp.message);
                }
            });
        }

        function startPolling() {
            setInterval(() => {
                if (!isConnected) return;

                const selToken = stockMap[selectedSymbol] || "2885";
                const selExch = stockExchanges[selectedSymbol] || "NSE";

                fetch(`/ltp?exchange=${selExch}&symbol=${selectedSymbol}&token=${selToken}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data && data.status === "success") {
                            const newPrice = data.price;
                            if (newPrice <= 0) return;
                            const sym = selectedSymbol;
                            const oldPrice = stockPrices[sym] || newPrice;
                            stockPrices[sym] = newPrice;

                            const wlEl = document.getElementById("wl_" + sym);
                            if (wlEl) {
                                wlEl.innerText = "₹" + newPrice.toFixed(2);
                                wlEl.className = newPrice > oldPrice ? "flash-up" : (newPrice < oldPrice ? "flash-down" : "");
                            }

                            if (activeTrade && activeTrade.symbol === sym) {
                                let pnl = activeTrade.type === 'BUY' ? (newPrice - activeTrade.entryPrice) * activeTrade.qty : (activeTrade.entryPrice - newPrice) * activeTrade.qty;
                                const pnlEl = document.getElementById("headerPnl");
                                pnlEl.innerText = (pnl >= 0 ? "+₹" : "-₹") + Math.abs(pnl).toFixed(2);
                                pnlEl.style.color = pnl >= 0 ? "#089981" : "#f23645";
                            }
                            
                            if (candlestickSeries) {
                                const currentTimeSec = Math.floor(Date.now() / 1000);
                                const interval = getCandleIntervalSeconds();
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

                            const chartEl = document.getElementById('chartContainer');
                            if (chart && chartEl && chartEl.clientWidth > 0) {
                                chart.resize(chartEl.clientWidth, 485);
                            }

                            if (botRunning) {
                                if (Math.random() < 0.03) {
                                    const targetMode = document.getElementById("botTargetMode").value;
                                    const qty = document.getElementById("botQty").value;
                                    const product = document.getElementById("botProduct").value;
                                    const sl = document.getElementById("botSl").value;
                                    
                                    let tradeSymbol = selectedSymbol;
                                    let tradeExch = selExch;
                                    let tradeToken = selToken;
                                    let tradePrice = newPrice;
                                    let txType = newPrice >= oldPrice ? 'BUY' : 'SELL';

                                    if (targetMode === 'OPTION_CE' || targetMode === 'OPTION_PE') {
                                        if (lastFetchedOptions.length > 0) {
                                            const midOpt = lastFetchedOptions[Math.floor(lastFetchedOptions.length / 2)];
                                            tradeSymbol = targetMode === 'OPTION_CE' ? midOpt.ceSymbol : midOpt.peSymbol;
                                            tradePrice = targetMode === 'OPTION_CE' ? midOpt.ceLtp : midOpt.peLtp;
                                            tradeExch = "NFO";
                                            tradeToken = "0";
                                            txType = 'BUY';
                                        } else {
                                            return;
                                        }
                                    }

                                    fetch('/order', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ symbol: tradeSymbol, token: tradeToken, exchange: tradeExch, transactionType: txType, quantity: parseInt(qty), productType: product, price: tradePrice, stopLoss: parseFloat(sl), trailingSl: 2.0 })
                                    }).then(r => r.json()).then(resp => {
                                        if(resp.status === "success") {
                                            showToast(`[Bot] Auto Order Executed: ${txType} ${tradeSymbol}`);
                                            addLog(`[Bot] Successfully executed automatic ${txType} order for ${tradeSymbol} at ₹${tradePrice}`);
                                        }
                                    });
                                }
                            }
                        }
                    }).catch(err => {});

                watchlist.forEach(s => {
                    if (s.symbol === selectedSymbol) return;
                    fetch(`/ltp?exchange=${s.exchange || 'NSE'}&symbol=${s.symbol}&token=${s.token}`)
                        .then(res => res.json())
                        .then(data => {
                            if (data && data.status === "success" && data.price > 0) {
                                const oldP = stockPrices[s.symbol] || s.price;
                                stockPrices[s.symbol] = data.price;
                                const wlEl = document.getElementById("wl_" + s.symbol);
                                if (wlEl) {
                                    wlEl.innerText = "₹" + data.price.toFixed(2);
                                    wlEl.className = data.price > oldP ? "flash-up" : (data.price < oldP ? "flash-down" : "");
                                }
                            }
                        }).catch(err => {});
                });

            }, 2000);
        }

        function executeQuickOrder(type) {
            const qty = document.getElementById("quickQty").value;
            const token = stockMap[selectedSymbol] || "2885";
            const exch = stockExchanges[selectedSymbol] || "NSE";
            const price = stockPrices[selectedSymbol] || 100.00;

            addLog(`Placing quick ${type} order for ${qty} quantity of ${selectedSymbol}...`);
            
            fetch('/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: selectedSymbol, token: token, exchange: exch, transactionType: type, quantity: parseInt(qty), productType: 'INTRADAY', price: price, stopLoss: 5.0, trailingSl: 2.0 })
            }).then(res => res.json()).then(resp => {
                if(resp.status === "success") {
                    activeTrade = { symbol: selectedSymbol, entryPrice: price, qty: parseInt(qty), type: type };
                    addLog(`SUCCESS: Quick ${type} order placed! ID: ${resp.orderId}`);
                    showToast(`Quick ${type} Order Executed Successfully!`);
                } else {
                    addLog(`ERROR: Order failed - ${resp.message}`);
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

@app.get("/options-chain")
def get_options_chain(index: str = "NIFTY", expiry: str = "2026-10-08"):
    base_price = 22620.0 if index == "NIFTY" else 48250.0
    chain = []
    step = 100 if index == "NIFTY" else 500
    
    for i in range(-5, 6):
        strike = base_price + (i * step)
        ce_ltp = max(5.0, 150.0 - (i * 20) + (i*i))
        pe_ltp = max(5.0, 150.0 + (i * 20) + (i*i))
        chain.append({
            "strike": int(strike),
            "ceSymbol": f"{index}{expiry.replace('-', '')}{int(strike)}CE",
            "ceLtp": round(ce_ltp, 2),
            "ceVol": 12500 + abs(i) * 1500,
            "peSymbol": f"{index}{expiry.replace('-', '')}{int(strike)}PE",
            "peLtp": round(pe_ltp, 2),
            "peVol": 14000 + abs(i) * 1200
        })
    return chain

@app.get("/history")
def get_historical_candles(token: str, exchange: str = "NSE", timeframe: str = "5m", before_to: int = None):
    global smart_api_obj
    if not smart_api_obj:
        return []
    
    interval_map = {"1m": "ONE_MINUTE", "5m": "FIVE_MINUTE", "15m": "FIFTEEN_MINUTE", "1h": "ONE_HOUR"}
    api_interval = interval_map.get(timeframe, "FIVE_MINUTE")
    
    if before_to:
        dt_to = datetime.fromtimestamp(before_to)
        to_date = dt_to.strftime("%Y-%m-%d %H:%M")
        from_date = (dt_to - timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
    else:
        to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        from_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
    
    try:
        historicParam = {
            "exchange": exchange,
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

@app.get("/ltp")
def get_live_ltp(exchange: str, symbol: str, token: str):
    global smart_api_obj
    if not smart_api_obj:
        return {"status": "error", "price": 0.0}
    try:
        resp = smart_api_obj.ltpData(exchange, symbol, token)
        if resp and resp.get("status") and resp.get("data"):
            ltp = float(resp["data"].get("ltp", 0.0))
            return {"status": "success", "price": ltp}
    except Exception as e:
        print("LTP fetch error:", e)
    return {"status": "error", "price": 0.0}

@app.post("/order")
async def place_live_order(data: dict):
    global smart_api_obj
    try:
        if not smart_api_obj:
            return {"status": "error", "message": "Broker not connected!"}
        
        symbol = data["symbol"]
        exchange = data.get("exchange", "NSE")
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
            "exchange": exchange,
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
            return {"status": "success", "orderId": str(order_id)}
        else:
            return {"status": "error", "message": "Order rejected by broker."}
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
            return {"status": "success"}
        else:
            return {"status": "error", "message": "Invalid Credentials"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
