import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# --- 頁面配置 ---
st.set_page_config(page_title="SOL 實時獵手", layout="wide")

# 側邊欄：設定參數
with st.sidebar:
    st.header("🎯 監控策略")
    start_btn = st.checkbox("🚀 啟動監測", value=False)
    
    st.divider()
    st.subheader("條件 1：低市值 + 單筆大單")
    c1_mcap = st.number_input("市值低於 (USD)", value=50000)
    c1_buy = st.number_input("單筆買入 > (USD)", value=500)
    
    st.subheader("條件 2：5分爆量")
    c2_vol = st.number_input("5分鐘總量 > (USD)", value=5000)
    
    st.subheader("條件 3：老幣喚醒")
    c3_days = st.number_input("天數 >", value=3)
    c3_buy = st.number_input("老幣單筆 > (USD)", value=800)

# --- 核心數據抓取 (使用 DexScreener 實時 Token 流) ---
def get_live_data():
    # 這是目前最穩定的 Solana 全鏈實時數據接口
    url = "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code != 200: return []
        
        pairs = res.json().get('pairs', [])
        results = []
        now = datetime.now()

        for p in pairs:
            # 只看 Solana 鏈
            if p.get('chainId') != 'solana': continue
            
            mcap = p.get('fdv', 0)
            vol_1m = p.get('volume', {}).get('m1', 0) # 用 1 分鐘量來過濾單筆大單
            vol_5m = p.get('volume', {}).get('m5', 0)
            created_at = datetime.fromtimestamp(p.get('pairCreatedAt', 0) / 1000)
            age_days = (now - created_at).days
            ca = p.get('baseToken', {}).get('address', '')
            platform = p.get('dexId', '').upper()
            symbol = p.get('baseToken', {}).get('symbol', '')

            # 邏輯判斷
            tag = ""
            if mcap <= c1_mcap and vol_1m >= c1_buy:
                tag = "🔥 低市大單"
            elif vol_5m >= c2_vol:
                tag = "⚡ 爆量噴發"
            elif age_days >= c3_days and vol_1m >= c3_buy:
                tag = "💎 老幣翻紅"
            
            if tag:
                results.append({
                    "時間": now.strftime("%H:%M:%S"),
                    "平台": platform,
                    "代幣": symbol,
                    "CA (一鍵複製)": ca,
                    "市值": f"${mcap:,.0f}",
                    "單筆/1m": f"${vol_1m:,.0f}",
                    "天數": f"{age_days}d",
                    "狀態": tag,
                    "連結": f"https://dexscreener.com/solana/{ca}"
                })
        return results
    except:
        return []

# --- 介面顯示 ---
st.title("🛡️ Solana 全平台實時監測")

if not start_btn:
    st.info("👈 請在左側設定參數後勾選「啟動監測」。")
else:
    if "log" not in st.session_state:
        st.session_state.log = []

    # 執行抓取
    new_data = get_live_data()
    for item in new_data:
        # 簡單去重
        if not any(x['CA (一鍵複製)'] == item['CA (一鍵複製)'] for x in st.session_state.log):
            st.session_state.log.insert(0, item)
    
    st.session_state.log = st.session_state.log[:30] # 保留30筆記錄

    if st.session_state.log:
        df = pd.DataFrame(st.session_state.log)
        st.dataframe(
            df,
            column_config={
                "CA (一鍵複製)": st.column_config.TextColumn("CA (點擊複製)", width="medium"),
                "連結": st.column_config.LinkColumn("查看圖表")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.write("正在掃描鏈上數據...")

    time.sleep(10) # 每 10 秒刷新一次
    st.rerun()
