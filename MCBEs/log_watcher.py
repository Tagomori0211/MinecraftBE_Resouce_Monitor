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
# Grafanaで「誰がいるか」を時系列で見るために使用します
PLAYER_ONLINE_STATUS = Gauge(
    'minecraft_player_online_status',
    'Current online status of the player (1 for online, 0 for offline)',
    ['user_name']
)

# ---------------------------------------------------------
# 2. Log Parsing Logic (Updated for Real Log Format)
# ---------------------------------------------------------
def parse_log_line(line):
    """
    ログ行を解析し、イベントタイプとユーザー名を返す
    Target Log Format:
      [INFO] Player connected: Shinari5295, xuid: 2533...
      [INFO] Player disconnected: Shinari5295, xuid: 2533...
    """
    
    # 正規表現の解説:
    # r"Player connected:\s*([^,]+),"
    # \s* : コロンの後のスペース（0個以上）にマッチ
    # ([^,]+) : カンマ以外の文字が続く限りキャプチャ（これがユーザー名になります）
    # ,       : 名前の後ろにあるカンマで区切る
    login_pattern = r"Player connected:\s*([^,]+),"
    logout_pattern = r"Player disconnected:\s*([^,]+),"

    # ログイン検知
    match_login = re.search(login_pattern, line)
    if match_login:
        # group(1)には "Shinari5295" が入ります
        return 'LOGIN', match_login.group(1).strip()

    # ログアウト検知
    match_logout = re.search(logout_pattern, line)
    if match_logout:
        return 'LOGOUT', match_logout.group(1).strip()

    return None, None

# ---------------------------------------------------------
# 3. K8s Log Watcher Logic
# ---------------------------------------------------------
def get_minecraft_pod(v1, namespace, label_selector):
    """
    指定されたラベルを持つPodを探して返す
    Podが再起動しても追従できるように動的に取得します
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
    # K8s設定読み込み (In-Cluster Config: Pod内部からAPIを叩くための設定)
    try:
        config.load_incluster_config()
    except Exception as e:
        print(f"❌ Failed to load in-cluster config: {e}")
        sys.exit(1)

    v1 = client.CoreV1Api()
    w = watch.Watch()
    
    NAMESPACE = "default"
    # Deploymentのラベルと一致させること
    POD_LABEL_SELECTOR = "app=minecraft-bedrock"

    print(f"🚀 Minecraft Log Exporter started.")
    print(f"📡 Prometheus metrics server running on port 8000")

    # メインループ (再接続・Pod再起動時の追従用)
    while True:
        pod_name = get_minecraft_pod(v1, NAMESPACE, POD_LABEL_SELECTOR)

        if not pod_name:
            print("⏳ Minecraft Pod not found. Retrying in 10s...")
            time.sleep(10)
            continue

        print(f"TARGET POD FOUND: {pod_name}. Starting log stream...")

        try:
            # ストリーミング開始
            # container="minecraft" を指定することで、Sidecarではなくゲームサーバーのログを取得
            for line in w.stream(v1.read_namespaced_pod_log, 
                               name=pod_name, 
                               namespace=NAMESPACE, 
                               container="minecraft", 
                               follow=True):
                
                log_line = line.strip()
                
                # 解析実行
                event, user = parse_log_line(log_line)
                
                if event == 'LOGIN':
                    print(f"✅ LOGIN DETECTED: {user}")
                    # Prometheusメトリクスを 1 (Online) にセット
                    PLAYER_ONLINE_STATUS.labels(user_name=user).set(1)
                    
                elif event == 'LOGOUT':
                    print(f"🚪 LOGOUT DETECTED: {user}")
                    # Prometheusメトリクスを 0 (Offline) にセット
                    PLAYER_ONLINE_STATUS.labels(user_name=user).set(0)

        except Exception as e:
            # ログストリームが切れた場合（Pod再起動など）はループ先頭に戻り再取得
            print(f"⚠️ Log stream interrupted: {e}")
            print("🔄 Reconnecting...")
            time.sleep(5)

# ---------------------------------------------------------
# 4. Main Execution
# ---------------------------------------------------------
if __name__ == '__main__':
    # Prometheus HTTPサーバー起動 (バックグラウンド)
    # ここに外部(Prometheus)がアクセスしてメトリクスを持っていきます
    start_http_server(8000)
    
    # ログ監視開始 (ブロッキング処理)
    watch_logs()