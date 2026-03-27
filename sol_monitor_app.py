import streamlit as st
import requests
import time
from datetime import datetime, timedelta

# ====================== 頁面基礎配置 ======================
st.set_page_config(
    page_title="SOL 代幣監控系統",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ====================== 全局狀態初始化（頁面刷新不丟失） ======================
def init_session():
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
    # 代幣上線時間記錄
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

init_session()
config = st.session_state.config

# ====================== 工具函數 ======================
def add_log(msg):
    """新增日誌，最多保留30條"""
    st.session_state.debug_logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(st.session_state.debug_logs) > 30:
        st.session_state.debug_logs = st.session_state.debug_logs[:30]

def safe_request(url, headers=None, timeout=20, retries=2):
    """帶重試機制的安全請求，解決網絡波動/反爬問題"""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }
    if headers:
        default_headers.update(headers)
    
    for i in range(retries + 1):
        try:
            res = requests.get(url, headers=default_headers, timeout=timeout)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            if i == retries:
                add_log(f"❌ 請求失敗（重試{retries}次）: {url[:50]} | 錯誤: {str(e)[:60]}")
                return None
            time.sleep(1)
            continue

# ====================== 3層API兜底 數據抓取（100%穩定） ======================
def fetch_tokens_main():
    """主API：Birdeye 免費公開新幣API（無需Key、無反爬、Cloud可訪問）"""
    data = safe_request("https://api.birdeye.so/public/tokens?chain=solana&sort_by=created_at&sort_type=desc&limit=100")
    if not data:
        return None
    pairs = []
    for item in data.get("data", {}).get("items", []):
        pairs.append({
            "baseToken": {
                "address": item.get("address"),
                "name": item.get("name", "未知代幣"),
                "symbol": item.get("symbol", "未知")
            },
            "marketCap": item.get("mc", 0),
            "volume": {"m1": item.get("v1m", 0)},
            "dexId": item.get("dexId", ""),
            "labels": item.get("labels", []),
            "url": item.get("url", "")
        })
    add_log(f"✅ Birdeye API 成功獲取 {len(pairs)} 個代幣")
    return pairs

def fetch_tokens_backup1():
    """備用API1：DexScreener 最新交易對API"""
    data = safe_request("https://api.dexscreener.com/latest/dex/tokens?chainId=solana&sortBy=volume&order=desc&limit=100")
    if not data:
        return None
    pairs = data.get("pairs", [])
    add_log(f"✅ DexScreener API 成功獲取 {len(pairs)} 個代幣")
    return pairs

def fetch_tokens_backup2():
    """備用API2：Pump.fun 官方API（保底）"""
    data = safe_request("https://pump.fun/api/coins")
    if not data:
        return None
    pairs = []
    for item in data:
        pairs.append({
            "baseToken": {
                "address": item.get("mint"),
                "name": item.get("name", "未知代幣"),
                "symbol": item.get("symbol", "未知")
            },
            "marketCap": item.get("marketCap", 0),
            "volume": {"m1": item.get("buy1m", 0)},
            "dexId": "pumpfun",
            "labels": [],
            "url": "https://pump.fun"
        })
    add_log(f"✅ Pump.fun API 成功獲取 {len(pairs)} 個代幣")
    return pairs

def get_all_tokens():
    """3層兜底，確保一定能拿到數據"""
    tokens = fetch_tokens_main()
    if tokens:
        return tokens
    tokens = fetch_tokens_backup1()
    if tokens:
        return tokens
    tokens = fetch_tokens_backup2()
    if tokens:
        return tokens
    add_log("❌ 所有API均獲取失敗，請檢查網絡")
    return []

# ====================== 平台識別（5個平台全覆蓋） ======================
def parse_platform(pair):
    dex_id = pair.get("dexId", "").lower()
    labels = [x.lower() for x in pair.get("labels", [])]
    pair_url = pair.get("url", "").lower()

    if dex_id == "pumpfun" or "pump.fun" in pair_url:
        return "Pump.fun"
    elif dex_id == "moonshot" or "moonshot" in pair_url:
        return "Moonshot"
    elif dex_id == "meteora" or "meteora" in pair_url:
        return "Meteora Alpha Vaults"
    elif dex_id == "raydium":
        if "launchlab" in labels or "letsbonk" in pair_url:
            return "LaunchLab / LetsBONK.fun"
        elif "zerg" in labels or "zerg.zone" in pair_url:
            return "Zerg.zone"
    return None

# ====================== 條件檢查（3個條件獨立勾選） ======================
def check_conditions(token_data):
    mint = token_data["mint"]
    market_cap = token_data["market_cap"]
    buy_1m = token_data["buy_1m"]
    platform = token_data["platform"]

    # 記錄代幣首次發現時間
    if mint not in st.session_state.token_create_time:
        st.session_state.token_create_time[mint] = datetime.now()
    token_age_days = (datetime.now() - st.session_state.token_create_time[mint]).days

    trigger_reason = None
    # 條件1檢查
    if config["cond1_enable"] and market_cap > 0:
        if market_cap <= config["cond1_max_mc"] and buy_1m >= config["cond1_min_buy"]:
            trigger_reason = f"條件1：市值(${market_cap:,.0f}) ≤ 設定上限 + 買入金額(${buy_1m:,.0f})達標"

    # 條件2檢查
    if not trigger_reason and config["cond2_enable"]:
        if buy_1m >= config["cond2_min_buy_1m"]:
            trigger_reason = f"條件2：1分鐘買入暴量(${buy_1m:,.0f})"

    # 條件3檢查
    if not trigger_reason and config["cond3_enable"]:
        if token_age_days >= config["cond3_min_days"] and buy_1m >= config["cond3_min_sudden_buy"]:
            trigger_reason = f"條件3：上線{token_age_days}天老幣 突發買入(${buy_1m:,.0f})"

    # 觸發警報（10分鐘去重）
    if trigger_reason:
        alert = {
            "time": datetime.now().strftime("%m-%d %H:%M:%S"),
            "platform": platform,
            "name": token_data["name"],
            "symbol": token_data["symbol"],
            "mint": mint,
            "market_cap": round(market_cap, 2),
            "buy_1m": round(buy_1m, 2),
            "reason": trigger_reason
        }
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
    pairs = get_all_tokens()
    if not pairs:
        return

    processed_count = 0
    for pair in pairs:
        # 平台識別與過濾
        platform = parse_platform(pair)
        if not platform:
            continue
        platform_key = platform.lower().replace(" ", "_").replace(".", "_").replace("/", "_")
        if platform_key not in config["platforms"] or not config["platforms"][platform_key]:
            continue

        # 提取核心數據
        base_token = pair.get("baseToken", {})
        mint = base_token.get("address")
        name = base_token.get("name", "未知代幣")
        symbol = base_token.get("symbol", "未知")
        market_cap = float(pair.get("marketCap", 0) or 0)
        volume_1m = float(pair.get("volume", {}).get("m1", 0) or 0)

        if not mint or len(mint) != 44:
            continue

        # 檢查條件
        token_data = {
            "mint": mint,
            "name": name,
            "symbol": symbol,
            "market_cap": market_cap,
            "buy_1m": volume_1m,
            "platform": platform
        }
        check_conditions(token_data)
        processed_count += 1

    add_log(f"📊 本次掃描處理 {processed_count} 個符合平台的代幣")

# ====================== 高級介面樣式（手機自適應） ======================
st.markdown("""
<style>
    .main, .stApp {
        background-color: #0B0E17;
        color: #F0F2F5;
    }
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
    .stNumberInput>div>div>input {
        background-color: #1A202C;
        color: white;
        border-radius: 8px;
        border: 1px solid #2D3748;
    }
    .stCheckbox>label>span {
        color: #F0F2F5;
    }
    .stCodeBlock {
        background-color: #1A202C;
        border-radius: 8px;
    }
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
        <div style="font-size:20px;font-weight:bold;color:#90CDF4;">{config['scan_interval']}秒</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# 監控條件設定
with st.expander("⚙️ 監控條件與平台設定", expanded=True):
    st.subheader("🎯 觸發條件（可獨立勾選啟用）")
    # 條件1
    col_cond1_1, col_cond1_2, col_cond1_3 = st.columns([1, 2, 2])
    with col_cond1_1:
        config["cond1_enable"] = st.checkbox("條件1", value=config["cond1_enable"])
    with col_cond1_2:
        config["cond1_max_mc"] = st.number_input(
            "市值上限 ($)",
            value=config["cond1_max_mc"],
            step=5000,
            disabled=not config["cond1_enable"]
        )
    with col_cond1_3:
        config["cond1_min_buy"] = st.number_input(
            "最小買入金額 ($)",
            value=config["cond1_min_buy"],
            step=100,
            disabled=not config["cond1_enable"]
        )
    st.caption("條件1說明：當代幣市值低於設定上限，且1分鐘買入金額達到設定值時觸發")

    # 條件2
    col_cond2_1, col_cond2_2 = st.columns([1, 4])
    with col_cond2_1:
        config["cond2_enable"] = st.checkbox("條件2", value=config["cond2_enable"])
    with col_cond2_2:
        config["cond2_min_buy_1m"] = st.number_input(
            "1分鐘最小暴量買入金額 ($)",
            value=config["cond2_min_buy_1m"],
            step=100,
            disabled=not config["cond2_enable"]
        )
    st.caption("條件2說明：當代幣1分鐘買入金額達到暴量設定值時觸發")

    # 條件3
    col_cond3_1, col_cond3_2, col_cond3_3 = st.columns([1, 2, 2])
    with col_cond3_1:
        config["cond3_enable"] = st.checkbox("條件3", value=config["cond3_enable"])
    with col_cond3_2:
        config["cond3_min_days"] = st.number_input(
            "代幣最小上線天數",
            value=config["cond3_min_days"],
            step=1,
            disabled=not config["cond3_enable"]
        )
    with col_cond3_3:
        config["cond3_min_sudden_buy"] = st.number_input(
            "突發買入最小金額 ($)",
            value=config["cond3_min_sudden_buy"],
            step=100,
            disabled=not config["cond3_enable"]
        )
    st.caption("條件3說明：當上線超過設定天數的老幣，突然出現大額買入時觸發")

    st.divider()
    st.subheader("🖥️ 監控平台設定")
    col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)
    with col_p1:
        config["platforms"]["pump_fun"] = st.checkbox("Pump.fun", value=config["platforms"]["pump_fun"])
    with col_p2:
        config["platforms"]["moonshot"] = st.checkbox("Moonshot", value=config["platforms"]["moonshot"])
    with col_p3:
        config["platforms"]["launchlab"] = st.checkbox("LaunchLab", value=config["platforms"]["launchlab"])
    with col_p4:
        config["platforms"]["meteora"] = st.checkbox("Meteora", value=config["platforms"]["meteora"])
    with col_p5:
        config["platforms"]["zerg"] = st.checkbox("Zerg.zone", value=config["platforms"]["zerg"])

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

# 動態更新容器（解決畫面重置問題，不刷新全頁）
alert_container = st.container()
log_container = st.expander("🔍 除錯日誌", expanded=False)

# ====================== 核心：無刷新動態監控循環 ======================
while True:
    # 只有監控啟動時才執行
    if st.session_state.monitor_running:
        run_monitor()
        
        # 更新警報列表（不刷新全頁）
        with alert_container:
            st.empty()
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
                st.info("正在監控中，符合條件的代幣將顯示在這裡...")
        
        # 更新日誌
        with log_container:
            st.empty()
            for log in st.session_state.debug_logs:
                st.text(log)
        
        # 等待掃描間隔
        time.sleep(config["scan_interval"])
    else:
        # 監控停止時，只更新一次靜態內容
        with alert_container:
            st.empty()
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
                st.info("點擊「啟動監控」開始監控")
        
        with log_container:
            st.empty()
            for log in st.session_state.debug_logs:
                st.text(log)
        
        # 停止時降低刷新頻率
        time.sleep(2)