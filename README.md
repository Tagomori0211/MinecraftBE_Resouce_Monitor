# **🏭 Hybrid Infrastructure & Observability Platform**

## **Secure On-Premise Operations with Cloud-Native Agility**

### **📖プロジェクト概要 (Executive Summary)**

本プロジェクトは、製造業や重要インフラにおける\*\*「IT/OT融合（IT-OT Convergence）」\*\*を想定した、技術実証ポートフォリオです。

**Minecraft Bedrock Edition (BE)** サーバーを「24時間365日稼働が求められるミッションクリティカルなアプリケーション」と見立て、以下の3つの運用課題を解決するプラットフォームを構築しています。

1. **機密データの保護:** ワールドデータ（現場データ）を閉鎖網内のオンプレミス環境で完結させ、外部流出を防止する。  
2. **運用のコード化 (IaC):** **TAKパイプライン (Terraform \> Ansible \> Kubernetes)** により、インフラ構築からアプリ展開までを完全自動化し、属人化を排除する。  
3. **可視化と予知保全:** サーバー内部の資源データ（チェストの中身やリソース使用率）を解析し、システムの健全性を可視化する。

**ターゲット:** 製造業DX、工場内エッジコンピューティング、セキュアなハイブリッドクラウド環境の構築

### **🏗 アーキテクチャ (System Architecture)**

セキュリティ要件の高い「オンプレミス閉鎖網（Edge）」と、開発効率の高い「パブリッククラウド（Cloud）」を組み合わせたハイブリッド構成を採用しています。

#### **🔄 The "TAK" Pipeline Strategy**

インフラの再現性と耐障害性(Disaster Recovery)を担保するため、以下の3段階のIaCパイプラインを実装しています。

```mermaid
graph TD
    subgraph "Phase 1: Provisioning (Infrastructure)"
        TF[Terraform] -->|Proxmox API| PVE[Proxmox VE Host]
        PVE -->|Create| VM1[VM: DevOps Core]
        PVE -->|Create| VM2[VM: App Server]
        style TF fill:#7B42BC,stroke:#fff,color:#fff
    end

    subgraph "Phase 2: Configuration (OS/Middleware)"
        ANS[Ansible] -->|SSH Config| VM1
        ANS -->|SSH Config| VM2
        VM1 -->|Install| Docker[Docker / Runners]
        VM2 -->|Install| K3s[K3s Cluster]
        style ANS fill:#EE0000,stroke:#fff,color:#fff
    end

    subgraph "Phase 3: Orchestration (Application)"
        K8S[Kubernetes Manifests] -->|Apply| K3s
        K3s -->|Deploy| POD_MC[Minecraft App]
        K3s -->|Deploy| POD_EXP[Exporter / Sidecars]
        style K8S fill:#326CE5,stroke:#fff,color:#fff
    end

    'TF --> ANS --> K8S'
```

#### **🛡️ ハイブリッド・データセキュリティ設計**

製造業の「図面や製造データは外に出せないが、開発は効率化したい」というニーズに対し、**Code（ロジック）とData（機密情報）を物理的に分離**する設計を行っています。

* **Public Cloud (Google Cloud / GitHub):**  
  * ソースコード、IaC定義ファイル、ドキュメント管理。  
  * 開発環境としてGoogle Cloud Workstationsを活用。  
* **Private On-Premise (Proxmox @ Home Lab):**  
  * **Data Sovereignty (データ主権):** 実際のワールドデータやユーザーログは、外部レジストリやクラウドストレージに出さず、ローカルのPostgreSQLとPV(Persistent Volume)のみで管理。  
  * **Edge Computing:** データ解析（ETL処理）をオンプレミス側で実行し、処理済みの軽量なメトリクスのみを可視化するアーキテクチャ。

### **🛠 技術スタック (Tech Stack)**

| Category | Technology | Usage & DX Relevance |
| :---- | :---- | :---- |
| **Infrastructure** | **Proxmox VE** | 仮想化基盤。高可用性(HA)やバックアップ運用を想定し、ベアメタルサーバー(Fujitsu PRIMERGY / Ryzen Server)上で運用。 |
| **IaC (Provisioning)** | **Terraform** | terraform/proxmox。VMのスペック定義、ネットワーク設定のコード化。**DR（災害復旧）時の即時復旧**を実現。 |
| **IaC (Config)** | **Ansible** | OS設定、セキュリティパッチ適用、K3sノード構築の自動化。多数のIoTデバイス管理への応用を想定。 |
| **Orchestration** | **Kubernetes (K3s)** | アプリケーションのコンテナ管理。自己修復機能(Self-healing)による可用性向上。 |
| **CI/CD** | **GitHub Actions** | Self-hosted Runnerを用いた、閉鎖網へのデプロイパイプライン。 |
| **Database** | **PostgreSQL** | PostgreSQL\_tables。時系列データ（スナップショット）とリレーショナルデータ（アイテムマスタ）の統合管理。 |
| **Scripting** | **Python / Bash** | データのETL処理、バックアップスクリプト、K8s自動運用ジョブ。 |

### **📊 実装機能詳細 (Implementation Highlights)**

#### **1\. Terraformによるインフラ定義 (Current Focus)**

現在、terraform/proxmox/main.tf により、以下のリソース管理をコード化済みです。これにより、ハードウェア故障時でもコマンド一つでインフラ環境を再現可能です。

* **DevOps VM:** CI/CDランナー、ダッシュボード、DBサーバーを集約。  
* **App Server VM:** Kubernetesノード、ゲームサーバーホスト。  
* **Networking:** 固定IP割り当て、ブリッジネットワーク設定。

#### **2\. Kubernetesによる自律運用 (Automated Ops)**

人間の介入を最小限にするため、運用タスクをK8sのリソースとして定義しています。

* **Auto Update (k8s-autoupdate.yaml):** 新しいサーバーバージョンを検知し、ユーザーへのRCON通知後にRolling Updateを実行。計画停止の自動化。  
* **Backup & Export (k8s-backup-export.yaml):** 毎日定時にワールドデータを圧縮し、解析用サーバーへ転送。失敗時の再試行ロジックも実装。

#### **3\. 資源状況の可視化 (Resource Observability)**

工場における「在庫管理」や「歩留まり監視」と同様のアプローチで、ゲーム内データを解析しています。

* **Data Pipeline:** バックアップデータ(.tar.gz)からLevelDBを解析し、チェスト内のアイテム数や位置情報を抽出。  
* **Visualization:** どのアイテム（資源）がどこにどれだけあるかをSQLで構造化し、ダッシュボードで追跡可能に（開発中）。

### **📅 ロードマップ (Roadmap)**

アジャイル開発手法を用い、フェーズごとに検証を行いながら機能拡張を進めています。

* \[x\] **Phase 1: Infrastructure as Code (Foundation)**  
  * TerraformによるProxmox VMプロビジョニングの実装完了。  
  * 基本的なネットワーク設計とセキュリティグループの定義。  
* \[ \] **Phase 2: Configuration Management (Automation)**  
  * Ansible Playbookの作成（Docker, K3sの自動インストール）。  
  * 閉鎖網内でのGitHub Actions Self-hosted Runnerの確立。  
* \[ \] **Phase 3: Service Deployment (Orchestration)**  
  * Minecraft BEサーバーおよびExporterのK8sデプロイ。  
  * minecraft.yaml に定義されたPV/PVCによるデータ永続化の実証。  
* \[ \] **Phase 4: Observability & Analytics (Value Creation)**  
  * Python解析エンジンの実装とPostgreSQLへのデータ蓄積。  
  * Grafana/Web UIによるリソースダッシュボードの公開。

### **👤 Information**
Mission:  
物理ハードウェア（自作サーバー、10Gネットワーク）の構築経験と、モダンなクラウドネイティブ技術（K8s, IaC）を融合させ、現場で本当に使えるDX基盤の構築を目指しています。  
Contact:tagomoriyuukichi@gmail.com 
GitHub Profile
*This project is a technical showcase for job application purposes.*
