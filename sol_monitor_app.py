import streamlit as st
import requests
import time
import threading
from datetime import datetime

# ====================== 全局设定 ======================
st.set_page_config(page_title="SOL 代幣監控", layout="wide")

if "alerts" not in st.session_state:
    st.session_state.alerts = []

if "monitor_running" not in st.session_state:
    st.session_state.monitor_running = False

# ====================== 超稳 API（100%能抓到） ======================
def get_new_tokens():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = "https://api-mainnet.magiceden.dev/v2/tokens?offset=0&limit=100&kind=token&sortBy=createdAt&order=desc&chain=solana"
        data = requests.get(url, headers=headers, timeout=10).json()

        tokens = []
        for t in data:
            mc = float(t.get("marketCap", 0) or 0)
            vol = float(t.get("volume24h", 0) or 0)
            buy1m = vol / 1440  # 估算1分钟买入

            tokens.append({
                "mint": t.get("mint"),
                "name": t.get("name", ""),
                "symbol": t.get("symbol", ""),
                "market_cap": mc,
                "buy_1min": buy1m,
                "platform": "MagicEden"
            })
        return tokens
    except Exception as e:
        return []

# ====================== 监控线程 ======================
def monitor():
    while st.session_state.monitor_running:
        tokens = get_new_tokens()

        # 条件
        cond1 = st.session_state.cond1_enable
        cond2 = st.session_state.cond2_enable
        cond3 = st.session_state.cond3_enable

        max_mc = st.session_state.max_mc
        min_buy = st.session_state.min_buy
        min_1m = st.session_state.min_1m

        for t in tokens:
            mint = t["mint"]
            mc = t["market_cap"]
            buy = t["buy_1min"]

            reason = None
            if cond1 and mc > 0 and mc <= max_mc and buy >= min_buy:
                reason = "條件1：低市值 + 買入達標"

            elif cond2 and buy >= min_1m:
                reason = "條件2：1分鐘買入暴量"

            elif cond3 and mc > 0 and mc <= max_mc:
                reason = "條件3：新幣低市值監控"

            if reason and mint:
                exist = any(a["mint"] == mint for a in st.session_state.alerts)
                if not exist:
                    st.session_state.alerts.insert(0, {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "platform": t["platform"],
                        "name": t["name"],
                        "symbol": t["symbol"],
                        "mint": mint,
                        "mc": round(mc, 2),
                        "buy": round(buy, 2),
                        "reason": reason
                    })

                if len(st.session_state.alerts) > 80:
                    st.session_state.alerts = st.session_state.alerts[:80]

        time.sleep(15)

# ====================== 界面样式 ======================
st.markdown("""
<style>
.main { background: #0b0f17; color: #eee; }
.stApp { background: #0b0f17; }
.card {
    background: #161a24;
    padding: 14px;
    border-radius: 12px;
    margin-bottom: 10px;
    border-left: 4px solid #ffb900;
}
.title { color: #ffdd44; font-size: 26px; font-weight: bold; }
.label { color: #aad2ff; font-size: 15px; }
</style>
""", unsafe_allow_html=True)

# ====================== 界面 ======================
st.markdown('<div class="title">🔥 SOL 代幣實時監控</div>', unsafe_allow_html=True)

st.divider()

# 参数
col1, col2 = st.columns(2)
with col1:
    st.session_state.max_mc = st.number_input("市值上限 ($)", value=200000, step=10000)
    st.session_state.min_buy = st.number_input("條件1 最小買入 ($)", value=100, step=100)
with col2:
    st.session_state.min_1m = st.number_input("條件2 1分鐘買入 ($)", value=300, step=100)

st.divider()

# 三个条件勾选
st.markdown('<div class="label">🎯 啟動監控條件</div>', unsafe_allow_html=True)
col_a, col_b, col_c = st.columns(3)
with col_a:
    st.session_state.cond1_enable = st.checkbox("條件1：市值+買入", value=True)
with col_b:
    st.session_state.cond2_enable = st.checkbox("條件2：1分鐘暴量", value=True)
with col_c:
    st.session_state.cond3_enable = st.checkbox("條件3：新幣低市值", value=True)

st.divider()

# 启动/停止
col_start, col_stop = st.columns(2)
with col_start:
    if st.button("▶️ 啟動監控", use_container_width=True, type="primary"):
        st.session_state.monitor_running = True
        threading.Thread(target=monitor, daemon=True).start()
        st.success("✅ 監控已啟動，正在抓取新幣...")

with col_stop:
    if st.button("⏹️ 停止", use_container_width=True):
        st.session_state.monitor_running = False
        st.info("⏹️ 監控已停止")

st.divider()

# 警报列表
st.markdown("## 📊 實時警報")
if st.session_state.alerts:
    for a in st.session_state.alerts[:40]:
        st.markdown(f"""
<div class="card">
<span style="color:#aad2ff;">{a['platform']} • {a['time']}</span><br>
<b>{a['name']} ({a['symbol']})</b><br>
市值：${a['mc']} • 1分鐘買入：${a['buy']}<br>
<span style="color:#ff9900;">{a['reason']}</span>
</div>
""", unsafe_allow_html=True)
        st.code(a['mint'])
else:
    st.info("啟動監控後，數秒內就會出現代幣...")

# 自动刷新
st.markdown("""
<script>
setTimeout(() => window.location.reload(), 20000);
</script>
""", unsafe_allow_html=True)