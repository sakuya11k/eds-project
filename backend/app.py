
# app.py の import ブロック

import os
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from functools import wraps
import datetime
import traceback
import time

# ▼▼▼【ここからが新しいSDKの正しいimport】▼▼▼
from google import genai
# 新しいSDKでは、typesモジュールを別名でインポートするのが作法
from google.genai import types as genai_types
# ▲▲▲【ここまでが新しいSDKの正しいimport】▲▲▲

import tweepy
from cryptography.fernet import Fernet
import json
import re 
import requests
from bs4 import BeautifulSoup
# .envファイルを読み込む
load_dotenv()
app = Flask(__name__)

# CORS設定
CRON_JOB_SECRET = os.environ.get('CRON_JOB_SECRET')

CORS(
    app,
    origins=["http://localhost:3000", "https://eds-saku-front.vercel.app"],
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    supports_credentials=True
)
print(">>> CORS configured.")

# 定数定義 (profilesテーブルから古いAPIキー関連を削除)
PROFILE_COLUMNS_TO_SELECT = [
    "id", "username", "website", "avatar_url",
    "brand_voice", "target_persona", "preferred_ai_model", "updated_at",
    "account_purpose", "main_target_audience", "core_value_proposition",
    "brand_voice_detail", "main_product_summary", "edu_s1_purpose_base",
    "edu_s2_trust_base", "edu_s3_problem_base", "edu_s4_solution_base",
    "edu_s5_investment_base", "edu_s6_action_base", "edu_r1_engagement_hook_base",
    "edu_r2_repetition_base", "edu_r3_change_mindset_base", "edu_r4_receptiveness_base",
    "edu_r5_output_encouragement_base", "edu_r6_baseline_shift_base"
]

# Supabase クライアント初期化
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
print(">>> Supabase client initialized.")

# Gemini API キー設定
try:
    gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_api_key:
        raise ValueError("API Key not found. Please set GOOGLE_API_KEY or GEMINI_API_KEY in your environment.")
    
    client = genai.Client(api_key=gemini_api_key)
    print(">>> Gen AI Client initialized successfully.")

except Exception as e:
    print(f"!!! Failed to initialize Gen AI Client: {e}")
    client = None

# 暗号化キーを環境変数から取得
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    raise ValueError("No ENCRYPTION_KEY set for Flask application")
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

class EncryptionManager:
    @staticmethod
    def encrypt(data: str) -> str:
        if not data: return ""
        return cipher_suite.encrypt(data.encode()).decode()

    @staticmethod
    def decrypt(encrypted_data: str) -> str:
        if not encrypted_data: return ""
        return cipher_suite.decrypt(encrypted_data.encode()).decode()

# ▼▼▼▼▼▼▼▼▼【ここからが修正箇所】▼▼▼▼▼▼▼▼▼

# --- AIモデル準備用のヘルパー関数 ---
# app.py 内の call_gemini_api 関数を以下の最終版で置き換える

def call_gemini_api(user_profile, contents, use_Google_Search=False, system_instruction_text=None):
    """
    新しい google-genai SDK を使用して、Gemini API にリクエストを送信する。（公式ドキュメント準拠）
    """
    global client
    if not client:
        raise Exception("Gen AI Client is not initialized. Check API Key.")

    try:
        # 1. モデル名を取得
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')

        # 2. ツール（Google検索）を決定
        tools = None
        if use_Google_Search:
            # 公式ドキュメントに沿った正しいツールの作成方法
            tools = [Tool(google_search=GoogleSearch())]

        # 3. 生成設定（config）を作成し、その中にツールを含める
        config = GenerateContentConfig(
            system_instruction=system_instruction_text,
            temperature=0.7,
            tools=tools
        )

        print(f">>> Calling Gemini API with model: {model_id} (Search: {use_Google_Search})")
        
        # 4. 新しいSDKの正しい作法でAPIを呼び出す
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=config # 正しい引数名 `config` を使用
        )
        return response

    except Exception as e:
        print(f"!!! Exception during Gemini API call: {e}")
        raise e
    


# --- 認証デコレーター (デバッグログ追加版) ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # どのAPIへのリクエストかをログに出力
        print(f"--- [DEBUG] Decorator called for: {request.method} {request.path} ---")

        if request.method == 'OPTIONS':
            print("--- [DEBUG] Handling OPTIONS request. Returning OK response. ---")
            return app.make_default_options_response()
        
        print("--- [DEBUG] Not an OPTIONS request. Proceeding to token validation. ---")
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
        
        if not token:
            print("--- [DEBUG] Token is missing! ---")
            return jsonify({"message": "認証トークンが見つかりません。"}), 401
        
        try:
            print("--- [DEBUG] Attempting to get user from Supabase... ---")
            user_response = supabase.auth.get_user(token)
            g.user = user_response.user
            if not g.user:
                print("--- [DEBUG] User not found for token. ---")
                return jsonify({"message": "無効なトークンです。"}), 401
            
            print(f"--- [DEBUG] User validation successful. User ID: {g.user.id} ---")
            
            print("--- [DEBUG] Attempting to get profile for g.profile... ---")
            profile_response = supabase.table('profiles').select("*").eq('id', g.user.id).maybe_single().execute()
            if profile_response.data:
                g.profile = profile_response.data
                print("--- [DEBUG] Profile found and set to g.profile. ---")
            else:
                g.profile = {}
                print("--- [DEBUG] Profile not found. g.profile is set to empty dict. ---")

        except Exception as e:
            print(f"!!! [DEBUG] Exception during token/profile validation: {e} !!!")
            traceback.print_exc()
            return jsonify({"message": "トークンが無効か期限切れです。", "error": str(e)}), 401
        
        print(f"--- [DEBUG] Decorator finished. Calling the original function for {request.path}... ---")
        return f(*args, **kwargs)
    return decorated

# --- ルート ---
@app.route('/')
def index():
    return jsonify({"message": "Welcome to the EDS Backend API!"})

# --- Xアカウント管理API ---
@app.route('/api/v1/x-accounts', methods=['POST', 'GET'])
@token_required
def handle_x_accounts():
    user_id = g.user.id
    
    if request.method == 'POST':
        try:
            data = request.json
            if not data: return jsonify({"error": "リクエストボディがありません"}), 400
            
            required_fields = ['x_username', 'api_key', 'api_key_secret', 'access_token', 'access_token_secret']
            if not all(field in data and data[field] for field in required_fields):
                return jsonify({"error": "すべてのフィールドを入力してください"}), 400
            
            # 暗号化
            encrypted_data = {
                'api_key_encrypted': EncryptionManager.encrypt(data['api_key']),
                'api_key_secret_encrypted': EncryptionManager.encrypt(data['api_key_secret']),
                'access_token_encrypted': EncryptionManager.encrypt(data['access_token']),
                'access_token_secret_encrypted': EncryptionManager.encrypt(data['access_token_secret']),
            }

            insert_payload = {
                'user_id': user_id, 
                'x_username': data['x_username'],
                **encrypted_data
            }
            
            # 最初の1件目のアカウントを is_active = true に設定
            existing_accounts, _ = supabase.table('x_accounts').select('id').eq('user_id', user_id).execute()
            if not existing_accounts[1]: # 既存アカウントがなければ
                insert_payload['is_active'] = True

            response = supabase.table('x_accounts').insert(insert_payload).execute()

            if response.data:
                return jsonify(response.data[0]), 201
            else:
                # Supabaseからのエラーをより詳細に返す
                error_info = response.error.message if hasattr(response, 'error') and response.error else 'Unknown error'
                raise Exception(f"Failed to insert or return data from Supabase. Details: {error_info}")

        except Exception as e:
            print(f"Error adding X account: {e}"); traceback.print_exc()
            return jsonify({"error": "Xアカウントの追加に失敗しました", "details": str(e)}), 500
            
    if request.method == 'GET':
        try:
            response = supabase.table('x_accounts').select('id, x_username, is_active, created_at').eq('user_id', user_id).order('created_at').execute()
            return jsonify(response.data), 200
        except Exception as e:
            print(f"Error getting X accounts: {e}")
            return jsonify({"error": "Xアカウントの取得に失敗しました", "details": str(e)}), 500

@app.route('/api/v1/x-accounts/<uuid:x_account_id>/activate', methods=['PUT'])
@token_required
def set_active_x_account(x_account_id):
    try:
        user_id = g.user.id
        # トランザクションで処理するのが望ましいが、ここでは順次実行
        supabase.table('x_accounts').update({'is_active': False}).eq('user_id', user_id).execute()
        update_response = supabase.table('x_accounts').update({'is_active': True}).eq('id', str(x_account_id)).eq('user_id', user_id).execute()
        
        if update_response.data:
            return jsonify(update_response.data[0]), 200
        else:
            return jsonify({"error": "アカウントが見つからないか、権限がありません"}), 404
            
    except Exception as e:
        print(f"Error activating X account: {e}")
        return jsonify({"error": "アカウントの切り替えに失敗しました", "details": str(e)}), 500

@app.route('/api/v1/x-accounts/<uuid:x_account_id>', methods=['DELETE'])
@token_required
def delete_x_account(x_account_id):
    try:
        user_id = g.user.id
        response = supabase.table('x_accounts').delete().eq('id', str(x_account_id)).eq('user_id', user_id).execute()

        if response.data:
            return jsonify({"message": "アカウントを削除しました"}), 200
        else:
            # deleteは成功してもdataが空の場合がある。エラーがなければ成功とみなす。
            if not (hasattr(response, 'error') and response.error):
                 return ('', 204) # No Content
            return jsonify({"error": "アカウントが見つからないか、権限がありません"}), 404

    except Exception as e:
        print(f"Error deleting X account: {e}")
        return jsonify({"error": "アカウントの削除に失敗しました", "details": str(e)}), 500

# --- Profile API (ユーザー基本設定) ---
@app.route('/api/v1/profile', methods=['GET', 'PUT'])
@token_required
def handle_profile():
    user_id = g.user.id
    
    # GETリクエスト: プロフィール情報を取得
    if request.method == 'GET':
        # token_requiredデコレーターでg.profileに設定済みの情報を返す
        if g.profile:
            return jsonify(g.profile)
        else:
            # プロフィールがまだ存在しない場合は404を返す
            return jsonify({"error": "Profile not found"}), 404

       # PUTリクエスト: プロフィール情報を更新または新規作成
    if request.method == 'PUT':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Invalid JSON"}), 400

            # 更新を許可するカラムだけを安全に抽出
            update_data = {}
            for field in PROFILE_COLUMNS_TO_SELECT:
                if field in data:
                    update_data[field] = data[field]
            
            if not update_data:
                return jsonify({"error": "No valid fields to update"}), 400
            
            # ユーザーIDと更新日時を強制的に設定
            update_data['id'] = user_id
            update_data['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Supabaseに送信する直前のデータを確認（デバッグ用）
            print(f"--- [DEBUG] Upserting to 'profiles' with payload: {update_data}")

            # upsertを使って、レコードがなければ挿入、あれば更新する
            response = supabase.table('profiles').upsert(update_data).execute()
            
            if response.data:
                return jsonify(response.data[0]), 200
            else:
                error_info = response.error.message if hasattr(response, 'error') and response.error else 'Unknown DB error'
                # データベースからのエラーをより具体的に返す
                print(f"!!! Supabase upsert error: {error_info}")
                return jsonify({"error": "データベースの更新に失敗しました。", "details": error_info}), 500

        except Exception as e:
            print(f"Error processing PUT request for profile: {e}"); traceback.print_exc()
            return jsonify({"error": "プロフィールの更新処理中にサーバーエラーが発生しました。", "details": str(e)}), 500
 
# --- Account Strategy API (Xアカウントごと) ---

@app.route('/api/v1/account-strategies/<uuid:x_account_id>', methods=['GET', 'PUT'])
@token_required
def handle_account_strategy(x_account_id):
    user_id = g.user.id

    try:
        # --- セキュリティチェック ---
        x_account_check_res = supabase.table('x_accounts').select('id', count='exact').eq('id', x_account_id).eq('user_id', user_id).execute()
        if x_account_check_res.count == 0:
            return jsonify({"error": "Account not found or access denied"}), 404

        # --- GETリクエスト処理 ---
        if request.method == 'GET':
            strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).limit(1).execute()
            strategy_data = strategy_res.data[0] if strategy_res.data else {}
            return jsonify(strategy_data), 200

        # --- PUTリクエスト処理 ---
        if request.method == 'PUT':
            data = request.get_json()
            if not data: 
                return jsonify({"error": "Invalid JSON"}), 400
            
            # ★★★ ここから修正・改良箇所 ★★★

            # 1. 更新する可能性のあるフィールドをすべて定義
            allowed_fields = [
                'account_purpose', 'persona_profile_for_ai', 'core_value_proposition', 
                'main_product_summary', 'main_target_audience', 'brand_voice_detail',
                'edu_s1_purpose_base', 'edu_s2_trust_base', 'edu_s3_problem_base',
                'edu_s4_solution_base', 'edu_s5_investment_base', 'edu_s6_action_base',
                'edu_r1_engagement_hook_base', 'edu_r2_repetition_base',
                'edu_r3_change_mindset_base', 'edu_r4_receptiveness_base',
                'edu_r5_output_encouragement_base', 'edu_r6_baseline_shift_base'
            ]
            
            # 2. フロントエンドから送られてきたデータの中から、許可されたフィールドのみを抽出
            data_to_update = {key: data[key] for key in allowed_fields if key in data}

            # 3. 更新データに必須情報を付与
            data_to_update['x_account_id'] = str(x_account_id)
            data_to_update['user_id'] = user_id
            data_to_update['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # upsertを使用してデータの挿入または更新を実行
            res = supabase.table('account_strategies').upsert(data_to_update, on_conflict='x_account_id').execute()
            
            # ★★★ 修正・改良ここまで ★★★

            if res.data:
                return jsonify(res.data[0]), 200
            else:
                error_details = res.error.message if hasattr(res, 'error') and res.error else "Unknown DB error"
                # Supabaseのエラーレスポンスをより詳細にログ出力
                print(f"!!! Supabase upsert error for user {user_id}: {error_details}")
                return jsonify({"error": "Failed to update strategy", "details": error_details}), 500
    
    except Exception as e:
        print(f"!!! UNHANDLED EXCEPTION in handle_account_strategy for user {user_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred.", "details": str(e)}), 500


# --- 商品管理 API ---
@app.route('/api/v1/products', methods=['POST'])
@token_required
def create_product():
    user = getattr(g, 'user', None); data = request.json
    if not user: return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    if not data or 'name' not in data or not data['name']: return jsonify({"message": "Missing required field: name"}), 400
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        new_p = {
            "name": data.get("name"),
            "description": data.get("description"),
            "price": data.get("price"),
            "target_audience": data.get("target_audience"),
            "value_proposition": data.get("value_proposition"),
            "user_id": user_id, 
            "currency": data.get("currency","JPY")
        }
        res = supabase.table('products').insert(new_p).execute()
        if res.data: return jsonify(res.data[0]), 201
        elif hasattr(res, 'error') and res.error: return jsonify({"message": "Error creating product", "error": str(res.error)}), 500
        return jsonify({"message": "Error creating product, unknown reason."}), 500
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error creating product", "error": str(e)}), 500
    
    
    # アカウント目的の提案
# app.py 内の suggest_account_purpose 関数を以下で置き換える
# app.py 内の suggest_account_purpose 関数を以下の最終版で置き換える

@app.route('/api/v1/profile/suggest-purpose', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def suggest_account_purpose():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400
        
        x_account_id = data.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "x_account_id is required"}), 400
        user_keywords = data.get('user_keywords', '')

    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # 1. アカウントごとの戦略情報を取得
        acc_strategy_res = supabase.table('account_strategies').select('main_product_summary').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = acc_strategy_res.data if acc_strategy_res else {}
        current_product_summary = account_strategy.get('main_product_summary', '（情報なし）')

        # 2. Xアカウント名を取得
        x_account_info_res = supabase.table('x_accounts').select('x_username').eq('id', x_account_id).maybe_single().execute()
        x_account_info = x_account_info_res.data if x_account_info_res else {}
        current_x_username = x_account_info.get('x_username', '名無しの発信者')

        # 3. プロンプトを組み立てる
        prompt_parts = [
            # プロンプト改善：役割設定をより具体的に
            "あなたは、個人のブランドストーリーを構築する、一流のストーリーテラー兼コピーライターです。",
            "あなたの仕事は、クライアントの断片的な情報から、その人の「物語の始まり」となる、魂のこもった「基本理念・パーパス」を紡ぎ出すことです。",
            "以下の情報を元に、読者の心を揺さぶり、希望を与える「基本理念・パーパス」のドラフトを1つ、250～350字程度で作成してください。",
            
            f"\n## クライアント情報:",
            f"  - アカウント名: @{current_x_username}",
            f"  - クライアントが表現したいこと（キーワード）: {user_keywords if user_keywords else '特に指定なし'}",
            f"  - 提供予定の商品/サービス概要: {current_product_summary}",
            
            # プロンプト改善：構成をより明確に指示
            f"\n## 作成指示:",
            "文章の構成は、以下の流れを意識してください。",
            "1. **共感のフック**: まず、ターゲットが心の中でつぶやいているような『悩み』や『諦め』の言葉から始め、強く引き込みます。",
            "2. **可能性の提示**: 次に、『でも、本当にそうでしょうか？』と優しく問いかけ、読者がまだ気づいていない『可能性』や『新しい視点』を提示します。",
            "3. **約束と宣言**: 最後に、このアカウントが読者と共に目指す『理想の未来』を約束し、その実現を助けるという『力強い使命』を宣言して締めくくります。",

            f"\n## 文体と出力形式:",
            "  - 全体として、誠実なトーンで記述してください。",
            "  - 完成された『基本理念・パーパス』の文章本文のみを出力してください。前置きや解説は一切不要です。"
        ]
        prompt = "\n".join(prompt_parts)
        print(f">>> Suggest Account Purpose Prompt: \n{prompt[:500]}...")
        
        # 4. 新しいSDKの作法でAPIを呼び出す
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        
        config = genai_types.GenerateContentConfig(temperature=0.7)

        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=config
        )

        suggestion = response.text.strip()
        print(f">>> AI Suggested Purpose: {suggestion}")
        return jsonify({"suggestion": suggestion}), 200

    except Exception as e:
        print(f"!!! Exception during AI purpose suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる目的提案中にエラーが発生しました。", "error": str(e)}), 500
    # ペルソナ案を複数提案
# suggest_persona_draft 


@app.route('/api/v1/profile/suggest-persona-draft', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def suggest_persona_draft():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400

        x_account_id = data.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "x_account_id is required"}), 400
        user_keywords = data.get('user_keywords', '')
        
    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # --- 1. 戦略情報を取得 ---
        acc_strategy_res = supabase.table('account_strategies').select('main_product_summary, account_purpose').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = acc_strategy_res.data if acc_strategy_res else {}
        current_product_summary = account_strategy.get('main_product_summary', '（情報なし）')
        current_account_purpose = account_strategy.get('account_purpose', '（情報なし）')
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')

        # --- 2. フェーズ1: 【ペルソナ創造AI】による詳細プロフィールの生成 ---
        profile_prompt_parts = [
            "あなたは、非常に解像度の高い顧客ペルソナを設計する、一流のマーケティングリサーチャーです。",
            "以下の情報を元に、この商品やサービスを最も必要とするであろう、一人のリアルな人物の【詳細なプロフィール】をJSON形式で生成してください。",
            f"\n## 参考情報:",
            f"  - アカウントの目的: {current_account_purpose}",
            f"  - 商品/サービス概要: {current_product_summary}",
            f"  - ターゲットのヒント（キーワード）: {user_keywords if user_keywords else '特に指定なし'}",
            f"\n## 生成すべきJSONの構造と指示:",
            "{",
            "  \"name\": \"実在しそうなフルネーム\",",
            "  \"age\": \"具体的な年齢（数値）\",",
            "  \"gender\": \"性別\",",
            "  \"location\": \"居住地（例：東京都世田谷区）\",",
            "  \"family\": \"家族構成（例：夫(46歳・会社員)、長男(高2)との3人暮らし）\",",
            "  \"job\": \"職業（例：パート・スーパーのレジ打ち）\",",
            "  \"income\": \"世帯年収（例：約650万円）\",",
            "  \"personality\": \"性格を表すキーワード3つ（例：心配性, 責任感が強い, 控えめ）\",",
            "  \"hobby\": \"具体的な趣味（例：寝る前にスマホで韓国ドラマを見ること）\",",
            "  \"info_source\": \"主な情報収集源（例：Instagram, ママ友とのLINE）\"",
            "}",
            "\n## 最重要の出力形式:",
            "  - **必ず、前置きや解説、```json ... ```のようなマークダウンは一切含めず、純粋なJSONオブジェクト（{{...}}）そのものだけを出力してください。**"
        ]
        profile_prompt = "\n".join(profile_prompt_parts)
        print(">>> Phase 1: Generating Persona Profile...")
        
        profile_config = genai_types.GenerateContentConfig(
            temperature=0.9,
            response_mime_type="application/json"
        )
        profile_response = client.models.generate_content(
            model=model_id, 
            contents=profile_prompt, 
            config=profile_config
        )
        
        try:
            response_text = profile_response.text
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_string = response_text[start:end+1]
                profile_json = json.loads(json_string)
            else:
                raise ValueError("Valid JSON object not found in the response.")
        except (json.JSONDecodeError, AttributeError, ValueError) as e_parse:
            print(f"!!! Error parsing Phase 1 Profile JSON: {e_parse}. Raw text: {getattr(profile_response, 'text', 'N/A')}")
            raise ValueError("ペルソナの基本情報生成に失敗しました。AIが有効なJSONを返せませんでした。")

        # --- 3. フェーズ2: 【脚本家AI】による物語の生成 ---
        story_prompt_parts = [
            "あなたは、一人の人間の「感情が動く瞬間」を切り取るのが得意な、プロの脚本家です。",
            "以下の詳細な人物プロフィールを元に、この人物の人生の『ターニングポイント』となった、読者の心を鷲掴みにする具体的なエピソードを創作してください。",
            f"\n## 主人公のプロフィール:\n{json.dumps(profile_json, ensure_ascii=False, indent=2)}",
            f"\n## 物語のテーマヒント: {current_account_purpose}",
            f"\n## 物語に含めるべき【必須の構成要素】:",
            "1. **【引き金となった出来事】**: 主人公が『もう、こんな人生は嫌だ！』と、現状に対して強烈な危機感や劣等感を抱いた、具体的な出来事や誰かの一言。",
            "2. **【行動できなかった理由／失敗談】**: なぜ、これまでその悩みを解決できなかったのか。その理由（例：「私には無理だという思い込み」「時間のなさ」「間違った自己投資による失敗」など）を具体的に描写する。",
            "\n## 作成指示:",
            " - 上記の3要素を、200～250字程度の、情景が目に浮かぶリアルな一つの物語として描写してください。",
            " - 主人公の心の声や、その時の感情（悔しさ、焦りなど）が鮮やかに伝わるようにしてください。",
            " - 最終的なアウトプットは、物語の文章本文のみとしてください。前置きや解説は不要です。"
        ]
        story_prompt = "\n".join(story_prompt_parts)
        print(">>> Phase 2: Generating Critical Story (Evolved)...")
        
        story_config = genai_types.GenerateContentConfig(temperature=0.8)
        story_response = client.models.generate_content(
            model=model_id, 
            contents=story_prompt, 
            config=story_config
        )
        critical_story = story_response.text.strip()

        # --- 4. フロントエンド向けのデータ整形 ---
        profile = profile_json
        story = critical_story

        age_attribute_text = (
            f"{profile.get('age')}歳 {profile.get('gender', '')} / {profile.get('job', '')}\n"
            f"【家族】{profile.get('family', '未設定')}\n"
            f"【年収】{profile.get('income', '未設定')}\n"
            f"【性格】{', '.join(profile.get('personality', []))}"
        )

        issue_text = (
            f"普段は{profile.get('info_source', 'Web')}で情報を集めているが、解決策を見出せずにいる。\n"
            f"趣味は{profile.get('hobby', '特になし')}。\n\n"
            f"【背景ストーリー】:\n{story}"
        )

        final_persona = {
            "name": profile.get("name", "名称未設定"),
            "age": age_attribute_text.strip(),
            "悩み": issue_text.strip()
        }

        print(f">>> AI Suggested Persona (Formatted): {[final_persona]}")
        return jsonify({"suggested_personas": [final_persona]}), 200

    except Exception as e:
        print(f"!!! Exception during AI persona suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによるペルソナ提案中にエラーが発生しました。", "error": str(e)}), 500
# app.py 内の suggest_value_proposition 関数を以下で置き換える
# app.py 内の suggest_value_proposition 関数を以下の最終版で置き換える

@app.route('/api/v1/profile/suggest-value-proposition', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def suggest_value_proposition():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400

        x_account_id = data.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "x_account_id is required"}), 400
            
    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # 1. アカウントごとの戦略情報を取得
        acc_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = acc_strategy_res.data if acc_strategy_res else {}
        
        account_purpose = account_strategy.get('account_purpose', '（情報なし）')
        main_target_audience_data = account_strategy.get('main_target_audience')
        current_product_summary = account_strategy.get('main_product_summary', '（情報なし）')
        
        target_audience_summary = "（情報なし）"
        if main_target_audience_data and isinstance(main_target_audience_data, list) and len(main_target_audience_data) > 0:
            first_persona = main_target_audience_data[0]
            if isinstance(first_persona, dict):
                name, age, problem = first_persona.get('name', ''), first_persona.get('age', ''), first_persona.get('悩み', '')
                target_audience_summary = f"ペルソナ「{name}」（{age}）が抱える主な悩みは「{problem}」"

        # 2. AIに渡すプロンプトを組み立てる（元のプロンプトを維持）
        prompt_parts = [
            "あなたは、顧客の心を掴む価値提案（バリュープロポジション）を作成する専門家です。",
            "以下の情報を元に、このアカウントの「コアとなる提供価値」のメッセージ案を1つ、簡潔な説明文として提案してください。",
            "\n## 分析対象となるアカウント戦略情報:",
            f"  - このアカウントの目的・パーパス: {account_purpose}",
            f"  - ターゲット顧客像（悩みや欲求）: {target_audience_summary}",
            f"  - 主要商品/サービス概要: {current_product_summary}",
            "\n## あなたの思考プロセスとタスク:",
            "**以下の思考ステップに従って、最終的な価値提案の文章を1つだけ作成してください。**",
            "1. **【ステップ1: 構成要素の抽出】**: まず、頭の中で以下の3つの要素を、上記の情報から抽出・言語化してください。（このステップの結果は出力しないでください）",
            "   - **要素A (理想の未来)**: 顧客が最終的に手に入れる「最高の結果」や「理想のライフスタイル」。",
            "   - **要素B (痛みの解消)**: 顧客が現在抱えている「具体的な悩み」や「精神的な苦痛」。",
            "   - **要素C (独自性)**: 他にはない、このアカウント/商品だけの「ユニークな特徴」や「特別な提供方法」。",
            "2. **【ステップ2: 文章への統合】**: 次に、ステップ1で抽出したA, B, Cの3要素を、自然でパワフルな一つの説明文（100～150字程度）に統合してください。文章は、ターゲット顧客が抱える**『痛み（要素B）』への深い共感**から始まり、**『独自性（要素C）』**によってそれを解決できることを示唆し、最終的に**『理想の未来（要素A）』**を提示する、という流れが理想的です。",
            "\n## 最終的なアウトプットに関する指示:",
            "  - ターゲット顧客が『これはまさに私のためのものだ！』と直感的に心を揺さぶられるような、具体的で力強い言葉を選んでください。",
            "  - 完成された、ただ一つの「バリュープロポジション」の文章本文のみを出力してください。",
            "  - 前置き、解説、思考プロセスなどは一切含めないでください。"
        ]
        prompt = "\n".join(prompt_parts)
        print(f">>> Suggest Value Proposition Prompt: \n{prompt[:500]}...")

        # 3. 新しいSDKの作法でAPIを呼び出す
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        
        config = genai_types.GenerateContentConfig(temperature=0.7)

        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=config
        )

        suggestion = response.text.strip()
        print(f">>> AI Suggested Value Proposition: {suggestion}")
        return jsonify({"suggestion": suggestion}), 200

    except Exception as e:
        print(f"!!! Exception during AI value proposition suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる目的提案中にエラーが発生しました。", "error": str(e)}), 500
    
    # ブランドボイス詳細（トーン、キーワード、NGワード）を提案
# app.py 内の suggest_brand_voice 関数を以下で置き換える

# app.py 内の suggest_brand_voice 関数を以下の最終版で置き換える

@app.route('/api/v1/profile/suggest-brand-voice', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def suggest_brand_voice():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400

        x_account_id = data.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "x_account_id is required"}), 400
        # フロントエンドからは 'adjectives' キーで送られてくることを想定
        adjectives = data.get('adjectives', '')
        
    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # 1. アカウントごとの戦略情報を取得
        acc_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = acc_strategy_res.data if acc_strategy_res else {}
        
        account_purpose = account_strategy.get('account_purpose', '（情報なし）')
        main_target_audience_data = account_strategy.get('main_target_audience')
        
        target_audience_summary = "（情報なし）"
        if main_target_audience_data and isinstance(main_target_audience_data, list) and len(main_target_audience_data) > 0:
            first_persona = main_target_audience_data[0]
            if isinstance(first_persona, dict):
                name, age, problem = first_persona.get('name', ''), first_persona.get('age', ''), first_persona.get('悩み', '')
                target_audience_summary = f"ペルソナ「{name}」（{age}）が抱える主な悩みは「{problem}」"
        
        # 2. プロンプトを組み立てる（改善版）
        prompt_parts = [
            "あなたは、ターゲット顧客の心に深く響く「ブランドボイス」を設計する、一流のブランド・パーソナリティ戦略家です。",
            "単にトーン＆マナーを提案するだけでなく、そのボイスが『なぜ』効果的なのか、そして『どのように』使うのかまでを具体的に提示してください。",
            "以下の情報を元に、最強の「ブランドボイス詳細」をJSON形式で提案してください。",
            
            f"\n## アカウントの戦略情報:",
            f"  - アカウントの目的と理想像: {account_purpose}",
            f"  - ターゲット顧客像とその悩み: {target_audience_summary}",
            f"  - ユーザーが目指すブランドの雰囲気（形容詞など）: {adjectives if adjectives else '特に指定なし (上記情報から最適なものを推測してください)'}",
            
            f"\n## 提案に含めるべき【必須の構成要素】:",
            "1. **`tone` (基本トーン)**: このアカウントがどのような「キャラクター」として振る舞うべきか、その話し方や態度を具体的に記述してください。",
            "2. **`reason` (そのトーンであるべき理由)**: なぜそのトーンが、このアカウントの目的とターゲット顧客に対して最も効果的なのか、その戦略的な理由を簡潔に説明してください。",
            "3. **`example_tweet` (ツイート例文)**: そのトーンを完璧に体現した、140字程度の具体的なツイートの例文を1つ作成してください。",
            "4. **`keywords` (推奨キーワード)**: そのトーンを表現する上で役立つ、具体的なキーワードやフレーズを**5つ**提案してください。",
            "5. **`ng_words` (NGワード)**: ブランドイメージを損なうため、このアカウントが決して使うべきではない言葉やフレーズを**3つ**提案してください。",

            f"\n## 最重要の出力形式:",
            "  - **必ず、前置きや解説、```json ... ```のようなマークダウンは一切含めず、純粋なJSONオブジェクト（{{...}}）そのものだけを出力してください。**",
            "  - キーは `tone`, `reason`, `example_tweet`, `keywords`, `ng_words` の5つにしてください。"
        ]
        prompt = "\n".join(prompt_parts)
        print(f">>> Suggest Brand Voice Prompt (Evolved): \n{prompt[:500]}...")

        # 3. 新しいSDKの作法でAPIを呼び出す
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        
        config = genai_types.GenerateContentConfig(
            temperature=0.8,
            response_mime_type="application/json"
        )

        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=config
        )

        # 4. 堅牢なJSON抽出ロジック
        try:
            response_text = response.text
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_string = response_text[start:end+1]
                suggested_brand_voice_detail = json.loads(json_string)
            else:
                raise ValueError("Valid JSON object not found in the response.")

            # フロントエンドで使うのは3つのキーなので、ここで絞り込む
            final_suggestion = {
                "tone": suggested_brand_voice_detail.get("tone", ""),
                "keywords": suggested_brand_voice_detail.get("keywords", []),
                "ng_words": suggested_brand_voice_detail.get("ng_words", [])
            }
            
            # (参考として、理由と例文もログには出力しておく)
            print(f">>> Reason: {suggested_brand_voice_detail.get('reason', 'N/A')}")
            print(f">>> Example Tweet: {suggested_brand_voice_detail.get('example_tweet', 'N/A')}")

        except (json.JSONDecodeError, ValueError) as e_parse:
            print(f"!!! Error parsing AI response for brand voice: {e_parse}. Raw text: {getattr(response, 'text', 'N/A')}")
            final_suggestion = {
                "tone": f"AI提案の解析に失敗しました。AIの応答: {getattr(response, 'text', 'N/A')}",
                "keywords": [],
                "ng_words": []
            }
        
        print(f">>> AI Suggested Brand Voice Detail (for Frontend): {final_suggestion}")
        return jsonify({"suggestion": final_suggestion}), 200

    except Exception as e:
        print(f"!!! Exception during AI brand voice suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによるブランドボイス提案中にエラーが発生しました。", "error": str(e)}), 500

    # 登録済み商品情報から「主要商品群の分析サマリー」を生成
# app.py 内の suggest_product_summary 関数を以下の最終版で置き換える

@app.route('/api/v1/profile/suggest-product-summary', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def suggest_product_summary():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400

        x_account_id = data.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "x_account_id is required"}), 400
            
    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # 1. ユーザーに紐づく商品情報を取得
        products_res = supabase.table('products').select("name, description, value_proposition").eq('user_id', user_id).execute()
        if hasattr(products_res, 'error') and products_res.error:
            raise Exception(f"Error fetching user products: {products_res.error}")
        
        user_products = products_res.data
        if not user_products:
            return jsonify({"suggestion": "登録されている商品がありません。まず商品を登録してください。"}), 200

        # 2. アカウントごとの戦略情報を取得
        acc_strategy_res = supabase.table('account_strategies').select('account_purpose, main_target_audience').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = acc_strategy_res.data if acc_strategy_res else {}
        account_purpose = account_strategy.get('account_purpose', '（特に設定なし）')
        
        target_audience_summary = "（情報なし）"
        main_target_audience_data = account_strategy.get('main_target_audience')
        if main_target_audience_data and isinstance(main_target_audience_data, list) and len(main_target_audience_data) > 0:
            first_persona = main_target_audience_data[0]
            if isinstance(first_persona, dict):
                target_audience_summary = f"ペルソナ「{first_persona.get('name', '未設定')}」({first_persona.get('age', '年齢不明')})など"

        # 3. プロンプトで使うための商品情報テキストを生成
        products_info_text = "\n".join([
            f"- 商品名: {p.get('name', '無名')}\n  提供価値: {p.get('value_proposition', '提供価値未設定')}"
            for p in user_products[:5]
        ])

        # 4. プロンプトを組み立てる（改善版）
        prompt_parts = [
            "あなたは、複数の商品を組み合わせて一つの強力なブランドメッセージを構築する、天才的なブランドプロデューサーです。",
            "以下の情報を分析し、この商品群全体を象徴する「コンセプト」と、それに基づいた具体的な「発信テーマ案」を含む、『主要商品群の分析サマリー』を作成してください。",
            
            f"\n## アカウントの基本情報:",
            f"  - アカウントの目的（パーパス）: {account_purpose}",
            f"  - ターゲット顧客像: {target_audience_summary}",
            
            f"\n## 分析対象の商品群:",
            f"{products_info_text}",
            
            f"\n## 作成指示:",
            "1. **商品群のコンセプト化**: まず、これらの商品群に共通する「核心的な価値」を一言で表現する、キャッチーな『コンセプト名』を考えてください。（例：「人生逆転キャリアアップ講座群」「あなたの時間を創り出す自動化ツールキット」など）",
            "2. **分析サマリーの作成**: 次に、そのコンセプト名を使い、商品群全体がターゲット顧客のどんな問題を解決し、アカウントの目的達成にどう貢献するのかを、200字程度で魅力的に要約してください。",
            "3. **具体的な発信テーマの提案**: 最後に、そのコンセプトとサマリーを元に、今すぐツイートできるような具体的な「発信テーマ案」を箇条書きで3つ提案してください。",
            
            f"\n## 出力形式:",
            "以下の形式で、改行を使い分かりやすく出力してください。",
            "【コンセプト名】\n[ここにコンセプト名]\n\n【分析サマリー】\n[ここに分析サマリー]\n\n【発信テーマ案】\n・[テーマ案1]\n・[テーマ案2]\n・[テーマ案3]",
            "\n前置きや解説は一切不要です。"
        ]
        prompt = "\n".join(prompt_parts)
        print(f">>> Suggest Product Summary Prompt (Evolved): \n{prompt[:500]}...")

        # 5. 新しいSDKの作法でAPIを呼び出す
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-2.5-flash-latest')
        
        config = genai_types.GenerateContentConfig(temperature=0.7)

        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=config
        )

        suggestion = response.text.strip()
        print(f">>> AI Suggested Product Summary: {suggestion}")
        return jsonify({"suggestion": suggestion}), 200
        
    except Exception as e:
        print(f"!!! Exception during AI product summary suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる商品概要サマリー提案中にエラーが発生しました。", "error": str(e)}), 500
# suggest-brand-voice のロジックが誤って混入していたものと思われるため、削除しました。

@app.route('/api/v1/products', methods=['GET'])
@token_required
def get_products():
    user = getattr(g, 'user', None)
    if not user: return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        res = supabase.table('products').select("*").eq('user_id', user_id).order('created_at', desc=True).execute()
        if res.data is not None: return jsonify(res.data)
        elif hasattr(res, 'error') and res.error: return jsonify({"message": "Error fetching products", "error": str(res.error)}), 500
        return jsonify({"message": "Error fetching products, unknown reason."}), 500
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error fetching products", "error": str(e)}), 500
    
    
    # アカウント戦略の各項目についてAIと対話形式

# app.py 内の chat_account_strategy_field 関数を以下の最終版で置き換える

@app.route('/api/v1/profile/chat-generic-field', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def chat_account_strategy_field():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400
        
        # フロントエンドから必須情報を受け取る
        x_account_id = data.get('x_account_id')
        field_key = data.get('field_key')
        current_user_message_text = data.get('current_user_message')
        if not all([x_account_id, field_key, current_user_message_text]):
            return jsonify({"error": "x_account_id, field_key, current_user_messageは必須です。"}), 400
            
        field_label = data.get('field_label', '指定の項目')
        current_field_value = data.get('current_field_value', '')
        chat_history_frontend = data.get('chat_history', [])
        
    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # 1. アカウントごとの戦略情報を取得
        acc_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = acc_strategy_res.data if acc_strategy_res else {}
        
        # プロンプトで使う情報を account_strategy から取得
        acc_purpose = account_strategy.get('account_purpose', '未設定')
        acc_product_summary = account_strategy.get('main_product_summary', '未設定')
        acc_value_prop = account_strategy.get('core_value_proposition', '未設定')
        brand_voice_detail = account_strategy.get('brand_voice_detail', {})
        acc_brand_voice = brand_voice_detail.get('tone') if isinstance(brand_voice_detail, dict) else 'プロフェッショナル'

        # 2. システム指示（プロンプト）を組み立てる（改善版）
        system_instruction_parts = [
            "あなたは、クライアントの曖昧な思考を、鋭い質問と具体的な提案によって明確な戦略へと昇華させる、超一流のブランド戦略コンサルタントです。",
            "あなたの役割は、単に質問に答えるのではなく、対話を通じてクライアント自身に『ハッ』とさせ、より深いレベルで思考を整理させることです。",
            f"現在、クライアントはXアカウント戦略の『{field_label}』という項目について悩んでいます。",
            
            f"\n## 対話の前提となる全体戦略（サマリー）:",
            f"  - アカウントの目的: {acc_purpose}",
            f"  - 主要商品/サービス: {acc_product_summary}",
            f"  - コア提供価値: {acc_value_prop}",
            f"  - ブランドボイス: {acc_brand_voice}",
            
            f"\n## 現在のクライアントの思考:",
            f"『{field_label}』について、クライアントは現在「{current_field_value if current_field_value else '(まだ何も考えていない)'}」という状態です。",
            
            f"\n## あなたの対話スタイル:",
            "  - 常にクライアントを肯定し、共感を示してください。",
            "  - 抽象的なアドバイスではなく、「なぜそう思うのですか？」「例えば、どのような状況ですか？」といった、思考を深掘りする具体的な質問を投げかけてください。",
            "  - 時には、思考を刺激するような大胆なアイデアや、全く新しい視点を提案してください。",
            "  - 最終的には、クライアントが『なるほど、そういうことか！』と納得し、自らの言葉で戦略を記述できるようになることをゴールとします。"
        ]
        system_instruction_text = "\n".join(system_instruction_parts)

        # 3. 新しいSDKの作法でチャットセッションを開始・継続する
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        
        # 新しいSDKでは、client.chats.create() でチャットを開始する
        chat_session = client.chats.create(
            model=model_id,
            history=chat_history_frontend, # フロントからの履歴をそのまま渡せる
            system_instruction=system_instruction_text
        )

        print(f">>> Sending to Gemini Chat (New SDK): User says: {current_user_message_text[:100]}...")
        
        # メッセージを送信
        response = chat_session.send_message(message=current_user_message_text)
        
        ai_response_text = response.text
        
        if not ai_response_text:
            raise Exception("AIからの応答テキストが空でした。")

        print(f">>> Gemini Chat AI Response: {ai_response_text.strip()[:100]}...")
        return jsonify({"ai_message": ai_response_text.strip()})
        
    except Exception as e:
        print(f"!!! Exception in chat_account_strategy_field for {field_label}: {e}")
        traceback.print_exc()
        return jsonify({"message": f"AIとの「{field_label}」に関する対話中にエラーが発生しました。", "error": str(e)}), 500


# 主要戦略情報を基に12の基本方針ドラフトを一括生成
# app.py 内の generate_account_base_policies_draft 関数を以下の最終版で置き換える
# app.py 内の generate_account_base_policies_draft 関数を以下の最終版で置き換える

@app.route('/api/v1/profile/generate-base-policies-draft', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def generate_account_base_policies_draft():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500
        
    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400

        x_account_id = data.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "x_account_id is required"}), 400
        
        account_purpose = data.get('account_purpose', '（情報なし）')
        main_target_audience_summary = data.get('main_target_audience_summary', '（情報なし）')
        core_value_proposition = data.get('core_value_proposition', '（情報なし）')
        main_product_summary = data.get('main_product_summary', '（情報なし）')

    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # 1. ブランドボイスのトーンを取得
        acc_strategy_res = supabase.table('account_strategies').select('brand_voice_detail').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = acc_strategy_res.data if acc_strategy_res else {}
        brand_voice_detail = account_strategy.get('brand_voice_detail', {})
        brand_voice_tone = brand_voice_detail.get('tone') if isinstance(brand_voice_detail, dict) else 'プロフェッショナルかつ親しみやすい'
        
        # ▼▼▼【ここが修正点】あなたがまとめてくれた「本質」の定義を使用▼▼▼
        base_policies_elements = [
            {'key': 'edu_s1_purpose_base', 'name': '目的の教育', 'desc': 'アカウント全体として、顧客が目指すべき理想の未来や提供する究極的な価値観についての方針。'},
            {'key': 'edu_s2_trust_base', 'name': '信用の教育', 'desc': 'アカウント全体として、発信者やブランドへの信頼をどのように構築・維持していくかの方針。'},
            {'key': 'edu_s3_problem_base', 'name': '問題点の教育', 'desc': 'ターゲット顧客が抱えるであろう、アカウント全体で共通して取り上げる問題意識や課題についての方針。'},
            {'key': 'edu_s4_solution_base', 'name': '手段の教育', 'desc': 'アカウントが提供する情報や商品が、顧客の問題をどのように解決するかの基本的な考え方。'},
            {'key': 'edu_s5_investment_base', 'name': '投資の教育', 'desc': '自己投資の重要性や、情報・商品への投資をどのように正当化し促すかの全体的な方針。'},
            {'key': 'edu_s6_action_base', 'name': '行動の教育', 'desc': '顧客に具体的な行動を促すための、アカウントとしての一貫したメッセージやアプローチ。'},
            {'key': 'edu_r1_engagement_hook_base', 'name': '読む・見る教育', 'desc': 'コンテンツの冒頭で読者の興味を惹きつけるための、アカウント共通のテクニックや考え方。'},
            {'key': 'edu_r2_repetition_base', 'name': '何度も聞く教育', 'desc': '重要なメッセージを繰り返し伝え、記憶に定着させるためのアカウント全体でのアプローチ。'},
            {'key': 'edu_r3_change_mindset_base', 'name': '変化の教育', 'desc': '現状維持からの脱却や、新しい価値観への変化を促すための、アカウントとしての基本的なスタンス。'},
            {'key': 'edu_r4_receptiveness_base', 'name': '素直の教育', 'desc': '情報やアドバイスを素直に受け入れることの重要性をどのように伝えるかの全体方針。'},
            {'key': 'edu_r5_output_encouragement_base', 'name': 'アウトプットの教育', 'desc': '顧客からの発信（UGC）を促すためのアカウント全体での働きかけや仕組み作りの考え方。'},
            {'key': 'edu_r6_baseline_shift_base', 'name': '基準値/覚悟の教育', 'desc': '顧客の常識や基準値を引き上げ、行動への覚悟を促すためのアカウントとしての一貫した姿勢。'},
        ]
        # ▲▲▲【ここまでが修正点】▲▲▲
        
        generated_drafts = {}
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')

        print(f">>> Generating All Base Policies Draft for x_account_id: {x_account_id}")

        for element in base_policies_elements:
            element_key = element['key']
            element_name = element['name']
            element_desc = element['desc']
            
            # ▼▼▼【ここからが修正点】プロンプトを「本質」を深掘りする指示に変更▼▼▼
            prompt_parts = [
                "あなたは、ブランドの核心的な哲学を言語化する、一流のブランドストラテジストです。",
                f"以下の【アカウントの全体戦略】と【思考の指針】を深く理解し、「{element_name}」に関する、アカウントの揺るぎない【基本方針】を150～200字で記述してください。",
                "この基本方針は、日々の投稿に一貫性を持たせる役割を果たします。",

                f"\n## 思考の指針（この方針が目指すべきこと）:",
                f"  - 要素名: {element_name}",
                f"  - 本質的な目的: {element_desc}",
                
                f"\n## アカウントの全体戦略（コンテキスト）:",
                f"  - アカウントのパーパス: {account_purpose}",
                f"  - ターゲット顧客像: {main_target_audience_summary}",
                f"  - コア提供価値: {core_value_proposition}",
                f"  - ブランドボイス: {brand_voice_tone}",

                f"\n## 作成指示:",
                "  - **最重要**: 具体的なツイート案や戦術の羅列ではなく、より上位の「考え方」や「スタンス」といった方針を記述してください。",
                "  - この方針を読むことで、ユーザーが多様な投稿アイデアを発想できるような、「余白」と「深み」のある文章にしてください。",
                "  - 生成するテキストは、指定された要素の基本方針の本文のみとしてください。前置きや後書きは不要です。"
                "  - 具体や抽象どちらかによりすぎないよう意識してください。"
                "  - 格好いい言葉に頼らず本質的な内容を意識して生成してください"
            ]
            # ▲▲▲【ここまでが修正点】▲▲▲
            
            prompt = "\n".join(prompt_parts)

            try:
                config = genai_types.GenerateContentConfig(temperature=0.7)
                response = client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=config
                )
                draft_text = response.text.strip()
                if not draft_text:
                    raise Exception("AI response was empty.")

                generated_drafts[element_key] = draft_text
                print(f"    Draft for {element_key}: {draft_text[:70]}...")

            except Exception as e_gen:
                print(f"!!! Exception generating draft for {element_key}: {e_gen}")
                generated_drafts[element_key] = f"AIによる「{element_name}」のドラフト生成中にエラーが発生しました。"
                
        return jsonify(generated_drafts), 200

    except Exception as e:
        print(f"!!! Major exception in generate_account_base_policies_draft: {e}")
        traceback.print_exc()
        return jsonify({"message": "12の基本方針の生成中に予期せぬエラーが発生しました。", "error": str(e)}), 500



@app.route('/api/v1/products/<uuid:product_id>', methods=['PUT'])
@token_required
def update_product(product_id):
    user = getattr(g, 'user', None); data = request.json
    if not user: return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    if not data: return jsonify({"message": "Invalid request: No JSON data provided."}), 400
    allowed=['name','description','price','currency','target_audience','value_proposition']; payload={k:v for k,v in data.items() if k in allowed}
    if not payload: return jsonify({"message": "No valid fields for update."}), 400
    payload['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        res = supabase.table('products').update(payload).eq('id',product_id).eq('user_id',user_id).execute()
        if res.data: return jsonify(res.data[0])
        elif hasattr(res, 'error') and res.error: return jsonify({"message": "Error updating product", "error": str(res.error)}), 500
        check_exists = supabase.table('products').select('id').eq('id', product_id).eq('user_id', user_id).maybe_single().execute()
        if not check_exists.data: return jsonify({"message":"Product not found or access denied."}),404
        return jsonify({"message":"Product updated (no data returned by default, check DB)."}),200
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error updating product", "error": str(e)}), 500

@app.route('/api/v1/products/<uuid:product_id>', methods=['DELETE'])
@token_required
def delete_product(product_id):
    user = getattr(g, 'user', None)
    if not user: return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        check_exists = supabase.table('products').select('id').eq('id', product_id).eq('user_id', user_id).maybe_single().execute()
        if not check_exists.data: return jsonify({"message":"Product not found or access denied."}),404
        
        res = supabase.table('products').delete().eq('id',product_id).eq('user_id',user_id).execute()
        if hasattr(res,'error') and res.error: return jsonify({"message": "Error deleting product", "error": str(res.error)}),500
        return '',204
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error deleting product", "error": str(e)}),500

# --- ローンチ計画と教育戦略 API ---
@app.route('/api/v1/launches', methods=['POST'])
@token_required
def create_launch():
    user_id = g.user.id
    data = request.json
    
    # ★ フロントエンドからx_account_idを受け取る
    x_account_id = data.get('x_account_id')
    name = data.get('name')
    product_id = data.get('product_id')

    # ★ 必須項目のチェックを強化
    if not all([x_account_id, name, product_id]):
        return jsonify({"message": "x_account_id, name, product_idは必須です"}), 400

    try:
        new_l_data = {
            "user_id": user_id,
            "x_account_id": x_account_id, # ★ x_account_idを保存データに含める
            "product_id": product_id,
            "name": name,
            "description": data.get("description"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "goal": data.get("goal"),
            "status": data.get("status", "planning")
        }
        
        # (以降のロジックはほぼ同じですが、エラーハンドリングを少し改善)
        l_res = supabase.table('launches').insert(new_l_data, returning='representation').execute()
        
        if not l_res.data:
            raise Exception(l_res.error.message if hasattr(l_res, 'error') and l_res.error else "Failed to create launch")

        created_launch = l_res.data[0]

        # ローンチに対応するeducation_strategiesも作成
        strategy_data = {
            "launch_id": created_launch['id'],
            "user_id": user_id,
            "x_account_id": x_account_id # ★ こちらにもx_account_idを保存
        }
        s_res = supabase.table('education_strategies').insert(strategy_data).execute()

        if hasattr(s_res, 'error') and s_res.error:
             print(f"!!! Launch {created_launch['id']} created, but failed to create strategy: {s_res.error}")
             # 207 Multi-Status: ローンチは成功したが、一部失敗
             return jsonify({"message":"ローンチは作成されましたが、戦略シートの自動作成に失敗しました。", "launch":created_launch, "strategy_error":str(s_res.error)}), 207

        return jsonify(created_launch), 201
        
    except Exception as e:
        print(f"!!! Exception creating launch: {e}")
        traceback.print_exc()
        return jsonify({"message": "ローンチの作成中にエラーが発生しました", "error": str(e)}), 500




# app.py の get_launches 関数
@app.route('/api/v1/launches', methods=['GET'])
@token_required
def get_launches():
    user_id = g.user.id
    # ★ クエリパラメータからx_account_idを受け取る
    x_account_id = request.args.get('x_account_id')

    if not x_account_id:
        return jsonify({"message": "x_account_idが必要です"}), 400

    try:
        # ★ user_id と x_account_id の両方で絞り込む
        res = supabase.table('launches').select(
            "*, products:product_id(id, name)" # JOINの記法を修正
        ).eq('user_id', user_id).eq('x_account_id', x_account_id).order('created_at', desc=True).execute()

        return jsonify(res.data), 200
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ローンチの取得中にエラーが発生しました", "error": str(e)}), 500
    
@app.route('/api/v1/launches/<uuid:launch_id>/strategy', methods=['GET', 'PUT'])
@token_required
def handle_launch_strategy(launch_id):
    user_id = g.user.id
    try:
        # 1. ローンチ情報を取得し、所有権とx_account_idを確認
        launch_res = supabase.table('launches').select('*, products:product_id(name), x_accounts(id, x_username)').eq('id', launch_id).eq('user_id', user_id).maybe_single().execute()
        if not launch_res.data:
            return jsonify({"error": "Launch not found or access denied"}), 404
        
        launch_data = launch_res.data
        x_account_id = launch_data.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "This launch is not associated with any X account"}), 500

        # --- GETリクエスト ---
        if request.method == 'GET':
            # 2. ローンチ固有の戦略を取得
            strategy_res = supabase.table('education_strategies').select('*').eq('launch_id', launch_id).maybe_single().execute()
            
            # 3. Xアカウント全体の普遍的な戦略を取得
            account_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).maybe_single().execute()
            
            # 4. 必要な情報をまとめてフロントエンドに返す
            return jsonify({
                "launch_info": {
                    "id": launch_data['id'], "name": launch_data['name'],
                    "product_name": launch_data['products']['name'] if launch_data.get('products') else 'N/A',
                    "x_account_id": x_account_id,
                    "x_username": launch_data['x_accounts']['x_username'] if launch_data.get('x_accounts') else 'N/A'
                },
                "launch_strategy": strategy_res.data or {},
                "account_strategy": account_strategy_res.data or {}
            }), 200

        # --- PUTリクエスト ---
        if request.method == 'PUT':
            data = request.json
            data['launch_id'] = str(launch_id)
            data['user_id'] = user_id
            data['x_account_id'] = x_account_id
            data['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            res = supabase.table('education_strategies').upsert(data, on_conflict='launch_id').execute()
            if not res.data: raise Exception("Failed to update launch strategy")
            return jsonify(res.data[0]), 200

    except Exception as e:
        print(f"!!! EXCEPTION in handle_launch_strategy: {e}"); traceback.print_exc()
        return jsonify({"error": "An internal server error occurred", "details": str(e)}), 500

# app.py に追記

@app.route('/api/v1/launches/<uuid:launch_id>', methods=['DELETE'])
@token_required
def delete_launch(launch_id):
    user = getattr(g, 'user', None)
    if not user:
        return jsonify({"message": "Authentication error."}), 401
    user_id = user.id

    if not supabase:
        return jsonify({"message": "Supabase client not initialized!"}), 500

    print(f">>> DELETE /api/v1/launches/{launch_id} called by user_id: {user_id}")

    try:
        # 0. (任意だが推奨) 削除対象のローンチが本当にそのユーザーのものかを確認
        launch_to_delete_res = supabase.table('launches').select("id").eq('id', launch_id).eq('user_id', user_id).maybe_single().execute()
        if not launch_to_delete_res.data:
            print(f"!!! Launch {launch_id} not found or access denied for user {user_id} during delete.")
            return jsonify({"message": "Launch not found or access denied."}), 404

        # 1. 関連する教育戦略を削除 (もし外部キーでCASCADE DELETEが設定されていない場合)
        #    Supabaseで launches.id と education_strategies.launch_id がリレーションされ、
        #    ON DELETE CASCADE が設定されていれば、launches の削除時に自動で education_strategies も削除される。
        #    その場合は以下の education_strategies の削除処理は不要。
        #    ここでは、念のため手動で削除する例も示す（CASCADEが理想）。
        
        # strategy_delete_res = supabase.table('education_strategies').delete().eq('launch_id', launch_id).eq('user_id', user_id).execute()
        # if hasattr(strategy_delete_res, 'error') and strategy_delete_res.error:
        #     # ローンチ本体を削除する前に戦略削除でエラーが出た場合、どう扱うか検討。
        #     # ここではエラーを返し、ローンチ本体の削除は行わない。
        #     print(f"!!! Error deleting education strategy for launch {launch_id}: {strategy_delete_res.error}")
        #     return jsonify({"message": "Failed to delete associated education strategy.", "error": str(strategy_delete_res.error)}), 500
        # print(f"--- Associated education strategy for launch {launch_id} deleted (or did not exist).")

        # 2. ローンチ計画本体を削除
        #    ON DELETE CASCADE が設定されていれば、この操作だけで関連する education_strategies も削除される。
        delete_res = supabase.table('launches').delete().eq('id', launch_id).eq('user_id', user_id).execute()

        if hasattr(delete_res, 'error') and delete_res.error:
            print(f"!!! Supabase launch delete error for launch_id {launch_id}: {delete_res.error}")
            return jsonify({"message": "Error deleting launch", "error": str(delete_res.error)}), 500
        
        # delete().execute() の data は通常、削除されたレコードを含まないか、影響行数を示す。
        # エラーがないことをもって成功と判断する。
        # (delete_res.count で影響行数を確認できる場合がある)
        # if delete_res.data and len(delete_res.data) > 0: # または delete_res.count > 0
        #     print(f">>> Launch {launch_id} deleted successfully by user {user_id}.")
        #     return '', 204
        # else:
        #     # 実際には削除されたが data が空の場合もあるので、エラーがなければ成功とみなす
        #     print(f">>> Launch {launch_id} deletion processed for user {user_id}. Assuming success as no error reported.")
        #     return '', 204

        print(f">>> Launch {launch_id} deleted successfully (or was already gone) by user {user_id}.")
        return '', 204 # No Content

    except Exception as e:
        print(f"!!! Exception deleting launch {launch_id}: {e}")
        traceback.print_exc()
        return jsonify({"message": "An unexpected error occurred while deleting the launch", "error": str(e)}), 500



@app.route('/api/v1/launches/<uuid:launch_id>/generate-tweet', methods=['POST'])
@token_required
def generate_tweet_for_launch(launch_id):
    user = getattr(g, 'user', None); user_profile = getattr(g, 'profile', {})
    if not user: return jsonify({"message": "Auth error."}),401
    user_id = user.id
    
    if not supabase: return jsonify({"message": "Supabase client not init!"}),500
    
    current_text_model = get_current_ai_model(user_profile)
    if not current_text_model: return jsonify({"message":"Gemini model not initialized. Check API Key and model availability."}),500

    print(f">>> POST /api/v1/launches/{launch_id}/generate-tweet by user_id: {user_id}")
    try:
        launch_res = supabase.table('launches').select("*,products(name,description,value_proposition)").eq('id',launch_id).eq('user_id',user_id).maybe_single().execute()
        if not launch_res.data: return jsonify({"message":"Launch not found or access denied."}),404
        launch_info = launch_res.data
        
        product_data = launch_info.get('products')
        product_name = "N/A"
        product_value = "N/A"
        if isinstance(product_data, dict): 
            product_name = product_data.get('name','N/A')
            product_value = product_data.get('value_proposition','N/A')
        elif isinstance(product_data, list) and product_data: 
            product_name = product_data[0].get('name','N/A')
            product_value = product_data[0].get('value_proposition','N/A')

        strategy_res = supabase.table('education_strategies').select("*").eq('launch_id',launch_id).eq('user_id',user_id).maybe_single().execute()
        if not strategy_res.data: return jsonify({"message":"Education strategy for this launch not found."}),404
        strategy_info = strategy_res.data
        
        brand_voice = user_profile.get('brand_voice','プロフェッショナルかつ親しみやすいトーン')
        target_persona = user_profile.get('target_persona',strategy_info.get('target_customer_summary','特定のターゲット顧客'))
        
        request_data = request.json if request.is_json else {}
        purpose = request_data.get('purpose','このローンチに関する魅力的で汎用的な告知ツイート')
        
        prompt_parts = [
            "あなたは経験豊富なX(旧Twitter)マーケティングの専門家です。",
            f"以下の情報を元に、ユーザーエンゲージメント（いいね、リツイート、返信、クリックなど）を最大化することを目的とした、魅力的で具体的なXの投稿文案を1つ作成してください。",
            f"### 基本情報",
            f"- ブランドボイス（投稿のトーン）: {brand_voice}",
            f"- ターゲット顧客像: {target_persona}",
            f"- 今回のローンチ名: {launch_info.get('name','(ローンチ名未設定)')}",
            f"- 販売商品名: {product_name}",
            f"- 商品の主な提供価値: {product_value}",
            f"### 教育戦略のポイント（今回のツイートで特に意識する要素）:",
            f"- 目的の教育: {strategy_info.get('edu_s1_purpose','(未設定)')}", 
            f"- 問題点の教育: {strategy_info.get('edu_s3_problem','(未設定)')}", 
            f"- 手段の教育（解決策）: {strategy_info.get('edu_s4_solution','(未設定)')}",
            f"### ツイート作成指示",
            f"- このツイートの具体的な目的・テーマ: {purpose}",
            f"- 形式: 140字以内の日本語のツイート。ハッシュタグは3-4個程度で、関連性が高く効果的なものを選ぶこと。",
            f"- 内容: 読者の興味を引き、クリックや詳細確認などの次のアクションを促すような内容にすること。",
            f"- 絵文字: 文脈に合わせて効果的に1～3個使用すること。",
            f"- 禁止事項: 誇大広告、誤解を招く表現、不適切な言葉遣いは避けること。",
            f"提供された情報を最大限活用し、最高のツイート案を提案してください。"
        ]
        prompt="\n".join(filter(None,prompt_parts))
        print(f">>> Gemini Prompt for Launch Tweet (model: {current_text_model._model_name}):\n{prompt[:600]}...")
        
        ai_response=current_text_model.generate_content(prompt)
        generated_tweet_text=""
        try: generated_tweet_text = ai_response.text
        except Exception: pass 
        if not generated_tweet_text and hasattr(ai_response,'candidates') and ai_response.candidates: 
            generated_tweet_text = "".join([p.text for c in ai_response.candidates for p in c.content.parts if hasattr(p,'text')])
        
        if not generated_tweet_text:
            feedback_message = "AIからの応答が空でした。"
            if hasattr(ai_response,'prompt_feedback'): 
                feedback_message = f"AI応答エラー: {ai_response.prompt_feedback}"
                print(f"!!! AI prompt feedback: {ai_response.prompt_feedback}")
            return jsonify({"message": feedback_message, "generated_tweet": None}), 500

        print(f">>> AI Generated Launch Tweet: {generated_tweet_text.strip()}")
        return jsonify({"generated_tweet": generated_tweet_text.strip()})
        
    except Exception as e: 
        print(f"!!! Exception in generate_tweet_for_launch: {e}")
        traceback.print_exc();
        return jsonify({"message":"Error generating tweet for launch","error":str(e)}),500

# app.py 内の chat_education_element 関数を以下の最終版で置き換える

@app.route('/api/v1/chat/education-element', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def chat_education_element():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400
        
        launch_id = data.get('launch_id')
        element_key = data.get('element_key')
        chat_history_frontend = data.get('chat_history', [])
        current_user_message_text = data.get('current_user_message')
        
        if not all([launch_id, element_key, current_user_message_text]):
            return jsonify({"error": "launch_id, element_key, current_user_messageは必須です。"}), 400
            
    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # 1. ローンチ情報、商品情報、XアカウントIDを取得
        launch_res = supabase.table('launches').select("*, products(name, value_proposition), x_account_id").eq('id', launch_id).eq('user_id', user_id).maybe_single().execute()
        if not launch_res.data:
            return jsonify({"message": "Launch not found or access denied."}), 404
        launch_info = launch_res.data
        x_account_id = launch_info.get('x_account_id')
        if not x_account_id:
            return jsonify({"message": "This launch is not linked to any X account."}), 500
            
        product_info = launch_info.get('products', {})

        # 2. ローンチ固有の戦略シートと、アカウント全体の普遍的戦略を取得
        launch_strategy_res = supabase.table('education_strategies').select(element_key).eq('launch_id', launch_id).eq('user_id', user_id).maybe_single().execute()
        launch_strategy = launch_strategy_res.data if launch_strategy_res else {}
        
        account_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = account_strategy_res.data if account_strategy_res else {}
        
        # 3. プロンプトで使う情報を準備
        brand_voice_detail = account_strategy.get('brand_voice_detail', {})
        brand_voice = brand_voice_detail.get('tone') if isinstance(brand_voice_detail, dict) else 'プロフェッショナル'
        target_persona_profile = launch_strategy.get('target_customer_summary', 'この商品を必要としている見込み客')
        
        element_map = {
            "product_analysis_summary":"商品分析の要点", "target_customer_summary":"ターゲット顧客分析の要点",
            "edu_s1_purpose":"目的の教育", "edu_s2_trust":"信用の教育", "edu_s3_problem":"問題点の教育", 
            "edu_s4_solution":"手段の教育", "edu_s5_investment":"投資の教育", "edu_s6_action":"行動の教育", 
            "edu_r1_engagement_hook":"読む・見る教育", "edu_r2_repetition":"何度も聞く教育", 
            "edu_r3_change_mindset":"変化の教育", "edu_r4_receptiveness":"素直の教育", 
            "edu_r5_output_encouragement":"アウトプットの教育", "edu_r6_baseline_shift":"基準値/覚悟の教育"
        }
        element_name_jp = element_map.get(element_key, element_key)
        current_element_memo = launch_strategy.get(element_key, "")

        # 4. システム指示（プロンプト）を組み立てる（改善版）
        system_instruction_parts = [
            f"あなたは、クライアントの思考を深掘りする戦略コンサルタントです。",
            f"あなたの役割は、単に質問に答えるのではなく、クライアントが『{element_name_jp}』という教育要素について、より戦略的でパワフルなアイデアを自ら生み出せるように、対話を通じて導くことです。",
            f"\n## この対話の全体像:",
            f"  - ローンチ名: {launch_info.get('name', '(名称未設定)')}",
            f"  - 対象商品: {product_info.get('name', '(商品名未設定)')}",
            f"  - ブランドボイス: {brand_voice}",
            f"  - ターゲット顧客: {target_persona_profile}",
            
            f"\n## 現在のクライアントの思考:",
            f"『{element_name_jp}』について、クライアントは現在「{current_element_memo if current_element_memo else '(まだ何も考えていない)'}」という状態です。",
            
            f"\n## あなたの対話スタイル:",
            "  - 常にクライアントを肯定し、共感の姿勢を示してください。",
            "  - 抽象的なアドバイスは避け、「では、その場合、ターゲット顧客は“心の中で”何と言っていると思いますか？」や「そのアイデアを、もっと読者の五感に訴える言葉で表現するとどうなりますか？」といった、思考を一段階深めるための具体的な質問を投げかけてください。",
            "  - 対話の最後には、必ずクライアントが次に取り組むべき具体的なアクションを1つ提示し、対話を締めくくってください。",
            "  - 全体を通して、クライアントに寄り添いながらも、プロとして頼りになる、知的で落ち着いた口調でお願いします。"
        ]
        system_instruction_text = "\n".join(system_instruction_parts)
        
        # 5. 新しいSDKの作法でチャットセッションを開始・継続する
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        
        chat_session = client.chats.create(
            model=model_id,
            history=chat_history_frontend,
            system_instruction=system_instruction_text
        )

        print(f">>> Sending to Gemini Chat (New SDK / {element_name_jp}): User says: {current_user_message_text[:100]}...")
        
        response = chat_session.send_message(message=current_user_message_text)
        
        ai_response_text = response.text
        if not ai_response_text:
            raise Exception("AIからの応答テキストが空でした。")

        print(f">>> Gemini Chat AI Response: {ai_response_text.strip()[:100]}...")
        return jsonify({"ai_message": ai_response_text.strip()})
        
    except Exception as e: 
        print(f"!!! Exception in chat_education_element: {e}")
        traceback.print_exc()
        return jsonify({"message":"AIとのチャット処理中にエラーが発生しました", "error":str(e)}), 500

#  generate_strategy_draft

@app.route('/api/v1/launches/<uuid:launch_id>/strategy/generate-draft', methods=['POST'])
@token_required
def generate_strategy_draft(launch_id):
    user = getattr(g, 'user', None) # userはtoken_requiredでセットされる
    user_profile = getattr(g, 'profile', {}) # token_requiredで新しい情報も入っているはず
    
    if not user: return jsonify({"message": "Authentication error."}), 401 #念のため
    user_id = user.id # ユーザーIDも取得しておく

    if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
    
    current_text_model = get_current_ai_model(user_profile) 
    if not current_text_model: return jsonify({"message":"Gemini model not initialized. Check API Key."}),500

    print(f">>> POST /api/v1/launches/{launch_id}/strategy/generate-draft by user_id: {user_id}")
    try:
        launch_res = supabase.table('launches').select("*, products(name, description, value_proposition)").eq('id', launch_id).eq('user_id', user_id).maybe_single().execute()
        if not launch_res.data: return jsonify({"message": "Launch not found or access denied."}), 404
        launch_info = launch_res.data
        
        product_data = launch_info.get('products')
        product_info = product_data if isinstance(product_data, dict) else (product_data[0] if isinstance(product_data, list) and product_data else {})

        # --- ▼ここから user_profile からアカウント戦略情報を取得し、プロンプト用に整形 ▼ ---
        account_purpose_profile = user_profile.get('account_purpose', 'このアカウントの明確な目的は設定されていません。')
        
        main_target_audience_data = user_profile.get('main_target_audience') # これはJSONB (リストや辞書) の可能性がある
        if isinstance(main_target_audience_data, list) and main_target_audience_data: # 簡単な例: 最初のペルソナの名前と悩み
            persona_sample = main_target_audience_data[0]
            target_audience_str = f"主なターゲットは「{persona_sample.get('name', '未設定の名前')}」({persona_sample.get('age', '年齢不明')})で、悩みは「{persona_sample.get('悩み', '未設定の悩み')}」などです。"
        elif isinstance(main_target_audience_data, dict): # 単一の辞書の場合
             target_audience_str = f"主なターゲットは「{main_target_audience_data.get('name', '未設定の名前')}」で、悩みは「{main_target_audience_data.get('悩み', '未設定の悩み')}」などです。"
        else:
            target_audience_str = user_profile.get('target_persona', 'この商品やサービスに価値を感じるであろう一般的な見込み客') # フォールバック

        core_value_proposition_profile = user_profile.get('core_value_proposition', 'アカウント全体の明確な提供価値は設定されていません。')
        
        brand_voice_detail_data = user_profile.get('brand_voice_detail') # JSONBの可能性がある
        if isinstance(brand_voice_detail_data, dict):
            brand_voice_str = f"トーンは「{brand_voice_detail_data.get('tone', '未設定')}」。重要キーワード: {brand_voice_detail_data.get('keywords', [])}。NGワード: {brand_voice_detail_data.get('ng_words', [])}。"
        else:
            brand_voice_str = user_profile.get('brand_voice', 'プロフェッショナルで、かつ親しみやすいトーン') # フォールバック
        # --- ▲ user_profile からのアカウント戦略情報取得と整形ここまで ▲ ---

        strategy_elements_definition = [
            {'key': 'product_analysis_summary', 'name': '商品分析の要点', 'desc': 'このローンチにおける商品の強み、弱み、ユニークな特徴、競合との比較など'},
            {'key': 'target_customer_summary', 'name': 'ターゲット顧客分析の要点', 'desc': 'このローンチで狙う顧客層、具体的なペルソナ、悩み、欲求、価値観など'},
            {'key': 'edu_s1_purpose', 'name': '目的の教育', 'desc': '顧客が目指すべき理想の未来、このローンチ/商品で何が得られるか'},
            # ... (他の要素の定義は既存のまま) ...
            {'key': 'edu_r6_baseline_shift', 'name': '基準値の教育／覚悟の教育', 'desc': '顧客の常識や基準値をどう変えるか、行動への覚悟をどう促すか'}
        ]
        generated_drafts = {}
        for element in strategy_elements_definition:
            element_key = element['key']
            element_name_jp = element['name']
            element_desc = element['desc']
            
            base_policy_key = f"{element_key}_base" # 例: "edu_s1_purpose_base"
            element_base_policy = user_profile.get(base_policy_key, 'この要素に関するアカウントの基本方針は特に設定されていません。まずはこちらを検討してください。')

            prompt = f"""あなたは経験豊富なマーケティング戦略プランナーです。
以下の情報と指示に基づき、「{element_name_jp}」という戦略要素に関する簡潔で具体的な初期ドラフト（箇条書き2～3点、または100～150字程度の説明文）を作成してください。これは後でユーザーが詳細を詰めるためのたたき台となります。

# アカウント全体の戦略方針 (最重要参考情報):
* アカウントの基本理念・パーパス: {account_purpose_profile}
* 主要ターゲット顧客像（概要）: {target_audience_str}
* アカウントのコアとなる提供価値: {core_value_proposition_profile}
* ブランドボイス・キャラクター（基本設定）: {brand_voice_str}
* 今回の戦略要素「{element_name_jp}」に関するアカウントの基本方針: {element_base_policy}

# 今回のローンチ（販売キャンペーン）について:
* ローンチ名: {launch_info.get('name', '(ローンチ名未設定)')}
* ローンチの主な目標: {launch_info.get('goal', '(目標未設定)')}

# 今回のローンチで販売する商品について:
* 商品名: {product_info.get('name', '(商品名未設定)')}
* 商品の主な提供価値・ベネフィット: {product_info.get('value_proposition', '(提供価値未設定)')}
* 商品の簡単な説明: {product_info.get('description', '(商品説明未設定)')}

# 現在ドラフト作成中の戦略要素:
* 要素名: {element_name_jp}
* この要素の一般的な目的・意味: {element_desc}

# 作成指示:
1.  上記の「アカウント全体の戦略方針」、特に「{element_name_jp}に関するアカウントの基本方針」を最も重要な指針としてください。
2.  その上で、「今回のローンチと商品情報」に合わせて、このローンチにおける具体的な「{element_name_jp}」の戦略ドラフトを記述してください。
3.  内容は、ユーザーがこのドラフトを見て「なるほど、ここからこう展開していこう」と考えられるような、具体的で示唆に富むものにしてください。
4.  形式は、箇条書きで2～3つの主要ポイントを挙げるか、あるいは100～150字程度の簡潔な説明文で記述してください。
5.  このローンチと商品に特化した、実践的な内容にしてください。一般的な理想論ではなく、具体的なアクションやメッセージの方向性を示してください。
"""
            print(f"\n--- Generating draft for: {element_key} ('{element_name_jp}') ---")
            # print(f"Prompt for {element_key}:\n{prompt[:300]}...\n...\n{prompt[-300:]}") # デバッグ用にプロンプト一部表示
            try:
                ai_response = current_text_model.generate_content(prompt)
                draft_text = ""
                try: 
                    draft_text = ai_response.text
                except Exception: # FOR SAFETY
                    pass 
                if not draft_text and hasattr(ai_response,'candidates') and ai_response.candidates: 
                    draft_text = "".join([p.text for c in ai_response.candidates for p in c.content.parts if hasattr(p,'text')])
                
                if not draft_text and hasattr(ai_response,'prompt_feedback'): 
                    feedback = ai_response.prompt_feedback
                    print(f"!!! AI prompt feedback for {element_key}: {feedback}")
                    draft_text = f"AIによる「{element_name_jp}」のドラフト生成に失敗しました (詳細: {feedback})"
                elif not draft_text:
                    draft_text = f"AIによる「{element_name_jp}」のドラフト生成結果が空でした。"

                generated_drafts[element_key] = draft_text.strip()
                print(f">>> Draft for {element_key}: {draft_text.strip()[:100]}...")
            except Exception as e_gen: 
                print(f"!!! Exception generating draft for {element_key}: {e_gen}")
                traceback.print_exc()
                generated_drafts[element_key] = f"AIによる「{element_name_jp}」のドラフト生成中にエラーが発生しました: {str(e_gen)}"
        
        return jsonify(generated_drafts)
    except Exception as e: 
        print(f"!!! Exception in generate_strategy_draft for launch {launch_id}: {e}")
        traceback.print_exc()
        return jsonify({"message": "Error generating strategy draft", "error": str(e)}), 500

# 他のAI関連API (generate_tweet_for_launch, chat_education_element) も同様に、
# user_profile (g.profile) から新しいアカウント戦略情報を取得し、
# プロンプトの内容に反映させる修正を行ってください。

# --- ツイート管理API ---
# in sakuya11k/eds-project/eds-project-feature-account-strategy-page/backend/app.py

@app.route('/api/v1/tweets', methods=['POST'])
@token_required
def save_tweet_draft():
    user_id = g.user.id
    data = request.json
    if not data: return jsonify({"message": "Invalid request: No JSON data provided."}), 400
    
    # --- ▼ここからが修正箇所▼ ---
    x_account_id = data.get('x_account_id')
    content = data.get('content')
    if not all([x_account_id, content]):
        return jsonify({"message": "x_account_idとcontentは必須です。"}), 400
    # --- ▲ここまでが修正箇所▲ ---

    status = data.get('status', 'draft')
    scheduled_at_str = data.get('scheduled_at')
    edu_el_key = data.get('education_element_key')
    launch_id_fk = data.get('launch_id')
    notes_int = data.get('notes_internal')
    image_urls = data.get('image_urls', []) # 元のロジックを維持

    # (日付変換処理なども元のまま)
    scheduled_at_ts = None
    if scheduled_at_str:
        try:
            # ... (元の日付変換ロジック)
            dt_obj_utc = datetime.datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
            scheduled_at_ts = dt_obj_utc.isoformat()
        except ValueError:
            return jsonify({"message": f"Invalid scheduled_at format: {scheduled_at_str}"}), 400
    
    try:
        new_tweet_data = {
            "user_id": user_id, 
            "x_account_id": x_account_id, # ★ x_account_idを追加
            "content": content, 
            "status": status, 
            "scheduled_at": scheduled_at_ts, 
            "education_element_key": edu_el_key, 
            "launch_id": launch_id_fk, 
            "notes_internal": notes_int,
            "image_urls": image_urls # ★ 元の画像URL処理を維持
        }
        
        res = supabase.table('tweets').insert(new_tweet_data, returning="representation").execute()
        if not res.data: raise Exception(res.error.message if res.error else "Failed to save tweet")
        return jsonify(res.data[0]), 201

    except Exception as e:
        print(f"!!! Tweet draft save exception: {e}"); traceback.print_exc()
        return jsonify({"message": "ツイートの保存中にエラーが発生しました", "error": str(e)}), 500

# --- ★ ここから予約投稿実行APIを追加 ★ ---
# sakuya11k/eds-project/eds-project-feature-account-strategy-page/backend/app.py

# app.py 内の execute_scheduled_tweets 関数を、以下のコードで完全に置き換えてください

@app.route('/api/v1/tweets/execute-scheduled', methods=['POST'])
@app.route('/api/v1/tweets/execute-scheduled/', methods=['POST'])
def execute_scheduled_tweets():
    if CRON_JOB_SECRET and request.headers.get('Authorization') != f"Bearer {CRON_JOB_SECRET}":
        print("!!! Unauthorized attempt to execute scheduled tweets.")
        return jsonify({"message": "Unauthorized"}), 401
    
    print(">>> POST /api/v1/tweets/execute-scheduled called")
    if not supabase:
        print("!!! Supabase client not initialized in execute_scheduled_tweets")
        return jsonify({"message": "Supabase client not initialized!"}), 500

    successful_posts = 0
    failed_posts = 0
    processed_tweets = []

    try:
        now_utc_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # x_accountsテーブルをJOINして認証情報を取得
        scheduled_tweets_res = supabase.table('tweets').select(
            '*, x_account:x_account_id(*)'
        ).eq('status', 'scheduled').lte('scheduled_at', now_utc_str).execute()

        if hasattr(scheduled_tweets_res, 'error') and scheduled_tweets_res.error:
            raise Exception(f"Error fetching scheduled tweets: {scheduled_tweets_res.error}")

        if not scheduled_tweets_res.data:
            print("--- No scheduled tweets to post at this time.")
            return jsonify({"message": "No scheduled tweets to post at this time.", "processed_count": 0}), 200

        tweets_to_process = scheduled_tweets_res.data
        print(f">>> Found {len(tweets_to_process)} scheduled tweets to process.")

        for tweet_data in tweets_to_process:
            tweet_id = tweet_data.get('id')
            content = tweet_data.get('content')
            image_urls = tweet_data.get('image_urls', []) # 画像URLリストを取得
            x_account_data = tweet_data.get('x_account')

            if not x_account_data:
                error_msg = f"X Account data not found for tweet ID {tweet_id}."
                print(f"--- {error_msg}")
                supabase.table('tweets').update({"status": "error", "error_message": error_msg}).eq('id', tweet_id).execute()
                failed_posts += 1
                continue

            try:
                # 認証情報を復号
                api_key = EncryptionManager.decrypt(x_account_data.get('api_key_encrypted'))
                api_key_secret = EncryptionManager.decrypt(x_account_data.get('api_key_secret_encrypted'))
                access_token = EncryptionManager.decrypt(x_account_data.get('access_token_encrypted'))
                access_token_secret = EncryptionManager.decrypt(x_account_data.get('access_token_secret_encrypted'))

                if not all([api_key, api_key_secret, access_token, access_token_secret]):
                    raise ValueError("X API credentials incomplete in the x_accounts table.")

                # ▼▼▼【メディアアップロード処理】▼▼▼
                media_ids = []
                if image_urls and isinstance(image_urls, list):
                    # メディアアップロードにはv1.1のAPIクライアントが必要
                    auth_v1 = tweepy.OAuth1UserHandler(api_key, api_key_secret, access_token, access_token_secret)
                    api_v1 = tweepy.API(auth_v1)
                    
                    for url in image_urls[:4]: # Twitter APIは最大4枚まで
                        tmp_filename = None
                        try:
                            # URLから画像をダウンロードして一時ファイルに保存
                            response = requests.get(url, stream=True)
                            response.raise_for_status()
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                tmp.write(response.content)
                                tmp_filename = tmp.name
                            
                            # 一時ファイルをアップロード
                            print(f"--- Uploading media for tweet {tweet_id} from {url}...")
                            media = api_v1.media_upload(filename=tmp_filename)
                            media_ids.append(media.media_id_string)
                            print(f"--- Media uploaded, media_id: {media.media_id_string}")

                        finally:
                            # 一時ファイルを削除
                            if tmp_filename and os.path.exists(tmp_filename):
                                os.remove(tmp_filename)
                # ▲▲▲【メディアアップロード処理ここまで】▲▲▲

                # ツイート投稿にはv2のAPIクライアントを使用
                client_v2 = tweepy.Client(
                    consumer_key=api_key, consumer_secret=api_key_secret,
                    access_token=access_token, access_token_secret=access_token_secret
                )
                
                # メディアIDを付けてツイート
                created_x_tweet_response = client_v2.create_tweet(
                    text=content,
                    media_ids=media_ids if media_ids else None
                )
                x_tweet_id_str = created_x_tweet_response.data.get('id')
                
                # 成功時のDB更新
                update_payload = {"status": "posted", "posted_at": now_utc_str, "x_tweet_id": x_tweet_id_str, "error_message": None}
                supabase.table('tweets').update(update_payload).eq('id', tweet_id).execute()
                successful_posts += 1
                processed_tweets.append({"id": tweet_id, "status": "posted", "x_tweet_id": x_tweet_id_str})

            except Exception as e_post:
                # 投稿失敗時のDB更新
                error_message = f"Post Error: {str(e_post)}"
                print(f"!!! Error posting tweet ID {tweet_id}: {error_message}")
                traceback.print_exc()
                supabase.table('tweets').update({"status": "error", "error_message": error_message}).eq('id', tweet_id).execute()
                failed_posts += 1
                processed_tweets.append({"id": tweet_id, "status": "error", "reason": error_message})
        
        print(f">>> Scheduled tweets processing finished. Success: {successful_posts}, Failed: {failed_posts}")
        return jsonify({
            "message": "Scheduled tweets processing finished.",
            "successful_posts": successful_posts,
            "failed_posts": failed_posts,
            "processed_tweets": processed_tweets
        }), 200

    except Exception as e:
        print(f"!!! Major exception in execute_scheduled_tweets: {e}")
        traceback.print_exc()
        return jsonify({"message": "An unexpected error occurred during scheduled tweet processing.", "error": str(e)}), 500



# [GET] ツイート一覧を取得するAPI
@app.route('/api/v1/tweets', methods=['GET'])
@token_required
def get_tweets():
    user_id = g.user.id
    x_account_id = request.args.get('x_account_id')
    if not x_account_id:
        return jsonify({"error": "x_account_id is required"}), 400
    try:
        query = supabase.table('tweets').select("*").eq('user_id', user_id).eq('x_account_id', x_account_id)
        
        status_filter = request.args.get('status')
        if status_filter:
            query = query.eq('status', status_filter)
        
        launch_id_filter = request.args.get('launch_id')
        if launch_id_filter:
            query = query.eq('launch_id', launch_id_filter)
        
        response = query.order('created_at', desc=True).execute()
        
        # 最新のsupabase-pyでは、エラーは例外としてスローされるため、
        # .execute()が成功すれば、そのままデータを返すのが最も安全でシンプル。
        return jsonify(response.data)

    except Exception as e:
        print(f"!!! Tweets fetch exception: {e}"); traceback.print_exc()
        # APIExceptionなど、Supabase固有のエラーをより詳細に返すことも可能
        error_message = str(e.args[0]) if e.args else str(e)
        return jsonify({"error": "ツイートの取得中にエラーが発生しました", "details": error_message}), 500

# [POST] 新規ツイートを作成するAPI
@app.route('/api/v1/tweets', methods=['POST'])
@token_required
def create_tweet():
    user_id = g.user.id
    try:
        data = request.json
        if not data: return jsonify({"error": "Invalid request: No JSON data provided."}), 400

        x_account_id = data.get('x_account_id')
        content = data.get('content')
        if not all([x_account_id, content]):
            return jsonify({"error": "x_account_id and content are required"}), 400

        scheduled_at_str = data.get('scheduled_at')
        scheduled_at_ts = None
        if scheduled_at_str:
            try:
                dt_obj_utc = datetime.datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
                scheduled_at_ts = dt_obj_utc.isoformat()
            except (ValueError, TypeError):
                return jsonify({"error": f"Invalid scheduled_at format: {scheduled_at_str}"}), 400
                
        payload = {
            "user_id": user_id,
            "x_account_id": x_account_id,
            "content": content,
            "status": data.get('status', 'draft'),
            "scheduled_at": scheduled_at_ts,
            "image_urls": data.get('image_urls', []),
            "education_element_key": data.get('education_element_key'),
            "launch_id": data.get('launch_id'),
            "notes_internal": data.get('notes_internal'),
        }
        response = supabase.table('tweets').insert(payload, returning="representation").execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        print(f"!!! Tweet creation exception: {e}"); traceback.print_exc()
        error_message = str(e.args[0]) if e.args else str(e)
        return jsonify({"error": "Failed to create tweet", "details": error_message}), 500

# [PUT] 既存ツイートを更新するAPI
@app.route('/api/v1/tweets/<uuid:tweet_id>', methods=['PUT'])
@token_required
def update_tweet(tweet_id):
    user_id = g.user.id
    try:
        data = request.json
        if not data: return jsonify({"error": "Invalid request: No JSON data provided."}), 400
            
        # 所有権の確認
        owner_check_res = supabase.table('tweets').select('id').eq('id', tweet_id).eq('user_id', user_id).maybe_single().execute()
        if not owner_check_res.data: return jsonify({"error": "Tweet not found or access denied"}), 404

        # 日付形式の変換 (もしあれば)
        if 'scheduled_at' in data and data['scheduled_at']:
            try:
                dt_obj_utc = datetime.datetime.fromisoformat(data['scheduled_at'].replace('Z', '+00:00'))
                data['scheduled_at'] = dt_obj_utc.isoformat()
            except (ValueError, TypeError):
                 data['scheduled_at'] = None
        
        data['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 更新対象外のキーを念のため削除
        data.pop('id', None)
        data.pop('created_at', None)
        data.pop('user_id', None)

        response = supabase.table('tweets').update(data).eq('id', tweet_id).execute()
        
        # Supabase v2のupdateはデフォルトでデータを返さないので、再取得して返す
        updated_tweet_res = supabase.table('tweets').select('*').eq('id', tweet_id).single().execute()
        return jsonify(updated_tweet_res.data)

    except Exception as e:
        print(f"!!! Tweet update exception: {e}"); traceback.print_exc()
        error_message = str(e.args[0]) if e.args else str(e)
        return jsonify({"error": "Failed to update tweet", "details": error_message}), 500

# [DELETE] 既存ツイートを削除するAPI
@app.route('/api/v1/tweets/<uuid:tweet_id>', methods=['DELETE'])
@token_required
def delete_tweet(tweet_id):
    user_id = g.user.id
    try:
        # 所有権の確認
        owner_check_res = supabase.table('tweets').select('id').eq('id', tweet_id).eq('user_id', user_id).maybe_single().execute()
        if not owner_check_res.data: return jsonify({"error": "Tweet not found or access denied"}), 404

        supabase.table('tweets').delete().eq('id', tweet_id).execute()
        return ('', 204) # 成功時はNo Content
    except Exception as e:
        print(f"!!! Tweet deletion exception: {e}"); traceback.print_exc()
        error_message = str(e.args[0]) if e.args else str(e)
        return jsonify({"error": "Failed to delete tweet", "details": error_message}), 500

# [POST] ツイートを即時投稿するAPI
@app.route('/api/v1/tweets/<uuid:tweet_id>/post-now', methods=['POST'])
@token_required
def post_tweet_now_api(tweet_id):
    user_id = g.user.id
    try:
        # 1. ツイート情報と、それに紐づくXアカウント情報をJOINして取得
        tweet_res = supabase.table('tweets').select('*, x_account:x_account_id(*)').eq('id', tweet_id).eq('user_id', user_id).single().execute()
        tweet_data = tweet_res.data
        
        if not tweet_data: return jsonify({"error": "Tweet not found"}), 404
        
        content = tweet_data.get('content')
        image_urls = tweet_data.get('image_urls', [])
        x_account_data = tweet_data.get('x_account')

        if not x_account_data: return jsonify({"error": "X Account credentials for this tweet not found"}), 404

        # 2. 認証情報を復号
        api_key = EncryptionManager.decrypt(x_account_data.get('api_key_encrypted'))
        api_key_secret = EncryptionManager.decrypt(x_account_data.get('api_key_secret_encrypted'))
        access_token = EncryptionManager.decrypt(x_account_data.get('access_token_encrypted'))
        access_token_secret = EncryptionManager.decrypt(x_account_data.get('access_token_secret_encrypted'))

        if not all([api_key, api_key_secret, access_token, access_token_secret]):
            return jsonify({"error": "X API credentials are not fully configured for this account"}), 500

        # 3. Tweepyクライアント初期化
        client_v2 = tweepy.Client(consumer_key=api_key, consumer_secret=api_key_secret, access_token=access_token, access_token_secret=access_token_secret)
        auth_v1 = tweepy.OAuth1UserHandler(api_key, api_key_secret, access_token, access_token_secret)
        api_v1 = tweepy.API(auth_v1)

        # 4. メディアアップロード処理
        media_ids = []
        if image_urls:
            import requests, tempfile, os
            for url in image_urls:
                tmp_filename = None
                try:
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                        tmp.write(response.content)
                        tmp_filename = tmp.name
                    media = api_v1.media_upload(filename=tmp_filename)
                    media_ids.append(media.media_id_string)
                finally:
                    if tmp_filename and os.path.exists(tmp_filename): os.remove(tmp_filename)
        
        # 5. ツイート投稿
        created_x_tweet = client_v2.create_tweet(text=content, media_ids=media_ids if media_ids else None)
        x_tweet_id_str = created_x_tweet.data.get('id')

        # 6. DBのステータス更新
        update_payload = { "status": "posted", "posted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "x_tweet_id": x_tweet_id_str, "error_message": None }
        supabase.table('tweets').update(update_payload).eq('id', tweet_id).execute()
        
        return jsonify({"message": "Tweet posted successfully!", "x_tweet_id": x_tweet_id_str}), 200

    except Exception as e:
        print(f"!!! Post tweet now exception: {e}"); traceback.print_exc()
        error_message = str(e.args[0]) if e.args else str(e)
        supabase.table('tweets').update({"status": "error", "error_message": error_message}).eq('id', tweet_id).execute()
        return jsonify({"error": "Failed to post tweet", "details": error_message}), 500


# 『心理』の資料内容を別の変数として定義
PSYCHOLOGY_TECHNIQUES = {
    "edu_s1": "関連する心理技術:\n- **価値再定義**: テーマの価値を『単なるスキル』から『理想の人生への切符』のように再定義し、魅力を伝える。\n- **成功ロードマップ**: 成果が出るまでの手順を具体的に見せ、『これなら自分にもできそう！』という感覚を抱かせる。\n- **ストーリー教育**: 感情を動かすストーリーで『自分もこうなりたい』と思わせる。",
    "edu_s2": "関連する心理技術:\n- **両面提示/自己不利益**: メリットだけでなくデメリットや自身の失敗も語り、誠実さ・信頼性を示す。\n- **反論処理**: 読者が抱きそうな疑問に先回りして回答し、客観性を示す。\n- **第三者の意見/権威性**: 『お客様の声』や実績を引用し、信頼を補強する。",
    "edu_s3": "関連する心理技術:\n- **仮想敵/二項対立**: 『成功する人 vs 失敗する人』のような対立軸で、『このままではマズい』という危機感を煽る。\n- **事例で動かす**: 大げさな数字より、一人の悲劇的な『事例』を深く掘り下げ、リアルな恐怖を感じさせる。",
    "edu_s4": "関連する心理技術:\n- **思考停止シンプル**: 『色々考えず、これだけやってればOK』と選択肢を奪い、迷いを断ち切る。\n- **ロールモデル提示**: 『〇〇さんのように真似するだけ』と具体的なモデルを示し、行動を簡略化する。\n- **優越感/錯覚の利用**: 『ほとんどの人が知らない裏技』と特別な情報であることを匂わせ、価値を錯覚させる。",
    "edu_s5": "関連する心理技術:\n- **マネーシェア**: 『お金の使い方が人生を決める』という価値観を繰り返し伝え、自己投資への意識を高める。\n- **錯覚利用**: 『投資しろ』と直接言わず、『成功者は〇〇にお金を使う』と周辺情報から重要性を悟らせる。\n- **成功体験の約束**: 『これを学ぶと、まず〇〇という小さな成功が手に入ります』と投資対効果を予感させる。",
    "edu_s6": "関連する心理技術:\n- **小さなコミットメント**: 『まずは「やる」とリプするだけ』のように、誰でもできる行動を促し、次の行動に繋げる。\n- **ラベリング/期待感**: 『あなたならできる』『私の読者は行動力が高い』と期待をかけ、その気にさせる。\n- **BYAF(自己選択)**: 『やるかやらないかは自由です』と選択を委ね、逆に当事者意識で行動させる。",
    "edu_r1": "関連する心理技術:\n- **興味づけ**: 有益なノウハウや波乱万丈なストーリーを冒頭で匂わせ、続きを読む気にさせる。\n- **優越感フック**: 『この情報を知ってるだけで上位1%』と優越感を刺激し、読まずにはいられなくする。",
    "edu_r2": "関連する心理技術:\n- **反復/時間分散**: 同じメッセージを1〜2週間かけて角度を変えながら繰り返し伝え、無意識に刷り込む。\n- **マインドシェア**: 様々な切り口でメッセージに触れさせ、読者の頭の中の占有率を高める。",
    "edu_r3": "関連する心理技術:\n- **顧客肯定**: まず現状を肯定してから変化を促し、抵抗感を和らげる。\n- **期待感の注入**: 『あなたならこの壁を乗り越えられる』と信じ込ませ、自己効力感を高める。\n- **ストーリーテリング**: 変化を乗り越えた物語で、変化の先にある未来を疑似体験させる。",
    "edu_r4": "関連する心理技術:\n- **仮想敵（自己流）批判**: 『自己流で時間を溶かした人の末路』を語り、素直に学ぶことの重要性を間接的に伝える。\n- **権威性による説得**: 実績を示した上で『遠回りしたくないなら、素直が一番』と語り、認知を歪める。",
    "edu_r5": "関連する心理技術:\n- **成功体験の演出**: アウトプットに反応（いいね、リプ）することで小さな成功体験を与え、行動を強化する。\n- **共同体意識の醸成**: 『みんなでアウトプットしよう』と呼びかけ、集団の力で行動を促す。\n- **ラベリング**: 『アウトプットするあなたは優秀』とラベルを貼り、行動を自然に促す。",
    "edu_r6": "関連する心理技術:\n- **基準値の比較**: 『凡人は〇〇。でも、突き抜ける人は△△』と圧倒的な差を見せつけ、常識を破壊する。\n- **優越感の刺激**: 『我々はここまでやる。だから勝てる』と、高い基準値を持つこと自体に優越感を感じさせる。\n- **権威の背中見せ**: 自身の異常な行動量を語り、『この世界ではこれが普通』と読者の認知をバグらせる。"
}

#generate_educational_tweet

@app.route('/api/v1/educational-tweets/generate', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def generate_educational_tweet():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON request"}), 400

        x_account_id = data.get('x_account_id')
        education_element_key = data.get('education_element_key')
        theme = data.get('theme')

        if not all([x_account_id, education_element_key, theme]):
            return jsonify({"error": "x_account_id, education_element_key, themeは必須です"}), 400

    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # 1. 戦略情報を取得
        account_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = account_strategy_res.data if account_strategy_res.data else {}
        user_profile = getattr(g, 'profile', {})
        
        # 2. プロンプトで使う情報を準備
        brand_voice_to_use = account_strategy.get('brand_voice_detail', {}).get('tone', 'プロフェッショナルかつ親しみやすい')
        target_persona_to_use = "一般的な顧客"
        if account_strategy.get('main_target_audience'):
            first_persona = account_strategy.get('main_target_audience')[0] if account_strategy.get('main_target_audience') else None
            if first_persona:
                target_persona_to_use = f"ペルソナ「{first_persona.get('name', '')}」({first_persona.get('age', '')})のような層"
        
        # ★★★ ここで「発信者のプロフィール(AI用)」を取得 ★★★
        persona_profile_for_ai = account_strategy.get('persona_profile_for_ai')

        # 3. 確定した「本質」と「構成指示」の定義 (この中身は変更しない)
        composition_instructions = {
            "target_customer_summary": ("ターゲット顧客に「これは、まさに私のためのアカウントだ！」と強烈な当事者意識を持たせる。", "指示: ターゲット顧客が心の奥底で抱える「悩み」「欲求」「密かな願望」を、まるで本人の日記を覗き見たかのようにリアルな言葉で代弁してください。読者が思わず「なんで私の心がわかるの！？」と動揺し、強く惹きつけられるようなツイートを作成してください。"),
            "product_analysis_summary": ("提供する価値の全体像を魅力的に伝え、「この人が提供するものなら間違いない」という期待感を醸成する。", "指示: このアカウントが提供する商品やサービス群が、最終的に顧客をどのような「約束の地」へ連れて行くのか、その核心的なベネフィットを一つの物語として語ってください。単なる機能紹介ではなく、顧客の人生がどう変わるのかを鮮やかに描写することが重要です。"),
            "edu_s1": ("読者の中に「こうなりたい！」という強烈な憧れや、抗いがたい欲求の炎を灯す。", "指示: 以下のいずれかの「型」を完全にランダムで1つのみ使って、読者の欲求を最大化するツイートを作成してください。\n- **【変化の断片型】**: 『3週間前の自分には想像できなかった今の状況』を、まだ完璧じゃない部分も含めて語る（リアリティ度80%）\n- **【意外な副作用型】**: 『○○を変えたら、まさか△△まで変わるとは思わなかった』という予想外の波及効果を描写（リアリティ度85%）\n- **【過程の振り返り型】**: 『まだ途中だけど、確実に変わってる』という進行中の変化を、具体的な日常の変化で表現（リアリティ度90%）\n- **【他人の反応型】**: 家族や友人の『え、なんか変わった？』という反応を通じて、自分の変化を客観視（リアリティ度85%）\n- **【実績提示型】**: 『○ヶ月で△△を達成した』『クライアントが□□の成果を出した』など具体的な数字や成果を提示（リアリティ度75%）\n- **【Before/After型】**: 『以前の私は○○だったが、今は△△になった』という明確な変化の対比（リアリティ度80%）\n- **【憧れの人物型】**: 『あの人みたいになりたい』という具体的な理想像への憧れを語る（リアリティ度80%）\n- **【将来ビジョン型】**: 『1年後にはこうなっていたい』という明確な未来像を描写（リアリティ度75%）\n**NG例**: 最後の読者に向けた前向きな言葉『人生が180度変わりました！』『毎日が最高です！』『完璧になりました！』"),
            "edu_s2": ("発信者の弱さや人間味に触れさせ、「この人は信頼できる」という感情的な繋がりを構築する。", "指示: 以下のいずれかの「型」を完全にランダムで1つのみ使って、人間的な信頼を獲得するツイートを作成してください。\n- **【失敗談カミングアウト型】**: 『今だから笑って話せるけど、昔〇〇で大失敗しました…』と、自身のカッコ悪い過去を正直に告白（リアリティ度85%）\n- **【価値観表明型】**: 『私がビジネスで絶対にやらないと決めていること』など、確固たる価値観や哲学を表明（リアリティ度80%）\n- **【迷いの告白型】**: 『正直、今でも○○の時は迷う』という現在進行形の悩みや葛藤を率直に語る（リアリティ度90%）\n- **【感情の揺れ型】**: 『昨日は調子よかったのに、今日は不安になってる』という感情の波を素直に表現（リアリティ度95%）\n- **【大義名分型】**: 『なぜ無料で価値提供するのか』『なぜこの情報を発信するのか』という理念や使命を語る（リアリティ度70%）\n- **【恥ずかしい過去型】**: 『実は昔、○○なことで悩んでいました』という恥ずかしい過去の告白（リアリティ度85%）\n- **【弱さの開示型】**: 『完璧に見えるかもしれませんが、実は○○が苦手です』という弱点の開示（リアリティ度90%）\n- **【感謝の表明型】**: 『皆さんのおかげで今の自分がある』という謙虚な感謝の気持ちを表現（リアリティ度80%）\n- **【師匠・メンター型】**: 『師匠に教わった大切なこと』『恩師の言葉』など、自分も学ぶ立場であることを示す（リアリティ度80%）\n**NG例**: 『完璧な人間になりました』『もう迷いはありません』『すべてを克服しました』"),
            "edu_s3": ("「このままではダメだ」という危機感を抱かせ、変化の必要性を認識させる。", "指示: 以下のいずれかの「型」を完全にランダムで1つのみ使って、読者に健全な危機感を抱かせるツイートを作成してください。\n- **【問題指摘型】**: 多くの人が見て見ぬふりをしている『問題の根本原因』を、「もしかして、あなたも〇〇してませんか？」と優しく指摘（リアリティ度75%）\n- **【未来予測型】**: その問題を放置した場合に訪れる『5年後の最悪の未来』をリアルに描写（リアリティ度70%）\n- **【気づきの瞬間型】**: 『○○の時にハッと気づいた』という、問題を認識した具体的な瞬間を描写（リアリティ度85%）\n- **【後悔の先取り型】**: 『このまま行くと、きっと○年後に後悔する』という具体的な後悔シーンの想像（リアリティ度75%）\n- **【現実の格差型】**: 『同世代でもこんなに差がついている』という現実の格差を提示（リアリティ度80%）\n- **【時間の無駄型】**: 『今やっていることが実は時間の無駄かもしれない』という時間の価値への気づき（リアリティ度75%）\n- **【機会損失型】**: 『今のままだと○○のチャンスを逃してしまう』という機会損失の提示（リアリティ度75%）\n- **【周囲との比較型】**: 『気がついたら周りに置いていかれている』という取り残される恐怖（リアリティ度80%）\n- **【現状維持の危険型】**: 『現状維持こそが一番のリスク』という現状維持の危険性を指摘（リアリティ度75%）\n**NG例**: 『今すぐ行動しないと人生終わり』『手遅れになる前に』『ラストチャンス』"),
            "edu_s4": ("多くの選択肢で迷っている読者に、「進むべき道は、これしかない」という確信を与える。", "指示: 以下のいずれかの「型」を使って、提示する手段の唯一性を際立たせてください。\n- **【優位性提示型】**: このアカウントが提唱する解決策がいかに『本質的で、再現性が高いか』を具体的に示す（リアリティ度75%）\n- **【競合否定型】**: 他の一般的な手段がなぜ『遠回り』あるいは『罠』であるのかを論理的に説明（リアリティ度70%）\n- **【体験談比較型】**: 『色々試した結果、結局○○が一番だった』という試行錯誤の末の結論（リアリティ度85%）\n- **【原理原則型】**: 『本質的に考えると、結局○○しかない』という根本的な理由を論理的に説明（リアリティ度80%）\n- **【成功者の共通点型】**: 『成功している人はみんな○○をやっている』という成功者の共通パターン（リアリティ度70%）\n- **【時短効果型】**: 『この方法なら最短で結果が出る』という効率性の提示（リアリティ度75%）\n- **【再現性証明型】**: 『誰がやっても同じ結果が出る』という再現性の高さを強調（リアリティ度75%）\n- **【本質回帰型】**: 『テクニックより本質が大事』という本質的アプローチの重要性（リアリティ度80%）\n- **【王道提示型】**: 『結局、王道が一番の近道』という王道の価値を再認識させる（リアリティ度80%）\n**NG例**: 『これ以外の方法はすべて無駄』『私の方法が絶対正しい』『他は全部詐欺』"),
            "edu_s5": ("お金に対する考え方を「消費」から「未来への投資」へと書き換えさせる。", "指示: 以下のいずれかの「型」を使って、自己投資の重要性を納得させてください。\n- **【機会損失提示型】**: 目先の出費を惜しむことによる『機会損失の大きさ』を具体的な金額や時間で示す（リアリティ度75%）\n- **【リターン提示型】**: 「最高の自己投資とは、未来の自分の時間を買うことだ」という事実を突きつける（リアリティ度70%）\n- **【過去の後悔型】**: 『あの時○○にお金を使っていれば、今頃△△だったのに』という具体的な後悔体験（リアリティ度85%）\n- **【投資効果実感型】**: 『○○に投資した結果、予想以上のリターンがあった』という具体的な成功体験（リアリティ度80%）\n- **【時間価値型】**: 『時間を買うという感覚』『お金で時間を買えるなら安い』という時間の価値観（リアリティ度75%）\n- **【成長投資型】**: 『自分への投資が一番確実なリターンを生む』という自己投資の価値（リアリティ度75%）\n- **【知識投資型】**: 『知識は誰にも奪われない財産』という知識への投資価値（リアリティ度80%）\n- **【環境投資型】**: 『環境を変えるための投資』『良い環境にいるための費用』という環境への投資（リアリティ度80%）\n- **【コスト比較型】**: 『独学の時間コストと教えてもらうコストを比較すると』という効率性の比較（リアリティ度75%）\n**NG例**: 『投資すれば必ず儲かる』『お金を使わない人は成功しない』『今すぐ大金を投資しろ』"),
            "edu_s6": ("「やらない理由」を探す思考を停止させ、「とりあえず、これだけやってみよう」と行動の初速を最大化する。", "指示: 以下のいずれかの「型」を使って、行動への心理的障壁を取り除いてください。\n- **【希少性提示型】**: 『ほとんどの人は結局行動しない。だから、ほんの少し行動するだけで、その他大勢から抜け出せる』という事実を伝える（リアリティ度75%）\n- **【ベイビーステップ型】**: 今日から5分でできるような『驚くほど簡単な第一歩』を具体的に提示（リアリティ度80%）\n- **【完璧主義破壊型】**: 『完璧を目指すより、とりあえず60点で始める』という行動優先の考え方を提示（リアリティ度85%）\n- **【経験談励まし型】**: 『私も最初は○○だったけど、やってみたら△△だった』という背中を押す体験談（リアリティ度80%）\n- **【行動の価値型】**: 『行動することそのものに価値がある』という行動の重要性を説く（リアリティ度75%）\n- **【失敗肯定型】**: 『失敗は成功への階段』『失敗しないと成長しない』という失敗への価値観転換（リアリティ度80%）\n- **【今すぐ実践型】**: 『今すぐできる小さな一歩』を具体的に提示して即行動を促す（リアリティ度80%）\n- **【習慣化型】**: 『小さな習慣から大きな変化が生まれる』という習慣の力を説明（リアリティ度80%）\n- **【行動者の特権型】**: 『行動した人だけが見える景色がある』という行動者だけの特別感を演出（リアリティ度75%）\n**NG例**: 『今すぐやらないと後悔する』『簡単に成功できる』『誰でもできる』"),
            "edu_r1": ("読者に「この記事を最後まで読むメリット」を明確に提示し、離脱を防ぐ。", "指示: 以下のいずれかの「型」を使って、読者の注意を強制的に引きつけてください。\n- **【メリット提示型】**: ツイートの冒頭で「なぜこのツイートを読むべきか？」という理由や、読者が得られる『大きなリターン』を約束する（リアリティ度75%）\n- **【希少性演出型】**: 『このツイート、気分次第で消します』のように『限定性』を演出し、読者の見逃したくないという心理を刺激（リアリティ度70%）\n- **【問題提起型】**: 『なぜ○○な人ほど△△なのか？』という疑問から始めて、読者の好奇心を刺激（リアリティ度80%）\n- **【個人的告白型】**: 『正直に告白します』という前置きで、パーソナルな情報への関心を引く（リアリティ度85%）\n- **【衝撃の事実型】**: 『実は○○だったという衝撃の事実』で読者の常識を揺さぶる（リアリティ度75%）\n- **【秘密暴露型】**: 『今まで言えなかった秘密を話します』という秘密への好奇心を刺激（リアリティ度70%）\n- **【読了特典型】**: 『最後まで読んだ人だけに特別な情報をお教えします』という読了へのインセンティブ（リアリティ度65%）\n- **【時間限定型】**: 『今日だけ特別に話します』という時間の限定性を演出（リアリティ度70%）\n- **【共感フック型】**: 『○○で悩んでいる人、実は私もそうでした』という共感から入る（リアリティ度85%）\n**NG例**: 『絶対に見逃すな』『超重要な情報』『必見です』"),
            "edu_r2": ("重要なメッセージを何度も触れてもらうことで、可処分時間を奪い、無意識レベルまで浸透させる。", "指示: 以下のいずれかの「型」を使って、中心的なメッセージを新鮮に伝えてください。\n- **【メタファー型】**: アカウントの最も重要なメッセージを、全く異なる『比喩（メタファー）』を使って表現する（リアリティ度80%）\n- **【反論先潰し型】**: 読者が抱きそうな『反論を先回りして潰す』形で、角度を変えてメッセージを伝える（リアリティ度75%）\n- **【日常の発見型】**: 『ふと気づいたんですが』という自然な気づきの形でメッセージを伝える（リアリティ度85%）\n- **【他者の言葉型】**: 『師匠に言われた言葉』『子どもの一言』など、他者の言葉を通じてメッセージを伝える（リアリティ度80%）\n- **【復習促進型】**: 『以前も話しましたが、改めて』という形で重要なポイントを再度強調（リアリティ度70%）\n- **【角度変更型】**: 同じメッセージを異なる視点や例を使って再度伝える（リアリティ度75%）\n- **【体験談別バージョン型】**: 同じ教訓を異なる体験談で語り直す（リアリティ度85%）\n- **【季節・時事ネタ型】**: 季節の話題や時事ネタを使って同じメッセージを再話（リアリティ度80%）\n- **【質問形式型】**: 『○○について考えたことありますか？』という質問形式で再度問いかける（リアリティ度80%）\n**NG例**: 『これが真実だ』『間違いない』『絶対に正しい』"),
            "edu_r3": ("変化への恐怖を、成長への期待感や興奮へと転換させる。", "指示: 以下のいずれかの「型」を使って、変化への決意を促してください。\n- **【現状否定型】**: 『現状維持は、昨日と同じ自分で居続けるという、最も退屈な選択だ』と断言する（リアリティ度75%）\n- **【ポジティブ再定義型】**: 『変化に伴う痛みや恐怖は、より高く飛ぶための屈伸運動だ』とポジティブに再定義する（リアリティ度70%）\n- **【成長実感型】**: 『変化の過程で感じた、これまでにない充実感』を具体的に描写（リアリティ度85%）\n- **【未来の自分型】**: 『1年後の自分が今の自分を見たら何と言うか』という未来視点での変化促進（リアリティ度80%）\n- **【変化の楽しさ型】**: 『変化するって、実は○○みたいで面白い』という変化への新しい捉え方を提示（リアリティ度80%）\n- **【成長痛肯定型】**: 『今の辛さは成長痛』『痛みを感じているということは成長している証拠』という痛みの再定義（リアリティ度75%）\n- **【冒険心刺激型】**: 『人生は冒険』『新しいことにチャレンジするワクワク感』という冒険心の刺激（リアリティ度75%）\n- **【殻破り型】**: 『殻を破って生まれ変わる』『古い自分を脱ぎ捨てる』という変身への憧れ（リアリティ度75%）\n- **【進化論型】**: 『進化し続ける者だけが生き残る』という進化の必然性を説く（リアリティ度70%）\n**NG例**: 『変化は簡単』『恐れる必要はない』『必ず成功する』"),
            "edu_r4": ("自己流や過去の成功体験というプライドを脱がせ、素直に学ぶ姿勢を作る。", "指示: 以下のいずれかの「型」を使って、素直さの重要性を説いてください。\n- **【失敗事例型】**: 『自己流で時間を溶かした人の悲劇』の物語を語る（リアリティ度75%）\n- **【成功事例型】**: 『成功者の唯一の共通点は素直さだった』という衝撃的な事実を提示する（リアリティ度70%）\n- **【プライド体験型】**: 『プライドが邪魔をして、結果的に遠回りした』という自分の体験談（リアリティ度85%）\n- **【学習効率型】**: 『素直な人ほど成長が早い理由』を論理的に説明（リアリティ度80%）\n- **【初心者マインド型】**: 『初心者の心を持ち続ける』『知れば知るほど無知を知る』という学習者マインド（リアリティ度80%）\n- **【メンター重要性型】**: 『良いメンターを持つことの価値』『教えを乞う姿勢の大切さ』（リアリティ度80%）\n- **【経験の罠型】**: 『経験が邪魔をすることがある』『過去の成功が足かせになる』という経験の落とし穴（リアリティ度80%）\n- **【空のコップ型】**: 『コップが空だから新しい知識が入る』という学習の準備状態（リアリティ度75%）\n- **【年齢と学習型】**: 『いくつになっても学ぶ姿勢』『年齢は学習の障害にならない』（リアリティ度85%）\n**NG例**: 『プライドを捨てろ』『素直になれば成功する』『経験は無意味』"),
            "edu_r5": ("感想や実践報告などのアウトプットを促し、エンゲージメントと成果報告を増やす。", "指示: 以下のいずれかの「型」を使って、アウトプットを促してください。\n- **【叱咤激励型】**: 『学んだことを自分の言葉で誰かに話せないなら、それは何も学んでいないのと同じだ』と少し厳しく断言する（リアリティ度70%）\n- **【メリット提示型】**: 『たった一つのアウトプットが、未来の仲間や仕事を引き寄せる』という具体的なメリットを提示（リアリティ度75%）\n- **【体験談型】**: 『アウトプットを始めてから、○○が変わった』という具体的な変化を描写（リアリティ度85%）\n- **【学習効果型】**: 『インプットとアウトプットの比率が、成長速度を決める』という学習の本質を説明（リアリティ度80%）\n- **【記憶定着型】**: 『アウトプットすることで記憶に定着する』という脳科学的根拠（リアリティ度80%）\n- **【コミュニティ形成型】**: 『アウトプットが仲間を呼ぶ』『発信することで同じ志の人と出会える』（リアリティ度75%）\n- **【成長可視化型】**: 『アウトプットが自分の成長を可視化してくれる』という成長の記録（リアリティ度80%）\n- **【価値提供型】**: 『あなたの体験が誰かの役に立つ』という価値提供の意義（リアリティ度75%）\n- **【習慣化促進型】**: 『アウトプットを習慣にすると人生が変わる』という習慣の力（リアリティ度80%）\n**NG例**: 『アウトプットしないと意味がない』『今すぐ発信しろ』『完璧なアウトプットを目指せ』"),
            "edu_r6": ("極端なエピソードで読者の基準値をバグらせ、覚悟を背中で見せることで行動力と自己投資意識を高める。", "指示: 以下のいずれかの「型」を使って、読者の基準値を破壊してください。\n- **【背中見せ型】**: 発信者自身の『常識から逸脱した行動量や自己投資のエピソード』を具体的に語る（リアリティ度80%）\n- **【覚悟問いかけ型】**: 『プロの世界ではこれが当たり前。あなたは、どちらの世界で生きたいですか？』と、読者に本気の覚悟を問う（リアリティ度75%）\n- **【基準値比較型】**: 『普通の人の○○と、成功者の○○の違い』を具体的に比較（リアリティ度80%）\n- **【努力の再定義型】**: 『本当の努力とは、○○することだ』という努力の概念を再定義（リアリティ度75%）\n- **【現実の厳しさ型】**: 『○○の世界の現実を知ったら、今の努力がいかに足りないかわかる』という現実提示（リアリティ度85%）\n- **【極端行動型】**: 『全財産を投資に回した』『寝る時間を削って勉強した』など極端な行動エピソード（リアリティ度80%）\n- **【犠牲の覚悟型】**: 『○○を諦めて△△に集中した』という何かを犠牲にした覚悟の話（リアリティ度85%）\n- **【常識破り型】**: 『常識では考えられない行動』『周りに反対されてもやり抜いた』（リアリティ度80%）\n- **【時間投資型】**: 『1日○時間を△△に投資した』という時間への極端な投資（リアリティ度80%）\n- **【リスク承知型】**: 『失敗するリスクを承知でやった』というリスクを取った覚悟（リアリティ度85%）\n**NG例**: 『もっと頑張れ』『努力が足りない』『甘えるな』"),
            "default": ("読者の心を動かす", "指示: 読者が興味を持つような、自由な構成で作成してください。")
        }

        element_key_for_lookup = education_element_key
        if "edu_" in education_element_key:
            element_key_for_lookup = education_element_key.split('_')[0] + '_' + education_element_key.split('_')[1]
            
        element_purpose, tweet_composition_instruction = composition_instructions.get(element_key_for_lookup, composition_instructions["default"])

        # (ここは外部定義の`PSYCHOLOGY_TECHNIQUES`を想定)
        related_psychology_technique = PSYCHOLOGY_TECHNIQUES.get(element_key_for_lookup)
        
        # 4. プロンプトを組み立てる
        prompt_parts = [
            "あなたは、プロのX(旧Twitter)コンテンツクリエイターです。", # シンプルに変更
            "以下の情報を元に、エンゲージメントを最大化する、最も効果的だと思われるツイート文案を1つ作成してください。",
            "\n## アカウントの基本設定:",
            f"  - ブランドボイス: {brand_voice_to_use}",
            f"  - ターゲット顧客: {target_persona_to_use}",
            f"  - プロフィール: {persona_profile_for_ai}",
            f"  - アカウントのパーパス: {account_strategy.get('account_purpose', '未設定')}",
            
        ]

        # ★★★ ここからが修正・追加箇所 ★★★

        # 「発信者プロフィール」が設定されている場合のみ、矛盾防止ルールを追加
        if persona_profile_for_ai and persona_profile_for_ai.strip():
            prompt_parts.append("\n## 矛盾を防ぐための絶対ルール：発信者の現在地")
            prompt_parts.append(f"  - プロフィール: {persona_profile_for_ai}")
            prompt_parts.append("  - **注意: 生成するツイートは、必ずこのプロフィールと矛盾しないようにしてください。ツイートの主テーマはこのプロフィール内容そのものではなく、あくまで矛盾を防ぐための「背景情報」として扱ってください。**")
            prompt_parts.append("  - NG例: 「フルリモートで成功している」というプロフィールなのに「パート先で嫌なことがあった」など、現在の立場と明らかに食い違う内容は絶対に含めないでください。")
        
        prompt_parts.append("\n## 今回のツイート作成指示:")
        prompt_parts.append(f"  - このツイートの目的（本質）: {element_purpose}")
        prompt_parts.append(f"  - 具体的なテーマ: {theme}")
        prompt_parts.append(f"  - 構成と表現のヒント（固定ルール）: {tweet_composition_instruction}")
        
        # 心理技術の情報があればプロンプトに「参考情報」として追加
        if related_psychology_technique:
            prompt_parts.append(f"\n## 参考となる心理技術（付加情報）: {related_psychology_technique}")
            prompt_parts.append("\n## 生成の最終指示:")
            prompt_parts.append("  - **まず「構成と表現のヒント（固定ルール）」の指示に厳密に従い、記載された「型」の中から完全にランダムで1つだけ選んでください。**")
            prompt_parts.append("  - 次に、その選んだ「型」をベースにしながら、「参考となる心理技術（付加情報）」の考え方を創造的に組み込み、ツイートをより説得力のあるものに昇華させてください。")
        else:
             prompt_parts.append("\n## 生成の最終指示:")
             prompt_parts.append("  - 上記の「構成と表現のヒント（固定ルール）」に記載された指示に従い、あなたの創造性を加えて最高のツイートに仕上げてください。")

        prompt_parts.extend([
            "\n## リアリティ創出のための重要ルール:",
            "  - **説明的な締め方の禁止**: ツイートの最後に、感情や状況を解説するような一文（例：『〜という自信でした』『〜は大事ですね』）を加えないでください。情景や事実を描写するに留め、解釈は読者に委ねることで、より深い余韻と感動を生み出してください。"
            "  - **時間軸の自然さ**: 「最近」「ついさっき」などの曖昧表現を適度に避け、「2週間前」「昨日の夜」など適度に具体的な時点を使う",
            "  - **感情の表現方法**: 「嬉しい」「辛い」ではなく、行動や身体感覚で表現（「思わず深呼吸した」「手が止まった」など）",
            "  - **完璧さの回避**: 途中経過、迷い、些細な失敗、予期しない副作用なども含める",
            "  - **台詞のリアルさ**: もし、セリフを入れる場合は、理想的すぎる発言を避け、人間らしい生々しさや予想外の反応を入れる",
            "  - **構造の自然化**: 結論を最初に持ってくる、話が脱線する、など自然な思考の流れを模倣",
            "  - **矛盾と揺らぎ**: 適度に「とはいえまだ不安だけど」「完全に解決したわけじゃないけど」など人間的な複雑さを含める",
            "  - **リアリティ度を意識**: 各型に設定されたリアリティ度を参考に、その水準での自然さを目指す",
            "\n## 基本仕様:",
            "  - **140字程度の日本語のツイートで伝えたいメッセージを一つに絞ってください。**",
            "  - 抽象的な前置きや余計な修飾語は削り、即本題に入ってください",
            "  - 絵文字を効果的に使用",
            "  - 完成されたツイート本文のみを出力（前置きや解説は不要）"
        ])
        
        prompt = "\n".join(filter(None, prompt_parts))
        
        # 5. 新しいSDKの作法でAPIを呼び出す
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        config = genai_types.GenerateContentConfig(temperature=0.9)

        print(f">>> Gemini Prompt for educational tweet (Final Version):\n{prompt[:600]}...")
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=config
        )
        
        generated_tweet_text = response.text.strip()
        if not generated_tweet_text:
            raise Exception("AIからの応答テキストが空でした。")
            
        print(f">>> AI Generated Educational Tweet: {generated_tweet_text}")
        return jsonify({"generated_tweet": generated_tweet_text})

    except Exception as e:
        print(f"!!! Exception during AI educational tweet generation: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる教育ツイート生成中に予期せぬエラーが発生しました。", "error": str(e)}), 500
    
    
# --- X API クライアント準備とツイート操作API ---
def get_x_api_client(user_x_credentials):
    consumer_key = user_x_credentials.get('x_api_key')
    consumer_secret = user_x_credentials.get('x_api_secret_key')
    access_token = user_x_credentials.get('x_access_token')
    access_token_secret = user_x_credentials.get('x_access_token_secret')

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        print("!!! X API client: Missing one or more credentials for X API v2 client.")
        return None
    
    try:
        client_v2 = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        print(">>> X API v2 client (tweepy.Client) initialized using 4 keys (User Context).")
        return client_v2
    except Exception as e:
        print(f"!!! Error initializing X API v2 client: {e}")
        traceback.print_exc()
        return None

@app.route('/api/v1/tweets/post-dummy', methods=['POST'])
@token_required
def post_dummy_tweet():
    user_profile = getattr(g, 'profile', {}) 
    if not user_profile:
        print("!!! User profile not found in g for post_dummy_tweet.")
        return jsonify({"message": "User profile not found."}), 500
    
    user_id = user_profile.get('id')

    print(f">>> Dummy post request for user_id: {user_id}")
    print(f"    X API Key from g.profile: {'Set' if user_profile.get('x_api_key') else 'Not Set'}")

    api_client_v2 = get_x_api_client(user_profile) 

    if not api_client_v2:
        return jsonify({"message": "Failed to initialize X API client. Check credentials in MyPage or X API version compatibility."}), 500

    try:
        tweet_text = f"これはEDSシステム (X API v2 Client)からのテスト投稿です！時刻: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        created_tweet_response = api_client_v2.create_tweet(text=tweet_text)
        
        if created_tweet_response.data and created_tweet_response.data.get('id'):
            tweet_id_str = created_tweet_response.data['id']
            print(f">>> Dummy tweet posted successfully using X API v2! Tweet ID: {tweet_id_str}")
            return jsonify({"message": "Dummy tweet posted successfully using X API v2!", "tweet_id": tweet_id_str, "text": tweet_text}), 200
        else:
            error_detail = "Unknown error or unexpected response structure from X API v2."
            if hasattr(created_tweet_response, 'errors') and created_tweet_response.errors:
                error_detail = str(created_tweet_response.errors)
            elif hasattr(created_tweet_response, 'reason'): 
                error_detail = created_tweet_response.reason
            print(f"!!! Error in v2 tweet creation response for user_id {user_id}: {error_detail}")
            return jsonify({"message": "Error posting dummy tweet with X API v2.", "error_detail": error_detail}), 500

    except tweepy.TweepyException as e_tweepy: 
        error_message = str(e_tweepy)
        print(f"!!! TweepyException posting dummy tweet for user_id {user_id}: {error_message}")
        if hasattr(e_tweepy, 'response') and e_tweepy.response is not None:
            try:
                error_json = e_tweepy.response.json()
                if 'errors' in error_json and error_json['errors']:
                     error_message = f"X API Error: {error_json['errors'][0].get('message', str(e_tweepy))}"
                elif 'title' in error_json: 
                     error_message = f"X API Error: {error_json['title']}: {error_json.get('detail', '')}"
                elif hasattr(e_tweepy.response, 'data') and e_tweepy.response.data:
                    error_message = f"X API Forbidden (403): {e_tweepy.response.data}"

            except ValueError: 
                pass
        elif hasattr(e_tweepy, 'api_codes') and hasattr(e_tweepy, 'api_messages'):
             error_message = f"X API Error {e_tweepy.api_codes}: {e_tweepy.api_messages}"
        traceback.print_exc()
        return jsonify({"message": "Error posting dummy tweet (TweepyException).", "error": error_message}), 500
    except Exception as e: 
        error_message = str(e)
        print(f"!!! General Exception posting dummy tweet for user_id {user_id}: {error_message}")
        traceback.print_exc()
        return jsonify({"message": "Error posting dummy tweet (General Exception).", "error": error_message}), 500
    
   
  

# ★★★ 「権威性の型」定義（変更なし） ★★★
AUTHORITY_TWEET_FORMATS = {
    "【問題解決型】": {
        "description": "読者の明確な悩みに、科学的根拠を添えて直接的な解決策を提示する。",
        "prompt": """
構造:
- 権威ある問題提起 - 研究データで問題の深刻さを証明
- 権威による共感 - 専門家も同じ問題を指摘
- 解決策の権威付け - 「○○大学が開発した手法」
- 科学的手順 - 各ステップに研究根拠を付与
- 権威ある注意点 - 専門機関の推奨事項
- 統計的効果 - 研究結果での改善率を提示

例テンプレート:
現代人の96%が集中力低下に悩んでいることをご存知ですか？
（厚生労働省 2024年調査）
実際、ハーバード大学のマシュー・キリングワース博士も「人間の心は47%の時間、今やっていることに集中していない」と警告しています。
でも安心してください。MIT認知科学研究所が開発した「注意力回復プログラム」で、この問題は確実に解決できます。
【科学的に証明された3ステップ】
①5分間マインドフルネス →UCLA研究：脳の注意制御機能が28%向上
②25分集中+5分休憩（ポモドーロ法） →イタリア国立研究所発案、NASA・IBMが正式採用
③デジタルデトックス環境 →シカゴ大学研究：スマホが視界にあるだけで認知能力20%低下
【重要】米国睡眠財団の推奨：90分以上の連続作業は避けること。
結果：この手法を実践した被験者1,247名のうち、89%が「集中力の大幅改善」を報告（スタンフォード大学6ヶ月追跡調査）
世界トップ企業が採用する手法、今日から始めてみませんか？
"""
    },
    "【ノウハウ公開型】": {
        "description": "専門的で体系化された知識や手法を、権威を借りて公開する。",
        "prompt": """
構造:
- 権威的価値宣言 - 「○○大学で教えている手法を公開」
- 権威の背景 - 研究機関・専門家・大企業の実績
- 核心部分 - 科学的根拠付きの最重要ポイント
- 詳細解説 - データ・統計を交えた手順
- 成功事例 - 有名企業・研究結果での効果
- まとめ - 権威ある機関の推奨として再強調

例テンプレート:
スタンフォード大学で教えられている副業構築法を全て公開します。
この手法はGoogleやAppleの元社員が実践し、平均月収12.7万円を達成しています。
最重要原則：「検証可能な小さな実験から始める」（シリコンバレー流MVP思考）
科学的手順：
1. スキル棚卸し（マッキンゼー式分析法）
2. 市場検証（リーン・スタートアップ理論）
3. MVP作成（最小限実行可能プロダクト）
4. データ収集（A/Bテスト手法）
5. スケール（パレートの法則活用）
実際、この手法を使った500人の追跡調査では、6ヶ月で副業収入を得た人が87%でした。
スタンフォード発の手法、試してみませんか？
"""
    },
    "【気づき共有型】": {
        "description": "権威ある研究結果と個人の体験を結びつけ、読者の常識を覆す「気づき」を与える。",
        "prompt": """
構造:
- 権威ある発見 - 「○○大学の研究で判明した事実」
- 個人体験との一致 - 研究結果と自分の経験がリンク
- 従来の常識への疑問 - 権威あるデータで常識を覆す
- 新しい真実 - 研究結果に基づく新視点
- 実践結果 - 個人実験 + 統計データ
- 行動提案 - 科学的根拠を示しての推奨

例テンプレート:
スタンフォード大学の20年間追跡調査で衝撃の事実が判明：「完璧主義者の方が実は成果が低い」
この研究結果を見た時、自分の経験と完全に一致しました。
従来の常識：完璧を目指せば高品質になる
研究が示す真実：完璧主義は行動を阻害し、結果的に低成果
ハーバード・ビジネス・レビューによると、60%完成度で開始する人の方が最終成果が高いそうです。
実際、私も60%ルールを導入してから：・企画通過率：30% → 90% ・プロジェクト完成率：50% → 85%
MIT教授も推奨する「勇気ある未完成」、始めてみませんか？
"""
    },
    "【比較検証型】": {
        "description": "対立する二つの説を権威あるデータで比較し、読者に判断基準を提供する。",
        "prompt": """
構造:
- 権威ある論争 - 「○○大学 vs △△大学の研究対立」
- 検証の意義 - なぜこの比較が重要か（データ付き）
- A案の権威付け - 支持する研究・専門家・企業
- B案の権威付け - 支持する研究・専門家・企業
- メタ分析結果 - 複数研究をまとめた結論
- 実践推奨 - どの権威に従うべきかの判断基準

例テンプレート:
ハーバード大学「朝活推奨」vs スタンフォード大学「夜活推奨」
この論争に決着をつけるため、両方を3ヶ月実践検証しました。
【朝活派】ハーバード大学研究 ・コルチゾール値が最適（朝6-8時） ・意思決定力が日中の1.5倍 ・Forbes500社CEO の68%が実践
【夜活派】スタンフォード大学研究   ・クリエイティビティは夜間に20%向上 ・記憶定着率が睡眠前学習で40%UP ・Google、Facebook幹部の74%が実践
結論：オックスフォード大学のメタ分析（15,000人対象）では「個人のクロノタイプ（生体リズム）による」
判定法：起床後4時間以内に最も集中できる→朝型。起床後8時間以降に最も集中できる→夜型
あなたはどちらのタイプでしたか？
"""
    }
}

# --- Block 5: 新しいAPIエンドポイント - 初期投稿生成 (Google検索対応) ---
@app.route('/api/v1/initial-tweets/generate', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def generate_initial_tweet():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    user_id = g.user.id
    try:
        data = request.json
        if not data: return jsonify({"error": "Invalid JSON request"}), 400
        x_account_id = data.get('x_account_id')
        initial_post_type = data.get('initial_post_type')
        theme = data.get('theme', '')
        use_Google_Search_flag = data.get('use_Google_Search', False)
        selected_authority_format_by_user = data.get('selected_authority_format', None)
        if not all([x_account_id, initial_post_type]): return jsonify({"error": "x_account_idとinitial_post_typeは必須です"}), 400
    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # --- 共通で使う情報を準備 ---
        account_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = account_strategy_res.data if account_strategy_res.data else {}
        user_profile = getattr(g, 'profile', {})
        account_purpose = account_strategy.get('account_purpose', '（設定なし）')
        core_value_proposition = account_strategy.get('core_value_proposition', '（設定なし）')
        persona_profile_for_ai = account_strategy.get('persona_profile_for_ai')
        target_persona_summary = "一般的なフォロワー"
        main_target_audience_data = account_strategy.get('main_target_audience')
        if main_target_audience_data and isinstance(main_target_audience_data, list) and main_target_audience_data:
            first_persona = main_target_audience_data[0]
            if isinstance(first_persona, dict):
                name, age, problem = first_persona.get('name', ''), first_persona.get('age', ''), first_persona.get('悩み', '')
                target_persona_summary = f"ペルソナ「{name}」({age})の悩みは「{problem}」"
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        grounding_info_to_return = None
        final_tweet = ""
        
        # ======================================================================
        # 分岐処理の開始
        # ======================================================================
        if initial_post_type == "value_tips":
            print(">>> Executing 8-Step Self-Improving QC loop for 'value_tips'...")
            
            # === フェーズ1: 悩み特定＆「権威性の型」決定 ===
            print(">>> Phase 1: Identifying problem and selecting format...")
            selected_problem = ""
            selected_format = ""
            if selected_authority_format_by_user and selected_authority_format_by_user in AUTHORITY_TWEET_FORMATS:
                print(f">>> User has selected the format: {selected_authority_format_by_user}")
                selected_format = selected_authority_format_by_user
                phase1_prompt = "\n".join([
                    "あなたは、クライアントの課題を多角的に分析し、最も解決すべき一点を見つけ出すのが得意な、プロの課題発見コンサルタントです。",
                    f"## 最終目的: ターゲット顧客の悩みを『{selected_format}』という型で解決するツイートを作成します。そのための最も効果的で「具体的」なテーマ（悩み）を特定してください。",
                    f"\n## アカウント情報\n- ターゲット顧客: {target_persona_summary}", f"- ユーザーからのヒント: {theme if theme else '（特になし）'}",
                    "\n## 指示", "ターゲット顧客が抱えるであろう「具体的な悩み」を一つだけ特定し、そのテキストのみを出力してください。説明は不要です。"
                ])
                phase1_response = client.models.generate_content(model=model_id, contents=phase1_prompt)
                selected_problem = phase1_response.text.strip()
            else:
                print(">>> User has not selected a format. AI will select both problem and format.")
                format_list_for_prompt = "\n".join([f"- {name}: {details['description']}" for name, details in AUTHORITY_TWEET_FORMATS.items()])
                phase1_prompt = "\n".join([
                    "あなたは、クライアントの課題を多角的に分析し、それに最適なコンテンツ戦略を立案するプロのコンサルタントです。",
                    "\n## 最重要ミッション", "**毎回、前回とは異なる視点から、新鮮で多様な「具体的な悩み」と、それを解決するための「最適な型」を提案すること。**",
                    "\n## 選択可能な「権威性の型」リスト", format_list_for_prompt,
                    "\n## 指示", "以下の2ステップの思考プロセスを経て、最終的な出力をJSON形式で生成してください。", "---",
                    "### ステップ1: 悩みの多角的ブレインストーミングと「型」のマッチング（あなたの頭の中だけで実行）", f"ターゲット顧客（{target_persona_summary}）が抱えそうな悩みを多角的に洗い出し、それぞれの悩みを解決するのに最も効果的な「権威性の型」は何かを検討してください。", "---",
                    "### ステップ2: 最も効果的な「悩み」と「型」の選定と出力", "ステップ1で検討した組み合わせの中から、最もツイートとして魅力的で、前回とは違う切り口になるものを一つだけ選び、以下のJSON形式で出力してください。",
                    '```json', '{', '  "selected_problem": "（ここに選んだ具体的な悩みを記述）",', '  "selected_format": "（ここに上記リストから選んだ型名を記述。例: 【問題解決型】）"', '}', '```', "JSON以外の説明文は絶対に含めないでください。"
                ])
                phase1_response = client.models.generate_content(model=model_id, contents=phase1_prompt)
                try:
                    cleaned_text = phase1_response.text.strip().replace("```json", "").replace("```", "")
                    decision = json.loads(cleaned_text)
                    selected_problem = decision['selected_problem']
                    selected_format = decision['selected_format']
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"!!! Phase 1 failed to parse AI response: {e}"); raise Exception("Phase 1: AIの応答形式が不正です。")
            if not selected_problem or not selected_format: raise Exception("Phase 1: AIが悩みまたは型を特定できませんでした。")
            print(f">>> Phase 1: Problem='{selected_problem}', Format='{selected_format}'")

            # === フェーズ2: 型に基づく情報収集キーワードの生成 ===
            print(">>> Phase 2: Generating search keywords...")
            phase2_prompt = "\n".join([
                "あなたは、与えられた戦略に基づいて、最適な調査計画を立てるAIリサーチャーです。",
                f"## 最終目的: 「{selected_problem}」という悩みを、「{selected_format}」という型で解決するツイートを作成するための、精度の高い情報を収集すること。",
                "\n## 指示", "上記の目的を達成するために、Googleで調査すべき「検索キーワード」を、カンマ区切りで3～5個出力してください。",
                "## 型に応じたキーワード生成のヒント:", "- もし型が【問題解決型】なら、「集中力 低下 原因 研究」「集中力 回復 方法 科学的根拠」のようなキーワードが必要です。", "- もし型が【比較検証型】なら、「朝活 夜活 メリット デメリット 研究」「クロノタイプ 診断」のようなキーワードが必要です。",
                "あなたの役割は、選ばれた型を構成するために必要な情報を逆算し、最適な検索キーワードを設計することです。キーワードのみを出力してください。"
            ])
            phase2_response = client.models.generate_content(model=model_id, contents=phase2_prompt)
            search_keywords = phase2_response.text.strip()
            if not search_keywords: raise Exception("Phase 2: AI failed to generate search keywords.")
            print(f">>> Phase 2: Keywords generated: {search_keywords}")

            # === フェーズ3: 情報収集・整理 ===
            print(">>> Phase 3: Researching the solution...")
            phase3_prompt = "\n".join([
                "あなたは、プロのAIリサーチャーです。",
                f"## 最終目的: 「{selected_problem}」という悩みを、「{selected_format}」という型で解決するツイートを作成するための根拠となる、信頼性が高く効果的な情報を収集・要約してください。",
                "\n## 指示", f"以下の【検索キーワード群】を使ってWeb調査を行い、【ユーザーの悩み】を解決するための、具体的で信頼性の高い情報を3～5個の箇条書きでリストアップしてください。",
                f"  - ユーザーの悩み: {selected_problem}", f"  - 調査に使う検索キーワード群: {search_keywords}",
                "- 複数のキーワードから得られた情報を統合し、最も本質的で効果的な解決策を要約してください。", "- あなた自身の意見やツイート本文の提案は含めず、事実のリストアップに徹してください。"
            ])
            research_config = genai_types.GenerateContentConfig(tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())])
            phase3_response = client.models.generate_content(model=model_id, contents=phase3_prompt, config=research_config)
            research_summary = phase3_response.text.strip()
            if phase3_response.candidates and hasattr(phase3_response.candidates[0], 'grounding_metadata'):
                g_meta = phase3_response.candidates[0].grounding_metadata
                if hasattr(g_meta, 'citations') and g_meta.citations:
                    grounding_info_to_return = [{"uri": getattr(c, 'uri', None), "title": getattr(c, 'title', None)} for c in g_meta.citations]
            if not research_summary: raise Exception("Phase 3: AI failed to research the solution.")
            print(f">>> Phase 3: Research summary created:\n{research_summary}")

            # === フェーズ4: ツイートの初回ドラフト生成 ===
            print(">>> Phase 4: Generating the first draft...")
            format_definition = AUTHORITY_TWEET_FORMATS.get(selected_format, {}).get("prompt", "指定された型が見つかりません。")
            phase4_prompt = "\n".join([
                "あなたは、与えられた素材の**論理的な関連性**を重視し、読者が納得できる文章を構築するプロのライターです。",
                "\n## ツイートの素材", f"  - 解決するべき悩み: {selected_problem}", f"  - 根拠となるリサーチ情報: {research_summary}",
                "\n## 矛盾を防ぐための絶対ルール", f"  - 発信者のプロフィール: {persona_profile_for_ai if persona_profile_for_ai else '設定なし'}",
                "\n## 作成指示", "以下の【ツイートの型】の構造に厳密に従って、最高のツイートを作成してください。",
                "### 【最重要・禁止事項】",
                "- **論理の飛躍の禁止:** リサーチ情報で見つけた「企業の事例」や「マクロな統計」と、「個人の学習法」や「個人の働き方」を、**直接的な因果関係があるかのように結びつけることは絶対にしないでください。**",
                "- **情報の誤用の禁止:** 例えば、「日本マイクロソフトの生産性向上」は、あくまで企業全体の取り組みの結果です。それを個人のスキル習得と直接結びつけるような、誤解を招く表現は厳禁です。",
                "### 【推奨される表現】",
                "- 関連性の薄い情報を繋げる場合は、「〇〇社の事例にも通じる考え方ですが…」「これはマクロな話ですが、個人のレベルでも…」のように、**あくまでアナロジー（類推）や参考事例**として提示するに留めてください。",
                "---", f"### 【ツイートの型】: {selected_format}", format_definition, "---"
            ])
            first_draft_response = client.models.generate_content(model=model_id, contents=phase4_prompt)
            current_tweet_draft = re.sub(r'^(.*\n)*', '', first_draft_response.text, 1).strip()
            
            # ★★★ 自己改善QCループ ★★★
            MAX_REVISIONS = 8
            PASSING_SCORE = 90
            best_score = 0
            best_tweet = current_tweet_draft
            current_research_summary = research_summary

            for i in range(MAX_REVISIONS):
                print(f"\n>>> QC Loop - Iteration {i+1}/{MAX_REVISIONS}...")
                
                # --- フェーズ5: AIによる辛口採点＆指示分岐 ---
                print(">>>   Phase 5: Quality Check, Scoring, and Task Assignment...")
                format_definition_for_qc = AUTHORITY_TWEET_FORMATS.get(selected_format, {}).get("prompt", "")
                qc_prompt = "\n".join([
                    "あなたは、超一流のコンテンツ編集長です。ライターが与えられた指示通りにツイート案を作成したかを厳しく評価し、具体的な改善点を指摘してください。",
                    "\n## ライターに与えられた指示", f"- **採用すべき型:** {selected_format}", f"- **型の定義:**\n```{format_definition_for_qc}```", f"- **守るべきルール:** 論理の飛躍や情報の誤用は禁止されています。",
                    "\n## ライターが使った素材", f"- **発信者のプロフィール:** {persona_profile_for_ai if persona_profile_for_ai else '設定なし'}", f"- **解決しようとした悩み:** {selected_problem}", f"- **根拠となるリサーチ情報:**\n{current_research_summary}",
                    "\n## 評価対象ツイート（ライターからの提出物）", "```", current_tweet_draft, "```",
                    "\n## 指示", "上記の**【ライターに与えられた指示】**を遵守できているかという観点で、以下の採点基準でツイート案を100点満点で採点してください。**もし権威性や具体性が不足していると感じた場合は、フィードバックに『〇〇に関する追加情報が必要です』と明確に記述してください。**",
                    "### 【採点基準】", "- **論理の一貫性 (30点):** **論理の飛躍や無関係な情報の強引な結合がないか？（最重要）**", "- **型の遵守度 (20点):** 指定された「型」の構造から逸脱していないか？", "- **目的達成度 (20点):** ツイートの目的（悩みのピンポイント解決）を達成しているか？",
                    "- **具体性 (15点):** 読者がすぐに行動できる具体的なアクションが示されているか？", "- **感情的魅力 (15点):** 読者の心を動かす共感や希望があるか？",
                    "\n### 【出力形式】", '```json', '{', '  "score": { "total": <合計点>, ... },', f'  "feedback": "（もし{PASSING_SCORE}点未満なら具体的な改善点を記述。{PASSING_SCORE}点以上なら『合格』と記述）"', '}', '```'
                ])
                qc_response = client.models.generate_content(model=model_id, contents=qc_prompt)
                
                try:
                    json_match = re.search(r'\{.*\}', qc_response.text, re.DOTALL)
                    if not json_match: raise json.JSONDecodeError("No JSON object found.", qc_response.text, 0)
                    json_string = json_match.group(0)
                    qc_result = json.loads(json_string)
                    current_score = qc_result.get("score", {}).get("total", 0)
                    feedback = qc_result.get("feedback", "")
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"!!! QC Loop failed to parse AI response: {e}. Raw: '{qc_response.text}'. Breaking."); break
                
                print(f">>>   Score: {current_score}/{PASSING_SCORE}")
                print("-------------------- FEEDBACK --------------------")
                print(feedback)
                print("-------------------------------------------------")
                
                if current_score > best_score:
                    best_score = current_score
                    best_tweet = current_tweet_draft
                if current_score >= PASSING_SCORE:
                    print(f">>> QC Passed! Final score: {current_score}."); break

                if i < MAX_REVISIONS - 1:
                    # --- フェーズ5.8: 指示の再構成（ToDoリスト化）---
                    print(">>>   Phase 5.8: Converting feedback to a ToDo list (by Desk)...")
                    todo_prompt = "\n".join([
                        "あなたは、厳しい編集長の意図を正確に汲み取り、ライターへの**「具体的で実行可能な作業指示」**に落とし込む、超優秀なデスク担当者です。",
                        "\n## あなたが使えるすべての素材", f"- 採用すべき型: {selected_format}", f"- 型の定義:\n```{format_definition}```", f"- 根拠となるリサーチ情報:\n{current_research_summary}",
                        "\n## 編集長からのフィードバック", "```", feedback, "```",
                        "\n## 指示", "編集長のフィードバックと、あなたが使えるすべての素材を元に、ライターが**次に何をすべきか**を、**極めて具体的な「修正指示ToDoリスト」**として箇条書きで出力してください。",
                        "### 【ToDoリスト作成のルール】",
                        "- **ダメ出しではなく、具体的なアクションを指示する:** 「具体性が足りない」ではなく、「リサーチ情報にある『クラウドワークス』という固有名詞を、ツイートの手順部分に追記せよ」のように記述する。",
                        "- **素材と型を結びつける:** 「リサーチ情報の【〇〇というデータ】を、【問題解決型】の【権威ある問題提起】のパートに、このように挿入せよ」といった、具体的なマッピング指示を行う。",
                        "- **文章レベルでの指示:** 「冒頭の『〇〇』という表現を、もっと共感を呼ぶ『△△』という表現に書き換えよ」のように、具体的な文章の修正案を提示する。"
                    ])
                    todo_response = client.models.generate_content(model=model_id, contents=todo_prompt)
                    todo_list = todo_response.text.strip()
                    print(f">>>   ToDo List:\n{todo_list}")
                    
                    # --- フェーズ6: 追加リサーチ（必要な場合のみ）---
                    research_needed_keywords = ["追加情報", "リサーチ", "調査", "権威性", "データ", "根拠"]
                    if any(keyword in todo_list for keyword in research_needed_keywords):
                        print(">>>   Phase 6: Executing additional research based on ToDo list (by Researcher)...")
                        additional_research_prompt = "\n".join([
                            "あなたは、デスク担当者からの調査依頼に基づき、深掘り調査を行うAIリサーチャーです。",
                            f"\n## 調査依頼（ToDoリスト）\n{todo_list}",
                            "\n## 指示\n上記のToDoリストに含まれる**調査依頼**について、Google検索で調査し、その結果を箇条書きで要約してください。"
                        ])
                        additional_research_config = genai_types.GenerateContentConfig(tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())])
                        additional_research_response = client.models.generate_content(model=model_id, contents=additional_research_prompt, config=additional_research_config)
                        additional_summary = additional_research_response.text.strip()
                        if additional_summary:
                            print(f">>>   Additional research summary:\n{additional_summary}")
                            current_research_summary += f"\n\n【追加リサーチ情報】\n{additional_summary}"
                    
                    # --- フェーズ7: ゼロからの再生成 ---
                    print(f">>>   Phase 7: Regenerating the tweet from scratch based on ToDo list...")
                    rewrite_prompt = "\n".join([
                        "あなたは、渡された**最終指示書（ToDoリスト）**と**素材**を元に、指定された「型」に沿ってツイートを**ゼロから書き上げる**プロのライターです。",
                        "\n## ★★★ 最優先事項 ★★★",
                        f"このツイートの目的は、読者の『{selected_problem}』という悩みをピンポイントで解決することです。必ずこのテーマに沿った内容にしてください。",
                        "\n## あなたが完成させるべき【ツイートの型】",
                        f"- **型名:** {selected_format}", f"- **型の定義（構造と例）:**\n```{format_definition}```",
                        "\n## あなたが使えるすべての素材",
                        f"- **発信者のプロフィール（矛盾チェック用）:** {persona_profile_for_ai if persona_profile_for_ai else '設定なし'}",
                        f"- **根拠となるリサーチ情報:**\n{current_research_summary}",
                        "\n## ★★★ あなたが実行すべき最終指示書（ToDoリスト） ★★★",
                        "```", todo_list, "```",
                        "\n## 指示",
                        "**これまでのドラフトはすべて忘れ、上記の【最終指示書】と【あなたが使えるすべての素材】だけを元に、ツイートをゼロから完全に新しく作成してください。**",
                        "**最優先事項は、【ツイートの型】の構造を守りつつ、【最終指示書】をすべて反映させることです。**",
                        "完成したツイート本文のみを出力してください。"
                    ])
                    rewrite_response = client.models.generate_content(model=model_id, contents=rewrite_prompt)
                    current_tweet_draft = re.sub(r'^(.*\n)*', '', rewrite_response.text, 1).strip()
                    print("----------------- REWRITTEN DRAFT -----------------")
                    print(current_tweet_draft)
                    print("--------------------------------------------------")
                    time.sleep(1)
                else:
                    print(">>> Max revisions reached. Outputting the best tweet so far.")
            
            final_tweet = best_tweet

        else:
            # --- それ以外のツイート（自己紹介など）の場合：従来の1段階処理を実行 ---
            print(f">>> Executing 1-step generation for '{initial_post_type}'...")
            
            research_summary = ""
            if use_Google_Search_flag and theme.strip():
                try:
                    print(">>> Research phase for non-value-tips post...")
                    current_year = datetime.datetime.now().year
                    research_prompt_text = "\n".join([
                        "あなたは、与えられたテーマについて、信頼性の高い情報を迅速に調査・要約するプロのAIリサーチャーです。",
                        "あなたの唯一のタスクは、後続のツイート生成AIが最高の「ネタ」として使える、客観的で興味深い事実を3～5個、箇条書きでリストアップすることです。",
                        f"\n## 主要な調査テーマ: {theme}",
                        f"\n## 参考情報（調査の文脈）:",
                        f"  - 調査対象の読者層: {target_persona_summary}",
                        f"  - アカウントの目的: {account_purpose}",
                        "\n## 調査・要約の指示:",
                        f"  - 必ず「{current_year}」や「最新」の情報を優先してください。",
                        "  - 具体的な数値データ、統計、専門機関の発表、意外な事実などを重視してください。",
                        "  - 各項目は、ツイートに引用しやすいように、簡潔な日本語で記述してください。",
                        "  - あなた自身の意見や、ツイート本文の提案は絶対に含めないでください。事実のリストアップに徹してください。"
                    ])
                    research_config = genai_types.GenerateContentConfig(tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())])
                    research_response = client.models.generate_content(model=model_id, contents=research_prompt_text, config=research_config)
                    research_summary = research_response.text.strip()
                    if research_response.candidates and hasattr(research_response.candidates[0], 'grounding_metadata'):
                        g_meta = research_response.candidates[0].grounding_metadata
                        if hasattr(g_meta, 'citations') and g_meta.citations:
                            grounding_info_to_return = [{"uri": getattr(c, 'uri', None), "title": getattr(c, 'title', None)} for c in g_meta.citations]
                    print(f">>> Research summary created for non-value-tips post:\n{research_summary}")
                except Exception as e_research:
                    print(f"!!! Exception during research for non-value-tips post: {e_research}")
                    research_summary = f"（最新情報の調査中にエラーが発生しました: {str(e_research)}）"
            
            prompt_parts = [
                "あなたは、X（旧Twitter）で数々のバズを生み出してきた、言葉選びのセンスが抜群のコンテンツクリエイターです。",
                "あなたの仕事は、クライアントのアカウント情報を元に、読者の心を掴んで離さない、多様な切り口のツイート案を無限に生み出すことです。",
                "以下の【ツイートの素材】と【作成指示】に基づいて、最高のツイート案を1つ作成してください。",
                "\n## ツイートの素材（ヒント）:",
                f"  - このアカウントの主人公（発信者）は、おそらく「{target_persona_summary}」という悩みを乗り越えた経験を持っています。",
                f"  - このアカウントが最終的に届けたい想い（パーパス）は「{account_purpose}」です。",
                f"  - このアカウントが提供する約束（コアバリュー）は「{core_value_proposition}」です。",
            ]
            if persona_profile_for_ai and persona_profile_for_ai.strip():
                 prompt_parts.extend(["\n## 矛盾を防ぐための絶対ルール：発信者の現在地", f"  - プロフィール: {persona_profile_for_ai}", "  - 注意: 生成するツイートは、必ずこのプロフィールと矛盾しないようにしてください。これはツイートのテーマではなく、矛盾を防ぐための「背景情報」です。", "  - NG例: 「フルリモートで成功している」というプロフィールなのに「パート先で嫌なことがあった」など、現在の立場と明らかに食い違う内容は絶対に含めないでください。"])
            if research_summary:
                prompt_parts.append(f"\n## 参考となる最新リサーチ情報（必要に応じて活用）:\n{research_summary}")
            if initial_post_type == "follow_reason":
                prompt_parts.append("\n## 今回のツイート作成指示:【フォローすべき理由】")
                prompt_parts.append("  - **思考のフレームワーク**: 以下の3つの心理的トリガーを刺激する要素を、あなたの卓越した文章力で自然に織り交ぜてください。")
                prompt_parts.append("    1. **自己関連付け (Self-Reference)**: 読者が『これは、まさに私のことだ…』とドキッとするような、具体的な悩みや状況を指摘する『問いかけ』。")
                prompt_parts.append("    2. **ゲインフレーム (Gain Frame)**: フォローすることで得られる『理想の未来』や『具体的なメリット』を、読者が鮮明にイメージできるように描写する。")
                prompt_parts.append("    3. **独自性 (Uniqueness)**: このアカウントでしか得られない『ユニークな価値』や『他とは違う視点』を明確に提示する。")
                prompt_parts.append(f"  - **テーマ**: {theme if theme else 'このアカウントをフォローすべき理由を、感情と論理の両面に訴えかける形で表現してください。'}")
            elif initial_post_type == "self_introduction":
                prompt_parts.append("\n## 今回のツイート作成指示:【自己紹介（自分神話の断片）】")
                prompt_parts.append("  - **思考のフレームワーク**: 以下の3つのストーリーテリング要素を、あなたの卓越した文章力でドラマチックに繋ぎ合わせてください。")
                prompt_parts.append("    1. **共感の谷 (Valley of Empathy)**: 読者と同じか、それ以上に『ダメダメだった過去』や『壮絶な失敗談』を、正直かつ具体的に描写する。")
                prompt_parts.append("    2. **転換点 (Turning Point)**: そのどん底の状態から這い上がる『きっかけ』となった出来事や、考え方の変化を簡潔に示す。")
                prompt_parts.append("    3. **理念の光 (Beacon of Philosophy)**: なぜ今、この情報発信をしているのか。その根底にある『情熱』や『譲れない想い』を、力強く宣言する。")
                prompt_parts.append(f"  - **テーマ**: {theme if theme else 'あなた自身の言葉で、読者の心を動かすショートストーリーを作成してください。'}")
            else:
                prompt_parts.append("\n## 今回のツイート作成指示:【自由テーマ】")
                prompt_parts.append("  - **思考のフレームワーク**: 以下のいずれか、または複数の要素を自由に組み合わせて、あなたのセンスで最高のツイートを作成してください。『時事ネタへの専門的見解』、『ターゲット層への鋭い問いかけ』、『個人的な体験談からの学び』、『意外な統計データと考察』。")
                prompt_parts.append(f"  - **テーマ**: {theme if theme else '自由にテーマを設定し、読者の興味を引くツイートを作成してください。'}")
            
            prompt = "\n".join(filter(None, prompt_parts))
            generation_config = genai_types.GenerateContentConfig(temperature=0.7)
            print(f">>> Final prompt for generation (non-value-tips):\n{prompt[:600]}...")
            response = client.models.generate_content(model=model_id, contents=prompt, config=generation_config)
            final_tweet = re.sub(r'^(.*\n)*', '', response.text, 1).strip()
        
        # --- 共通の最終処理 ---
        if not final_tweet:
            raise Exception("AIによるツイート生成に失敗しました。")

        return jsonify({
            "generated_tweet": final_tweet,
            "grounding_info": grounding_info_to_return 
        }), 200

    except Exception as e:
        print(f"!!! Major exception in generate_initial_tweet: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる初期ツイート生成中に予期せぬエラーが発生しました。", "error": str(e)}), 500
    
# Flaskサーバーの起動
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)