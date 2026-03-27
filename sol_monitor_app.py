import streamlit as st
import requests
import threading
import time
from datetime import datetime, timedelta

# ====================== 頁面基礎配置 ======================
st.set_page_config(
    page_title="SOL 代幣監控系統",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ====================== 全局狀態初始化（線程安全） ======================
def init_session():
    # 核心監控狀態
    if "monitor_running" not in st.session_state:
        st.session_state.monitor_running = False
    if "stop_event" not in st.session_state:
        st.session_state.stop_event = threading.Event()
    if "monitor_thread" not in st.session_state:
        st.session_state.monitor_thread = None
    
    # 配置參數
    if "config" not in st.session_state:
        st.session_state.config = {
            "cond1_enable": True,
            "cond1_max_mc": 1000000,
            "cond1_min_buy": 50,
            "cond2_enable": True,
            "cond2_min_buy_1m": 100,
            "cond3_enable": True,
            "cond3_min_days": 1,
            "cond3_min_sudden_buy": 200,
            "platforms": {
                "pump_fun": True,
                "moonshot": True,
                "launchlab": True,
                "meteora": True,
                "zerg": True,
            },
            "all_platform_enable": False,
            "scan_interval": 20
        }
    
    # 數據存儲
    if "token_create_time" not in st.session_state:
        st.session_state.token_create_time = {}
    if "alerts" not in st.session_state:
        st.session_state.alerts = []
    if "debug_logs" not in st.session_state:
        st.session_state.debug_logs = []
    if "raw_token_data" not in st.session_state:
        st.session_state.raw_token_data = []

init_session()
config = st.session_state.config

# ====================== 工具函數（線程安全） ======================
def add_log(msg):
    """新增日誌，線程安全"""
    st.session_state.debug_logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if len(st.session_state.debug_logs) > 30:
        st.session_state.debug_logs = st.session_state.debug_logs[:30]

def test_api_connection():
    """一鍵測試API連接"""
    try:
        res = requests.get(
            "https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1",
            headers={"Accept": "application/json"},
            timeout=10
        )
        res.raise_for_status()
        data = res.json()
        count = len(data.get("data", []))
        return True, f"✅ API連接成功，獲取到 {count} 個交易對"
    except Exception as e:
        return False, f"❌ API連接失敗: {str(e)[:80]}"

# ====================== 【核心】穩定API數據獲取 ======================
def get_solana_tokens():
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        url = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1"
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
        
        pools = data.get("data", [])
        formatted_pairs = []
        st.session_state.raw_token_data = pools
        
        for pool in pools:
            attributes = pool.get("attributes", {})
            relationships = pool.get("relationships", {})
            
            base_token = relationships.get("base_token", {}).get("data", {})
            dex_id = relationships.get("dex", {}).get("data", {}).get("id", "")
            token_name = attributes.get("name", "").lower()
            base_token_symbol = attributes.get("base_token_symbol", "").lower()
            
            formatted_pairs.append({
                "baseToken": {
                    "address": base_token.get("id", ""),
                    "name": attributes.get("name", "未知代幣"),
                    "symbol": attributes.get("base_token_symbol", "未知")
                },
                "marketCap": float(attributes.get("market_cap", 0) or 0),
                "volume": {
                    "m1": float(attributes.get("volume_1m", 0) or 0),
                    "m5": float(attributes.get("volume_5m", 0) or 0)
                },
                "dexId": dex_id,
                "token_name": token_name,
                "token_symbol": base_token_symbol,
                "pool_created_at": attributes.get("pool_created_at", "")
            })
        
        add_log(f"✅ API成功獲取 {len(formatted_pairs)} 個Solana交易對")
        return formatted_pairs
    
    except Exception as e:
        add_log(f"❌ API獲取失敗: {str(e)[:80]}")
        return []

# ====================== 平台識別 ======================
def parse_platform(pair):
    dex_id = pair.get("dexId", "").lower()
    token_name = pair.get("token_name", "").lower()
    token_symbol = pair.get("token_symbol", "").lower()
    
    if "pump" in dex_id:
        return "Pump.fun"
    elif "moonshot" in dex_id:
        return "Moonshot"
    elif "meteora" in dex_id:
        return "Meteora Alpha Vaults"
    elif "raydium" in dex_id:
        if "launchlab" in token_name or "letsbonk" in token_name or "bonk" in token_symbol:
            return "LaunchLab / LetsBONK.fun"
        elif "zerg" in token_name or "zerg" in token_symbol:
            return "Zerg.zone"
    return None

# ====================== 條件檢查 ======================
def check_conditions(token_data):
    mint = token_data["mint"]
    market_cap = token_data["market_cap"]
    buy_1m = token_data["buy_1m"]
    platform = token_data["platform"]
    pool_create_time = token_data["pool_create_time"]

    if mint not in st.session_state.token_create_time:
        try:
            if pool_create_time:
                create_time = datetime.fromisoformat(pool_create_time.replace("Z", "+00:00"))
                st.session_state.token_create_time[mint] = create_time
            else:
                st.session_state.token_create_time[mint] = datetime.now()
        except:
            st.session_state.token_create_time[mint] = datetime.now()
    
    token_age_days = (datetime.now() - st.session_state.token_create_time[mint]).days
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
            if a["mint"] == mint and (datetime.now() - datetime.strptime(a["time"], "%m-%d %H:%M:%S")) < timedelta(minutes=5)
        ]
        if not recent_alerts:
            st.session_state.alerts.insert(0, alert)
            add_log(f"🚨 觸發警報: {token_data['symbol']} | {trigger_reason}")
            if len(st.session_state.alerts) > 50:
                st.session_state.alerts = st.session_state.alerts[:50]

# ====================== 【核心】後台監控線程主函數 ======================
def monitor_worker():
    """後台監控線程，不阻塞主頁面"""
    add_log("✅ 監控線程已啟動，開始執行監控")
    stop_event = st.session_state.stop_event
    
    while not stop_event.is_set():
        try:
            # 獲取數據
            pairs = get_solana_tokens()
            if pairs:
                processed_count = 0
                platform_match_count = 0

                for pair in pairs:
                    # 檢查是否需要停止
                    if stop_event.is_set():
                        break
                    
                    # 平台識別與過濾
                    platform = parse_platform(pair)
                    platform_key = platform.lower().replace(" ", "_").replace(".", "_").replace("/", "_") if platform else ""
                    
                    is_allowed = False
                    if config["all_platform_enable"]:
                        is_allowed = True
                        platform = platform or "全平台"
                    elif platform and platform_key in config["platforms"] and config["platforms"][platform_key]:
                        is_allowed = True
                        platform_match_count += 1
                    
                    if not is_allowed:
                        continue

                    # 提取數據
                    base_token = pair.get("baseToken", {})
                    mint = base_token.get("address")
                    name = base_token.get("name", "未知代幣")
                    symbol = base_token.get("symbol", "未知")
                    market_cap = float(pair.get("marketCap", 0) or 0)
                    volume_1m = float(pair.get("volume", {}).get("m1", 0) or 0)
                    pool_create_time = pair.get("pool_created_at", "")

                    if not mint or len(mint) != 44:
                        continue

                    # 檢查條件
                    token_data = {
                        "mint": mint,
                        "name": name,
                        "symbol": symbol,
                        "market_cap": market_cap,
                        "buy_1m": volume_1m,
                        "platform": platform,
                        "pool_create_time": pool_create_time
                    }
                    check_conditions(token_data)
                    processed_count += 1

                add_log(f"📊 本次掃描：符合平台規則 {platform_match_count} 個，實際處理 {processed_count} 個代幣")
            
            # 等待掃描間隔，期間檢查是否需要停止
            wait_start = time.time()
            while time.time() - wait_start < config["scan_interval"] and not stop_event.is_set():
                time.sleep(0.5)
        
        except Exception as e:
            add_log(f"❌ 監控線程異常: {str(e)[:80]}")
            # 出錯也不停止線程，等待下次循環
            time.sleep(5)
    
    add_log("⚠️ 監控線程已安全停止")

# ====================== 啟動/停止按鈕回調函數 ======================
def start_monitor():
    """啟動監控按鈕回調"""
    if st.session_state.monitor_running:
        st.warning("監控已在運行中，無需重複啟動")
        return
    
    # 重置停止事件
    st.session_state.stop_event.clear()
    # 創建並啟動線程
    st.session_state.monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
    st.session_state.monitor_thread.start()
    # 更新狀態
    st.session_state.monitor_running = True
    st.success("✅ 監控已成功啟動，後台正在執行掃描")

def stop_monitor():
    """停止監控按鈕回調"""
    if not st.session_state.monitor_running:
        st.warning("監控未在運行中")
        return
    
    # 發送停止信號
    st.session_state.stop_event.set()
    # 等待線程停止
    if st.session_state.monitor_thread:
        st.session_state.monitor_thread.join(timeout=5)
    # 更新狀態
    st.session_state.monitor_running = False
    st.warning("⚠️ 監控已成功停止")

# ====================== 頁面自動刷新（實時顯示狀態，不阻塞） ======================
if st.session_state.monitor_running:
    st.markdown("""
    <meta http-equiv="refresh" content="3">
    """, unsafe_allow_html=True)

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

# API測試按鈕
col_test, col_empty = st.columns([1, 3])
with col_test:
    if st.button("🔧 一鍵測試API連接", use_container_width=True):
        success, msg = test_api_connection()
        if success:
            st.success(msg)
        else:
            st.error(msg)

st.divider()

# 監控條件設定
with st.expander("⚙️ 監控條件與平台設定", expanded=True):
    # 保底開關：全平台監控
    config["all_platform_enable"] = st.checkbox("✅ 開啟全平台監控（保底，一定有數據）", value=config["all_platform_enable"])
    st.caption("如果開啟指定平台後沒有數據，請勾選此開關，將監控全網所有Solana代幣")

    st.divider()
    st.subheader("🎯 觸發條件（可獨立勾選啟用）")
    # 條件1
    col_cond1_1, col_cond1_2, col_cond1_3 = st.columns([1, 2, 2])
    with col_cond1_1:
        config["cond1_enable"] = st.checkbox("條件1", value=config["cond1_enable"])
    with col_cond1_2:
        config["cond1_max_mc"] = st.number_input(
            "市值上限 ($)",
            value=config["cond1_max_mc"],
            step=10000,
            disabled=not config["cond1_enable"]
        )
    with col_cond1_3:
        config["cond1_min_buy"] = st.number_input(
            "最小買入金額 ($)",
            value=config["cond1_min_buy"],
            step=10,
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
            step=10,
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
            step=10,
            disabled=not config["cond3_enable"]
        )
    st.caption("條件3說明：當上線超過設定天數的老幣，突然出現大額買入時觸發")

    st.divider()
    st.subheader("🖥️ 指定監控平台設定")
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

# 啟動/停止按鈕（核心，點擊立刻觸發回調）
col_start, col_stop = st.columns(2)
with col_start:
    st.button("▶️ 啟動監控", type="primary", use_container_width=True, on_click=start_monitor)
with col_stop:
    st.button("⏹️ 停止監控", use_container_width=True, on_click=stop_monitor)

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
with st.expander("🔍 除錯日誌與原始數據", expanded=False):
    st.subheader("系統日誌")
    for log in st.session_state.debug_logs[:20]:
        st.text(log)
    
    st.divider()
    st.subheader("API原始數據預覽（前5條）")
    if st.session_state.raw_token_data:
        st.json(st.session_state.raw_token_data[:5])
    else:
        st.info("啟動監控後會顯示原始數據")