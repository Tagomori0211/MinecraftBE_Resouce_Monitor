import time
import re
import datetime
import sys
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from prometheus_client import start_http_server, Gauge

# ---------------------------------------------------------
# 1. Prometheus Metrics Definition
# ---------------------------------------------------------
# ユーザーのオンライン状態 (1: Online, 0: Offline)
PLAYER_ONLINE_STATUS = Gauge(
    'minecraft_player_online_status',
    'Current online status of the player (1 for online, 0 for offline)',
    ['user_name']
)

# ---------------------------------------------------------
# 2. Log Parsing Logic
# ---------------------------------------------------------
def parse_log_line(line):
    """
    ログ行を解析し、イベントタイプとユーザー名を返す
    Return: (event_type, user_name) or (None, None)
    event_type: 'LOGIN', 'LOGOUT'
    """
    # Bedrock Server Log Format Examples:
    # [INFO] Player Tagomori connected
    # [INFO] Player Tagomori disconnected
    
    # 正規表現パターン
    # Note: サーバーのバージョンによって微妙に異なる場合があるため、汎用的に記述
    login_pattern = r"Player (.+) connected"
    logout_pattern = r"Player (.+) disconnected"

    # ログイン検知
    match_login = re.search(login_pattern, line)
    if match_login:
        return 'LOGIN', match_login.group(1)

    # ログアウト検知
    match_logout = re.search(logout_pattern, line)
    if match_logout:
        return 'LOGOUT', match_logout.group(1)

    return None, None

# ---------------------------------------------------------
# 3. K8s Log Watcher Logic
# ---------------------------------------------------------
def get_minecraft_pod(v1, namespace, label_selector):
    """
    指定されたラベルを持つPodを探して返す
    """
    try:
        pods = v1.list_namespaced_pod(namespace, label_selector=label_selector)
        for pod in pods.items:
            # Running状態のPodを優先する
            if pod.status.phase == "Running":
                return pod.metadata.name
    except ApiException as e:
        print(f"⚠️ Error listing pods: {e}")
    return None

def watch_logs():
    # K8s設定読み込み (In-Cluster Config)
    try:
        config.load_incluster_config()
    except Exception as e:
        print(f"❌ Failed to load in-cluster config: {e}")
        print("Note: This script must run inside a K8s Pod with ServiceAccount.")
        sys.exit(1)

    v1 = client.CoreV1Api()
    w = watch.Watch()
    
    NAMESPACE = "default"
    POD_LABEL_SELECTOR = "app=minecraft-bedrock"

    print(f"🚀 Minecraft Log Exporter started.")
    print(f"📡 Prometheus metrics server running on port 8000")

    # メインループ (再接続用)
    while True:
        pod_name = get_minecraft_pod(v1, NAMESPACE, POD_LABEL_SELECTOR)

        if not pod_name:
            print("⏳ Minecraft Pod not found. Retrying in 10s...")
            time.sleep(10)
            continue

        print(f"TARGET POD FOUND: {pod_name}. Starting log stream...")

        try:
            # ストリーミング開始 (follow=True)
            # _preload_content=False にすることで、行ごとに処理できるようにするらしいが
            # watch.streamを使うのが一般的
            for line in w.stream(v1.read_namespaced_pod_log, name=pod_name, namespace=NAMESPACE, follow=True):
                log_line = line.strip()
                
                # 解析
                event, user = parse_log_line(log_line)
                
                if event == 'LOGIN':
                    print(f"✅ LOGIN: {user}")
                    # Prometheusメトリクス更新
                    PLAYER_ONLINE_STATUS.labels(user_name=user).set(1)
                    
                elif event == 'LOGOUT':
                    print(f"🚪 LOGOUT: {user}")
                    # Prometheusメトリクス更新
                    PLAYER_ONLINE_STATUS.labels(user_name=user).set(0)

        except Exception as e:
            print(f"⚠️ Log stream interrupted: {e}")
            print("🔄 Reconnecting...")
            time.sleep(5)
            # ループ先頭に戻り、再度Podを探すところから始める

# ---------------------------------------------------------
# 4. Main Execution
# ---------------------------------------------------------
if __name__ == '__main__':
    # Prometheus HTTPサーバー起動 (バックグラウンド)
    start_http_server(8000)
    
    # ログ監視開始 (ブロッキング)
    watch_logs()