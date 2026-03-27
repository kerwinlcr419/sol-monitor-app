import streamlit as st
import asyncio
import websockets
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from solana.rpc.api import Client

# --- 🔐 配置區 ---
# ⚠️ 請替換為你付費 RPC 供應商的 API KEY
HELIUS_API_KEY = "YOUR_HELIUS_API_KEY" 
RPC_HTTPS_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
RPC_WSS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# Solana 核心合約地圖 (部分)
PUMP_FUN_PROGRAM_ID = "6EF8rrecth7DY54Z4863WE7498369262624262426242" # 模擬，需填寫真實 ID
METEORA_PROGRAM_ID = "Eo7Wj5L98S9W545H5262624262426242624262"   # 模擬，需填寫真實 ID

# 監測條件 (你的設定)
st.sidebar.header("⚙️ 條件設定")
MCAP_LIMIT = st.sidebar.number_input("1. 市值設定值以下 (USD)", value=50000)
BUY_LIMIT = st.sidebar.number_input("1. 買入金額設定值 (SOL)", value=10)
VOL_1M_LIMIT = st.sidebar.number_input("2. 每分鐘買入量 (SOL)", value=30)
OLD_DAYS = st.sidebar.number_input("3. 老幣定義天數", value=3)
OLD_SURGE_LIMIT = st.sidebar.number_input("3. 老幣突襲買入量 (SOL)", value=20)

# 初始化 RPC 用戶端
solana_client = Client(RPC_HTTPS_URL)

# --- 🧠 數據處理邏輯 ---

def get_token_info(mint_address):
    """
    透過 RPC 獲取代幣的詳細資訊（供應量、價格、市值、建立時間）
    ⚠️ 這是高頻 RPC 請求，免費節點會在此處斷線
    實戰中通常會接 Birdeye API 或 DexScreener API 來獲取這部分數據，而非直接 RPC
    """
    try:
        # 模擬獲取數據 (真實 RPC 需要解析 AccountData 和 TokenAccount)
        # 此處省略複雜的 RPC 解析邏輯，假設獲取成功
        return {
            "mcap": 45000, 
            "price_sol": 0.00001,
            "created_time": datetime.now() - timedelta(days=5)
        }
    except Exception as e:
        return None

# 快取用於計算 1 分鐘成交量
trade_volume_cache = {} # {mint: [(timestamp, amount), ...]}

def calculate_1m_volume(mint):
    now = datetime.now()
    one_min_ago = now - timedelta(minutes=1)
    if mint in trade_volume_cache:
        # 移除一分鐘前的交易
        trade_volume_cache[mint] = [t for t in trade_volume_cache[mint] if t[0] > one_min_ago]
        # 計算總量
        return sum(t[1] for t in trade_volume_cache[mint])
    return 0

def check_filters(platform, mint, info, amount_sol):
    """執行你的三項條件篩選"""
    mcap = info['mcap']
    vol_1m = calculate_1m_volume(mint)
    age = (datetime.now() - info['created_time']).days

    tag = None
    # 1. 低市爆買
    if mcap < MCAP_LIMIT and amount_sol >= BUY_LIMIT:
        tag = "🔥 低市爆買"
    # 2. 爆量噴發
    elif vol_1m >= VOL_1M_LIMIT:
        tag = "⚡ 爆量噴發"
    # 3. 老幣回血
    elif age >= OLD_DAYS and amount_sol >= OLD_SURGE_LIMIT:
        tag = "💎 老幣回血"
    
    if tag:
        return {
            "時間": datetime.now().strftime("%H:%M:%S"),
            "平台": platform,
            "代幣": mint[:8] + "...",
            "市值": f"${mcap:,}",
            "交易額": f"{amount_sol} SOL",
            "狀態": tag
        }
    return None

# --- 🌐 Streamlit 介面 ---
st.title("🚀 Solana 真實鏈上監測 (RPC 版)")
st.caption(f"監聽節點: {RPC_WSS_URL[:30]}...")

# 用於顯示結果的 Dataframe
if "alert_data" not in st.session_state:
    st.session_state.alert_data = []

placeholder = st.empty()

# --- 🕷️ WebSocket 監聽主程式 ---
async def start_monitoring():
    platform_map = {
        PUMP_FUN_PROGRAM_ID: "Pump.fun",
        METEORA_PROGRAM_ID: "Meteora"
    }

    async with websockets.connect(RPC_WSS_URL) as websocket:
        # 訂閱所有交易紀錄 (logsSubscribe)
        subscribe_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "logsSubscribe",
            "params": [
                {"mentions": [PUMP_FUN_PROGRAM_ID, METEORA_PROGRAM_ID]}, # 監聽這些 Program 的交易
                {"commitment": "confirmed"}
            ]
        }
        await websocket.send(json.dumps(subscribe_msg))
        st.success("✅ 已建立 WebSocket 連線，正在監聽交易...")

        while True:
            try:
                response = await websocket.recv()
                data = json.loads(response)
                
                # 解析交易日誌 (這是最複雜的地方，需根據 Program 邏輯解析)
                # 這裡是一個簡化的流程：
                if "params" in data:
                    logs = data["params"]["result"]["value"]["logs"]
                    signature = data["params"]["result"]["value"]["signature"]
                    
                    # 判斷是哪個平台並提取關鍵資訊 (Mint 地址, 買入 SOL 金額)
                    platform = None
                    for log in logs:
                        if PUMP_FUN_PROGRAM_ID in log: platform = platform_map[PUMP_FUN_PROGRAM_ID]
                        elif METEORA_PROGRAM_ID in log: platform = platform_map[METEORA_PROGRAM_ID]
                    
                    if platform:
                        # ⚠️ 真實解析需要更深入的日誌分析或 getTransaction RPC 調用
                        # 此處模擬解析結果
                        mint = "TokenMintAddressxxxxxxxxxxxxxx" 
                        amount_sol = random.uniform(5, 50) # 模擬真實解析出的 SOL 金額
                        
                        # 更新快取
                        if mint not in trade_volume_cache: trade_volume_cache[mint] = []
                        trade_volume_cache[mint].append((datetime.now(), amount_sol))

                        # 獲取代幣詳情
                        info = get_token_info(mint)
                        if info:
                            result = check_filters(platform, mint, info, amount_sol)
                            if result:
                                st.session_state.alert_data.insert(0, result) # 加入最新警告
                                # 更新 UI
                                with placeholder.container():
                                    df = pd.DataFrame(st.session_state.alert_data[:20]) # 只顯示前20筆
                                    st.dataframe(df, use_container_width=True)

            except Exception as e:
                st.error(f"❌ 斷線或錯誤: {e}")
                await asyncio.sleep(5) # 嘗試重新連線
                break

# --- 啟動異步任務 ---
# 因為 Streamlit 是同步的，需要特殊的技巧來運行異步 WebSocket
if st.button("開始監測"):
    asyncio.run(start_monitoring())
