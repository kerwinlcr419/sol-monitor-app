import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# --- 頁面配置 ---
st.set_page_config(page_title="SOL 真實鏈上監控", layout="wide")

# 注入自定義 CSS (優化手機顯示與一鍵複製體驗)
st.markdown("""
    <style>
    .stDataFrame { width: 100%; }
    [data-testid="stMetricValue"] { font-size: 24px; color: #00ffa3; }
    </style>
""", unsafe_allow_html=True)

# --- 側邊欄設定 (連動你的 3 項條件) ---
with st.sidebar:
    st.header("🎯 篩選策略設定")
    target_mcap = st.number_input("1. 市值上限 (USD)", value=50000, help="低於此市值才顯示")
    min_buy_vol = st.number_input("1. 買入門檻 (USD)", value=1000, help="單筆或短時買入額")
    velocity_5m = st.number_input("2. 5分鐘成交量門檻", value=5000)
    old_token_days = st.number_input("3. 老幣定義 (天數)", value=3)

# --- 核心：獲取真實鏈上數據 ---
def get_realtime_sol_data():
    """調用 DexScreener API 獲取 Solana 最新代幣對"""
    try:
        # 抓取 Solana 鏈上最新變動的 30 個交易對
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        # 這裡改用另一個更強大的 API：最新 Boosted 交易對 (包含 Pump.fun 畢業後的幣)
        search_url = "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
        
        response = requests.get(search_url, timeout=10)
        if response.status_code != 200: return []
        
        pairs = response.json().get('pairs', [])
        now = datetime.now()
        matches = []

        for p in pairs:
            # 過濾非 Solana 鏈數據
            if p.get('chainId') != 'solana': continue
            
            # 提取關鍵數據
            mcap = p.get('fdv', 0)  # 完全稀釋估值 (即市值)
            vol_5m = p.get('volume', {}).get('m5', 0)
            vol_1h = p.get('volume', {}).get('h1', 0)
            created_at = datetime.fromtimestamp(p.get('pairCreatedAt', 0) / 1000)
            age_days = (now - created_at).days
            ca = p.get('baseToken', {}).get('address', '')
            platform = p.get('dexId', 'Unknown').capitalize()
            symbol = p.get('baseToken', {}).get('symbol', 'Unknown')

            # --- 你的 3 項硬核條件判斷 ---
            tag = ""
            # 1. 市值設定值以下 且 買入金額達標 (這裡用 5m 成交量作為參考)
            if mcap <= target_mcap and vol_5m >= min_buy_vol:
                tag = "🔥 低市爆買"
            # 2. 5分鐘內成交量暴增
            elif vol_5m >= velocity_5m:
                tag = "⚡ 爆量噴發"
            # 3. 超過設定天數的老幣 突然爆量
            elif age_days >= old_token_days and vol_5m > (velocity_5m * 0.5):
                tag = "💎 老幣翻紅"

            if tag:
                matches.append({
                    "時間": now.strftime("%H:%M:%S"),
                    "平台": platform,
                    "代幣": symbol,
                    "CA (一鍵複製)": ca,
                    "市值": f"${mcap:,.0f}",
                    "5m成交額": f"${vol_5m:,.0f}",
                    "天數": f"{age_days}天",
                    "狀態": tag,
                    "圖表": f"https://dexscreener.com/solana/{ca}"
                })
        return matches
    except Exception as e:
        return [{"狀態": "Error", "代幣": str(e)}]

# --- UI 介面 ---
st.title("🛡️ Solana Real-time Alpha Hunter")
st.caption("數據來源：DexScreener API (涵蓋 Pump.fun, Raydium, Meteora)")

# 自動刷新容器
placeholder = st.empty()

# 為了讓它在 Streamlit 上像真正的監控器，使用無限循環
while True:
    real_data = get_realtime_sol_data()
    
    with placeholder.container():
        if real_data:
            df = pd.DataFrame(real_data)
            # 使用自定義顯示
            st.dataframe(
                df,
                column_config={
                    "CA (一鍵複製)": st.column_config.TextColumn("CA (點擊右側複製)", width="medium"),
                    "圖表": st.column_config.LinkColumn("查看線圖")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("⌛ 目前池子中無符合條件的目標，持續掃描中...")
            
    time.sleep(12) # API 限制建議每 10-15 秒請求一次
    st.rerun()
