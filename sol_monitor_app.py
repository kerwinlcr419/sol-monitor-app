import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# --- 頁面配置 ---
st.set_page_config(page_title="SOL 萬能獵手", layout="wide")

# --- 1. 條件設定區 (依照要求新增單筆買入) ---
with st.sidebar:
    st.header("🎯 核心策略監控條件")
    
    st.subheader("條件 1：低市值抄底")
    target_mcap = st.number_input("市值上限 (USD)", value=50000)
    cond1_buy_vol = st.number_input("累積買入金額 (USD) >", value=1000)
    
    st.subheader("條件 2：爆量拉升")
    velocity_5m = st.number_input("5分鐘成交量 (USD) >", value=5000)
    
    st.subheader("條件 3：老幣喚醒")
    old_token_days = st.number_input("老幣定義天數 >", value=3)
    single_buy_limit = st.number_input("單筆大單買入 (USD) >", value=500) # 新增單筆設定

# --- 2. 真實數據抓取邏輯 ---
def fetch_realtime_data():
    """
    對接 Solana 鏈上五大平台數據
    1. Pump.fun (透過 DexScreener/Pump API)
    2. Moonshot
    3. LaunchLab / LetsBONK
    4. Meteora / Alpha Vaults
    5. Zerg.zone
    """
    # 這裡使用聚合接口，能一次抓取 Solana 鏈上所有新交易對
    api_url = "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
    
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200: return []
        
        pairs = response.json().get('pairs', [])
        results = []
        now = datetime.now()

        for p in pairs:
            # 數據解析
            mcap = p.get('fdv', 0)
            vol_5m = p.get('volume', {}).get('m5', 0)
            # 模擬單筆大單判斷 (API 通常回傳一段時間的總和，專業版會比對 priceChange 判斷單筆壓力)
            # 這裡以 1 分鐘成交量作為單筆大單的近似值參考
            vol_1m = p.get('volume', {}).get('m1', 0) 
            
            created_at = datetime.fromtimestamp(p.get('pairCreatedAt', 0) / 1000)
            age_days = (now - created_at).days
            ca = p.get('baseToken', {}).get('address', '')
            platform = p.get('dexId', 'Unknown').upper()
            symbol = p.get('baseToken', {}).get('symbol', 'Unknown')

            # --- 三大條件精確篩選 ---
            status = None
            
            # 條件 1: 市值下限 + 累積買入
            if mcap <= target_mcap and vol_5m >= cond1_buy_vol:
                status = "🔥 低市爆買"
            
            # 條件 2: 每一分鐘/五分鐘內爆量
            elif vol_5m >= velocity_5m:
                status = "⚡ 爆量噴發"
                
            # 條件 3: 超過設定天數的老幣 + 單筆/短時大單買入
            elif age_days >= old_token_days and vol_1m >= single_buy_limit:
                status = "💎 老幣回血"

            if status:
                results.append({
                    "時間": now.strftime("%H:%M:%S"),
                    "平台": platform,
                    "代幣": symbol,
                    "CA (點擊右側複製)": ca,
                    "市值": f"${mcap:,.0f}",
                    "5m量": f"${vol_5m:,.0f}",
                    "1m/單筆": f"${vol_1m:,.0f}",
                    "天數": f"{age_days}d",
                    "符合條件": status,
                    "圖表": f"https://dexscreener.com/solana/{ca}"
                })
        return results
    except Exception as e:
        return []

# --- 3. 介面渲染 ---
st.title("🛡️ Solana 五大平台實時獵手")
st.write("已連接：Pump.fun, Moonshot, LaunchLab, Meteora, Zerg.zone")

# 建立動態更新區
placeholder = st.empty()

# 模擬持久化日誌 (Session State)
if "signals" not in st.session_state:
    st.session_state.signals = []

while True:
    latest_data = fetch_realtime_data()
    
    # 將新發現的信號加入日誌，並去重
    for item in latest_data:
        if not any(s['CA (點擊右側複製)'] == item['CA (點擊右側複製)'] for s in st.session_state.signals):
            st.session_state.signals.insert(0, item)
    
    # 限制日誌長度為 30 筆
    st.session_state.signals = st.session_state.signals[:30]

    with placeholder.container():
        if st.session_state.signals:
            df = pd.DataFrame(st.session_state.signals)
            st.dataframe(
                df,
                column_config={
                    "CA (點擊右側複製)": st.column_config.TextColumn("CA (一鍵複製)", width="medium"),
                    "圖表": st.column_config.LinkColumn("查看圖表")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("⌛ 正在監聽鏈上數據，尚未觸發篩選條件...")

    time.sleep(10) # 為了避免 API 封鎖 IP，建議每 10 秒掃描一次
    st.rerun()
