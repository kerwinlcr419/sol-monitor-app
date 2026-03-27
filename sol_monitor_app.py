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
        "MAX_MARKET_CAP": 30000,
        "CONDITION_1_MIN_BUY": 500,
        "CONDITION_2_MIN_BUY_1MIN": 1000,
        "CONDITION_3_OLD_TOKEN_DAYS": 7,
        "CONDITION_3_SUDDEN_BUY": 2000,
        "SCAN_INTERVAL": 30,
        "ENABLE_PLATFORMS": {
            "pump_fun": True,
            "moonshot": True,
            "launchlab": True,
            "meteora": True,
            "zerg": True,
        },
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": ""
    }

CONFIG = st.session_state.config

# 全局状态
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "token_buys" not in st.session_state:
    st.session_state.token_buys = defaultdict(list)
if "monitor_started" not in st.session_state:
    st.session_state.monitor_started = False
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []

# ====================== 日志工具 ======================
def log_debug(msg):
    st.session_state.debug_logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(st.session_state.debug_logs) > 50:
        st.session_state.debug_logs = st.session_state.debug_logs[:50]

# ====================== 数据库 ======================
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
        c.execute("INSERT OR REPLACE INTO tokens VALUES (?, ?, ?, ?)",
                  (address, platform, datetime.now(), top10, locked))
        conn.commit()
        conn.close()
    except Exception as e:
        log_debug(f"DB保存失败: {e}")

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

# ====================== 平台抓取（兼容最新反爬） ======================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://pump.fun",
    "Referer": "https://pump.fun/"
}

def safe_request(url, headers=None, timeout=20):
    try:
        res = requests.get(url, headers=headers or HEADERS, timeout=timeout)
        res.raise_for_status()
        data = res.json()
        log_debug(f"✅ {url} 返回 {len(data) if isinstance(data, list) else 'data'}")
        return data
    except Exception as e:
        log_debug(f"❌ {url} 失败: {str(e)[:100]}")
        return None

# Pump.fun 备用公开接口
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
        "platform": "Pump.fun"
    } for x in data if x.get("mint") and x.get("marketCap")]

# Moonshot 备用接口
def fetch_moonshot():
    data = safe_request("https://api.moonshot.so/v1/tokens")
    if not data:
        data = safe_request("https://moonshot-api.fly.dev/v1/tokens")
    if not data:
        return []
    return [{
        "mint": x.get("mint"),
        "market_cap": float(x.get("marketCap", 0)),
        "buy_1min": float(x.get("volume1m", 0)),
        "platform": "Moonshot"
    } for x in data.get("tokens", []) if x.get("mint")]

# LaunchLab / LetsBONK
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

# Meteora Alpha Vaults
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

# Zerg.zone
def fetch_zerg():
    headers = {**HEADERS, "Referer": "https://zerg.zone/"}
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

# ====================== Rug 风险检测（简化版） ======================
def check_rug_risk(mint):
    # 这里可以接入 Birdeye / Dune API 做真实检测，先做简化版
    top10 = 0.7  # 模拟前10持有人占比
    locked = False
    risk = "高" if top10 > 0.5 or not locked else "低"
    return top10, locked, risk

# ====================== Telegram 推送 ======================
def send_telegram(alert):
    if not CONFIG["TELEGRAM_BOT_TOKEN"] or not CONFIG["TELEGRAM_CHAT_ID"]:
        return
    msg = f"""
🔥 SOL 警报
平台: {alert['platform']}
合约: `{alert['mint']}`
市值: ${alert['mc']}
1分钟买入: ${alert['buy1m']}
原因: {alert['reason']}
Rug风险: {alert['rug_risk']}
    """
    try:
        url = f"https://api.telegram.org/bot{CONFIG['TELEGRAM_BOT_TOKEN']}/sendMessage"
        requests.post(url, json={"chat_id": CONFIG["TELEGRAM_CHAT_ID"], "text": msg, "parse_mode": "Markdown"})
    except:
        pass

# ====================== 条件判断 ======================
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
        reason = "低市值 + 买入达标"
    elif buy >= CONFIG["CONDITION_2_MIN_BUY_1MIN"]:
        reason = "1分钟买入暴量"
    elif days >= CONFIG["CONDITION_3_OLD_TOKEN_DAYS"] and buy >= CONFIG["CONDITION_3_SUDDEN_BUY"]:
        reason = f"老币{days}天 突然大额买入"
    elif len(st.session_state.token_buys[mint]) >= 2:
        prev = st.session_state.token_buys[mint][-2]
        if prev > 0 and buy / prev >= 3:
            reason = "买入量环比激增3倍"

    if reason:
        alert = {
            "time": datetime.now().strftime("%m-%d %H:%M:%S"),
            "platform": platform,
            "mint": mint,
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
            send_telegram(alert)

# ====================== 监控线程 ======================
def monitor_thread():
    init_db()
    while st.session_state.monitor_started:
        for platform, enabled in CONFIG["ENABLE_PLATFORMS"].items():
            if not enabled:
                continue
            try:
                tokens = FETCHER_MAP[platform]()
                log_debug(f"{platform} 抓取到 {len(tokens)} 个代币")
                for t in tokens:
                    if t.get("mint"):
                        check_token(t)
            except Exception as e:
                log_debug(f"{platform} 异常: {str(e)[:100]}")
        time.sleep(CONFIG["SCAN_INTERVAL"])

# ====================== Streamlit 手机界面 ======================
st.set_page_config(page_title="SOL Monitor", layout="wide")
st.title("🔥 SOL 多平台代币监测")

# 配置面板
with st.expander("⚙️ 监控设置", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        CONFIG["MAX_MARKET_CAP"] = st.number_input("市值上限 ($)", value=CONFIG["MAX_MARKET_CAP"], step=5000)
        CONFIG["CONDITION_1_MIN_BUY"] = st.number_input("条件1 最小买入 ($)", value=CONFIG["CONDITION_1_MIN_BUY"], step=100)
        CONFIG["CONDITION_2_MIN_BUY_1MIN"] = st.number_input("条件2 1分钟买入 ($)", value=CONFIG["CONDITION_2_MIN_BUY_1MIN"], step=100)
    with col2:
        CONFIG["CONDITION_3_OLD_TOKEN_DAYS"] = st.number_input("条件3 老币天数", value=CONFIG["CONDITION_3_OLD_TOKEN_DAYS"], step=1)
        CONFIG["CONDITION_3_SUDDEN_BUY"] = st.number_input("条件3 突然买入 ($)", value=CONFIG["CONDITION_3_SUDDEN_BUY"], step=100)
        CONFIG["SCAN_INTERVAL"] = st.number_input("扫描间隔 (秒)", value=CONFIG["SCAN_INTERVAL"], step=10)

    st.subheader("📱 Telegram 推送（可选）")
    CONFIG["TELEGRAM_BOT_TOKEN"] = st.text_input("Bot Token", value=CONFIG["TELEGRAM_BOT_TOKEN"], type="password")
    CONFIG["TELEGRAM_CHAT_ID"] = st.text_input("Chat ID", value=CONFIG["TELEGRAM_CHAT_ID"])

    st.subheader("🖥️ 启用平台")
    cols = st.columns(3)
    for i, platform in enumerate(CONFIG["ENABLE_PLATFORMS"].keys()):
        with cols[i % 3]:
            CONFIG["ENABLE_PLATFORMS"][platform] = st.checkbox(platform, value=CONFIG["ENABLE_PLATFORMS"][platform])

# 控制按钮
col_start, col_stop = st.columns(2)
with col_start:
    if st.button("▶️ 启动监控", use_container_width=True, type="primary"):
        st.session_state.monitor_started = True
        threading.Thread(target=monitor_thread, daemon=True).start()
        st.success("✅ 监控已启动")
with col_stop:
    if st.button("⏹️ 停止监控", use_container_width=True, type="secondary"):
        st.session_state.monitor_started = False
        st.warning("⚠️ 监控已停止")

# 实时警报
st.subheader("📈 警报列表")
if st.session_state.alerts:
    for alert in st.session_state.alerts[:20]:
        with st.container(border=True):
            st.markdown(f"**{alert['platform']}** | {alert['time']} | 🚨 Rug风险: {alert['rug_risk']}")
            st.markdown(f"市值: `${alert['mc']}` | 1分钟买入: `${alert['buy1m']}`")
            st.markdown(f"**原因**: {alert['reason']}")
            st.code(alert['mint'], language="text")
else:
    st.info("暂无警报，监控运行中... 可查看下方日志排查问题")

# 调试日志
with st.expander("🔍 调试日志", expanded=False):
    for log in st.session_state.debug_logs[:20]:
        st.text(log)

# 自动刷新
st.markdown("""
<script>
setTimeout(() => window.location.reload(), 30000);
</script>
""", unsafe_allow_html=True)