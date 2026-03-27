import streamlit as st
import requests
import sqlite3
import time
from datetime import datetime, timedelta
import threading
from collections import defaultdict

# ====================== 配置 ======================
if "config" not in st.session_state:
    st.session_state.config = {
        "MAX_MARKET_CAP": 50000,
        "CONDITION_1_MIN_BUY": 800,
        "CONDITION_2_MIN_BUY_1MIN": 1500,
        "CONDITION_3_OLD_TOKEN_DAYS": 7,
        "CONDITION_3_SUDDEN_BUY": 3000,
        "SCAN_INTERVAL": 60,
        "ENABLE_PLATFORMS": {
            "pump_fun": True,
            "moonshot": True,
            "launchlab": True,
            "meteora": True,
            "zerg": True,
        }
    }

CONFIG = st.session_state.config

# 全局状态
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "token_buys" not in st.session_state:
    st.session_state.token_buys = defaultdict(list)  # 记录最近买入量
if "monitor_started" not in st.session_state:
    st.session_state.monitor_started = False

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
    except Exception as e:
        st.warning(f"DB保存失败: {e}")

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

# ====================== 平台抓取（修复版） ======================
def safe_request(url, headers=None, timeout=15):
    try:
        res = requests.get(url, headers=headers or {}, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        st.error(f"请求失败: {url} -> {str(e)}")
        return None

def fetch_pump_fun():
    data = safe_request("https://pump.fun/api/coins")
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("buy1m", 0)),
        "platform": "Pump.fun"
    } for x in data if x.get("mint") and x.get("marketCap") is not None]

def fetch_moonshot():
    data = safe_request("https://api.moonshot.so/api/v1/tokens")
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("volume1m", 0)),
        "platform": "Moonshot"
    } for x in data.get("tokens", []) if x.get("mint")]

def fetch_launchlab():
    data = safe_request("https://letsbonk.fun/api/new")
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("buy1m", 0)),
        "platform": "LaunchLab"
    } for x in data if x.get("mint")]

def fetch_meteora():
    data = safe_request("https://api.meteora.ag/clusters/mainnet/alpha-vaults")
    if not data:
        return []
    return [{
        "mint": x.get("tokenMint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("buyVolume1m", 0)),
        "platform": "Meteora"
    } for x in data if x.get("tokenMint")]

def fetch_zerg():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    data = safe_request("https://zerg.zone/api/v1/new-tokens", headers=headers)
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("buy1m", 0)),
        "platform": "Zerg.zone"
    } for x in data.get("data", []) if x.get("mint")]

FETCHER_MAP = {
    "pump_fun": fetch_pump_fun,
    "moonshot": fetch_moonshot,
    "launchlab": fetch_launchlab,
    "meteora": fetch_meteora,
    "zerg": fetch_zerg,
}

# ====================== 条件判断（优化版） ======================
def check_token(token):
    mint = token["mint"]
    mc = token["market_cap"]
    buy = token["buy_1min"]
    platform = token["platform"]
    days = get_token_days(mint)
    save_token(mint, platform)

    # 记录买入量用于趋势判断
    st.session_state.token_buys[mint].append(buy)
    if len(st.session_state.token_buys[mint]) > 10:
        st.session_state.token_buys[mint] = st.session_state.token_buys[mint][-10:]

    reason = None
    if mc <= CONFIG["MAX_MARKET_CAP"] and buy >= CONFIG["CONDITION_1_MIN_BUY"]:
        reason = "低市值 + 买入达标"
    elif buy >= CONFIG["CONDITION_2_MIN_BUY_1MIN"]:
        reason = "1分钟买入暴量"
    elif days >= CONFIG["CONDITION_3_OLD_TOKEN_DAYS"] and buy >= CONFIG["CONDITION_3_SUDDEN_BUY"]:
        reason = f"老币{days}天 突然大额买入"
    # 新增：买入量环比激增（可选优化）
    elif len(st.session_state.token_buys[mint]) >= 2:
        prev_buy = st.session_state.token_buys[mint][-2]
        if prev_buy > 0 and buy / prev_buy >= 3:
            reason = "买入量环比激增3倍以上"

    if reason:
        alert = {
            "time": datetime.now().strftime("%m-%d %H:%M:%S"),
            "platform": platform,
            "mint": mint,
            "mc": round(mc, 2),
            "buy1m": round(buy, 2),
            "reason": reason
        }
        # 去重：避免同一代币短时间重复报警
        recent_alerts = [a for a in st.session_state.alerts if a["mint"] == mint and (datetime.now() - datetime.strptime(a["time"], "%m-%d %H:%M:%S")) < timedelta(minutes=5)]
        if not recent_alerts:
            st.session_state.alerts.insert(0, alert)
            if len(st.session_state.alerts) > 100:
                st.session_state.alerts = st.session_state.alerts[:100]

# ====================== 监控线程 ======================
def monitor_thread():
    init_db()
    while True:
        for platform, enabled in CONFIG["ENABLE_PLATFORMS"].items():
            if not enabled:
                continue
            try:
                fetcher = FETCHER_MAP[platform]
                tokens = fetcher()
                for t in tokens:
                    if t.get("mint"):
                        check_token(t)
            except Exception as e:
                st.error(f"{platform} 监测失败: {e}")
        time.sleep(CONFIG["SCAN_INTERVAL"])

# ====================== Streamlit 界面（手机优化版） ======================
st.set_page_config(page_title="SOL 监测", layout="wide")
st.title("🔥 SOL 多平台代币监测")

# 配置面板（手机友好）
with st.expander("📊 监控设置", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        CONFIG["MAX_MARKET_CAP"] = st.number_input("市值上限 ($)", value=CONFIG["MAX_MARKET_CAP"], step=1000)
        CONFIG["CONDITION_1_MIN_BUY"] = st.number_input("条件1 最小买入 ($)", value=CONFIG["CONDITION_1_MIN_BUY"], step=100)
        CONFIG["CONDITION_2_MIN_BUY_1MIN"] = st.number_input("条件2 1分钟买入 ($)", value=CONFIG["CONDITION_2_MIN_BUY_1MIN"], step=100)
    with col2:
        CONFIG["CONDITION_3_OLD_TOKEN_DAYS"] = st.number_input("条件3 老币天数", value=CONFIG["CONDITION_3_OLD_TOKEN_DAYS"], step=1)
        CONFIG["CONDITION_3_SUDDEN_BUY"] = st.number_input("条件3 突然买入 ($)", value=CONFIG["CONDITION_3_SUDDEN_BUY"], step=100)
        CONFIG["SCAN_INTERVAL"] = st.number_input("扫描间隔 (秒)", value=CONFIG["SCAN_INTERVAL"], step=10)

    st.subheader("启用平台")
    for platform in CONFIG["ENABLE_PLATFORMS"].keys():
        CONFIG["ENABLE_PLATFORMS"][platform] = st.checkbox(platform, value=CONFIG["ENABLE_PLATFORMS"][platform])

# 启动/停止监控
col_start, col_stop = st.columns(2)
with col_start:
    if st.button("▶️ 启动监控", use_container_width=True):
        if not st.session_state.monitor_started:
            st.session_state.monitor_started = True
            threading.Thread(target=monitor_thread, daemon=True).start()
            st.success("✅ 监控已启动")
with col_stop:
    if st.button("⏹️ 停止监控", use_container_width=True):
        st.session_state.monitor_started = False
        st.warning("⚠️ 监控已停止")

# 警报列表（手机优化）
st.subheader("📈 实时警报")
if st.session_state.alerts:
    for alert in st.session_state.alerts[:20]:
        with st.container(border=True):
            st.markdown(f"**{alert['platform']}** | {alert['time']}")
            st.markdown(f"市值: `${alert['mc']}` | 1分钟买入: `${alert['buy1m']}`")
            st.markdown(f"⚠️ **{alert['reason']}**")
            st.code(alert['mint'], language="text")
else:
    st.info("暂无警报，监控运行中...")

# 自动刷新（手机友好）
st.markdown("""
    <script>
        setTimeout(function(){
            window.location.reload();
        }, 60000);
    </script>
""", unsafe_allow_html=True)