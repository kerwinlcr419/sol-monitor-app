import streamlit as st
import requests
import sqlite3
import time
from datetime import datetime
import threading

# ====================== 配置 ======================
CONFIG = {
    "MAX_MARKET_CAP": 50000,
    "CONDITION_1_MIN_BUY": 800,
    "CONDITION_2_MIN_BUY_1MIN": 1500,
    "CONDITION_3_OLD_TOKEN_DAYS": 7,
    "CONDITION_3_SUDDEN_BUY": 3000,
    "SCAN_INTERVAL": 60,
}

# 全局警报列表
if "alerts" not in st.session_state:
    st.session_state.alerts = []

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
        st.session_state.alerts.insert(0, alert)
        if len(st.session_state.alerts) > 100:
            st.session_state.alerts = st.session_state.alerts[:100]

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

# ====================== Streamlit 界面（手机自适应） ======================
st.set_page_config(page_title="SOL 监测", layout="wide")
st.title("🔥 SOL 多平台代币监测")

# 配置面板
with st.expander("📊 监控条件设置", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        CONFIG["MAX_MARKET_CAP"] = st.number_input("市值上限 ($)", value=CONFIG["MAX_MARKET_CAP"])
        CONFIG["CONDITION_1_MIN_BUY"] = st.number_input("条件1 最小买入 ($)", value=CONFIG["CONDITION_1_MIN_BUY"])
        CONFIG["CONDITION_2_MIN_BUY_1MIN"] = st.number_input("条件2 1分钟买入 ($)", value=CONFIG["CONDITION_2_MIN_BUY_1MIN"])
    with col2:
        CONFIG["CONDITION_3_OLD_TOKEN_DAYS"] = st.number_input("条件3 老币天数", value=CONFIG["CONDITION_3_OLD_TOKEN_DAYS"], step=1)
        CONFIG["CONDITION_3_SUDDEN_BUY"] = st.number_input("条件3 突然买入 ($)", value=CONFIG["CONDITION_3_SUDDEN_BUY"])
        CONFIG["SCAN_INTERVAL"] = st.number_input("扫描间隔 (秒)", value=CONFIG["SCAN_INTERVAL"], step=10)

# 启动监控线程
if "monitor_started" not in st.session_state:
    st.session_state.monitor_started = True
    threading.Thread(target=monitor_thread, daemon=True).start()
    st.success("✅ 监控已启动")

# 警报列表
st.subheader("📈 实时警报")
if st.session_state.alerts:
    for alert in st.session_state.alerts[:30]:
        with st.container(border=True):
            st.markdown(f"**平台**: {alert['platform']} | **时间**: {alert['time']}")
            st.markdown(f"市值: `${alert['mc']}` | 1分钟买入: `${alert['buy1m']}`")
            st.markdown(f"**触发原因**: {alert['reason']}")
            st.code(alert['mint'], language="text")
else:
    st.info("暂无警报，监控运行中...")

# 自动刷新
st.markdown("""
    <script>
        setTimeout(function(){
            window.location.reload();
        }, 60000);
    </script>
""", unsafe_allow_html=True)