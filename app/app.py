from flask import Flask, jsonify
import requests
import os

app = Flask(__name__)

# PrometheusのURL (Docker Compose内でのサービス名でアクセス)
# ポートは9090番が標準
PROMETHEUS_URL = "http://prometheus:9090"

def query_prometheus(query):
    """
    PrometheusにPromQLクエリを投げて結果を返す関数
    """
    try:
        # PrometheusのAPIエンドポイント /api/v1/query にGETリクエストを送る
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query})
        data = response.json()
        
        # データが正常に返ってきているか確認
        if data["status"] == "success" and len(data["data"]["result"]) > 0:
            # 最新の値を返す (valueは [timestamp, "値"] の形式なので2番目を取得)
            return data["data"]["result"][0]["value"][1]
        return None
    except Exception as e:
        print(f"Error querying Prometheus: {e}")
        return None

@app.route('/')
def hello():
    # ヘルスチェック用 (Nginxがここを見て生存確認したりする)
    return jsonify({
        "message": "Minecraft Monitor API is Running!",
        "status": "OK"
    })

@app.route('/api/status')
def get_status():
    """
    フロントエンドが叩くAPI。
    Prometheusから各メトリクスを集めてJSONで返す。
    """
    
    # 1. オンライン人数 (mc-monitorのメトリクス)
    players_online = query_prometheus('mc_bedrock_players_online')
    
    # 2. 最大接続人数
    players_max = query_prometheus('mc_bedrock_players_max')
    
    # 3. バージョン情報 
    # (mc_bedrock_version というメトリクスのラベルに含まれることが多い。
    #  数値ではない情報を取るのは少し工夫がいるけど、まずは簡易的に取得)
    # ※もし取得できなければ "Unknown" にする
    version_data = "Unknown" 
    # TODO: バージョン取得ロジックはExporterの仕様に合わせて後で調整が必要かも

    # 4. CPU/メモリ使用率
    # K3s環境なので、Podごとのリソースは cAdvisor (kubelet) 経由で取れるはず。
    # ここでは仮のクエリを入れるけど、Prometheusの設定によっては取れない場合がある。
    # その場合は "N/A" を返すようにするね。
    cpu_usage = query_prometheus('sum(rate(container_cpu_usage_seconds_total{image!="", container="minecraft"}[1m])) * 100')
    mem_usage = query_prometheus('sum(container_memory_working_set_bytes{image!="", container="minecraft"}) / 1024 / 1024') # MB換算

    # データの整形
    status_data = {
        "status": "Online" if players_online is not None else "Offline",
        "players": {
            "online": int(players_online) if players_online else 0,
            "max": int(players_max) if players_max else 0
        },
        "server": {
            "version": version_data,
            "cpu_usage": f"{float(cpu_usage):.1f}%" if cpu_usage else "N/A",
            "memory_usage": f"{float(mem_usage):.0f} MB" if mem_usage else "N/A"
        }
    }

    return jsonify(status_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)