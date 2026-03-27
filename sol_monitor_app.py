import time
import requests
import json
from datetime import datetime, timedelta

# --- 配置區 ---
SETTINGS = {
    "MARKET_CAP_LIMIT": 50000,    # 1. 市值設定值 (USD)
    "BUY_AMOUNT_LIMIT": 10,       # 1. 買入金額設定值 (SOL)
    "MIN_VOLUME_PER_MIN": 5,      # 2. 每一分鐘內買入金額設定值 (SOL)
    "OLD_TOKEN_DAYS": 3,          # 3. 超過設定值天數
    "OLD_TOKEN_SURGE": 20         # 3. 老幣突然買入金額設定值 (SOL)
}

PLATFORMS = [
    "Pump.fun", "Moonshot", "LaunchLab/LetsBONK", "Meteora/AlphaVaults", "Zerg.zone"
]

# 模擬 API 請求與緩存（實際建議接各平台 WebSocket）
token_cache = {}

class SolMonitor:
    def __init__(self, config):
        self.config = config

    def check_market_cap_buy(self, mcap, buy_vol):
        """條件 1: 市值與買入金額判斷"""
        return mcap < self.config["MARKET_CAP_LIMIT"] and buy_vol >= self.config["BUY_AMOUNT_LIMIT"]

    def check_velocity(self, vol_1min):
        """條件 2: 每一分鐘買入量"""
        return vol_1min >= self.config["MIN_VOLUME_PER_MIN"]

    def check_old_token_surge(self, launch_date, current_buy_vol):
        """條件 3: 老幣異常活動"""
        age = (datetime.now() - launch_date).days
        return age >= self.config["OLD_TOKEN_DAYS"] and current_buy_vol >= self.config["OLD_TOKEN_SURGE"]

    def fetch_data(self, platform):
        # 這裡應替換為各平台的實體 API 呼叫 (如 DexScreener API 或 Helius RPC)
        # 此處僅回傳模擬數據用於展示邏輯
        return {
            "symbol": "SOL_MEME",
            "mcap": 45000,
            "buy_1m": 8,
            "launch_time": datetime.now() - timedelta(days=5),
            "recent_buy": 25
        }

    def run(self):
        print(f"--- 🚀 啟動監測: {', '.join(PLATFORMS)} ---")
        while True:
            for platform in PLATFORMS:
                data = self.fetch_data(platform)
                
                # 執行篩選邏輯
                c1 = self.check_market_cap_buy(data['mcap'], data['buy_1m'])
                c2 = self.check_velocity(data['buy_1m'])
                c3 = self.check_old_token_surge(data['launch_time'], data['recent_buy'])

                if c1 or c2 or c3:
                    self.alert(platform, data, c1, c2, c3)
            
            time.sleep(10) # 掃描頻率

    def alert(self, platform, data, c1, c2, c3):
        tag = ""
        if c1: tag += "[低市值爆買] "
        if c2: tag += "[高頻買入] "
        if c3: tag += "[老幣突襲] "
        
        print(f"🔔 {tag}\n平台: {platform} | 代幣: {data['symbol']}\n市值: ${data['mcap']} | 買入量: {data['recent_buy']} SOL\n" + "-"*30)

if __name__ == "__main__":
    monitor = SolMonitor(SETTINGS)
    monitor.run()
