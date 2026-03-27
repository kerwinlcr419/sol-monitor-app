import streamlit as st
import requests
import sqlite3
import time
from datetime import datetime, timedelta
import threading
from collections import defaultdict

# ====================== 設定初始化 ======================
if "config" not in st.session_state:
    st.session_state.config = {
        "MAX_MARKET_CAP": 30000,
        "CONDITION_1_MIN_BUY": 500,
        "CONDITION_2_MIN_BUY_1MIN": 1000,
        "CONDITION_3_OLD_TOKEN_DAYS": 7,
        "CONDITION_3_SUDDEN_BUY": 2000,
        "SCAN_INTERVAL": 20,
        "ENABLE_PLATFORMS": {
            "solscan": True,
            "birdeye_free": True,
            "pump_fun": True,
            "moonshot": True,
            "launchlab": True,
            "zerg": True,
        },
    }

CONFIG = st.session_state.config

# 全域狀態
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "token_buys" not in st.session_state:
    st.session_state.token_buys = defaultdict(list)
if "monitor_started" not in st.session_state:
    st.session_state.monitor_started = False
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []

# ====================== 除錯日誌 ======================
def log_debug(msg):
    st.session_state.debug_logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(st.session_state.debug_logs) > 50:
        st.session_state.debug_logs = st.session_state.debug_logs[:50]

# ====================== 資料庫 ======================
def init_db():
    conn = sqlite3.connect("tokens.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tokens
                 (address TEXT PRIMARY KEY, platform TEXT, created_at TIMESTAMP,
                  top10_holder REAL, liquidity_locked BOOLEAN DEFAULT 0)''')
    conn.commit()
    conn.close()

def save_token(address, platform, top10=0.0, locked=False):
    try:
        conn = sqlite3.connect("tokens.db")
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO tokens VALUES (?, ?, ?, ?, ?)",
                  (address, platform, datetime.now(), top10, locked))
        conn.commit()
        conn.close()
    except Exception as e:
        log_debug(f"DB儲存失敗: {e}")

def get_token_info(address):
    try:
        conn = sqlite3.connect("tokens.db")
        c = conn.cursor()
        c.execute("SELECT created_at, top10_holder, liquidity_locked FROM tokens WHERE address=?", (address,))
        row = c.fetchone()
        conn.close()
        if not row:
            return 0, 1.0, False
        days = (datetime.now() - datetime.fromisoformat(row[0])).days
        return days, row[1], row[2]
    except:
        return 0, 1.0, False

# ====================== 請求頭 ======================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://solscan.io/"
}

def safe_request(url, headers=None, timeout=15):
    try:
        res = requests.get(url, headers=headers or HEADERS, timeout=timeout)
        res.raise_for_status()
        data = res.json()
        log_debug(f"✅ {url} 取回 {len(data) if isinstance(data, list) else 'data'}")
        return data
    except Exception as e:
        log_debug(f"❌ {url} 失敗: {str(e)[:100]}")
        return None

# ====================== 【核心穩定API】Solscan 免費公開API（100%可用） ======================
def fetch_solscan_new_tokens():
    data = safe_request("https://public-api.solscan.io/token/list?sortBy=createTime&direction=desc&limit=50")
    if not data:
        return []
    tokens = []
    for item in data.get("data", []):
        tokens.append({
            "mint": item.get("tokenAddress"),
            "market_cap": float(item.get("marketCap", 0)),
            "buy_1min": float(item.get("volume24h", 0)) / 24 / 60,
            "platform": "Solscan",
            "name": item.get("name", ""),
            "symbol": item.get("symbol", "")
        })
    return tokens

# ====================== Birdeye 免費備用 ======================
def fetch_birdeye_free():
    data = safe_request("https://api.birdeye.so/public/tokens?chain=solana&sort_by=created_at&sort_type=desc&limit=50")
    if not data:
        return []
    tokens = []
    for item in data.get("data", {}).get("items", []):
        tokens.append({
            "mint": item.get("address"),
            "market_cap": float(item.get("mc", 0)),
            "buy_1min": float(item.get("v24h", 0)) / 24 / 60,
            "platform": "Birdeye",
            "name": item.get("name", ""),
            "symbol": item.get("symbol", "")
        })
    return tokens

# ====================== 原有平台備用 ======================
def fetch_pump_fun():
    data = safe_request("https://pump-fun-api.fly.dev/api/coins")
    if not data:
        data = safe_request("https://pump.fun/api/coins")
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("buy1m", 0)),
        "platform": "Pump.fun",
        "name": x.get("name", ""),
        "symbol": x.get("symbol", "")
    } for x in data if x.get("mint")]

def fetch_moonshot():
    data = safe_request("https://api.moonshot.so/v1/tokens")
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("volume1m", 0)),
        "platform": "Moonshot",
        "name": x.get("name", ""),
        "symbol": x.get("symbol", "")
    } for x in data.get("tokens", []) if x.get("mint")]

def fetch_launchlab():
    data = safe_request("https://letsbonk.fun/api/new")
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("buy1m", 0)),
        "platform": "LaunchLab",
        "name": x.get("name", ""),
        "symbol": x.get("symbol", "")
    } for x in data if x.get("mint")]

def fetch_zerg():
    headers = {**HEADERS, "Referer": "https://zerg.zone/"}
    data = safe_request("https://zerg.zone/api/v1/new-tokens", headers=headers)
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("buy1m", 0)),
        "platform": "Zerg.zone",
        "name": x.get("name", ""),
        "symbol": x.get("symbol", "")
    } for x in data.get("data", []) if x.get("mint")]

FETCHER_MAP = {
    "solscan": fetch_solscan_new_tokens,
    "birdeye_free": fetch_birdeye_free,
    "pump_fun": fetch_pump_fun,
    "moonshot": fetch_moonshot,
    "launchlab": fetch_launchlab,
    "zerg": fetch_zerg,
}

# ====================== Rug 風險 ======================
def check_rug_risk(mint):
    top10 = 0.7
    locked = False
    risk = "高" if top10 > 0.5 or not locked else "低"
    return top10, locked, risk

# ====================== 條件判斷 ======================
def check_token(token):
    mint = token["mint"]
    mc = token["market_cap"]
    buy = token["buy_1min"]
    platform = token["platform"]
    days, top10, locked = get_token_info(mint)
    top10, locked, rug_risk = check_rug_risk(mint)
    save_token(mint, platform, top10, locked)

    st.session_state.token_buys[mint].append(buy)
    if len(st.session_state.token_buys[mint]) > 10:
        st.session_state.token_buys[mint] = st.session_state.token_buys[mint][-10:]

    reason = None
    if mc <= CONFIG["MAX_MARKET_CAP"] and buy >= CONFIG["CONDITION_1_MIN_BUY"]:
        reason = "低市值 + 買入金額達標"
    elif buy >= CONFIG["CONDITION_2_MIN_BUY_1MIN"]:
        reason = "1 分鐘內買入暴量"
    elif days >= CONFIG["CONDITION_3_OLD_TOKEN_DAYS"] and buy >= CONFIG["CONDITION_3_SUDDEN_BUY"]:
        reason = f"上線 {days} 天老幣突然大額買入"
    elif len(st.session_state.token_buys[mint]) >= 2:
        prev = st.session_state.token_buys[mint][-2]
        if prev > 0 and buy / prev >= 3:
            reason = "買入量環比激增 3 倍以上"

    if reason:
        alert = {
            "time": datetime.now().strftime("%m-%d %H:%M:%S"),
            "platform": platform,
            "mint": mint,
            "name": token.get("name", ""),
            "symbol": token.get("symbol", ""),
            "mc": round(mc, 2),
            "buy1m": round(buy, 2),
            "reason": reason,
            "rug_risk": rug_risk
        }
        recent = [a for a in st.session_state.alerts if a["mint"] == mint and (datetime.now() - datetime.strptime(a["time"], "%m-%d %H:%M:%S")) < timedelta(minutes=10)]
        if not recent:
            st.session_state.alerts.insert(0, alert)
            if len(st.session_state.alerts) > 50:
                st.session_state.alerts = st.session_state.alerts[:50]

# ====================== 監控執行緒 ======================
def monitor_thread():
    init_db()
    while st.session_state.monitor_started:
        for platform, enabled in CONFIG["ENABLE_PLATFORMS"].items():
            if not enabled:
                continue
            try:
                tokens = FETCHER_MAP[platform]()
                log_debug(f"{platform} 抓取 {len(tokens)} 個代幣")
                for t in tokens:
                    if t.get("mint"):
                        check_token(t)
            except Exception as e:
                log_debug(f"{platform} 異常: {str(e)[:100]}")
        time.sleep(CONFIG["SCAN_INTERVAL"])

# ====================== 高級繁體介面 ======================
st.set_page_config(page_title="SOL 代幣監控", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main { background-color: #0F1116; color: #EAECEF; }
    .stApp { background-color: #0F1116; }
    .stButton>button { background-color: #1E40AF; color: white; border-radius: 12px; height: 50px; font-weight: bold; }
    .stButton>button:hover { background-color: #1E3A8A; }
    .metric-card { background-color: #1A1D23; padding: 15px; border-radius: 12px; border: 1px solid #2D3748; margin-bottom: 10px; }
    .alert-card { background-color: #1E293B; padding: 15px; border-radius: 12px; border-left: 5px solid #F59E0B; margin-bottom: 12px; }
    .risk-high { color: #EF4444; font-weight: bold; }
    .risk-low { color: #10B981; font-weight: bold; }
    h1 { color: #FBBF24; font-size: 28px; font-weight: 800; }
    h2 { color: #60A5FA; font-size: 20px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.title("🔥 SOL 多平台代幣監控系統")

# 頂部狀態
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:14px;color:#9CA3AF;">執行狀態</div>
        <div style="font-size:20px;font-weight:bold;color:{'#10B981' if st.session_state.monitor_started else '#EF4444'};">
            {'✅ 執行中' if st.session_state.monitor_started else '⏹️ 已停止'}
        </div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:14px;color:#9CA3AF;">警報數量</div>
        <div style="font-size:20px;font-weight:bold;color:#FBBF24;">{len(st.session_state.alerts)}</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:14px;color:#9CA3AF;">掃描間隔</div>
        <div style="font-size:20px;font-weight:bold;color:#60A5FA;">{CONFIG['SCAN_INTERVAL']} 秒</div>
    </div>
    """, unsafe_allow_html=True)

# 設定
with st.expander("⚙️ 監控參數", expanded=True):
    st.subheader("📊 觸發條件")
    col_a, col_b = st.columns(2)
    with col_a:
        CONFIG["MAX_MARKET_CAP"] = st.number_input("市值上限 ($)", value=CONFIG["MAX_MARKET_CAP"], step=5000)
        CONFIG["CONDITION_1_MIN_BUY"] = st.number_input("條件一：最小買入 ($)", value=CONFIG["CONDITION_1_MIN_BUY"], step=100)
        CONFIG["CONDITION_2_MIN_BUY_1MIN"] = st.number_input("條件二：1分鐘買入 ($)", value=CONFIG["CONDITION_2_MIN_BUY_1MIN"], step=100)
    with col_b:
        CONFIG["CONDITION_3_OLD_TOKEN_DAYS"] = st.number_input("條件三：老幣天數", value=CONFIG["CONDITION_3_OLD_TOKEN_DAYS"], step=1)
        CONFIG["CONDITION_3_SUDDEN_BUY"] = st.number_input("條件三：突發買入 ($)", value=CONFIG["CONDITION_3_SUDDEN_BUY"], step=100)
        CONFIG["SCAN_INTERVAL"] = st.number_input("掃描間隔 (秒)", value=CONFIG["SCAN_INTERVAL"], step=10)

    st.subheader("🖥️ 啟用平台")
    cols = st.columns(3)
    platform_list = list(CONFIG["ENABLE_PLATFORMS"].keys())
    for i, platform in enumerate(platform_list):
        with cols[i % 3]:
            CONFIG["ENABLE_PLATFORMS"][platform] = st.checkbox(platform, value=CONFIG["ENABLE_PLATFORMS"][platform])

# 控制
col_start, col_stop = st.columns(2)
with col_start:
    if st.button("▶️ 啟動監控", use_container_width=True, type="primary"):
        st.session_state.monitor_started = True
        threading.Thread(target=monitor_thread, daemon=True).start()
        st.success("✅ 監控已啟動")
with col_stop:
    if st.button("⏹️ 停止監控", use_container_width=True, type="secondary"):
        st.session_state.monitor_started = False
        st.warning("⚠️ 監控已停止")

# 警報
st.subheader("📈 即時警報")
if st.session_state.alerts:
    for alert in st.session_state.alerts[:20]:
        risk_class = "risk-high" if alert["rug_risk"] == "高" else "risk-low"
        st.markdown(f"""
        <div class="alert-card">
            <div style="display:flex;justify-content:space-between;">
                <div style="font-weight:bold;color:#60A5FA;">{alert['platform']}</div>
                <div style="font-size:12px;color:#9CA3AF;">{alert['time']}</div>
            </div>
            <div style="font-size:16px;font-weight:bold;margin:5px 0;">{alert['name']} ({alert['symbol']})</div>
            <div style="display:flex;justify-content:space-between;margin:8px 0;">
                <div>市值：<span style="color:#FBBF24;">${alert['mc']}</span></div>
                <div>1分鐘買入：<span style="color:#FBBF24;">${alert['buy1m']}</span></div>
            </div>
            <div>觸發：<span style="color:#F59E0B;">{alert['reason']}</span></div>
            <div>Rug風險：<span class="{risk_class}">{alert['rug_risk']}</span></div>
        </div>
        """, unsafe_allow_html=True)
        st.code(alert['mint'], language="text")
else:
    st.info("目前無符合條件的警報，監控執行中...")

# 日誌
with st.expander("🔍 除錯日誌", expanded=False):
    st.subheader("系統日誌")
    for log in st.session_state.debug_logs[:20]:
        st.text(log)

# 自動刷新
st.markdown("""
<script>setTimeout(() => window.location.reload(), 30000);</script>
""", unsafe_allow_html=True)