import streamlit as st
import pandas as pd
import random
import time
from datetime import datetime, timedelta

# --- 頁面配置 ---
st.set_page_config(page_title="SOL 鏈即時監控", layout="wide")

# --- 模擬數據生成 (對接實體 API 時修改此處) ---
def fetch_sol_data():
    platforms = ["Pump.fun", "Moonshot", "LaunchLab", "Meteora", "Zerg.zone"]
    data = []
    for p in platforms:
        mcap = random.randint(5000, 150000)
        buy_1m = round(random.uniform(0.5, 60.0), 2)
        age = random.randint(0, 10)
        
        # 你的 3 項條件判斷邏輯
        status = "✅ 掃描中"
        # 1. 市值 5萬以下 且 買入 > 10 SOL
        if mcap < 50000 and buy_1m > 10: status = "🔥 低市爆買"
        # 2. 1分鐘內買入量 > 30 SOL
        elif buy_1m > 30: status = "⚡ 急速拉升"
        # 3. 超過 3天 的老幣 買入 > 20 SOL
        elif age >= 3 and buy_1m > 20: status = "💎 老幣回血"
        
        data.append({
            "平台": p,
            "代幣名稱": f"SOL-{random.randint(100, 999)}",
            "市值 (USD)": f"${mcap:,}",
            "1min 買入 (SOL)": buy_1m,
            "上線天數": f"{age}天",
            "狀態": status
        })
    return data

# --- 介面渲染 ---
st.title("🚀 Solana 多平台即時監測")
st.caption("自動監控：Pump.fun, Moonshot, LaunchLab, Meteora, Zerg.zone")

# 設定自動刷新 (Streamlit 自動刷新機制)
if "load_count" not in st.session_state:
    st.session_state.load_count = 0

# 側邊欄設定 (讓你可以隨時手動調整數值)
st.sidebar.header("⚙️ 條件設定")
mcap_limit = st.sidebar.number_input("1. 市值設定值以下", value=50000)
buy_limit = st.sidebar.number_input("1. 買入金額設定值", value=10)
vol_1m_limit = st.sidebar.number_input("2. 每分鐘買入量設定值", value=30)
old_days = st.sidebar.number_input("3. 老幣定義天數", value=3)

# 顯示數據表格
current_data = fetch_sol_data()
df = pd.DataFrame(current_data)

# 使用顏色高亮觸發條件的行
def highlight_status(val):
    color = '#1f77b4' if val == "✅ 掃描中" else '#d62728'
    return f'background-color: {color}'

st.table(df) # 或者使用 st.dataframe(df)

# 自動更新腳本 (讓網頁每 5 秒動一次)
time.sleep(5)
st.rerun()
