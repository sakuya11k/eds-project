
import os
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from functools import wraps
import datetime
import traceback
import time
from google import genai
from google.genai import types as genai_types
import tweepy
from cryptography.fernet import Fernet
import json
import re 
import requests
from bs4 import BeautifulSoup

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



# --- AIモデル準備用のヘルパー関数 ---

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
        
        # 4. 新しいSDKの作法でAPIを呼び出す
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=config 
        )
        return response

    except Exception as e:
        print(f"!!! Exception during Gemini API call: {e}")
        raise e
    


# --- 認証デコレーター ---
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
            

            # 1. フィールドをすべて定義
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
            
           
            res = supabase.table('account_strategies').upsert(data_to_update, on_conflict='x_account_id').execute()
            
            

            if res.data:
                return jsonify(res.data[0]), 200
            else:
                error_details = res.error.message if hasattr(res, 'error') and res.error else "Unknown DB error"
                
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
            
            "あなたは、個人のブランドストーリーを構築する、一流のストーリーテラー兼コピーライターです。",
            "あなたの仕事は、クライアントの断片的な情報から、その人の「物語の始まり」となる、魂のこもった「基本理念・パーパス」を紡ぎ出すことです。",
            "以下の情報を元に、読者の心を揺さぶり、希望を与える「基本理念・パーパス」のドラフトを1つ、250～350字程度で作成してください。",
            
            f"\n## クライアント情報:",
            f"  - アカウント名: @{current_x_username}",
            f"  - クライアントが表現したいこと（キーワード）: {user_keywords if user_keywords else '特に指定なし'}",
            f"  - 提供予定の商品/サービス概要: {current_product_summary}",
            
           
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
        
        # 4. 新しいSDKでAPIを呼び出す
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

#目的の提案

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

        # 3. 新しいSDKでAPIを呼び出す
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
        
        # 2. プロンプトを組み立てる
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

        # 3. 新しいSDKでAPIを呼び出す
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

        # 4. JSON抽出ロジック
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

        # 4. プロンプトを組み立てる
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

        # 5. 新しいSDKでAPIを呼び出す
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

#商品取得
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

        # 2. システム指示（プロンプト）を組み立てる
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

        # 3. 新しいSDKでチャットセッションを開始・継続する
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        
        #  チャットを開始する
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
        
        
        generated_drafts = {}
        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')

        print(f">>> Generating All Base Policies Draft for x_account_id: {x_account_id}")

        for element in base_policies_elements:
            element_key = element['key']
            element_name = element['name']
            element_desc = element['desc']
            
        
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
            
             return jsonify({"message":"ローンチは作成されましたが、戦略シートの自動作成に失敗しました。", "launch":created_launch, "strategy_error":str(s_res.error)}), 207

        return jsonify(created_launch), 201
        
    except Exception as e:
        print(f"!!! Exception creating launch: {e}")
        traceback.print_exc()
        return jsonify({"message": "ローンチの作成中にエラーが発生しました", "error": str(e)}), 500




#ローンチ取得
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

        
        delete_res = supabase.table('launches').delete().eq('id', launch_id).eq('user_id', user_id).execute()

        if hasattr(delete_res, 'error') and delete_res.error:
            print(f"!!! Supabase launch delete error for launch_id {launch_id}: {delete_res.error}")
            return jsonify({"message": "Error deleting launch", "error": str(delete_res.error)}), 500
        
        

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
        
        # 5. 新しいSDKでチャットセッションを開始・継続する
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
        

        strategy_elements_definition = [
            {'key': 'product_analysis_summary', 'name': '商品分析の要点', 'desc': 'このローンチにおける商品の強み、弱み、ユニークな特徴、競合との比較など'},
            {'key': 'target_customer_summary', 'name': 'ターゲット顧客分析の要点', 'desc': 'このローンチで狙う顧客層、具体的なペルソナ、悩み、欲求、価値観など'},
            {'key': 'edu_s1_purpose', 'name': '目的の教育', 'desc': '顧客が目指すべき理想の未来、このローンチ/商品で何が得られるか'},
            
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



# --- ツイート管理API ---


@app.route('/api/v1/tweets', methods=['POST'])
@token_required
def save_tweet_draft():
    user_id = g.user.id
    data = request.json
    if not data: return jsonify({"message": "Invalid request: No JSON data provided."}), 400
    

    x_account_id = data.get('x_account_id')
    content = data.get('content')
    if not all([x_account_id, content]):
        return jsonify({"message": "x_account_idとcontentは必須です。"}), 400


    status = data.get('status', 'draft')
    scheduled_at_str = data.get('scheduled_at')
    edu_el_key = data.get('education_element_key')
    launch_id_fk = data.get('launch_id')
    notes_int = data.get('notes_internal')
    image_urls = data.get('image_urls', []) 

  
    scheduled_at_ts = None
    if scheduled_at_str:
        try:
        
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



# ツイート一覧を取得
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
        

        return jsonify(response.data)

    except Exception as e:
        print(f"!!! Tweets fetch exception: {e}"); traceback.print_exc()
    
        error_message = str(e.args[0]) if e.args else str(e)
        return jsonify({"error": "ツイートの取得中にエラーが発生しました", "details": error_message}), 500

#新規ツイート作成
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

# 既存ツイートを更新する
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

# 既存ツイートを削除
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

# ツイートを即時投稿する
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

        # 3.構成指示
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
        
        # 5. 新しいSDKでAPIを呼び出す
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
    
   
  


AUTHORITY_TWEET_FORMATS = {
    "【問題解決型】": {
        "description": "読者の明確な悩みに、具体的な手順を添えて直接的な解決策を提示する。",
        "required_elements": [
            "問題提起: ユーザーの悩みの深刻さや重要性が伝わる、具体的な事実やデータ。",
            "解決策: 悩みを解決できるという希望と、その方法の簡単な紹介。",
            "具体的な手順: 読者がすぐに行動できる、シンプルなステップ。",
            "未来の提示: その行動によって得られるポジティブな変化。"
        ]
    },
    "【ノウハウ公開型】": {
        "description": "専門的で体系化された知識や手法を、具体的な手順として公開する。",
        "required_elements": [
            "価値宣言: これから何を公開するのか、その価値が伝わる魅力的な一文。",
            "ノウハウの核心: 具体的で実践的な知識や手順を数点。",
            "最重要ポイント: 数あるノウハウの中で、特に意識すべきこと。",
            "行動喚起: 読者が「やってみよう」と思えるような、軽やかな締めの一文。"
        ]
    },
    "【気づき共有型】": {
        "description": "権威ある研究結果と個人の体験を結びつけ、読者の常識を覆す「気づき」を与える。",
        "required_elements": [
            "衝撃の事実: 読者の常識を揺さぶるような、意外な研究結果やデータ。",
            "従来の常識との対比: これまで信じられていたことと、新しい事実の違いを明確にする。",
            "新しい視点の提供: その事実から導き出される、新しい考え方や教訓。",
            "行動への誘い: 新しい視点に基づいた、今日からできる小さなアクション。"
        ]
    },
    "【比較検証型】": {
        "description": "対立する二つの説を権威あるデータで比較し、読者に判断基準を提供する。",
        "required_elements": [
            "論争の提示: 「A vs B」という対立構造を読者に分かりやすく提示する。",
            "両案のメリット: それぞれの選択肢の魅力的な点を、具体的なデータや事例を交えて紹介する。",
            "明確な結論・判断基準: 読者が「自分はどっちを選ぶべきか」を自己診断できる、シンプルな基準を提供する。"
        ]
    }
}

@app.route('/api/v1/initial-tweets/generate', methods=['POST', 'OPTIONS'], strict_slashes=False)
@token_required
def generate_initial_tweet():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    print("\n" + "="*80)
    print("--- [AGENT_LOG] START: generate_initial_tweet process ---")
    print("="*80)
    
    user_id = g.user.id
    try:
        data = request.json
        print(f"--- [AGENT_LOG] 1. Received request data:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
        if not data: return jsonify({"error": "Invalid JSON request"}), 400
        x_account_id = data.get('x_account_id')
        initial_post_type = data.get('initial_post_type')
        theme = data.get('theme', '')
        use_Google_Search_flag = True # デフォルトで検索をONにする
        selected_format = data.get('selected_authority_format_by_user', "【問題解決型】")
        if not all([x_account_id, initial_post_type, theme, selected_format]): 
            return jsonify({"error": "x_account_id, initial_post_type, theme, selected_authority_formatは必須です"}), 400
    except Exception as e_parse:
        return jsonify({"error": "Failed to parse request", "details": str(e_parse)}), 400

    try:
        # --- 共通で使う情報を準備 ---
        account_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = account_strategy_res.data if account_strategy_res.data else {}
        user_profile = getattr(g, 'profile', {})
        persona_profile_for_ai = account_strategy.get('persona_profile_for_ai')
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')
        grounding_info_to_return = None
        final_tweet = ""
        
        if initial_post_type == "value_tips":
            print("\n--- [AGENT_LOG] Executing Self-Improving QC loop for 'value_tips'...")
            
            selected_problem = theme
            print(f"--- [AGENT_LOG]   - User Input -> Problem: '{selected_problem}', Format: '{selected_format}'")
            
            research_summary = ""
            if use_Google_Search_flag:
                print(f"--- [AGENT_LOG]   - Google Search is ENABLED by default.")
                # === フェーズ2: 情報収集キーワードの生成 ===
                print("\n--- [AGENT_LOG] Phase 2: Generating search keywords...")
                phase2_prompt = "\n".join([
                    "あなたは、与えられた戦略に基づいて、最適な調査計画を立てるAIリサーチャーです。",
                    f"## 最終目的: 「{selected_problem}」という悩みを、「{selected_format}」という型で解決するツイートを作成するための、精度の高い情報を収集すること。",
                    "\n## 指示", "上記の目的を達成するために、Googleで調査すべき「検索キーワード」を、カンマ区切りで3～5個出力してください。",
                    f"## 型に応じたキーワード生成のヒント:", f" - 今回の型は「{selected_format}」です。この型を構成するために必要な情報を逆算してキーワードを設計してください。",
                    "キーワードのみを出力してください。"
                ])
                phase2_response = client.models.generate_content(model=model_id, contents=phase2_prompt)
                search_keywords = phase2_response.text.strip()
                if not search_keywords: raise Exception("Phase 2: AI failed to generate search keywords.")
                print(f"--- [AGENT_LOG]   - Keywords: {search_keywords}")

                # === フェーズ3: 情報収集・整理 ===
                print("\n--- [AGENT_LOG] Phase 3: Researching the solution...")
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
                print(f"--- [AGENT_LOG]   - Research summary created.")
            else:
                print(f"--- [AGENT_LOG]   - Google Search is DISABLED.")
                research_summary = "（Google検索は使用されていません）"


            # === フェーズ4: ツイートの初回ドラフト生成 ===
            print("\n--- [AGENT_LOG] Phase 4: Generating the first draft...")
            
            format_info = AUTHORITY_TWEET_FORMATS.get(selected_format, {})
            required_elements_list = format_info.get("required_elements", [])
            elements_for_prompt = "\n- ".join(required_elements_list)

            phase4_prompt = "\n".join([
                "あなたは、抽象的なコンセプトを誰もが共感できる「具体的なストーリー」や「実用的なアドバイス」に落とし込むのが得意な、超一流のコンテンツプロデューサーです。",
                "あなたの唯一のミッションは、読者の悩みを「とにかくシンプルに、伝わりやすく」解決することです。\n",
                "## 【最重要ゴールデンルール：抽象から具体へ】",
                "あなたの仕事は、**抽象的なアドバイス（例：『目標を決めよう』）で終わらせず、必ず具体的なアクションや数字（例：『まずは月5万を目指そう』）にまで落とし込んで**、読者に提供することです。",
                "**（〇〇は？△△は？）のような読者への質問で終わらせるのは、仕事の放棄とみなします。**\n",
                "## 【必須構成要素】",
                f"- {elements_for_prompt}\n",
                "## 【絶対に守るべきルール】",
                "1. **文字数:** 全体を**必ず140字以内**に収めること。",
                "2. **簡潔さ:** 難しい言葉や余計な修飾を避け、**一読で理解できる**文章を心がけること。",
                "3. **価値:** 読者が「これだけで悩みが解決した！」と感じるような、**核心的な価値**を提供すること。\n",
                "## 【出力】",
                "- 完成したツイート本文のみを出力してください。見出しや説明は不要です。\n",
                "## 【あなたが使える素材】",
                f"- **解決すべき悩み:** {selected_problem}",
                f"- **根拠となるリサーチ情報:**\n{research_summary}",
                f"- **発信者のプロフィール（最重要注意点：これはツイートのトーン＆マナーを決めるための参考情報です。ツイートの価値を高めない限り、この情報を無理に本文に含める必要は一切ありません。特に『週4勤務』などの個人的すぎる情報は、通常は不要です。）:**\n{persona_profile_for_ai if persona_profile_for_ai else '設定なし'}\n",
                "さあ、あなたのプロの技で、最高の解決策を提示してください。"
            ])
            
            generation_config = genai_types.GenerateContentConfig(temperature=0.8)
            first_draft_response = client.models.generate_content(model=model_id, contents=phase4_prompt, config=generation_config)
            current_tweet_draft = first_draft_response.text.strip()
            
            # ★★★ 自己改善QCループ ★★★
            MAX_REVISIONS = 10
            PASSING_SCORE = 95
            best_score = 0
            best_tweet = current_tweet_draft
            current_research_summary = research_summary

            for i in range(MAX_REVISIONS):
                print(f"\n--- [AGENT_LOG] QC Loop - Iteration {i+1}/{MAX_REVISIONS} ---")
                print(f"--- [AGENT_LOG]   - Current Draft to be evaluated:\n'''\n{current_tweet_draft}\n'''")
                
                print("\n--- [AGENT_LOG]   Phase 5: Quality Check, Scoring, and Task Assignment...")
                
                qc_prompt = "\n".join([
                    "あなたは、結果を出すことにこだわる、超一流のコンテンツ編集長です。",
                    "ライターが提出したツイート案が、読者の悩みを本当に解決し、アカウントの信頼性を高めるかをかなり厳しく採点してより良く改善するためのフィードバックをしてください。",
                    "\n## ★★★ 編集部の絶対憲法（グランドルール） ★★★",
                    "1. **【具体性こそ正義】:** 抽象論は罪。具体的な数字、固有名詞、アクションプランを含んでこそ価値がある。",
                    "2. **【140字の芸術】:** 長文は自己満足。140字以内で核心を突くのがプロの仕事。",
                    "3. **【一読で理解】:** 読者に考えさせたら負け。中学生でも分かる言葉で語ること。",
                    "4. **【悩みの解決】:** ツイートの目的は、読者の悩みをピンポイントで解決すること。それ以外の要素はノイズ。",
                    "5. **【一貫性】:** 発信者のプロフィールと矛盾した内容は、信頼を失うため絶対に許されない。",

                    "\n## 評価対象ツイート（ライターからの提出物）", "```", current_tweet_draft, "```",
                    
                    "\n## 評価のための参考情報",
                    f"- **解決すべき悩み:** {selected_problem}",
                    f"- **根拠となったリサーチ情報:**\n{current_research_summary}",
                    f"- **発信者のプロフィール:**\n{persona_profile_for_ai if persona_profile_for_ai else '設定なし'}\n",

                    "\n## 指示",
                    "上記の**【絶対憲法】**と**【参考情報】**を元に、ツイート案を100点満点で採点してください。",
                    "**【一貫性】の評価では、表面的な数字のズレだけでなく、文脈を読んでください。** 例えば、月20万円稼ぐ人が『最初のステップとして月1万円を目指そう』と語るのは、ストーリーとして自然であり、**矛盾ではありません。**",
                    
                    # ★ QC AIに追加リサーチを命じる権限を与える ★
                
                    "**【重要】もしツイートの主張を裏付けるための【根拠となるリサーチ情報】が不足している、または質が低いと感じた場合は、フィードバックに『〇〇に関する追加リサーチが必要です』と明確に記述してください。**",
                    "** 見やすい投稿にするために改行の指示もしてください**",
                    
                    "\n### 【採点基準】",
                    "- **悩みのピンポイント解決度 (20点):** 『解決すべき悩み』に直接答えているか？",
                    "- **具体性と核心的価値 (20点):** 抽象論に逃げず、具体的な数字や行動が示されているか？",
                    "- **文字数と簡潔さ (20点):** 140字以内で、かつ一読で理解でき、見やすい改行になってるか？",
                    "- **プロフィールとの文脈的一貫性 (10点):** 発信者のストーリーや立場と、文脈的に矛盾がないか？",
                    "- **ツイート型 (15点):** 選択されたツイートの型の要素をみたしてるか",
                    "- **権威性 (15点):** 読者を信頼させるデータや出典があるか",

                    "\n### 【出力形式】",
                    '```json', '{', '  "score": { "total": <合計点>, ... },', f'  "feedback": "（もし{PASSING_SCORE}点未満なら具体的な改善点を記述。{PASSING_SCORE}点以上なら『合格』と記述）"', '}', '```'
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
                    print(f"!!! [AGENT_LOG] QC Loop failed to parse AI response: {e}. Raw: '{qc_response.text}'. Breaking loop."); break
                
                print(f"--- [AGENT_LOG]   - QC Score: {current_score} / {PASSING_SCORE}")
                print(f"--- [AGENT_LOG]   - QC Feedback:\n'''\n{feedback}\n'''")
                
                if current_score > best_score:
                    best_score = current_score
                    best_tweet = current_tweet_draft
                if current_score >= PASSING_SCORE:
                    print(f"--- [AGENT_LOG]   - QC Passed! Final score: {current_score}. Exiting loop.")
                    break

                if i < MAX_REVISIONS - 1:
                    print("\n--- [AGENT_LOG]   Phase 5.8: Converting feedback to a ToDo list...")
                    todo_prompt = "\n".join([
                        "あなたは、編集長の意図を正確に汲み取り、ライターへの**「具体的で実行可能な作業指示」**に落とし込む、超優秀なデスク担当者です。",
                        "\n## 編集部の絶対憲法",
                        "1. **具体性こそ正義**", "2. **140字の芸術**", "3. **一読で理解**", "4. **悩みをピンポイント解決**", "5. **プロフィールと一貫性**",
                        "\n## 編集長からのフィードバック", "```", feedback, "```",
                        "\n## 指示", "編集長のフィードバックと絶対憲法を元に、ライターが**次に何をすべきか**を、**極めて具体的な「修正指示ToDoリスト」**として箇条書きで出力してください。",
                        "特に、フィードバックに『具体性が足りない』や『追加リサーチが必要』といった指摘があれば、**『〇〇という固有名詞を追加せよ』『△△について追加調査せよ』**のように、ToDoを具体化することがあなたの重要な役割です。"
                    ])
                    todo_response = client.models.generate_content(model=model_id, contents=todo_prompt)
                    todo_list = todo_response.text.strip()
                    print(f"--- [AGENT_LOG]   - Generated ToDo List:\n'''\n{todo_list}\n'''")
                    
                    if any(keyword in todo_list for keyword in ["追加情報", "リサーチ", "調査", "権威性", "データ", "根拠"]):
                        print("\n--- [AGENT_LOG]   Phase 6: Executing additional research based on ToDo list...")
                        additional_research_prompt = "\n".join([
                            "あなたは、デスク担当者からの調査依頼に基づき、深掘り調査を行うAIリサーチャーです。",
                            f"\n## 調査依頼（ToDoリスト）\n{todo_list}",
                            "\n## 指示\n上記のToDoリストに含まれる**調査依頼**について、Google検索で調査し、その結果を箇条書きで要約してください。"
                        ])
                        additional_research_config = genai_types.GenerateContentConfig(tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())])
                        additional_research_response = client.models.generate_content(model=model_id, contents=additional_research_prompt, config=additional_research_config)
                        additional_summary = additional_research_response.text.strip()
                        if additional_summary:
                            print(f"--- [AGENT_LOG]     - Additional research summary found.")
                            current_research_summary += f"\n\n【追加リサーチ情報】\n{additional_summary}"
                    
                    print("\n--- [AGENT_LOG]   Phase 7: Revising the tweet based on ToDo list...")
                    revise_prompt = "\n".join([
                        "あなたは、編集デスクからの**具体的な修正指示**に従って、既存のツイート案を改善するプロのライターです。",
                        "\n## ★★★ あなたが修正すべき、現在のツイート案 ★★★",
                        "```", current_tweet_draft, "```",
                        "\n## ★★★ あなたが従うべき、具体的な修正指示書（ToDoリスト） ★★★",
                        "```", todo_list, "```",
                        "\n## 参考情報（修正時に利用可能）",
                        f"- **ツイートの型:** {selected_format}",
                        f"- **根拠となるリサーチ情報:**\n{current_research_summary}",
                        "\n## あなたのタスク",
                        "**【現在のツイート案】**に対して、**【具体的な修正指示書】**に書かれている修正を**すべて**適用してください。",
                        "ゼロから書き直すのではなく、元の文章の良い部分は活かしつつ、指示された箇所だけを的確に修正・改善すること。",
                        "完成したツイート本文のみを出力してください。"
                    ])
                    
                    revise_generation_config = genai_types.GenerateContentConfig(temperature=0.7)
                    revise_response = client.models.generate_content(model=model_id, contents=revise_prompt, config=revise_generation_config)
                    current_tweet_draft = revise_response.text.strip()
                    print(f"--- [AGENT_LOG]   - Revised Draft created.")

                else:
                    print("--- [AGENT_LOG] Max revisions reached. Outputting the best tweet so far.")
            
            final_tweet = best_tweet

        else:
            # --- それ以外のツイート（自己紹介など）の場合 ---
            print(f">>> Executing 1-step generation for '{initial_post_type}'...")
            
            research_summary = ""
            
            
            prompt = "\n".join(filter(None, prompt_parts))
            generation_config = genai_types.GenerateContentConfig(temperature=0.7)
            response = client.models.generate_content(model=model_id, contents=prompt, config=generation_config)
            final_tweet = response.text.strip()
        
        # --- 共通の最終処理 ---
        if not final_tweet:
            raise Exception("AIによるツイート生成に失敗しました。")

        print("\n" + "="*80)
        print("--- [AGENT_LOG] END: generate_initial_tweet process (SUCCESS) ---")
        print(f"--- [AGENT_LOG] Final Tweet to be returned:\n'''\n{final_tweet}\n'''")
        print("="*80 + "\n")
        
        return jsonify({
            "generated_tweet": final_tweet,
            "grounding_info": grounding_info_to_return 
        }), 200

    except Exception as e:
        print(f"!!! [AGENT_LOG] CRITICAL EXCEPTION in generate_initial_tweet: {e}")
        traceback.print_exc()
        print("\n" + "="*80)
        print("--- [AGENT_LOG] END: generate_initial_tweet process (with error) ---")
        print("="*80 + "\n")
        return jsonify({"message": "AIによる初期ツイート生成中に予期せぬエラーが発生しました。", "error": str(e)}), 500
    

# 悩み生成

@app.route('/api/v1/problems/generate', methods=['POST'])
@token_required
def generate_problems():
    global client
    if not client:
        return jsonify({"message": "Gen AI Client is not initialized. Check API Key."}), 500

    print("\n" + "="*80)
    print("--- [AGENT_LOG] START: generate_problems process (17 Hybrid Equations Method) ---")
    print("="*80)

    user_id = g.user.id
    try:
        data = request.json
        print(f"--- [AGENT_LOG] 1. Received request data:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
        x_account_id = data.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "x_account_idは必須です"}), 400

        # --- ペルソナ情報の収集 ---
        account_strategy_res = supabase.table('account_strategies').select('main_target_audience').eq('x_account_id', x_account_id).eq('user_id', user_id).single().execute()
        strategy_data = account_strategy_res.data
        
        target_persona_summary = "一般的なフォロワー"
        main_target_audience_data = strategy_data.get('main_target_audience')
        if main_target_audience_data and isinstance(main_target_audience_data, list) and main_target_audience_data:
            first_persona = main_target_audience_data[0]
            if isinstance(first_persona, dict):
                name = first_persona.get('name', '')
                age = first_persona.get('age', '')
                problem = first_persona.get('悩み', '')
                target_persona_summary = f"ペルソナ「{name}」({age})の悩みは「{problem}」"

        user_profile = getattr(g, 'profile', {})
        model_id = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest')

        # === フェーズ1: 17のハイブリッド方程式による悩みの発散的生成 ===
        print("\n--- [AGENT_LOG] Phase 1: Divergent thinking with 17 Hybrid Equations...")
        
        # 感情エンジン（12の葛藤方程式）
        conflict_equations = [
            "【理想 vs 現実】: [こうありたいという理想] がある。しかし [目を背けたい不甲斐ない現実] がある。",
            "【義務 vs 欲望】: [やるべきこと（理性）] は分かっている。しかし [楽をしたいという誘惑（本能）] に勝てない。",
            "【過去の栄光 vs 現在の停滞】: [過去はこうだったという輝かしい記憶] がある。しかし [それに比べて今の自分は停滞している] という焦りがある。",
            "【挑戦への希望 vs 失敗への恐怖】: [新しいことに挑戦したいという希望] がある。しかし [過去の失敗体験や、未知への恐怖] が足を引っ張る。",
            "【承認欲求 vs 他者からの無理解】: [特定の人に認められたい] と願う。しかし [その人からは心ない言葉や無関心な態度] を示される。",
            "【自己主張 vs 関係性の悪化リスク】: [自分の本音を主張したい]。しかし [それを言うことで、相手との関係が悪化するのが怖い]。",
            "【優越感への渇望 vs 他者との比較による劣等感】: [他人より優位に立ちたい] という欲求がある。しかし [キラキラした他人と自分を比べて] 劣等感を抱いている。",
            "【時間の有限性 vs 無限の選択肢】: [人生の時間は限られているという焦り] がある。しかし [世の中には情報や選択肢が溢れすぎていて]、何から手をつければいいか分からない。",
            "【経済的自由への憧れ vs 社会的制約】: [もっと自由にお金を使いたいという憧れ] がある。しかし [扶養、税金などの社会的制約] に縛られている。",
            "【個人の成長意欲 vs 環境の変化】: [自分は成長したいと強く願っている]。しかし [自分ではコントロールできない環境の変化] に対応せざるを得ない。",
            "【正当な情報への渇望 vs 信頼できない情報源】: [本当に信頼できる情報が知りたい]。しかし [ネット上には怪しい儲け話や、自分とはかけ離れた成功談ばかり] で何を選べばいいか分からない。",
            "【未来への希望 vs 過去への後悔】: [こうすれば未来は変えられるかもしれないという希望]。しかし [『あの時ああしていれば…』という過去への後悔] が、新しい一歩を躊躇させる。"
        ]

        # 行動エンジン（5つのアクション方程式）
        action_equations = [
            "【目標設定の壁】: [〇〇したい]という願望はあるが、[具体的な目標（何を・いつまでに・どのくらい）]に落とし込めず、行動が始まらない。",
            "【情報収集の壁】: [〇〇を学ぶため]に情報を集めているが、[特定の情報（どの本、どのサイト、どのツール）]が信頼できるか分からず、立ち往生している。",
            "【学習・実践の壁】: [〇〇をやってみた]が、[具体的なエラーや問題（××ができない、△△でつまずく）]にぶつかり、解決できずに挫折しそう。",
            "【継続・習慣化の壁】: [〇〇を続ける]と決めたのに、[具体的な障害（急な残業、子供の夜泣き）]によって計画が崩れ、自己嫌悪に陥る。",
            "【収益化・応用の壁】: [〇〇のスキル]は少し身についたが、[それをどうやってお金に変えるか（営業方法、価格設定）]が全く分からず、宝の持ち腐れになっている。"
        ]

        # 全ての方程式を結合
        all_equations = conflict_equations + action_equations
        
        mindmap_prompt = "\n".join([
            "あなたは、人間の深層心理と行動原理を深く理解し、それを心を揺さぶる言葉に変換するプロのコピーライター兼マーケティング戦略家です。",
            "あなたの仕事は、指定されたペルソナが抱えるであろう「葛藤」や「行動の壁」を、多様な切り口から、具体的で共感を呼ぶ「悩み」として言語化することです。\n",
            "## あなたが思考の前提とする情報",
            f"- **ペルソナ:** {target_persona_summary}\n",
            "## ★★★ あなたが実行すべき思考法：17のハイブリッド方程式 ★★★",
            "以下の**17個の『方程式』**のそれぞれを思考の起点としてください。",
            "各方程式の[ ]の中身をペルソナの状況に合わせて埋めることで、具体的な悩みを**それぞれ3個ずつ**、合計で約50個生成してください。\n",
            "### 17の方程式（感情エンジン + 行動エンジン）",
            "\n".join(f"- {eq}" for eq in all_equations),
            "\n## 指示",
            "上記の思考法を用いて、合計約50個の具体的な悩みを生成し、以下のJSON形式で出力してください。",
            "**『感情的な悩み』と『行動に直結する悩み』がバランス良く含まれるように**、リスト全体を構成してください。",
            "生成する悩みは、読者が『これ、私のことだ…』と強く共感するような、具体的で生々しい言葉で記述してください。\n",
            "## 最終的な出力形式",
            "```json",
            "{",
            '  "generated_problems": [',
            '    { "equation_type": "理想 vs 現実", "problem_text": "（この方程式から生まれた悩み1）" },',
            '    { "equation_type": "目標設定の壁", "problem_text": "（この方程式から生まれた悩み2）" },',
            "    ...",
            '    { "equation_type": "収益化・応用の壁", "problem_text": "（この方程式から生まれた悩み51）" }',
            "  ]",
            "}",
            "```",
            "JSON以外の説明文は、一切含めないでください。"
        ])

        generation_config = genai_types.GenerateContentConfig(temperature=0.95) # 多様性を最大化
        response = client.models.generate_content(model=model_id, contents=mindmap_prompt, config=generation_config)
        
        try:
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if not json_match: raise json.JSONDecodeError("No JSON object found.", response.text, 0)
            initial_problems = json.loads(json_match.group(0)).get("generated_problems", [])
        except (json.JSONDecodeError, KeyError) as e:
            raise Exception(f"Phase 1 failed to parse AI response: {e}")

        print(f"--- [AGENT_LOG]   - Generated {len(initial_problems)} draft problems.")
        
        # === フェーズ2 & 3: QCと修正のループ ===
        MAX_REVISIONS = 2
        best_problems = initial_problems

        for i in range(MAX_REVISIONS):
            print(f"\n--- [AGENT_LOG] Problem QC Loop - Iteration {i+1}/{MAX_REVISIONS} ---")
            
            qc_prompt = "\n".join([
                "あなたは、読者の心を一瞬で掴む言葉を見つけ出すのが得意な、超一流の編集長です。",
                "コピーライターが提出した『悩みのドラフトリスト』を評価し、品質が低いものを指摘・修正してください。\n",
                "## 品質の低い悩みの定義",
                "- **抽象的すぎる:** 『〇〇について知りたい』のような、誰にでも当てはまる漠然とした悩み。",
                "- **行動に繋がらない:** 感情の吐露だけで終わり、『じゃあ、どうすれば？』という具体的な行動課題が見えない悩み。",
                "- **重複している:** リスト内に、本質的に同じ悩みが複数含まれている。\n",
                "## ドラフトリスト",
                "```json",
                json.dumps(best_problems, indent=2, ensure_ascii=False),
                "```\n",
                "## 指示",
                f"1. **評価:** リストに品質の低い悩みが含まれていないか、また、重複がないか、悩みの総数が50個に満たない場合は、その旨を指摘してください。",
                "2. **フィードバック:** もし改善点がある場合、具体的な修正指示を出してください。修正指示がない場合は、`feedback`は`'合格'`としてください。",
                "3. **修正:** フィードバックに基づき、リスト全体を修正・再生成し、必ず50個の**重複がなく、それぞれが『感情』と『行動』の両面で鋭い言葉で表現された高品質な悩み**のリストにしてください。\n",
                "## 出力形式",
                "```json",
                '{',
                '  "feedback": "（具体的な改善指示、または『合格』）",',
                '  "revised_problems": [ ... ]',
                '}',
                "```"
            ])

            qc_response = client.models.generate_content(model=model_id, contents=qc_prompt)
            
            try:
                json_match = re.search(r'\{.*\}', qc_response.text, re.DOTALL)
                if not json_match: raise json.JSONDecodeError("No JSON object found.", qc_response.text, 0)
                qc_result = json.loads(json_match.group(0))
                feedback = qc_result.get("feedback", "")
                revised_problems = qc_result.get("revised_problems", [])
            except (json.JSONDecodeError, KeyError) as e:
                print(f"!!! [AGENT_LOG] Problem QC Loop failed to parse AI response: {e}. Breaking loop."); break
            
            print(f"--- [AGENT_LOG]   - QC Feedback:\n'''\n{feedback}\n'''")
            best_problems = revised_problems
            
            if feedback == '合格':
                print(f"--- [AGENT_LOG]   - QC Passed! Exiting loop.")
                break
        
        # === 最終出力 ===
        print(f"\n--- [AGENT_LOG] 4. Finalizing {len(best_problems)} problems to return to frontend...")
        final_problems_for_frontend = [{"problem_text": p.get("problem_text"), "pain_point": p.get("equation_type", "不明")} for p in best_problems]
        return jsonify({"generated_problems": final_problems_for_frontend}), 200

    except Exception as e:
        print(f"!!! [AGENT_LOG] CRITICAL EXCEPTION in generate_problems: {e}"); traceback.print_exc()
        return jsonify({"message": "悩みリストの生成中にエラーが発生しました。", "error": str(e)}), 500


# フロントエンドから悩みリストを保存

@app.route('/api/v1/problems/save', methods=['POST'])
@token_required
def save_problems():
    user_id = g.user.id
    try:
        data = request.json
        problems_to_save = data.get('problems_to_save', [])
        x_account_id = data.get('x_account_id')

        if not problems_to_save or not x_account_id:
            return jsonify({"error": "保存する悩みリストとx_account_idは必須です"}), 400

        problems_to_insert = [
            {
                "user_id": user_id,
                "x_account_id": x_account_id,
                "problem_text": item.get("problem_text"),
                "pain_point": item.get("pain_point"),
                "status": "saved" # 保存するのでステータスを'saved'に
            }
            for item in problems_to_save if item.get("problem_text")
        ]

        if not problems_to_insert:
            return jsonify({"error": "保存する有効な悩みがありません"}), 400

        insert_res = supabase.table('generated_problems').insert(problems_to_insert).execute()

        if insert_res.data:
            return jsonify({"message": f"{len(insert_res.data)}件の悩みを保存しました。"}), 201
        else:
            error_message = "Unknown error"
            if insert_res.error:
                error_message = insert_res.error.message
            raise Exception(f"データベースへの保存に失敗しました。Error: {error_message}")

    except Exception as e:
        print(f"!!! Exception in save_problems: {e}"); traceback.print_exc()
        return jsonify({"message": "悩みの保存中にエラーが発生しました。", "error": str(e)}), 500
    

# 保存済みの悩みリストを取得するAPI。

@app.route('/api/v1/problems', methods=['GET'])
@token_required
def get_problems():
    user_id = g.user.id
    try:
        x_account_id = request.args.get('x_account_id')
        if not x_account_id:
            return jsonify({"error": "x_account_idは必須です"}), 400

        # 保存済みの悩み（statusが'saved'）を取得し、作成日の降順で並び替え
        problems_res = supabase.table('generated_problems') \
            .select('*') \
            .eq('user_id', user_id) \
            .eq('x_account_id', x_account_id) \
            .eq('status', 'saved') \
            .order('created_at', desc=True) \
            .execute()

        if problems_res.data:
            return jsonify(problems_res.data), 200
        else:
            return jsonify([]), 200 # データがなくても空のリストを返す

    except Exception as e:
        print(f"!!! Exception in get_problems: {e}"); traceback.print_exc()
        return jsonify({"message": "悩みリストの取得中にエラーが発生しました。", "error": str(e)}), 500


#  選択した悩みを削除

@app.route('/api/v1/problems', methods=['DELETE'])
@token_required
def delete_problems():
    user_id = g.user.id
    try:
        data = request.json
        problem_ids = data.get('problem_ids', []) # 削除する悩みのIDリスト
        if not problem_ids:
            return jsonify({"error": "削除する悩みのIDを指定してください"}), 400

        # 指定されたIDの悩みを削除
        delete_res = supabase.table('generated_problems') \
            .delete() \
            .in_('id', problem_ids) \
            .eq('user_id', user_id) \
            .execute()

        if delete_res.data:
            return jsonify({"message": f"{len(delete_res.data)}件の悩みを削除しました。"}), 200
        else:
            # エラーレスポンスがあるか確認
            error_message = "削除に失敗しました。対象の悩みが見つからないか、権限がありません。"
            if delete_res.error:
                error_message = delete_res.error.message
            raise Exception(error_message)

    except Exception as e:
        print(f"!!! Exception in delete_problems: {e}"); traceback.print_exc()
        return jsonify({"message": "悩みの削除中にエラーが発生しました。", "error": str(e)}), 500




# Flaskサーバーの起動
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)