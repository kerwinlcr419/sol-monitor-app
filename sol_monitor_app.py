import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

# --- 頁面設定 ---
st.set_page_config(page_title="Solana 實時監測", layout="wide")

# --- 你的 3 項條件設定 (側邊欄) ---
st.sidebar.header("📊 監控條件設定")
MCAP_LIMIT = st.sidebar.number_input("1. 市值設定值以下 (USD)", value=50000)
BUY_LIMIT = st.sidebar.number_input("1. 買入金額門檻 (USD)", value=1000) # API以USD計
VOL_1M_LIMIT = st.sidebar.number_input("2. 5分鐘內成交量門檻 (USD)", value=5000)
OLD_DAYS_LIMIT = st.sidebar.number_input("3. 老幣天數設定", value=3)

# --- 核心數據抓取 ---
def fetch_real_solana_data():
    # 使用 DexScreener API 獲取 Solana 鏈上最新交易對
    url = "https://api.dexscreener.com/token-profiles/latest/v1"
    try:
        # 獲取最新代幣列表
        response = requests.get(url)
        profiles = response.json()
        
        # 為了獲取市值和成交量，我們轉向獲取特定排名的池子數據
        # 這裡改用 Solana 的最新 Boosted 或 Trend 接口來模擬
        search_url = "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112" # 獲取熱門SOL對
        res = requests.get(search_url)
        pairs = res.json().get('pairs', [])
        
        results = []
        now = datetime.now()

        for pair in pairs:
            # 取得基礎數據
            mcap = pair.get('fdv', 0)
            vol_5m = pair.get('volume', {}).get('m5', 0)
            created_at = datetime.fromtimestamp(pair.get('pairCreatedAt', 0) / 1000)
            age_days = (now - created_at).days
            
            # 判斷邏輯
            status = "🔍 掃描中"
            if mcap < MCAP_LIMIT and vol_5m > BUY_LIMIT:
                status = "🔥 低市爆買"
            elif vol_5m > VOL_1M_LIMIT:
                status = "⚡ 爆量噴發"
            elif age_days >= OLD_DAYS_LIMIT and vol_5m > (VOL_1M_LIMIT * 2):
                status = "💎 老幣回血"
            
            if status != "🔍 掃描中":
                results.append({
                    "時間": now.strftime("%H:%M:%S"),
                    "平台": pair.get('dexId', 'Unknown').capitalize(),
                    "代幣": pair.get('baseToken', {}).get('symbol', 'Unknown'),
                    "市值": f"${mcap:,.0f}",
                    "5分成交額": f"${vol_5m:,.0f}",
                    "上線天數": f"{age_days}天",
                    "狀態": status,
                    "連結": f"https://dexscreener.com/solana/{pair.get('pairAddress')}"
                })
        return results
    except Exception as e:
        st.error(f"數據抓取失敗: {e}")
        return []

# --- 介面渲染 ---
st.title("🚀 Solana 鏈真實代幣監測器")
st.write(f"監測對象：Pump.fun, Raydium, Meteora (透過 DexScreener API)")

placeholder = st.empty()

# 模擬即時循環
while True:
    data = fetch_real_solana_data()
    with placeholder.container():
        if data:
            df = pd.DataFrame(data)
            # 使用 Dataframe 展示並讓連結可以點擊
            st.dataframe(
                df, 
                column_config={"連結": st.column_config.LinkColumn("查看圖表")},
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("目前尚未發現符合條件的代幣，持續監控中...")
            
    time.sleep(10) # 每 10 秒刷新一次 API
    st.rerun()
