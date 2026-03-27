import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime

st.set_page_config(page_title="SOL監測", layout="wide", initial_sidebar_state="collapsed")

st.title("🚀 SOL 鏈幣即時監測 App")
st.caption("5 大平台 • 3 項條件 • CA 一鍵複製 • 手機專用")

# ====================== 側邊欄設定 ======================
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

# ====================== 目前條件設定面板（新功能） ======================
st.subheader("📊 目前條件設定值")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("條件1：市值以下 + 買入", f"${mcap_threshold:,} USD + {buy_amount1} SOL")
with col2:
    st.metric("條件2：每分鐘買入", f"{minute_buy_threshold} SOL")
with col3:
    st.metric("條件3：老幣突然大買", f"{age_threshold_days} 天以上 + {sudden_buy_amount} SOL")

if st.button("🔄 重置全部為預設值"):
    st.session_state.clear()
    st.rerun()

# ====================== 模擬數據 ======================
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "tokens" not in st.session_state:
    st.session_state.tokens = []

def generate_mock_token():
    platform = random.choice(selected)
    ca_chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    ca = ''.join(random.choices(ca_chars, k=44))
    return {
        "時間": datetime.now().strftime("%H:%M:%S"),
        "平台": platform,
        "幣種": f"${random.choice(['PEPE','DOGE','BONK','MOON','ZERG'])}{random.randint(100,999)}",
        "CA": ca,
        "市值": random.randint(8000, 150000),
        "幣齡(天)": random.randint(0, 30),
        "單筆買入(SOL)": round(random.uniform(5, 120), 1),
        "1分鐘買入(SOL)": round(random.uniform(10, 200), 1),
    }

# ====================== CA 一鍵複製按鈕 ======================
def copy_ca_button(ca):
    st.markdown(
        f"""
        <a href="#" onclick="navigator.clipboard.writeText('{ca}'); 
        this.style.backgroundColor='#10a37f'; 
        this.innerHTML='✅ 已複製！'; 
        setTimeout(() => {{this.innerHTML='📋 複製 CA'; this.style.backgroundColor='#00cc66';}}, 1800); 
        return false;"
        style="background-color:#00cc66; color:white; padding:8px 16px; border-radius:8px; 
        text-decoration:none; display:inline-block; font-size:15px; font-weight:bold;">
        📋 複製 CA
        </a>
        """,
        unsafe_allow_html=True,
    )

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
    for _ in range(40):   # 可長時間運行
        token = generate_mock_token()
        st.session_state.tokens.append(token)
        
        # 條件1
        if token["市值"] < mcap_threshold and token["單筆買入(SOL)"] >= buy_amount1:
            alert_text = f"🚨條件1 | {token['平台']} | {token['幣種']} | 市值${token['市值']:,} | 買入{token['單筆買入(SOL)']}SOL"
            st.session_state.alerts.append({"時間": token["時間"], "警報": alert_text, "CA": token["CA"], "等級": "高"})
        
        # 條件2
        if token["1分鐘買入(SOL)"] >= minute_buy_threshold:
            alert_text = f"🚨條件2 | {token['平台']} | {token['幣種']} | 1分鐘買入{token['1分鐘買入(SOL)']}SOL"
            st.session_state.alerts.append({"時間": token["時間"], "警報": alert_text, "CA": token["CA"], "等級": "中"})
        
        # 條件3
        if token["幣齡(天)"] > age_threshold_days and token["單筆買入(SOL)"] >= sudden_buy_amount:
            alert_text = f"🚨條件3 | {token['平台']} | {token['幣種']} | 老幣{token['幣齡(天)']}天 | 突買{token['單筆買入(SOL)']}SOL"
            st.session_state.alerts.append({"時間": token["時間"], "警報": alert_text, "CA": token["CA"], "等級": "高"})
        
        # 顯示最新 Token
        df = pd.DataFrame(st.session_state.tokens[-8:])
        token_placeholder.dataframe(df[["時間", "平台", "幣種", "CA", "市值", "幣齡(天)", "單筆買入(SOL)"]], use_container_width=True, hide_index=True)
        
        # 顯示警報（每筆都有 CA 一鍵複製）
        alert_container = alert_placeholder.container()
        with alert_container:
            st.subheader("🚨 最新警報")
            for alert in reversed(st.session_state.alerts[-6:]):
                st.markdown(f"**{alert['時間']}** | {alert['警報']}")
                copy_ca_button(alert["CA"])
                st.divider()
        
        time.sleep(5)

# ====================== 歷史警報 ======================
st.header("📜 歷史警報紀錄")
if st.session_state.alerts:
    for alert in reversed(st.session_state.alerts):
        st.markdown(f"**{alert['時間']}** | {alert['警報']}")
        copy_ca_button(alert["CA"])
        st.divider()
else:
    st.info("尚未觸發警報")

st.success("✅ 新功能已加入！CA 可以一鍵複製，條件數值也在主畫面清楚顯示")
st.caption("💡 部署後直接在手機主畫面開啟即可使用")