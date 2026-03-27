import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# --- 頁面配置 ---
st.set_page_config(page_title="SOL 實時獵手 Pro", layout="wide")

# 自定義 CSS (優化手機複製 CA 的視覺反饋)
st.markdown("""
    <style>
    .stDataFrame { width: 100%; }
    .stButton>button { width: 100%; background-color: #00ffa3; color: black; font-weight: bold; }
    [data-testid="stMetricValue"] { font-size: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 1. 側邊欄：硬核條件設定 ---
with st.sidebar:
    st.header("🎯 監控策略設定")
    
    # 啟動按鈕
    run_monitor = st.checkbox("🚀 開啟實時監測", value=False)
    
    st.divider()
    
    st.subheader("條件 1：低市值 + 大單")
    c1_mcap_max = st.number_input("市值低於 (USD)", value=50000)
    c1_single_buy = st.number_input("單筆買入超過 (USD)", value=500, key="c1_buy")
    
    st.subheader("條件 2：短時爆量")
    c2_vol_5m = st.number_input("5分鐘總成交 > (USD)", value=5000)
    
    st.subheader("條件 3：老幣喚醒")
    c3_days = st.number_input("老幣定義天數 >", value=3)
    c3_single_buy = st.number_input("老幣單筆買入 > (USD)", value=800, key="c3_buy")

# --- 2. 真實數據抓取引擎 ---
def fetch_chain_data():
    """對接 Solana 鏈上真實數據流"""
    # 使用 DexScreener 聚合接口 (涵蓋五大平台數據)
    api_url = "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
    
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200: return []
        
        pairs = response.json().get('pairs', [])
        now = datetime.now()
        matches = []

        for p in pairs:
            # 數據解析 (FDV 作為市值參考)
            mcap = p.get('fdv', 0)
            vol_1m = p.get('volume', {}).get('m1', 0) # 近似單筆/短時大單
            vol_5m = p.get('volume', {}).get('m5', 0)
            created_at = datetime.fromtimestamp(p.get('pairCreatedAt', 0) / 1000)
            age_days = (now - created_at).days
            ca = p.get('baseToken', {}).get('address', '')
            platform = p.get('dexId', 'Unknown').upper()
            symbol = p.get('baseToken', {}).get('symbol', 'Unknown')

            # --- 三大硬核條件判斷 ---
            status = None
            
            # 條件 1: 市值低於設定值 AND 單筆買入達標
            if mcap <= c1_mcap_max and vol_1m >= c1_single_buy:
                status = "🔥 低市大單"
            
            # 條件 2: 5分鐘爆量
            elif vol_5m >= c2_vol_5m:
                status = "⚡ 爆量噴發"
                
            # 條件 3: 老幣天數 AND 單筆買入達標
            elif age_days >= c3_days and vol_1m >= c3_single_buy:
                status = "💎 老幣翻紅"

            if status:
                matches.append({
                    "時間": now.strftime("%H:%M:%S"),
                    "平台": platform,
                    "代幣": symbol,
                    "CA (點擊複製)": ca,
                    "市值": f"${mcap:,.0f}",
                    "單筆推估": f"${vol_1m:,.0f}",
                    "5m總量": f"${vol_5m:,.0f}",
                    "天數": f"{age_days}d",
                    "符合條件": status,
                    "圖表": f"https://dexscreener.com/solana/{ca}"
                })
        return matches
    except Exception as e:
        return []

# --- 3. 介面渲染邏輯 ---
st.title("🛡️ SOL 鏈全平台實時監測")
st.caption("支援平台：Pump.fun, Moonshot, LaunchLab, Meteora, Zerg.zone")

if not run_monitor:
    st.info("👈 請在左側設定參數後，勾選「開啟實時監測」啟動程式。")
else:
    # 建立信號存儲
    if "signal_history" not in st.session_state:
        st.session_state.signal_history = []

    placeholder = st.empty()

    # 開始循環監測
    while run_monitor:
        new_data = fetch_chain_data()
        
        # 存入 Session 並去重
        for item in new_data:
            if not any(s['CA (點擊複製)'] == item['CA (點擊複製)'] for s in st.session_state.signal_history):
                st.session_state.signal_history.insert(0, item)
        
        # 保持顯示最新 50 筆
        st.session_state.signal_history = st.session_state.signal_history[:50]

        with placeholder.container():
            if st.session_state.signal_history:
                df = pd.DataFrame(st.session_state.signal_history)
                st.dataframe(
                    df,
                    column_config={
                        "CA (點擊複製)": st.column_config.TextColumn("CA (一鍵複製)", width="medium"),
                        "圖表": st.column_config.LinkColumn("查看圖表")
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.spinner("正在掃描鏈上數據...")
        
        time.sleep(12) # 避免 API 頻繁請求
        st.rerun()
