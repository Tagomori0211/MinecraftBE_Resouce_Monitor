from flask import Flask, jsonify
import requests
import os

app = Flask(__name__)

# PrometheusのURL
# Docker Compose内のサービス名でアクセス
PROMETHEUS_URL = "http://prometheus:9090"

def query_prometheus(query):
    """
    Prometheusからデータを取得し、生データ(result[0])を返す
    """
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query})
        data = response.json()
        
        # データが正常、かつ結果が空でない場合
        if data["status"] == "success" and len(data["data"]["result"]) > 0:
            return data["data"]["result"][0]
        return None
    except Exception as e:
        print(f"Error querying Prometheus: {e}")
        return None

@app.route('/')
def hello():
    # ヘルスチェック用
    return jsonify({"message": "Minecraft Monitor API OK", "status": "Running"})


@app.route('/api/status')
def get_status():
    # -------------------------------------------------
    # 1. ゲーム内情報の取得 (Exporter)
    # -------------------------------------------------
    # オンライン人数
    online_res = query_prometheus('minecraft_status_players_online_count')
    # 最大人数
    max_res = query_prometheus('minecraft_status_players_max_count')
    # サーバー健全性 (ここにバージョン情報が含まれる)
    healthy_res = query_prometheus('minecraft_status_healthy')

    # -------------------------------------------------
    # 2. システム負荷情報の取得 (cAdvisor)
    # -------------------------------------------------
    # CPU使用率 (%)
    # 生データに合わせてラベル名を修正
    cpu_query = 'sum(rate(container_cpu_usage_seconds_total{container_label_io_kubernetes_container_name="minecraft"}[1m])) * 100'
    cpu_res = query_prometheus(cpu_query)

    # メモリ使用量 (Bytes)
    # 生データに合わせてラベル名を修正
    mem_query = 'sum(container_memory_working_set_bytes{container_label_io_kubernetes_container_name="minecraft"})'
    mem_res = query_prometheus(mem_query)

    # 【追加】メモリ上限 (Bytes)
    # container_spec_memory_limit_bytes を取得
    limit_query = 'sum(container_spec_memory_limit_bytes{container_label_io_kubernetes_container_name="minecraft"})'
    limit_res = query_prometheus(limit_query)


    # -------------------------------------------------
    # 3. データの整形
    # -------------------------------------------------
    # デフォルト値
    players_online = 0
    players_max = 0
    version = "Unknown"
    status = "Offline"
    cpu_usage = "N/A"
    mem_usage = "N/A"

    # ステータス判定 (人数が取れていればOnlineとみなす)
    if online_res:
        status = "Online"
        players_online = int(online_res['value'][1])
    

    if max_res:
        players_max = int(max_res['value'][1])

    # バージョン情報の抽出 (ラベル: server_version)
    if healthy_res and 'metric' in healthy_res:
        version = healthy_res['metric'].get('server_version', 'Unknown')

    # CPU使用率の整形
    if cpu_res:
        val = float(cpu_res['value'][1])
        cpu_usage = f"{val:.1f}%"
    
    # メモリ使用量の処理 (計算ロジック強化！)
    if mem_res:
        mem_val = float(mem_res['value'][1])
        # MB表記 (1MB = 1048576 bytes)
        mem_usage_str = f"{mem_val / 1048576:.0f} MB"
        
    if limit_res:
        limit_val = float(limit_res['value'][1])
        # 上限はGB表記の方が見やすいかも (1GB = 1073741824 bytes)
        # 4GiBなら "4.0 GB" と表示される
        mem_limit_str = f"{limit_val / 1073741824:.1f} GB"

    # パーセンテージ計算
    if mem_val > 0 and limit_val > 0:
        percent = (mem_val / limit_val) * 100
        mem_percent_str = f"({percent:.1f}%)"

    # -------------------------------------------------
    # 4. レスポンス (JSON)
    # -------------------------------------------------
    return jsonify({
        "status": status,
        "players": {
            "online": players_online,
            "max": players_max
        },
        "server": {
            "version": version,
            "cpu_usage": cpu_usage,
            # メモリ情報をリッチにする
            "memory_usage": mem_usage_str,
            "memory_limit": mem_limit_str,
            "memory_percent": mem_percent_str
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)