from flask import Flask, render_template_string
import random
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# --- 模擬監測數據 (對接 API 時替換此處) ---
def get_mock_data():
    platforms = ["Pump.fun", "Moonshot", "LaunchLab", "Meteora", "Zerg.zone"]
    data_list = []
    for p in platforms:
        mcap = random.randint(10000, 200000)
        buy_1m = round(random.uniform(0, 50), 2)
        age_days = random.randint(0, 10)
        
        # 判斷是否觸發條件
        status = "Normal"
        if mcap < 50000 and buy_1m > 10: status = "🔥 低市大買"
        elif buy_1m > 30: status = "⚡ 爆量噴發"
        elif age_days > 3 and buy_1m > 20: status = "💎 老幣翻紅"
        
        data_list.append({
            "platform": p,
            "symbol": f"TOKEN-{random.randint(100,999)}",
            "mcap": f"${mcap:,}",
            "buy_1m": f"{buy_1m} SOL",
            "age": f"{age_days}天",
            "status": status
        })
    return data_list

# --- HTML 介面設計 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Solana 監測儀表板</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: white; padding: 10px; }
        .card { background: #1e1e1e; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #00ffa3; }
        .alert { border-left: 5px solid #ff3e3e; background: #2d1a1a; }
        .header { display: flex; justify-content: space-between; align-items: center; }
        .tag { background: #00ffa3; color: black; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .mcap { color: #888; font-size: 14px; }
        .buy { color: #00ffa3; font-weight: bold; }
    </style>
    <script>
        setTimeout(function(){ location.reload(); }, 3000); // 每3秒自動刷新
    </script>
</head>
<body>
    <h2>🚀 Sol 鏈即時監控</h2>
    <p style="font-size: 12px; color: #666;">更新時間: {{ time }}</p>
    <hr color="#333">
    {% for item in data %}
    <div class="card {{ 'alert' if 'Normal' not in item.status else '' }}">
        <div class="header">
            <span><strong>{{ item.symbol }}</strong> <small>({{ item.platform }})</small></span>
            <span class="tag">{{ item.status }}</span>
        </div>
        <div style="margin-top: 10px;">
            <span class="mcap">市值: {{ item.mcap }}</span> | 
            <span class="buy">1分買入: {{ item.buy_1m }}</span>
        </div>
        <div style="font-size: 12px; color: #555; margin-top: 5px;">天數: {{ item.age }}</div>
    </div>
    {% endfor %}
</body>
</html>
"""

@app.route('/')
def index():
    now = datetime.now().strftime("%H:%M:%S")
    return render_template_string(HTML_TEMPLATE, data=get_mock_data(), time=now)

if __name__ == '__main__':
    # 手機運行建議使用 0.0.0.0 方便同網域查看
    app.run(debug=True, host='0.0.0.0', port=5000)
