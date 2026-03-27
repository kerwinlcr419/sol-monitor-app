import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# --- 頁面配置 ---
st.set_page_config(page_title="SOL Alpha Hunter", layout="wide")

# 自定義 CSS 讓表格看起來更專業，並隱藏不必要的元件
st.markdown("""
    <style>
    .stDataFrame { width: 100%; }
    .copy-btn { background-color: #00ffa3; color: black; border-radius: 5px; padding: 2px 5px; cursor: pointer; }
    </style>
""", unsafe_allow_html=True)

# --- 側邊欄設定 (你的 3 項條件) ---
with st.sidebar:
    st.header("⚙️ 策略參數")
    MCAP_LIMIT = st.number_input("1. 市值上限 (USD)", value=50000)
    BUY_LIMIT_SOL = st.number_input("1. 買入觸發 (SOL)", value=10.0)
    VOL_1M_LIMIT = st.number_input("2. 1分鐘爆量 (SOL)", value=30.0)
    OLD_DAYS = st.number_input("3. 老幣定義 (天)", value=3)

# --- 核心數據抓取 (對接實時 API) ---
def fetch_data():
    # 這裡模擬從 Solana RPC 或 DexScreener 獲取的真實數據流
    # 實際上你會對接到 Pump.fun / Meteora 的實時 API
    mock_data = [
        {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Platform": "Pump.fun",
            "Symbol": "PEPE_SOL",
            "CA": "6EF8rrecth7DY54Z4863WE7498369262624262426242", # 範例 CA
            "MCap": 12500,
            "Vol_1m": 45.2,
            "Age": 0.1,
            "Dex": "https://dexscreener.com/solana/..."
        },
        {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Platform": "Meteora",
            "Symbol": "WIF_MOON",
            "CA": "EKpQ9A7P5m24Pmc2iSptYp6kSxyFwtT1V299V75Ypump", # 範例 CA
            "MCap": 48000,
            "Vol_1m": 12.0,
            "Age": 5.0,
            "Dex": "https://dexscreener.com/solana/..."
        }
    ]
    
    processed = []
    for d in mock_data:
        # 你的 3 項篩選邏輯
        tag = ""
        if d['MCap'] < MCAP_LIMIT and d['Vol_1m'] > BUY_LIMIT_SOL: tag = "🔥 低市爆買"
        elif d['Vol_1m'] > VOL_1M_LIMIT: tag = "⚡ 爆量噴發"
        elif d['Age'] >= OLD_DAYS and d['Vol_1m'] > (BUY_LIMIT_SOL * 2): tag = "💎 老幣回血"
        
        if tag:
            processed.append({
                "時間": d['Time'],
                "平台": d['Platform'],
                "代幣": d['Symbol'],
                "CA (點擊複製)": d['CA'], # 這是我們要處理的欄位
                "市值": f"${d['MCap']:,}",
                "1min": f"{d['Vol_1m']} SOL",
                "天數": f"{d['Age']}d",
                "狀態": tag,
                "查看": d['Dex']
            })
    return processed

# --- 主畫面 ---
st.title("🛡️ Solana 實時監測：Alpha Hunter")

if "data_log" not in st.session_state:
    st.session_state.data_log = []

# 更新數據
new_entries = fetch_data()
for ne in new_entries:
    if ne not in st.session_state.data_log:
        st.session_state.data_log.insert(0, ne)

# 保持長度
st.session_state.data_log = st.session_state.data_log[:20]

if st.session_state.data_log:
    df = pd.DataFrame(st.session_state.data_log)
    
    # 💡 關鍵：使用 Streamlit 的 column_config.TextColumn 搭配複製功能
    st.dataframe(
        df,
        column_config={
            "CA (點擊複製)": st.column_config.TextColumn(
                "CA (點擊複製)",
                help="點擊右側圖標即可複製合約地址",
                width="medium",
            ),
            "查看": st.column_config.LinkColumn("圖表連結")
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("⌛ 等待信號中... 自動刷新中")

# 自動刷新
time.sleep(5)
st.rerun()
