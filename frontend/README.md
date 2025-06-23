# AI SNSコンテンツ戦略・投稿自動化ツール (EDS Project)

## 概要

このプロジェクトは、AIを活用してX (旧Twitter) のアカウント運用を効率化し、エンゲージメントを高めるための戦略立案から投稿作成・予約までを一貫してサポートするWebアプリケーションです。

Googleの生成AIモデル「Gemini」とSupabaseをバックエンドに利用し、ユーザーの目的やターゲットに合わせたペルソナ設定、投稿戦略の策定、そして日々のツイートコンテンツの自動生成機能を提供します。

## 主な機能

-   **ユーザー認証**: メールアドレスとパスワードによるサインアップ、ログイン機能。
-   **X (旧Twitter) アカウント連携**: ユーザーのXアカウントを安全に連携し、投稿や分析を可能にします。
-   **AIによるペルソナ・戦略策定**:
    -   運用の目的、ターゲット、提供価値などを入力することで、AIが最適なアカウントのペルソナと投稿戦略を提案します。
-   **AIによる初回ポスト生成**: 設定したペルソナに基づき、エンゲージメントを高めるための最初の固定ツイートやプロフィール文をAIが自動で作成します。
-   **AIツイート自動生成**:
    -   指定したテーマやキーワードに基づき、複数のツイート案をAIが生成します。
    -   生成されたツイートは編集・予約が可能です。
-   **投稿カレンダー**: 予約したツイートをカレンダー形式で視覚的に管理できます。
-   **教育的ツイートの検索**: 過去の有益なツイートを検索・閲覧し、コンテンツ作成の参考にすることができます。
-   **商品・サービス管理**: ユーザーが宣伝したい商品やサービスを登録し、投稿生成に活用できます。

## 使用技術

### フロントエンド

-   [Next.js](https://nextjs.org/) (Reactフレームワーク)
-   [TypeScript](https://www.typescriptlang.org/)
-   [Tailwind CSS](https://tailwindcss.com/)
-   [Supabase Client](https://supabase.com/docs/library/js/getting-started) (認証、データフェッチ)
-   [React-Calendar](https://github.com/wojtekmaj/react-calendar)

### バックエンド

-   [Python 3.12](https://www.python.org/)
-   [Flask](https://flask.palletsprojects.com/) (Webフレームワーク)
-   [Supabase (Python)](https://github.com/supabase-community/supabase-py) (データベース連携、認証)
-   [Google Generative AI (Gemini)](https://ai.google.dev/)
-   [Tweepy](https://www.tweepy.org/) (Twitter API連携)

### データベース

-   [Supabase](https://supabase.com/) (PostgreSQL)

### デプロイ

-   [Vercel](https://vercel.com/)

## セットアップと実行方法

### 必要なもの

-   Python 3.12+
-   Node.js (v18+) and npm
-   各種APIキー (Supabase, Google Gemini, Twitter*フロントエンドで使用)

### 1. 環境変数の設定

プロジェクトのルートディレクトリに、バックエンド用とフロントエンド用の環境変数ファイルを作成します。

#### バックエンド (`/backend/.env`)

```bash
FLASK_APP=app
FLASK_ENV=development

# Supabase
SUPABASE_URL="YOUR_SUPABASE_URL"
SUPABASE_KEY="YOUR_SUPABASE_SERVICE_ROLE_KEY"

# Google Gemini API
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"


フロントエンド (/frontend/.env.local)
Bash

NEXT_PUBLIC_SUPABASE_URL="YOUR_SUPABASE_URL"
NEXT_PUBLIC_SUPABASE_ANON_KEY="YOUR_SUPABASE_ANON_KEY"

2. バックエンドのセットアップ
Bash

# 1. backendディレクトリに移動
cd backend

# 2. Python仮想環境の作成と有効化
python -m venv env
source env/bin/activate  # Mac/Linuxの場合
# env\Scripts\activate  # Windowsの場合

# 3. 依存ライブラリのインストール
pip install -r requirements.txt

# 4. Flaskサーバーの起動
flask run
バックエンドサーバーが http://127.0.0.1:5001 で起動します。

3. フロントエンドのセットアップ
Bash

# 1. frontendディレクトリに移動
cd frontend

# 2. 依存ライブラリのインストール
npm install

# 3. 開発サーバーの起動
npm run dev
フロントエンドの開発サーバーが http://localhost:3000 で起動します。

ディレクトリ構成
.
├── backend/                  # Python/Flask バックエンド
│   ├── app.py                # Flaskアプリケーション本体
│   ├── requirements.txt      # Pythonの依存ライブラリ
│   └── env/                  # Python仮想環境
├── frontend/                 # Next.js フロントエンド
│   ├── src/
│   │   ├── app/              # App Routerのページとレイアウト
│   │   ├── components/       # 再利用可能なReactコンポーネント
│   │   ├── context/          # React Context (認証情報など)
│   │   └── lib/              # Supabaseクライアントなどのライブラリ
│   ├── package.json          # npmの依存関係とスクリプト
│   └── next.config.ts        # Next.jsの設定ファイル
└── README.md                 # このファイル