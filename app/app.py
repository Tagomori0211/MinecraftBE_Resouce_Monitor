from flask import Flask, jsonify
import requests
import os

app = Flask(__name__)

# PrometheusのURL定義 (Docker Compose内のサービス名解決)
PROMETHEUS_URL = "http://prometheus:9090"

def query_prometheus(query):
    """
    Prometheus APIにクエリを投げ、結果の最初の要素を返すヘルパー関数
    Args:
        query (str): PromQLクエリ文字列
    Returns:
        dict or None: 取得したメトリクスデータ、失敗時はNone
    """
    try:
        # PrometheusのAPIエンドポイントへGETリクエスト
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query})
        data = response.json()
        # ステータスがsuccessかつデータが存在する場合のみ返す
        if data["status"] == "success" and len(data["data"]["result"]) > 0:
            return data["data"]["result"][0]
        return None
    except Exception as e:
        print(f"Error querying Prometheus: {e}")
        return None

@app.route('/')
def hello():
    return jsonify({"message": "Minecraft Monitor API OK", "status": "Running"})

# 【追加】デバッグ用エンドポイント
# ブラウザで /api/debug にアクセスすると、Prometheusからの生データが見れます
@app.route('/api/debug')
def debug_prometheus():
    results = {}
    queries = [
        'minecraft_status_players_online_count',
        'minecraft_status_players_max_count',
        'minecraft_status_healthy',
        'minecraft_status_response_time_seconds',
        'minecraft_player_online_status' # log-watcherの方も確認
    ]
    
    for q in queries:
        try:
            res = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': q})
            results[q] = res.json()
        except Exception as e:
            results[q] = str(e)
            
    return jsonify(results)

@app.route('/api/status')
def get_status():
    # -------------------------------------------------
    # 1. Prometheusからメトリクス収集 (mc-monitor由来を優先)
    # -------------------------------------------------
    
    # [A] オンライン人数 (mc-monitor: Port 30001)
    online_res = query_prometheus('minecraft_status_players_online_count')
    
    # [B] 最大人数 (mc-monitor)
    max_res = query_prometheus('minecraft_status_players_max_count')
    
    # [C] サーバーの健全性とバージョン (mc-monitor)
    healthy_res = query_prometheus('minecraft_status_healthy')
    
    # [D] 応答速度 Ping (mc-monitor)
    ping_res = query_prometheus('minecraft_status_response_time_seconds')

    # [E] リソース情報 (cAdvisor: Port 30002)
    cpu_query = 'sum(rate(container_cpu_usage_seconds_total{container_label_io_kubernetes_container_name="minecraft"}[1m])) * 100'
    cpu_res = query_prometheus(cpu_query)

    mem_query = 'sum(container_memory_working_set_bytes{container_label_io_kubernetes_container_name="minecraft"})'
    mem_res = query_prometheus(mem_query)

    limit_query = 'sum(container_spec_memory_limit_bytes{container_label_io_kubernetes_container_name="minecraft"})'
    limit_res = query_prometheus(limit_query)

    # -------------------------------------------------
    # 2. データの整形
    # -------------------------------------------------
    players_online = 0
    players_max = 0
    version = "Unknown"
    latency = 0
    status_text = "Offline"
    
    cpu_usage = "N/A"
    mem_usage_str = "N/A"
    mem_limit_str = "N/A"
    mem_percent_str = ""

    # --- ステータス判定ロジック ---
    # minecraft_status_healthy が 1 であればオンライン
    is_online = False
    
    if healthy_res:
        val = int(float(healthy_res['value'][1]))
        if val == 1:
            is_online = True
            status_text = "Online"
            
            # バージョン情報取得
            if 'metric' in healthy_res:
                version = healthy_res['metric'].get('version', 'Unknown') 
                if version == 'Unknown':
                    version = healthy_res['metric'].get('server_version', 'Unknown')

    # オンライン時の追加データ取得処理
    if is_online:
        if online_res:
            players_online = int(float(online_res['value'][1]))
        
        if max_res:
            players_max = int(float(max_res['value'][1]))
            
        if ping_res:
            val = float(ping_res['value'][1])
            latency = int(val * 1000)

    # --- リソース整形 ---
    if cpu_res:
        val = float(cpu_res['value'][1])
        cpu_usage = f"{val:.1f}%"
    
    if mem_res:
        mem_val = float(mem_res['value'][1])
        mem_usage_str = f"{mem_val / 1048576:.0f} MB"
        
    if limit_res:
        limit_val = float(limit_res['value'][1])
        mem_limit_str = f"{limit_val / 1073741824:.1f} GB"

    if mem_res and limit_res:
        m_val = float(mem_res['value'][1])
        l_val = float(limit_res['value'][1])
        if l_val > 0:
            percent = (m_val / l_val) * 100
            mem_percent_str = f"({percent:.1f}%)"

    return jsonify({
        "status": status_text,
        "players": {
            "online": players_online,
            "max": players_max
        },
        "server": {
            "version": version,
            "latency": latency,
            "cpu_usage": cpu_usage,
            "memory_usage": mem_usage_str,
            "memory_limit": mem_limit_str,
            "memory_percent": mem_percent_str
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)