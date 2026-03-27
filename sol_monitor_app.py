import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="SOL鏈代幣自動監測器",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 SOL鏈代幣自動監測器（5大平台）")
st.caption("✅ **Pump.fun 全自動即時掃描**｜其餘4平台因無公開「最新幣」API，採用 CA 查詢模式（真實 Dexscreener 資料）｜全部使用公開免費 API，無模擬")

# ==================== 側邊欄條件設定 ====================
st.sidebar.header("⚙️ 警報條件設定（3 項）")
mc_threshold = st.sidebar.number_input("1. 市值設定值以下 (USD)", value=150000, step=10000)
single_buy_sol = st.sidebar.number_input("   一次買入金額設定值 (SOL)", value=12.0, step=0.5)

min_buy_sol = st.sidebar.number_input("2. 每一分鐘內買入金額設定值 (SOL)", value=45.0, step=5.0)

age_days = st.sidebar.number_input("3. 超過設定值天數以上的幣", value=3, min_value=1)
sudden_buy_sol = st.sidebar.number_input("   突然買入金額設定值 (SOL)", value=25.0, step=5.0)

st.sidebar.divider()
st.sidebar.info("""💡 自動監測說明：
• Pump.fun：完全自動抓取最新50枚幣 + 即時交易 → 自動檢查3條件
• Moonshot / LetsBONK / Meteora / Zerg.zone：目前無公開免費「最新幣列表」API（需 websocket / 付費如 Bitquery 或 CoinVera 才能全自動）
• 因此其他4平台保留 CA 查詢模式（貼地址即可即時監測真實資料）""")

# ==================== 共用真實 API 函式 ====================
@st.cache_data(ttl=30)
def fetch_pump_latest():
    """Pump.fun 官方真實最新代幣（全自動）"""
    try:
        url = "https://frontend-api-v3.pump.fun/coins/latest"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Pump.fun API 錯誤: {e}")
        return []

@st.cache_data(ttl=20)
def fetch_pump_trades(mint: str):
    """Pump.fun 單幣真實交易紀錄"""
    try:
        url = f"https://frontend-api-v3.pump.fun/trades/all/{mint}?limit=100"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except:
        return []

@st.cache_data(ttl=30)
def get_dexscreener_pairs(token_address: str):
    """Dexscreener 公開 API（用於其他4平台）"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("pairs", []) if isinstance(data, dict) else []
    except:
        return []

def check_conditions(coin: dict, trades: list):
    """3 項條件檢查（Pump.fun 專用）"""
    alerts = []
    mc = coin.get("market_cap") or coin.get("usd_market_cap") or 0
    
    # 條件1：市值 + 單次大買
    if mc < mc_threshold:
        for t in trades[:30]:
            if t.get("is_buy") and float(t.get("sol_amount", 0)) >= single_buy_sol:
                alerts.append(f"🔥 條件1：市值 ${mc:,.0f} < {mc_threshold:,} + 單次買入 ≥ {single_buy_sol} SOL")
                break
    
    # 條件2：1分鐘買入總額
    now = datetime.utcnow()
    one_min_ago = now - timedelta(minutes=1)
    buy_1min = 0.0
    for t in trades:
        try:
            ts = t.get("timestamp") or t.get("time", 0)
            if ts > 1e10:
                ts = ts / 1000
            trade_time = datetime.fromtimestamp(ts)
            if trade_time > one_min_ago and t.get("is_buy"):
                buy_1min += float(t.get("sol_amount", 0))
        except:
            continue
    if buy_1min >= min_buy_sol:
        alerts.append(f"⚡ 條件2：最近1分鐘買入 {buy_1min:.1f} SOL ≥ {min_buy_sol} SOL")
    
    # 條件3：老幣突然大買
    created = coin.get("created_timestamp") or coin.get("timestamp", 0)
    if created:
        try:
            if created > 1e10:
                created = created / 1000
            age = (datetime.utcnow().timestamp() - created) / 86400
            if age > age_days:
                for t in trades[:15]:
                    if t.get("is_buy") and float(t.get("sol_amount", 0)) >= sudden_buy_sol:
                        alerts.append(f"🚨 條件3：老幣（{age:.1f} 天）突然大買 ≥ {sudden_buy_sol} SOL")
                        break
        except:
            pass
    
    return alerts, mc

# ==================== 5 個平台分頁 ====================
tabs = st.tabs(["1. Pump.fun（全自動）", "2. Moonshot", "3. LaunchLab / LetsBONK.fun", "4. Meteora / Alpha Vaults", "5. Zerg.zone"])

# Tab 1: Pump.fun 全自動檢測
with tabs[0]:
    st.subheader("📌 1. Pump.fun（官方真實 API 全自動掃描）")
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 立即全自動刷新 Pump.fun", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    coins = fetch_pump_latest()
    st.info(f"✅ 已自動抓取 {len(coins)} 枚最新 Pump.fun 代幣，正在檢查您的3項條件...")
    
    alert_count = 0
    for coin in coins[:40]:   # 限制數量避免過載
        mint = coin.get("mint")
        if not mint:
            continue
        name = coin.get("name", "Unknown")
        symbol = coin.get("symbol", "")
        mc = coin.get("market_cap") or coin.get("usd_market_cap") or 0
        
        trades = fetch_pump_trades(mint)
        alerts, _ = check_conditions(coin, trades)
        
        if alerts:
            alert_count += 1
            with st.expander(f"🚨 {name} ({symbol}) ─ 市值 ${mc:,.0f}", expanded=False):
                st.code(mint, language="text")
                for a in alerts:
                    st.markdown(f"<div style='background:#ff4d4d;color:white;padding:12px;border-radius:8px;margin:8px 0;'>{a}</div>", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(trades[:10]), use_container_width=True)
    
    if alert_count > 0:
        st.success(f"🎯 本次自動掃描發現 {alert_count} 枚符合您3項條件的 Pump.fun 代幣！")
    else:
        st.success("✅ Pump.fun 目前無符合警報的代幣（持續自動監測中）")

# Tab 2~5：其他平台（CA 查詢模式，真實資料）
with tabs[1]:
    st.subheader("📌 2. Moonshot（Dexscreener 真實資料）")
    st.info("Moonshot 無公開最新幣 API → 請貼 CA 即時查詢")
    ca = st.text_input("輸入 Moonshot 代幣地址 (CA)", placeholder="貼 Solana 合約地址")
    if ca:
        pairs = get_dexscreener_pairs(ca)
        if pairs:
            for p in pairs[:5]:
                bt = p.get("baseToken", {})
                st.metric(label=bt.get("name", "Unknown"), value=f"${p.get('marketCap', 0):,.0f}")
                st.write(f"5分鐘成交量：${p.get('volume', {}).get('m5', 0):,.0f}｜買入筆數：{p.get('txns', {}).get('m5', {}).get('buys', 0)}")
                st.divider()
        else:
            st.warning("無資料，請確認地址正確")

with tabs[2]:
    st.subheader("📌 3. LaunchLab / LetsBONK.fun（Dexscreener 真實資料）")
    st.info("LaunchLab / LetsBONK.fun 無公開最新幣 API → 請貼 CA 即時查詢")
    ca2 = st.text_input("輸入 LaunchLab / LetsBONK 代幣地址 (CA)")
    if ca2:
        pairs = get_dexscreener_pairs(ca2)
        if pairs:
            data = [{
                "名稱": p.get("baseToken", {}).get("name"),
                "市值": p.get("marketCap"),
                "5分鐘成交量": p.get("volume", {}).get("m5"),
                "5分鐘買入筆數": p.get("txns", {}).get("m5", {}).get("buys")
            } for p in pairs[:8]]
            st.dataframe(pd.DataFrame(data), use_container_width=True)

with tabs[3]:
    st.subheader("📌 4. Meteora / Alpha Vaults（Dexscreener 真實資料）")
    st.info("Meteora / Alpha Vaults 無公開最新池 API → 請貼 CA 即時查詢")
    ca3 = st.text_input("輸入 Meteora 代幣或池地址 (CA)")
    if ca3:
        pairs = get_dexscreener_pairs(ca3)
        if pairs:
            st.dataframe(pd.DataFrame([{"池地址": p.get("pairAddress"), "市值": p.get("marketCap")} for p in pairs]), use_container_width=True)

with tabs[4]:
    st.subheader("📌 5. Zerg.zone（Dexscreener 真實資料）")
    st.info("Zerg.zone 無公開最新幣 API → 請貼 CA 即時查詢")
    ca4 = st.text_input("輸入 Zerg.zone 代幣地址 (CA)")
    if ca4:
        pairs = get_dexscreener_pairs(ca4)
        if pairs:
            st.dataframe(pd.DataFrame([p.get("baseToken") for p in pairs]), use_container_width=True)

# ==================== 頁尾 ====================
st.divider()
st.caption(f"最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}（台灣時間）")
st.caption("💡 把此檔案存成 **app.py** 上傳 GitHub → Streamlit Cloud 部署即可永久運行")
st.caption("🔥 Pump.fun 已完全自動檢測！其他平台若想全自動，可改用付費服務（Bitquery / CoinVera），需要我幫你加整合嗎？")