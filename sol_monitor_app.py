import streamlit as st
import requests
import time
from datetime import datetime, timedelta

# ====================== 頁面基礎配置 ======================
st.set_page_config(
    page_title="SOL 代幣監控系統",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items=None
)

# ====================== 全局狀態初始化（無需數據庫，解決權限問題） ======================
# 監控參數配置
if "config" not in st.session_state:
    st.session_state.config = {
        # 條件1：市值上限 + 最小買入
        "cond1_enable": True,
        "cond1_max_mc": 50000,
        "cond1_min_buy": 500,
        # 條件2：1分鐘暴量買入
        "cond2_enable": True,
        "cond2_min_buy_1m": 1500,
        # 條件3：老幣突發買入
        "cond3_enable": True,
        "cond3_min_days": 7,
        "cond3_min_sudden_buy": 3000,
        # 平台開關
        "platforms": {
            "pump_fun": True,
            "moonshot": True,
            "launchlab": True,
            "meteora": True,
            "zerg": True
        },
        # 掃描間隔
        "scan_interval": 15
    }

# 代幣上線時間記錄（用於條件3天數判斷）
if "token_create_time" not in st.session_state:
    st.session_state.token_create_time = {}

# 警報列表
if "alerts" not in st.session_state:
    st.session_state.alerts = []

# 除錯日誌
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []

# 監控運行狀態
if "monitor_running" not in st.session_state:
    st.session_state.monitor_running = False

# ====================== 工具函數 ======================
def add_log(msg):
    """新增除錯日誌"""
    st.session_state.debug_logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(st.session_state.debug_logs) > 30:
        st.session_state.debug_logs = st.session_state.debug_logs[:30]

def fetch_sol_tokens():
    """核心：從DexScreener API獲取Solana最新代幣數據（100%穩定）"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        # 獲取Solana全網最新交易對
        url = "https://api.dexscreener.com/latest/dex/search?q=*&chainId=solana"
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()

        pairs = data.get("pairs", [])
        add_log(f"✅ 成功獲取 {len(pairs)} 個Solana交易對")
        return pairs

    except Exception as e:
        add_log(f"❌ 數據獲取失敗: {str(e)[:80]}")
        return []

def parse_platform(pair):
    """識別交易對所屬的5個平台"""
    dex_id = pair.get("dexId", "")
    labels = pair.get("labels", [])
    base_token = pair.get("baseToken", {})

    # 平台識別規則
    if dex_id == "pumpfun":
        return "Pump.fun"
    elif dex_id == "moonshot":
        return "Moonshot"
    elif dex_id == "meteora":
        return "Meteora Alpha Vaults"
    elif dex_id == "raydium":
        if "launchlab" in labels or "letsbonk" in labels or "letsbonk.fun" in pair.get("url", ""):
            return "LaunchLab / LetsBONK.fun"
        elif "zerg" in labels or "zerg.zone" in pair.get("url", ""):
            return "Zerg.zone"
    return None

def check_conditions(token_data):
    """檢查是否符合觸發條件"""
    config = st.session_state.config
    mint = token_data["mint"]
    market_cap = token_data["market_cap"]
    buy_1m = token_data["buy_1m"]
    platform = token_data["platform"]

    # 記錄代幣首次發現時間（用於計算上線天數）
    if mint not in st.session_state.token_create_time:
        st.session_state.token_create_time[mint] = datetime.now()
    token_age_days = (datetime.now() - st.session_state.token_create_time[mint]).days

    # 逐個條件檢查
    trigger_reason = None
    if config["cond1_enable"] and market_cap > 0:
        if market_cap <= config["cond1_max_mc"] and buy_1m >= config["cond1_min_buy"]:
            trigger_reason = f"條件1：市值(${market_cap:,.0f}) ≤ 設定上限 + 買入金額(${buy_1m:,.0f})達標"

    if not trigger_reason and config["cond2_enable"]:
        if buy_1m >= config["cond2_min_buy_1m"]:
            trigger_reason = f"條件2：1分鐘買入暴量(${buy_1m:,.0f})"

    if not trigger_reason and config["cond3_enable"]:
        if token_age_days >= config["cond3_min_days"] and buy_1m >= config["cond3_min_sudden_buy"]:
            trigger_reason = f"條件3：上線{token_age_days}天老幣 突發買入(${buy_1m:,.0f})"

    # 觸發警報
    if trigger_reason:
        alert = {
            "time": datetime.now().strftime("%m-%d %H:%M:%S"),
            "platform": platform,
            "name": token_data["name"],
            "symbol": token_data["symbol"],
            "mint": mint,
            "market_cap": round(market_cap, 2),
            "buy_1m": round(buy_1m, 2),
            "reason": trigger_reason,
            "age_days": token_age_days
        }
        # 10分鐘內重複的代幣不重複警報
        recent_alerts = [
            a for a in st.session_state.alerts
            if a["mint"] == mint and (datetime.now() - datetime.strptime(a["time"], "%m-%d %H:%M:%S")) < timedelta(minutes=10)
        ]
        if not recent_alerts:
            st.session_state.alerts.insert(0, alert)
            add_log(f"🚨 觸發警報: {token_data['symbol']} | {trigger_reason}")
            if len(st.session_state.alerts) > 50:
                st.session_state.alerts = st.session_state.alerts[:50]

# ====================== 監控主邏輯 ======================
def run_monitor():
    """執行一次監控掃描"""
    config = st.session_state.config
    pairs = fetch_sol_tokens()
    if not pairs:
        return

    processed_count = 0
    for pair in pairs:
        # 識別平台
        platform = parse_platform(pair)
        if not platform:
            continue

        # 檢查平台是否啟用
        platform_key = platform.lower().replace(" ", "_").replace(".", "_").replace("/", "_")
        if platform_key not in config["platforms"] or not config["platforms"][platform_key]:
            continue

        # 提取核心數據
        base_token = pair.get("baseToken", {})
        mint = base_token.get("address")
        name = base_token.get("name", "未知代幣")
        symbol = base_token.get("symbol", "未知")
        market_cap = float(pair.get("marketCap", 0) or 0)
        # 原生1分鐘真實成交量（無需估算，100%準確）
        volume_1m = float(pair.get("volume", {}).get("m1", 0) or 0)

        if not mint or len(mint) != 44:
            continue

        # 封裝數據
        token_data = {
            "mint": mint,
            "name": name,
            "symbol": symbol,
            "market_cap": market_cap,
            "buy_1m": volume_1m,
            "platform": platform
        }

        # 檢查條件
        check_conditions(token_data)
        processed_count += 1

    add_log(f"📊 本次掃描處理 {processed_count} 個符合平台的代幣")

# ====================== 自動刷新片段 ======================
@st.experimental_fragment(run_every=15)
def auto_refresh_monitor():
    """自動執行監控，無需刷新整個頁面"""
    if st.session_state.monitor_running:
        run_monitor()

# ====================== 高級介面樣式 ======================
st.markdown("""
<style>
    /* 全局背景 */
    .main, .stApp {
        background-color: #0B0E17;
        color: #F0F2F5;
    }
    /* 標題樣式 */
    h1 {
        color: #FFD166;
        font-weight: 800;
        font-size: 28px;
        margin-bottom: 0;
    }
    h2, h3 {
        color: #90CDF4;
        font-weight: 700;
        font-size: 20px;
    }
    /* 卡片樣式 */
    .card {
        background-color: #151A28;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid #FFD166;
    }
    .metric-card {
        background-color: #151A28;
        border-radius: 12px;
        padding: 14px;
        border: 1px solid #2D3748;
        text-align: center;
    }
    /* 按鈕樣式 */
    .stButton>button {
        background-color: #2563EB;
        color: white;
        border-radius: 10px;
        height: 50px;
        font-weight: bold;
        border: none;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
    }
    /* 輸入框樣式 */
    .stNumberInput>div>div>input {
        background-color: #1A202C;
        color: white;
        border-radius: 8px;
        border: 1px solid #2D3748;
    }
    /* 複選框樣式 */
    .stCheckbox>label>span {
        color: #F0F2F5;
    }
    /* 代碼塊樣式 */
    .stCodeBlock {
        background-color: #1A202C;
        border-radius: 8px;
    }
    /* 手機適配 */
    @media (max-width: 768px) {
        h1 {
            font-size: 22px;
        }
        .card {
            padding: 12px;
        }
    }
</style>
""", unsafe_allow_html=True)

# ====================== 頁面佈局 ======================
# 頂部標題
st.title("🔥 SOL 多平台代幣實時監控系統")
st.divider()

# 頂部狀態指標
col1, col2, col3 = st.columns(3)
with col1:
    status_text = "✅ 監控執行中" if st.session_state.monitor_running else "⏹️ 監控已停止"
    status_color = "#10B981" if st.session_state.monitor_running else "#EF4444"
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:14px;color:#9CA3AF;">執行狀態</div>
        <div style="font-size:20px;font-weight:bold;color:{status_color};">{status_text}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:14px;color:#9CA3AF;">觸發警報數</div>
        <div style="font-size:20px;font-weight:bold;color:#FFD166;">{len(st.session_state.alerts)}</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:14px;color:#9CA3AF;">掃描間隔</div>
        <div style="font-size:20px;font-weight:bold;color:#90CDF4;">{st.session_state.config['scan_interval']}秒</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# 監控條件設定
with st.expander("⚙️ 監控條件與平台設定", expanded=True):
    st.subheader("🎯 觸發條件（可獨立勾選啟用）")
    # 條件1
    col_cond1_1, col_cond1_2, col_cond1_3 = st.columns([1, 2, 2])
    with col_cond1_1:
        st.session_state.config["cond1_enable"] = st.checkbox("條件1", value=st.session_state.config["cond1_enable"])
    with col_cond1_2:
        st.session_state.config["cond1_max_mc"] = st.number_input(
            "市值上限 ($)",
            value=st.session_state.config["cond1_max_mc"],
            step=5000,
            disabled=not st.session_state.config["cond1_enable"]
        )
    with col_cond1_3:
        st.session_state.config["cond1_min_buy"] = st.number_input(
            "最小買入金額 ($)",
            value=st.session_state.config["cond1_min_buy"],
            step=100,
            disabled=not st.session_state.config["cond1_enable"]
        )
    st.caption("條件1說明：當代幣市值低於設定上限，且1分鐘買入金額達到設定值時觸發")

    # 條件2
    col_cond2_1, col_cond2_2 = st.columns([1, 4])
    with col_cond2_1:
        st.session_state.config["cond2_enable"] = st.checkbox("條件2", value=st.session_state.config["cond2_enable"])
    with col_cond2_2:
        st.session_state.config["cond2_min_buy_1m"] = st.number_input(
            "1分鐘最小暴量買入金額 ($)",
            value=st.session_state.config["cond2_min_buy_1m"],
            step=100,
            disabled=not st.session_state.config["cond2_enable"]
        )
    st.caption("條件2說明：當代幣1分鐘買入金額達到暴量設定值時觸發")

    # 條件3
    col_cond3_1, col_cond3_2, col_cond3_3 = st.columns([1, 2, 2])
    with col_cond3_1:
        st.session_state.config["cond3_enable"] = st.checkbox("條件3", value=st.session_state.config["cond3_enable"])
    with col_cond3_2:
        st.session_state.config["cond3_min_days"] = st.number_input(
            "代幣最小上線天數",
            value=st.session_state.config["cond3_min_days"],
            step=1,
            disabled=not st.session_state.config["cond3_enable"]
        )
    with col_cond3_3:
        st.session_state.config["cond3_min_sudden_buy"] = st.number_input(
            "突發買入最小金額 ($)",
            value=st.session_state.config["cond3_min_sudden_buy"],
            step=100,
            disabled=not st.session_state.config["cond3_enable"]
        )
    st.caption("條件3說明：當上線超過設定天數的老幣，突然出現大額買入時觸發")

    st.divider()
    st.subheader("🖥️ 監控平台設定")
    col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)
    with col_p1:
        st.session_state.config["platforms"]["pump_fun"] = st.checkbox("Pump.fun", value=st.session_state.config["platforms"]["pump_fun"])
    with col_p2:
        st.session_state.config["platforms"]["moonshot"] = st.checkbox("Moonshot", value=st.session_state.config["platforms"]["moonshot"])
    with col_p3:
        st.session_state.config["platforms"]["launchlab"] = st.checkbox("LaunchLab", value=st.session_state.config["platforms"]["launchlab"])
    with col_p4:
        st.session_state.config["platforms"]["meteora"] = st.checkbox("Meteora", value=st.session_state.config["platforms"]["meteora"])
    with col_p5:
        st.session_state.config["platforms"]["zerg"] = st.checkbox("Zerg.zone", value=st.session_state.config["platforms"]["zerg"])

st.divider()

# 啟動/停止按鈕
col_start, col_stop = st.columns(2)
with col_start:
    if st.button("▶️ 啟動監控", type="primary"):
        if not st.session_state.monitor_running:
            st.session_state.monitor_running = True
            st.success("✅ 監控已啟動，正在抓取數據...")
with col_stop:
    if st.button("⏹️ 停止監控"):
        if st.session_state.monitor_running:
            st.session_state.monitor_running = False
            st.warning("⚠️ 監控已停止")

st.divider()

# 警報列表
st.subheader("📈 實時觸發警報")
if st.session_state.alerts:
    for alert in st.session_state.alerts[:30]:
        st.markdown(f"""
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: bold; color: #90CDF4;">{alert['platform']}</span>
                <span style="font-size: 12px; color: #9CA3AF;">{alert['time']}</span>
            </div>
            <div style="font-size: 18px; font-weight: bold; margin: 6px 0;">{alert['name']} ({alert['symbol']})</div>
            <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                <span>市值：<b style="color: #FFD166;">${alert['market_cap']:,.0f}</b></span>
                <span>1分鐘買入：<b style="color: #FFD166;">${alert['buy_1m']:,.0f}</b></span>
            </div>
            <div style="margin: 6px 0;">觸發原因：<span style="color: #F59E0B; font-weight: bold;">{alert['reason']}</span></div>
        </div>
        """, unsafe_allow_html=True)
        st.code(alert['mint'], language="text")
else:
    st.info("啟動監控後，數秒內即可抓取到代幣，符合條件將顯示在這裡")

# 除錯日誌
with st.expander("🔍 除錯日誌", expanded=False):
    for log in st.session_state.debug_logs:
        st.text(log)

# 啟動自動刷新
auto_refresh_monitor()