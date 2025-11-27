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
    # cAdvisorはK8sの長いコンテナ名(k8s_minecraft_...)で認識するため、
    # 正規表現(name=~".*minecraft.*")で「名前にminecraftを含むコンテナ」を抽出する
    cpu_query = 'sum(rate(container_cpu_usage_seconds_total{name=~".*minecraft.*"}[1m])) * 100'
    cpu_res = query_prometheus(cpu_query)

    # メモリ使用量 (Bytes)
    # cacheを含まない working_set_bytes を使用するのが一般的
    mem_query = 'sum(container_memory_working_set_bytes{name=~".*minecraft.*"})'
    mem_res = query_prometheus(mem_query)

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
        # 小数点1桁まで
        cpu_usage = f"{val:.1f}%"
    
    # メモリ使用量の整形 (Bytes -> MB)
    if mem_res:
        val = float(mem_res['value'][1])
        # 1MB = 1024 * 1024 bytes
        mb_val = val / 1048576
        mem_usage = f"{mb_val:.0f} MB"

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
            "memory_usage": mem_usage
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)