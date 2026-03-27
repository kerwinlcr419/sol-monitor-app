import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime

st.set_page_config(page_title="SOL監測", layout="wide", initial_sidebar_state="collapsed")

st.title("🚀 SOL 鏈幣即時監測 App")
st.caption("5 大平台 • 3 項條件 • 手機專用")

with st.sidebar:
    st.header("監測平台")
    platforms = ["Pump.fun", "Moonshot", "LaunchLab / LetsBONK.fun", "Meteora / Alpha Vaults", "Zerg.zone"]
    selected = st.multiselect("選擇平台", platforms, default=platforms)
    
    st.header("⚙️ 3 項條件設定")
    mcap_threshold = st.number_input("1. 市值低於 (USD)", value=50000, step=1000)
    buy_amount1 = st.number_input("   買入金額 (SOL)", value=10.0, step=1.0)
    
    minute_buy_threshold = st.number_input("2. 每分鐘買入 (SOL)", value=50.0, step=5.0)
    
    age_threshold_days = st.number_input("3. 幣齡超過 (天)", value=7, step=1)
    sudden_buy_amount = st.number_input("   突然大買 (SOL)", value=30.0, step=5.0)

if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "tokens" not in st.session_state:
    st.session_state.tokens = []

def generate_mock_token():
    platform = random.choice(selected)
    return {
        "時間": datetime.now().strftime("%H:%M:%S"),
        "平台": platform,
        "幣種": f"${random.choice(['PEPE','DOGE','BONK','MOON','ZERG'])}{random.randint(100,999)}",
        "市值": random.randint(8000, 150000),
        "幣齡(天)": random.randint(0, 30),
        "單筆買入(SOL)": round(random.uniform(5, 120), 1),
        "1分鐘買入(SOL)": round(random.uniform(10, 200), 1),
    }

st.header("📡 實時監測中")
col1, col2 = st.columns([3,1])
if col1.button("🔄 開始監測（每5秒更新）", type="primary", use_container_width=True):
    st.session_state.monitoring = True
if col2.button("⏹️ 停止", use_container_width=True):
    st.session_state.monitoring = False

placeholder = st.empty()
alert_placeholder = st.empty()

if st.session_state.get("monitoring", False):
    for _ in range(30):
        token = generate_mock_token()
        st.session_state.tokens.append(token)
        
        if token["市值"] < mcap_threshold and token["單筆買入(SOL)"] >= buy_amount1:
            st.session_state.alerts.append({"時間": token["時間"], "警報": f"🚨條件1 | {token['平台']} | {token['幣種']} | 市值${token['市值']} | 買入{token['單筆買入(SOL)']}SOL", "等級": "高"})
        if token["1分鐘買入(SOL)"] >= minute_buy_threshold:
            st.session_state.alerts.append({"時間": token["時間"], "警報": f"🚨條件2 | {token['平台']} | {token['幣種']} | 1分鐘{token['1分鐘買入(SOL)']}SOL", "等級": "中"})
        if token["幣齡(天)"] > age_threshold_days and token["單筆買入(SOL)"] >= sudden_buy_amount:
            st.session_state.alerts.append({"時間": token["時間"], "警報": f"🚨條件3 | {token['平台']} | {token['幣種']} | 老幣{token['幣齡(天)']}天 | 突買{token['單筆買入(SOL)']}SOL", "等級": "高"})
        
        df = pd.DataFrame(st.session_state.tokens[-8:])
        placeholder.dataframe(df, use_container_width=True, hide_index=True)
        
        if st.session_state.alerts:
            alert_df = pd.DataFrame(st.session_state.alerts[-6:])
            alert_placeholder.dataframe(alert_df, use_container_width=True, hide_index=True)
        
        time.sleep(5)

st.success("✅ App 已準備好！點上方開始監測即可")
st.caption("💡 手機版已優化，側邊欄自動收合")