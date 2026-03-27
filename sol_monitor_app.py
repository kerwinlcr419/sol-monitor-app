import time
import json
import sqlite3
import threading
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()

# ====================== 配置 ======================
CONFIG = {
    "MAX_MARKET_CAP": 50000,
    "CONDITION_1_MIN_BUY": 800,
    "CONDITION_2_MIN_BUY_1MIN": 1500,
    "CONDITION_3_OLD_TOKEN_DAYS": 7,
    "CONDITION_3_SUDDEN_BUY": 3000,
    "SCAN_INTERVAL": 60,
}

ALERTS = []

# ====================== 数据库 ======================
def init_db():
    conn = sqlite3.connect("tokens.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tokens
                 (address TEXT PRIMARY KEY, platform TEXT, created_at TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_token(address, platform):
    try:
        conn = sqlite3.connect("tokens.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO tokens VALUES (?, ?, ?)",
                  (address, platform, datetime.now()))
        conn.commit()
        conn.close()
    except:
        pass

def get_token_days(address):
    try:
        conn = sqlite3.connect("tokens.db")
        c = conn.cursor()
        c.execute("SELECT created_at FROM tokens WHERE address=?", (address,))
        row = c.fetchone()
        conn.close()
        if not row:
            return 0
        delta = datetime.now() - datetime.fromisoformat(row[0])
        return delta.days
    except:
        return 0

# ====================== 平台抓取 ======================
def fetch_pump_fun():
    try:
        res = requests.get("https://pump.fun/api/coins", timeout=10)
        data = res.json()
        return [{
            "mint": x["mint"],
            "market_cap": float(x.get("marketCap", 0)),
            "buy_1min": float(x.get("buy1m", 0)),
            "platform": "Pump.fun"
        } for x in data if x.get("mint")]
    except:
        return []

def fetch_moonshot():
    try:
        res = requests.get("https://api.moonshot.so/api/v1/tokens", timeout=10)
        data = res.json()
        return [{
            "mint": x["mint"],
            "market_cap": float(x.get("marketCap", 0)),
            "buy_1min": float(x.get("volume1m", 0)),
            "platform": "Moonshot"
        } for x in data.get("tokens", []) if x.get("mint")]
    except:
        return []

def fetch_launchlab():
    try:
        res = requests.get("https://letsbonk.fun/api/new", timeout=10)
        data = res.json()
        return [{
            "mint": x["mint"],
            "market_cap": float(x.get("marketCap", 0)),
            "buy_1min": float(x.get("buy1m", 0)),
            "platform": "LaunchLab"
        } for x in data if x.get("mint")]
    except:
        return []

def fetch_meteora():
    try:
        res = requests.get("https://api.meteora.ag/clusters/mainnet/alpha-vaults", timeout=10)
        data = res.json()
        return [{
            "mint": x["tokenMint"],
            "market_cap": float(x.get("marketCap", 0)),
            "buy_1min": float(x.get("buyVolume1m", 0)),
            "platform": "Meteora"
        } for x in data if x.get("tokenMint")]
    except:
        return []

def fetch_zerg():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get("https://zerg.zone/api/v1/new-tokens", headers=headers, timeout=10)
        data = res.json()
        return [{
            "mint": x["mint"],
            "market_cap": float(x.get("marketCap", 0)),
            "buy_1min": float(x.get("buy1m", 0)),
            "platform": "Zerg.zone"
        } for x in data.get("data", []) if x.get("mint")]
    except:
        return []

ALL_FETCHERS = [fetch_pump_fun, fetch_moonshot, fetch_launchlab, fetch_meteora, fetch_zerg]

# ====================== 条件判断 ======================
def check_token(token):
    mc = token["market_cap"]
    buy = token["buy_1min"]
    mint = token["mint"]
    platform = token["platform"]
    days = get_token_days(mint)
    save_token(mint, platform)

    reason = None

    if mc <= CONFIG["MAX_MARKET_CAP"] and buy >= CONFIG["CONDITION_1_MIN_BUY"]:
        reason = "低市值 + 买入达标"

    elif buy >= CONFIG["CONDITION_2_MIN_BUY_1MIN"]:
        reason = "1分钟买入暴量"

    elif days >= CONFIG["CONDITION_3_OLD_TOKEN_DAYS"] and buy >= CONFIG["CONDITION_3_SUDDEN_BUY"]:
        reason = f"老币{days}天 突然大额买入"

    if reason:
        alert = {
            "time": datetime.now().strftime("%m-%d %H:%M:%S"),
            "platform": platform,
            "mint": mint,
            "mc": round(mc, 2),
            "buy1m": round(buy, 2),
            "reason": reason
        }
        ALERTS.insert(0, alert)
        if len(ALERTS) > 100:
            del ALERTS[100:]

# ====================== 监控线程 ======================
def monitor_thread():
    init_db()
    while True:
        for f in ALL_FETCHERS:
            try:
                tokens = f()
                for t in tokens:
                    check_token(t)
            except:
                pass
        time.sleep(CONFIG["SCAN_INTERVAL"])

# ====================== 手机自适应网页界面 ======================
@app.get("/", response_class=HTMLResponse)
def home():
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SOL 监测</title>
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; font-family:system-ui; }}
            body {{ background:#0b0f1a; color:#eaecef; padding:12px; }}
            .title {{ text-align:center; font-size:22px; margin-bottom:12px; color:#ffdd57; }}
            .config {{ background:#121a29; padding:10px; border-radius:12px; margin-bottom:12px; font-size:14px; }}
            .alert {{ background:#151c30; padding:10px; border-radius:10px; margin-bottom:8px;
                      border-left:3px solid #ffdd57; font-size:14px; }}
            .platform {{ color:#7ccfff; font-weight:bold; }}
            .reason {{ color:#ff7070; margin-top:4px; }}
            .mint {{ color:#aaa; word-break:break-all; font-size:12px; margin-top:4px; }}
        </style>
    </head>
    <body>
        <div class="title">SOL 多平台代币监测</div>

        <div class="config">
            市值上限: ${CONFIG['MAX_MARKET_CAP']}<br>
            1分钟买入: ≥${CONFIG['CONDITION_2_MIN_BUY_1MIN']}<br>
            老币天数: {CONFIG['CONDITION_3_OLD_TOKEN_DAYS']}天
        </div>
    """

    for a in ALERTS[:30]:
        html += f'''
        <div class="alert">
            <div class="platform">{a['platform']}</div>
            <div>市值: ${a['mc']}　买入1m: ${a['buy1m']}</div>
            <div class="reason">{a['reason']}</div>
            <div class="mint">{a['mint']}</div>
            <div style="font-size:11px;color:#888;margin-top:4px;">{a['time']}</div>
        </div>
        '''

    html += """
    </body>
    </html>
    """
    return html

# ====================== 启动 ======================
if __name__ == "__main__":
    threading.Thread(target=monitor_thread, daemon=True).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)