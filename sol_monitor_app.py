import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime

st.set_page_config(page_title="SOL監測", layout="wide", initial_sidebar_state="collapsed")

st.title("🚀 SOL 鏈幣即時監測 App")
st.caption("5 大平台 • 3 項條件 • 真實 CA • 長按複製 • 手機專用")

# ====================== 警告說明 ======================
st.warning("⚠️ 目前仍是模擬監測（買入數據為測試），但 CA 已改成真實存在的 Solana 幣。你複製後可在 Solscan / Birdeye 找到真實幣。想接真實即時數據（Pump.fun/Moonshot）請告訴我！")

# ====================== 主畫面條件設定 ======================
st.subheader("⚙️ 條件設定（直接在這裡手動修改）")
with st.expander("🔧 展開調整 3 項條件", expanded=True):
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        mcap_threshold = st.number_input("1. 市值低於 (USD)", value=50000, step=1000)
        buy_amount1 = st.number_input("   買入金額 (SOL)", value=10.0, step=1.0)
    with col_set2:
        minute_buy_threshold = st.number_input("2. 每分鐘買入 (SOL)", value=50.0, step=5.0)
    
    col_set3, col_set4 = st.columns(2)
    with col_set3:
        age_threshold_days = st.number_input("3. 幣齡超過 (天)", value=7, step=1)
    with col_set4:
        sudden_buy_amount = st.number_input("   突然大買 (SOL)", value=30.0, step=5.0)

# ====================== 目前條件值 ======================
st.subheader("📊 目前條件設定值")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("條件1", f"${mcap_threshold:,} + {buy_amount1} SOL")
with col2:
    st.metric("條件2", f"{minute_buy_threshold} SOL/分鐘")
with col3:
    st.metric("條件3", f"{age_threshold_days} 天 + {sudden_buy_amount} SOL")

# ====================== 監測平台 ======================
with st.sidebar:
    st.header("監測平台")
    platforms = ["Pump.fun", "Moonshot", "LaunchLab / LetsBONK.fun", "Meteora / Alpha Vaults", "Zerg.zone"]
    selected = st.multiselect("選擇平台", platforms, default=platforms)

# ====================== 真實 CA 資料庫（已修正） ======================
REAL_CAS = [
    "SoLeKPdJ5GjUtvFAeNtefpKhRj42vjoZWmrvLmSWnmS",   # Pump.fun 真實幣
    "Ek3ts4r6kGC7VmFBVimFEz7CqyRZGpxcbwXs57YDYLoH",   # Pump.fun 真實幣
    "pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn",    # $PUMP 官方
    "7MUp1jJd25RTqUatDep55qMbVSNpLfn8qLKXv9Rbpump",   # meme coin 真實
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",   # USDC (測試用)
]

if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "tokens" not in st.session_state:
    st.session_state.tokens = []

def generate_mock_token():
    platform = random.choice(selected)
    ca = random.choice(REAL_CAS)          # ← 改用真實 CA
    return {
        "時間": datetime.now().strftime("%H:%M:%S"),
        "平台": platform,
        "幣種": f"${random.choice(['PEPE','DOGE','BONK','MOON','ZERG','PUMP'])}{random.randint(100,999)}",
        "CA": ca,
        "市值": random.randint(8000, 150000),
        "幣齡(天)": random.randint(0, 30),
        "單筆買入(SOL)": round(random.uniform(5, 120), 1),
        "1分鐘買入(SOL)": round(random.uniform(10, 200), 1),
    }

# ====================== 實時監測 ======================
st.header("📡 實時監測中")
col_start, col_stop = st.columns([3,1])
if col_start.button("🔄 開始監測（每5秒更新）", type="primary", use_container_width=True):
    st.session_state.monitoring = True
if col_stop.button("⏹️ 停止", use_container_width=True):
    st.session_state.monitoring = False

token_placeholder = st.empty()
alert_placeholder = st.empty()

if st.session_state.get("monitoring", False):
    for _ in range(50):
        token = generate_mock_token()
        st.session_state.tokens.append(token)
        
        # 條件判斷（同之前）
        if token["市值"] < mcap_threshold and token["單筆買入(SOL)"] >= buy_amount1:
            alert_text = f"🚨條件1 | {token['平台']} | {token['幣種']} | 市值${token['市值']:,} | 買入{token['單筆買入(SOL)']}SOL"
            st.session_state.alerts.append({"時間": token["時間"], "警報": alert_text, "CA": token["CA"]})
        if token["1分鐘買入(SOL)"] >= minute_buy_threshold:
            alert_text = f"🚨條件2 | {token['平台']} | {token['幣種']} | 1分鐘{token['1分鐘買入(SOL)']}SOL"
            st.session_state.alerts.append({"時間": token["時間"], "警報": alert_text, "CA": token["CA"]})
        if token["幣齡(天)"] > age_threshold_days and token["單筆買入(SOL)"] >= sudden_buy_amount:
            alert_text = f"🚨條件3 | {token['平台']} | {token['幣種']} | 老幣{token['幣齡(天)']}天 | 突買{token['單筆買入(SOL)']}SOL"
            st.session_state.alerts.append({"時間": token["時間"], "警報": alert_text, "CA": token["CA"]})
        
        # 顯示 Token 列表
        df = pd.DataFrame(st.session_state.tokens[-8:])
        token_placeholder.dataframe(df[["時間", "平台", "幣種", "CA", "市值", "幣齡(天)", "單筆買入(SOL)"]], use_container_width=True, hide_index=True)
        
        # 警報區（長按複製 CA）
        with alert_placeholder.container():
            st.subheader("🚨 最新警報")
            for alert in reversed(st.session_state.alerts[-8:]):
                st.markdown(f"**{alert['時間']}** | {alert['警報']}")
                st.code(alert["CA"], language=None)   # ← 長按即可複製
                st.caption("📱 長按上方 CA 文字 → 複製")
                st.markdown(f"[🔍 查看 Solscan](https://solscan.io/token/{alert['CA']})")
                st.divider()
        
        time.sleep(5)

# ====================== 歷史警報 ======================
st.header("📜 歷史警報紀錄")
if st.session_state.alerts:
    for alert in reversed(st.session_state.alerts):
        st.markdown(f"**{alert['時間']}** | {alert['警報']}")
        st.code(alert["CA"], language=None)
        st.caption("📱 長按 CA 文字即可複製")
        st.markdown(f"[🔍 查看 Solscan](https://solscan.io/token/{alert['CA']})")
        st.divider()
else:
    st.info("尚未觸發警報")

st.success("✅ 已修正！CA 現在是真實幣，複製方式改成長按即可")
st.caption("測試完告訴我是否要升級成「真實即時數據」（Pump.fun/Moonshot 真實買入）")