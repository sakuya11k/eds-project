import os
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from functools import wraps
import datetime
import traceback
import google.generativeai as genai
from google.generativeai.types import Tool, GenerationConfig
import tweepy
from cryptography.fernet import Fernet

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
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    print(">>> Gemini API key configured.")

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
def get_current_ai_model(user_profile, use_Google_Search=False, system_instruction_text=None):
    """
    ユーザーのプロフィール設定に基づいて、適切なGoogle Generative AIモデルを初期化して返す。
    """
    try:
        # ユーザーが選択したモデル名を取得。未設定ならデフォルト値を使用。
        # ここでは g.profile ではなく、引数で渡された user_profile を使用する
        model_name = user_profile.get('preferred_ai_model', 'gemini-1.5-flash-latest') # デフォルトモデルを最新版に
        
        # Google検索ツールを使うかどうかの設定
        tools = [Tool.from_google_search_retrieval(google_search_retrieval={})] if use_Google_Search else None
        
        # AIへの事前指示（システムプロンプト）の設定
        system_instruction = system_instruction_text if system_instruction_text else None

        # GenerationConfig の設定 (必要に応じて)
        # temperatureが高いほど創造的に、低いほど決定論的になる (0.0 ~ 1.0)
        generation_config = GenerationConfig(
            temperature=0.7,
        )

        print(f">>> Initializing AI model: {model_name} (Search: {use_Google_Search})")
        
        # モデルを初期化
        model = genai.GenerativeModel(
            model_name=model_name,
            tools=tools,
            system_instruction=system_instruction,
            generation_config=generation_config
        )
        return model

    except Exception as e:
        print(f"!!! Failed to initialize AI model '{user_profile.get('preferred_ai_model', 'default')}': {e}")
        traceback.print_exc()
        return None

# --- 認証デコレーター (最終修正版) ---
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
        # このx_account_idが本当にこのユーザーのものかを確認
        x_account_check_res = supabase.table('x_accounts').select('id', count='exact').eq('id', x_account_id).eq('user_id', user_id).execute()
        if x_account_check_res.count == 0:
            return jsonify({"error": "Account not found or access denied"}), 404

        # --- GETリクエスト処理 ---
        if request.method == 'GET':
            # x_account_idに紐づく戦略を取得
            strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).limit(1).execute()
            
            strategy_data = strategy_res.data[0] if strategy_res.data else {}
            return jsonify(strategy_data), 200

        # --- PUTリクエスト処理 ---
        if request.method == 'PUT':
            data = request.get_json()
            if not data: return jsonify({"error": "Invalid JSON"}), 400
            
            # 更新データに必須情報を付与
            data['x_account_id'] = str(x_account_id)
            data['user_id'] = user_id
            data['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            res = supabase.table('account_strategies').upsert(data, on_conflict='x_account_id').execute()

            if res.data:
                return jsonify(res.data[0]), 200
            else:
                error_details = res.error.message if hasattr(res, 'error') and res.error else "Unknown DB error"
                return jsonify({"error": "Failed to update strategy", "details": error_details}), 500
    
    except Exception as e:
        # この関数内で発生した予期せぬ例外をすべてキャッチ
        print(f"!!! UNHANDLED EXCEPTION in handle_account_strategy: {e}")
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

@app.route('/api/v1/profile/suggest-purpose', methods=['POST'])
@token_required
def suggest_account_purpose():
    user_profile = getattr(g, 'profile', {})
    if not user_profile:
        return jsonify({"message": "User profile not found."}), 403

    data = request.json
    user_keywords = data.get('user_keywords', '') # 例: "自由な働き方, 初心者向け, 収益化支援"
    existing_website_content = data.get('website_content', '') # 将来的にウェブサイトのURLから内容を取得する機能も考えられる

    # 現在のプロファイル情報も参考にする
    current_username = user_profile.get('username', '名無しの発信者')
    current_product_summary = user_profile.get('main_product_summary', '提供商品・サービスについての詳細情報')

    model = get_current_ai_model(user_profile)
    if not model:
        return jsonify({"message": "AI model could not be initialized."}), 500

    prompt_parts = [
        f"あなたは経験豊富なブランドストラテジスト兼コピーライターです。",
        f"以下の情報を元に、ユーザー「{current_username}」のXアカウントの魅力的で共感を呼ぶ「基本理念・パーパス」のドラフトを3案、それぞれ100～150字程度で提案してください。",
        f"## 参考情報:",
        f"  - ユーザーが入力したキーワード: {user_keywords if user_keywords else '特に指定なし'}",
        f"  - ユーザーの主要商品/サービス概要: {current_product_summary if current_product_summary else '特に指定なし'}",
    ]
    if existing_website_content:
        prompt_parts.append(f"  - ユーザーの既存ウェブサイトの内容（抜粋）: {existing_website_content[:500]}...") # 長文の場合は切り詰める
    
    prompt_parts.append(f"## 作成指示:")
    prompt_parts.append(f"  - 各提案は、ターゲット顧客に響き、アカウントの方向性を示すような内容にしてください。")
    prompt_parts.append(f"  - ポジティブで、インスピレーションを与えるようなトーンが望ましいです。")
    prompt_parts.append(f"  - 提案は箇条書きで、各案の前に「提案1:」「提案2:」のように番号を振ってください。")
    
    prompt = "\n".join(prompt_parts)
    print(f">>> Suggest Account Purpose Prompt: \n{prompt[:500]}...")

    try:
        ai_response = model.generate_content(prompt)
        suggestions_text = ai_response.text
        
        # AIの応答から各提案をパースする (単純な改行区切りなどを想定)
        # より複雑な場合は正規表現や構造化された出力をAIに求める
        suggestions_list = [s.strip().lstrip("提案1:").lstrip("提案2:").lstrip("提案3:").strip() for s in suggestions_text.splitlines() if s.strip()]
        
        # 最初の提案をメインのsuggestionとして返すか、リスト全体を返すか選択
        # ここでは最初の提案を返す例
        main_suggestion = suggestions_list[0] if suggestions_list else "AIからの提案生成に失敗しました。もう一度お試しください。"

        print(f">>> AI Suggested Purpose: {main_suggestion}")
        # フロントエンドが複数の提案を扱えるなら、リストで返す
        # return jsonify({"suggestions": suggestions_list}), 200 
        return jsonify({"suggestion": main_suggestion}), 200

    except Exception as e:
        print(f"!!! Exception during AI purpose suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる目的提案中にエラーが発生しました。", "error": str(e)}), 500
    
    # ペルソナ案を複数提案

@app.route('/api/v1/profile/suggest-persona-draft', methods=['POST'])
@token_required
def suggest_persona_draft():
    user_profile = getattr(g, 'profile', {})
    if not user_profile:
        return jsonify({"message": "User profile not found."}), 403

    data = request.json
    user_keywords = data.get('user_keywords', '') # 例: "30代 主婦 副業"
    num_personas_to_suggest = data.get('num_personas', 2) # フロントエンドから提案数を指定できるようにする

    # アカウント戦略の他の情報も参考にする
    current_product_summary = user_profile.get('main_product_summary', '未設定の商品・サービス概要')
    current_account_purpose = user_profile.get('account_purpose', '未設定のアカウント目的')

    model = get_current_ai_model(user_profile)
    if not model:
        return jsonify({"message": "AI model could not be initialized."}), 500

    prompt_parts = [
        f"あなたは経験豊富なマーケターであり、ペルソナ設定の専門家です。",
        f"以下の情報を元に、ターゲット顧客となりうる具体的なペルソナのドラフトを{num_personas_to_suggest}案、提案してください。",
        f"各ペルソナ案には、以下の項目を含めてください: 「名前（例：佐藤みき）」「年齢層/属性（例：30代後半、子育て中のパート主婦）」「主な悩み/欲求/課題（例：子供との時間を大切にしながら、家計のために月5万円の追加収入が欲しい。PCスキルにはあまり自信がない。）」。",
        f"## 参考情報:",
        f"  - ユーザーが入力したターゲットキーワード: {user_keywords if user_keywords else '特に指定なし'}",
        f"  - ユーザーの主要商品/サービス概要: {current_product_summary}",
        f"  - ユーザーのアカウントの目的: {current_account_purpose}",
        f"## 作成指示:",
        f"  - 各ペルソナは、提供される商品やサービスに興味を持ちそうな、現実的な人物像として描写してください。",
        f"  - 悩みや欲求は、商品やサービスで解決できる可能性のあるものを含めてください。",
        f"  - 出力は、各ペルソナを辞書のリスト（JSON形式）として返してください。各辞書のキーは 'name', 'age', '悩み' としてください。",
        f"例: [{'name': '田中あい', 'age': '20代後半 OL', '悩み': 'キャリアアップしたいが、何を学ぶべきか分からない。'}, {{'name': '鈴木けんた', 'age': '40代 個人事業主', '悩み': '集客がうまくいかず、売上が不安定。'}}]"
    ]
    prompt = "\n".join(prompt_parts)
    print(f">>> Suggest Persona Draft Prompt (first 500 chars): \n{prompt[:500]}...")

    try:
        ai_response = model.generate_content(prompt)
        # AIにJSON形式で出力するよう指示しているので、パースを試みる
        try:
            # AIの応答が ```json ... ``` のようなマークダウン形式で返ってくる場合を考慮
            import json
            response_text = ai_response.text
            if response_text.strip().startswith("```json"):
                response_text = response_text.strip()[7:-3].strip() # ```json と ``` を除去
            
            suggested_personas = json.loads(response_text)
            if not isinstance(suggested_personas, list): # リスト形式でなければエラー
                raise ValueError("AI response for personas is not a list.")
            # 各ペルソナに必要なキーがあるか簡易チェック
            for persona in suggested_personas:
                if not all(k in persona for k in ['name', 'age', '悩み']):
                    raise ValueError("Persona object missing required keys.")

        except (json.JSONDecodeError, ValueError) as e_parse:
            print(f"!!! Error parsing AI response for personas: {e_parse}. Raw text: {ai_response.text}")
            # パース失敗時は、テキストをそのまま返すか、エラーメッセージと共に返す
            # ここでは、パース失敗を示すメッセージをリストに入れて返す例
            suggested_personas = [{"name": "AI提案解析エラー", "age": "-", "悩み": f"AIの応答を期待した形式で解析できませんでした。AIの応答: {ai_response.text[:200]}..."}]
            toast_message_frontend = "AI提案の形式が正しくありませんでした。テキストとして表示します。"
            # return jsonify({"message": toast_message_frontend, "suggested_personas_raw_text": ai_response.text}), 500


        print(f">>> AI Suggested Personas: {suggested_personas}")
        return jsonify({"suggested_personas": suggested_personas}), 200

    except Exception as e:
        print(f"!!! Exception during AI persona suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによるペルソナ提案中にエラーが発生しました。", "error": str(e)}), 500
    
    
    # 商品概要やペルソナの悩みから提供価値を提案します

@app.route('/api/v1/profile/suggest-value-proposition', methods=['POST'])
@token_required
def suggest_value_proposition():
    user_profile = getattr(g, 'profile', {})
    if not user_profile:
        return jsonify({"message": "User profile not found."}), 403

    # アカウント戦略から必要な情報を取得
    current_product_summary = user_profile.get('main_product_summary', '未設定の商品・サービス概要')
    main_target_audience_data = user_profile.get('main_target_audience') # JSONB想定 (リスト)
    
    target_audience_summary = "設定されていません。"
    if main_target_audience_data and isinstance(main_target_audience_data, list) and len(main_target_audience_data) > 0:
        # 簡単のため、最初のペルソナの悩みを代表として使用
        first_persona = main_target_audience_data[0]
        target_audience_summary = f"ペルソナ「{first_persona.get('name', '未設定')}」が抱える主な悩みは「{first_persona.get('悩み', '未設定の悩み')}」です。"
    elif user_profile.get('target_persona'): # 簡易版のフォールバック
        target_audience_summary = user_profile.get('target_persona')

    model = get_current_ai_model(user_profile)
    if not model:
        return jsonify({"message": "AI model could not be initialized."}), 500

    prompt_parts = [
        f"あなたは顧客の心を掴む価値提案（バリュープロポジション）を作成する専門家です。",
        f"以下の情報を元に、このアカウントの「コアとなる提供価値」のメッセージ案を3つ、それぞれ簡潔に提案してください。",
        f"## 参考情報:",
        f"  - アカウントの主要商品/サービス概要: {current_product_summary}",
        f"  - 主なターゲット顧客とその悩み（概要）: {target_audience_summary}",
        f"  - アカウントの目的・パーパス（もしあれば）: {user_profile.get('account_purpose', '未設定')}",
        f"## 作成指示:",
        f"  - 各提案は、ターゲット顧客が「これは私のためのものだ！」と感じ、強く惹きつけられるような、具体的でユニークな価値を表現してください。",
        f"  - 商品やサービスが顧客のどのような問題を解決し、どのような理想の未来をもたらすのかを明確に示してください。",
        f"  - 簡潔かつキャッチーな表現を心がけてください（各50～100字程度）。",
        f"  - 提案は箇条書きで、各案の前に「提案A:」「提案B:」のように記号を振ってください。"
    ]
    prompt = "\n".join(prompt_parts)
    print(f">>> Suggest Value Proposition Prompt (first 500 chars): \n{prompt[:500]}...")

    try:
        ai_response = model.generate_content(prompt)
        suggestions_text = ai_response.text
        suggestions_list = [s.strip().lstrip("提案A:").lstrip("提案B:").lstrip("提案C:").strip() for s in suggestions_text.splitlines() if s.strip()]
        main_suggestion = suggestions_list[0] if suggestions_list else "AIからの提案生成に失敗しました。"

        print(f">>> AI Suggested Value Proposition: {main_suggestion}")
        # フロントエンドが複数提案を扱えるならリストで返す
        # return jsonify({"suggestions": suggestions_list}), 200 
        return jsonify({"suggestion": main_suggestion}), 200
    except Exception as e:
        print(f"!!! Exception during AI value proposition suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる提供価値提案中にエラーが発生しました。", "error": str(e)}), 500
    
    
    # ブランドボイス詳細（トーン、キーワード、NGワード）を提案

@app.route('/api/v1/profile/suggest-brand-voice', methods=['POST'])
@token_required
def suggest_brand_voice():
    user_profile = getattr(g, 'profile', {})
    if not user_profile:
        return jsonify({"message": "User profile not found."}), 403

    data = request.json
    adjectives = data.get('adjectives', '') # 例: "親しみやすい, 専門的, 熱血"
    # reference_account_url = data.get('reference_account_url', '') # 将来的にはURLから分析も

    model = get_current_ai_model(user_profile)
    if not model:
        return jsonify({"message": "AI model could not be initialized."}), 500

    prompt_parts = [
        f"あなたはブランドパーソナリティとSNSコミュニケーションの専門家です。",
        f"ユーザーが目指すブランドイメージに合致する「ブランドボイス詳細」を提案してください。",
        f"提案には、「基本トーン（簡潔な説明文）」「推奨キーワード/フレーズ（5個程度）」「避けるべきNGワード/フレーズ（3個程度）」の3点を含めてください。",
        f"## ユーザーがイメージするブランドの雰囲気（形容詞など）:",
        f"  - {adjectives if adjectives else '特に指定なし (ユーザーの既存設定や商品特性から推測してください)'}",
        f"## 参考情報（ユーザーの既存設定）:",
        f"  - アカウントの目的: {user_profile.get('account_purpose', '未設定')}",
        f"  - ターゲット顧客像（概要）: {user_profile.get('target_persona', '未設定')}", # main_target_audience を使う方が良い
        f"  - 主要商品/サービス概要: {user_profile.get('main_product_summary', '未設定')}",
        f"## 作成指示:",
        f"  - 提案するトーン、キーワード、NGワードは、上記の情報と調和し、一貫性のあるブランドイメージを形成する助けとなるようにしてください。",
        f"  - 出力は、キーが 'tone' (文字列), 'keywords' (文字列のリスト), 'ng_words' (文字列のリスト) であるJSONオブジェクト形式で返してください。",
        f"例: {{ \"tone\": \"読者に寄り添い、優しく励ますお姉さんのようなトーン。専門的な内容も分かりやすく解説するが、上から目線にならないように注意する。\", \"keywords\": [\"あなたならできる\", \"一緒に頑張ろう\", \"大丈夫だよ\", \"ステップバイステップ\", \"分かりやすい\"], \"ng_words\": [\"絶対\", \"簡単すぎる\", \"誰でも稼げる\"] }}"
    ]
    prompt = "\n".join(prompt_parts)
    print(f">>> Suggest Brand Voice Prompt (first 500 chars): \n{prompt[:500]}...")
    
    # 登録済み商品情報から「主要商品群の分析サマリー」を生成

@app.route('/api/v1/profile/suggest-product-summary', methods=['POST'])
@token_required
def suggest_product_summary():
    user_profile = getattr(g, 'profile', {})
    user_id = getattr(g, 'user', {}).id
    if not user_profile or not user_id:
        return jsonify({"message": "User context not found."}), 403

    # ユーザーの商品情報をデータベースから取得
    try:
        products_res = supabase.table('products').select("name, description, price, target_audience, value_proposition").eq('user_id', user_id).execute()
        if hasattr(products_res, 'error') and products_res.error:
            print(f"!!! Error fetching user products: {products_res.error}")
            return jsonify({"message": "ユーザーの商品情報の取得に失敗しました。", "error": str(products_res.error)}), 500
        
        user_products = products_res.data
        if not user_products:
            return jsonify({"suggestion": "登録されている商品がありません。まず商品を登録してください。"}), 200 # 提案ではなく情報提供

    except Exception as e_db:
        print(f"!!! DB Exception fetching user products: {e_db}")
        traceback.print_exc()
        return jsonify({"message": "商品情報取得中にデータベースエラーが発生しました。", "error": str(e_db)}), 500

    model = get_current_ai_model(user_profile)
    if not model:
        return jsonify({"message": "AI model could not be initialized."}), 500

    products_info_text = "\n".join([
        f"- 商品名: {p.get('name', '無名')}\n  説明: {p.get('description', '説明なし')[:100]}...\n  提供価値: {p.get('value_proposition', '提供価値未設定')[:100]}..."
        for p in user_products[:5] # 最大5商品までを参考情報とする（プロンプト長制限のため）
    ])

    prompt_parts = [
        f"あなたは複数の商品を展開するビジネスのブランド戦略家です。",
        f"以下のユーザーが登録している商品群の情報を元に、アカウント全体の「主要商品群の分析サマリー」を作成してください。",
        f"このサマリーは、アカウント戦略の基盤となり、発信内容の一貫性を保つために使われます。",
        f"## ユーザー登録商品情報（一部抜粋）:",
        f"{products_info_text if products_info_text else '商品情報がありません。'}",
        f"## 作成指示:",
        f"  - 商品群全体に共通する「強み」「中心的な提供価値」「主要なターゲット層への訴求ポイント」を分析し、簡潔に（200～300字程度で）まとめてください。",
        f"  - 個々の商品紹介ではなく、商品群全体を俯瞰した上での特徴や戦略的意義を記述してください。",
        f"  - ポジティブで魅力的な表現を心がけてください。"
    ]
    prompt = "\n".join(prompt_parts)
    print(f">>> Suggest Product Summary Prompt (first 500 chars): \n{prompt[:500]}...")

    try:
        ai_response = model.generate_content(prompt)
        suggestion = ai_response.text.strip() if ai_response.text else "AIからの提案生成に失敗しました。"
        
        print(f">>> AI Suggested Product Summary: {suggestion}")
        return jsonify({"suggestion": suggestion}), 200
    except Exception as e:
        print(f"!!! Exception during AI product summary suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる商品概要サマリー提案中にエラーが発生しました。", "error": str(e)}), 500

    try:
        ai_response = model.generate_content(prompt)
        try:
            import json
            response_text = ai_response.text
            if response_text.strip().startswith("```json"):
                response_text = response_text.strip()[7:-3].strip()
            
            suggested_brand_voice_detail = json.loads(response_text)
            # 必要なキーがあるか簡易チェック
            if not all(k in suggested_brand_voice_detail for k in ['tone', 'keywords', 'ng_words']):
                raise ValueError("Brand voice object missing required keys.")
            if not isinstance(suggested_brand_voice_detail['keywords'], list) or not isinstance(suggested_brand_voice_detail['ng_words'], list):
                raise ValueError("Keywords or NG words are not lists.")

        except (json.JSONDecodeError, ValueError) as e_parse:
            print(f"!!! Error parsing AI response for brand voice: {e_parse}. Raw text: {ai_response.text}")
            # パース失敗時のフォールバック
            suggested_brand_voice_detail = {
                "tone": f"AI提案の解析に失敗しました。AIの応答: {ai_response.text[:100]}...",
                "keywords": [],
                "ng_words": []
            }
        
        print(f">>> AI Suggested Brand Voice Detail: {suggested_brand_voice_detail}")
        return jsonify({"suggestion": suggested_brand_voice_detail}), 200
    except Exception as e:
        print(f"!!! Exception during AI brand voice suggestion: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによるブランドボイス提案中にエラーが発生しました。", "error": str(e)}), 500

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

@app.route('/api/v1/profile/chat-generic-field', methods=['POST'])
@token_required
def chat_account_strategy_field():
    user_profile = getattr(g, 'profile', {})
    if not user_profile:
        return jsonify({"message": "User profile not found."}), 403

    data = request.json
    field_key = data.get('field_key') # 例: "account_purpose", "edu_s1_purpose_base"
    field_label = data.get('field_label', '指定の項目')
    current_field_value = data.get('current_field_value', '')
    chat_history_frontend = data.get('chat_history', []) # フロントエンドからのチャット履歴
    current_user_message_text = data.get('current_user_message')
    account_context = data.get('account_context', {}) # フロントから送られてくる他のフォーム項目の情報

    if not all([field_key, current_user_message_text]):
        return jsonify({"message": "Missing required parameters: field_key or current_user_message."}), 400

    # account_context から主要な情報を抽出
    acc_purpose = account_context.get('purpose', user_profile.get('account_purpose', '未設定'))
    acc_product_summary = account_context.get('product_summary', user_profile.get('main_product_summary', '未設定'))
    acc_value_prop = account_context.get('core_value_proposition', user_profile.get('core_value_proposition', '未設定'))
    acc_brand_voice = account_context.get('brand_voice_tone', user_profile.get('brand_voice_detail', {}).get('tone', 'プロフェッショナル'))


    system_instruction_parts = [
        f"あなたは、ユーザーのXアカウント戦略における「{field_label}」の項目を、より具体的で魅力的な内容にブラッシュアップするためのAIアシスタントです。",
        f"ユーザーの現在のアカウント戦略の全体像（一部）は以下の通りです。これを踏まえて対話してください。",
        f"  - アカウントの目的: {acc_purpose}",
        f"  - 主要商品概要: {acc_product_summary}",
        f"  - コア提供価値: {acc_value_prop}",
        f"  - ブランドボイス（トーン）: {acc_brand_voice}",
        f"現在、ユーザーは「{field_label}」について以下のように考えています（または入力途中です）:\n-----\n{current_field_value if current_field_value else '(まだ具体的に記述されていません)'}\n-----",
        f"あなたの役割は、ユーザーの思考を整理し、質問を投げかけたり、具体的なアイデアを提案したりすることで、この「{field_label}」の項目がより戦略的で効果的なものになるよう支援することです。",
        f"共感的かつ建設的な対話を心がけ、ユーザーが自身の言葉でより良い戦略を練り上げられるように導いてください。"
    ]
    system_instruction_text = "\n".join(system_instruction_parts)

    model = get_current_ai_model(user_profile, system_instruction_text=system_instruction_text)
    if not model:
        return jsonify({"message": "AI chat model could not be initialized."}), 500

    gemini_sdk_history = []
    for entry in chat_history_frontend:
        role_sdk = entry.get('role')
        parts_data_sdk = entry.get('parts')
        if role_sdk and parts_data_sdk and isinstance(parts_data_sdk, list) and parts_data_sdk:
            text_content_sdk = parts_data_sdk[0].get('text') if isinstance(parts_data_sdk[0], dict) else None
            if isinstance(text_content_sdk, str):
                gemini_sdk_history.append({'role': role_sdk, 'parts': [{'text': text_content_sdk}]})
    
    chat_session = model.start_chat(history=gemini_sdk_history)
    print(f">>> Sending to Gemini Chat (Account Strategy Field: {field_label}, History Len: {len(gemini_sdk_history)}): User says: {current_user_message_text[:100]}...")

    try:
        response = chat_session.send_message(current_user_message_text)
        ai_response_text = ""
        try: ai_response_text = response.text
        except Exception: pass
        if not ai_response_text and hasattr(response, 'candidates') and response.candidates:
            ai_response_text = "".join([p.text for c in response.candidates for p in c.content.parts if hasattr(p,'text')])
        
        if not ai_response_text:
            feedback_message = "AIからの応答が空でした。"
            if hasattr(response,'prompt_feedback'): 
                feedback_message = f"AI応答エラー: {response.prompt_feedback}"
            return jsonify({"message": feedback_message, "ai_message": None}), 500

        print(f">>> Gemini Chat AI Response for {field_label}: {ai_response_text.strip()[:100]}...")
        return jsonify({"ai_message": ai_response_text.strip()})
        
    except Exception as e:
        print(f"!!! Exception in chat_account_strategy_field for {field_label}: {e}")
        traceback.print_exc()
        return jsonify({"message": f"AIとの「{field_label}」に関する対話中にエラーが発生しました。", "error": str(e)}), 500


# 主要戦略情報を基に12の基本方針ドラフトを一括生成

@app.route('/api/v1/profile/generate-base-policies-draft', methods=['POST'])
@token_required
def generate_account_base_policies_draft():
    user_profile = getattr(g, 'profile', {})
    if not user_profile:
        return jsonify({"message": "User profile not found."}), 403
    user_id = user_profile.get('id') # ログ用

    data = request.json
    # フロントエンドから送られてくる、AIのインプットとなる主要なアカウント戦略情報
    account_purpose = data.get('account_purpose', user_profile.get('account_purpose', '未設定のアカウント目的'))
    # main_target_audience_summary はフロントエンドで整形されて送られてくる想定
    main_target_audience_summary = data.get('main_target_audience_summary', '未設定のターゲット顧客像の概要')
    core_value_proposition = data.get('core_value_proposition', user_profile.get('core_value_proposition', '未設定のコア提供価値'))
    main_product_summary = data.get('main_product_summary', user_profile.get('main_product_summary', '未設定の商品概要'))
    # ブランドボイスのトーンを取得 (詳細設定があればそちらを優先)
    brand_voice_tone_from_detail = user_profile.get('brand_voice_detail', {}).get('tone')
    brand_voice_tone = brand_voice_tone_from_detail if brand_voice_tone_from_detail else user_profile.get('brand_voice', 'プロフェッショナルかつ親しみやすい')


    model = get_current_ai_model(user_profile)
    if not model:
        return jsonify({"message": "AI model could not be initialized."}), 500

    # 12の教育要素の定義 (フロントエンドの basePolicyElementsDefinition と対応)
    base_policies_elements = [
        {'key': 'edu_s1_purpose_base', 'name': '目的の教育 基本方針', 'desc': "アカウント全体として、顧客が目指すべき理想の未来や提供する究極的な価値観についての方針。"},
        {'key': 'edu_s2_trust_base', 'name': '信用の教育 基本方針', 'desc': "アカウント全体として、発信者やブランドへの信頼をどのように構築・維持していくかの方針。"},
        {'key': 'edu_s3_problem_base', 'name': '問題点の教育 基本方針', 'desc': "ターゲット顧客が抱えるであろう、アカウント全体で共通して取り上げる問題意識や課題についての方針。"},
        {'key': 'edu_s4_solution_base', 'name': '手段の教育 基本方針', 'desc': "アカウントが提供する情報や商品が、顧客の問題をどのように解決するかの基本的な考え方。"},
        {'key': 'edu_s5_investment_base', 'name': '投資の教育 基本方針', 'desc': "自己投資の重要性や、情報・商品への投資をどのように正当化し促すかの全体的な方針。"},
        {'key': 'edu_s6_action_base', 'name': '行動の教育 基本方針', 'desc': "顧客に具体的な行動を促すための、アカウントとしての一貫したメッセージやアプローチ。"},
        {'key': 'edu_r1_engagement_hook_base', 'name': '読む・見る教育 基本方針', 'desc': "コンテンツの冒頭で読者の興味を惹きつけるための、アカウント共通のテクニックや考え方。"},
        {'key': 'edu_r2_repetition_base', 'name': '何度も聞く教育 基本方針', 'desc': "重要なメッセージを繰り返し伝え、記憶に定着させるためのアカウント全体でのアプローチ。"},
        {'key': 'edu_r3_change_mindset_base', 'name': '変化の教育 基本方針', 'desc': "現状維持からの脱却や、新しい価値観への変化を促すための、アカウントとしての基本的なスタンス。"},
        {'key': 'edu_r4_receptiveness_base', 'name': '素直の教育 基本方針', 'desc': "情報やアドバイスを素直に受け入れることの重要性をどのように伝えるかの全体方針。"},
        {'key': 'edu_r5_output_encouragement_base', 'name': 'アウトプットの教育 基本方針', 'desc': "顧客からの発信（UGC）を促すためのアカウント全体での働きかけや仕組み作りの考え方。"},
        {'key': 'edu_r6_baseline_shift_base', 'name': '基準値/覚悟の教育 基本方針', 'desc': "顧客の常識や基準値を引き上げ、行動への覚悟を促すためのアカウントとしての一貫した姿勢。"},
    ]
    generated_drafts = {}

    print(f">>> Generating All Base Policies Draft for user: {user_id}")
    print(f"    Context - Purpose: {str(account_purpose)[:70]}...")
    print(f"    Context - Target Audience Summary: {str(main_target_audience_summary)[:70]}...")
    print(f"    Context - Core Value: {str(core_value_proposition)[:70]}...")
    print(f"    Context - Product Summary: {str(main_product_summary)[:70]}...")
    print(f"    Context - Brand Voice Tone: {str(brand_voice_tone)[:70]}...")


    for element in base_policies_elements:
        element_key = element['key']
        element_name_jp = element['name']
        element_desc = element['desc']
        
        prompt = f"""あなたは経験豊富なブランド戦略コンサルタントであり、SNSアカウントの教育コンテンツ戦略立案の専門家です。
以下のユーザーアカウント全体の戦略情報を強く踏まえ、「{element_name_jp}」に関するアカウントの【基本方針】のドラフトを150字～200字程度で作成してください。
この基本方針は、ユーザーが今後の具体的な発信内容や個別の販売キャンペーン（ローンチ）におけるメッセージを考える際の重要な土台となります。

# ユーザーアカウント全体の戦略情報（コンテキスト）:
* アカウントの基本理念・パーパス: {account_purpose}
* 主要ターゲット顧客像（概要）: {main_target_audience_summary}
* アカウントのコア提供価値: {core_value_proposition}
* 主要商品群の分析サマリー: {main_product_summary}
* ブランドボイス（基本トーン）: {brand_voice_tone}

# 現在ドラフト作成中の「基本方針」の要素:
* 要素名: {element_name_jp}
* この要素の一般的な目的・意味: {element_desc}

# 作成指示:
* 上記の「ユーザーアカウント全体の戦略情報」と矛盾せず、それらを補強・具体化するような「{element_name_jp}」の基本方針を記述してください。
* このアカウントが、この教育要素を通じて顧客にどのような影響を与え、どのような状態に導きたいのか、その核となる考え方や方向性を示してください。
* ユーザーがこのドラフトを元に、具体的な行動計画や発信テーマを考えやすくなるような、示唆に富んだ内容にしてください。
* 簡潔かつ実践的な言葉を選び、抽象的すぎないように注意してください。
* 生成するテキストは、指定された要素の基本方針の本文のみとしてください。前置きや後書きは不要です。
"""
        # print(f"    Generating draft for: {element_key} ('{element_name_jp}') - Prompt (first 100 chars): {prompt[:100]}...") # デバッグ用
        try:
            ai_response = model.generate_content(prompt)
            draft_text = ""
            try:
                draft_text = ai_response.text.strip()
            except Exception: # Safety net for .text access
                pass
            
            if not draft_text and hasattr(ai_response, 'candidates') and ai_response.candidates:
                 draft_text = "".join([part.text for candidate in ai_response.candidates for part in candidate.content.parts if hasattr(part, 'text')]).strip()

            if not draft_text:
                print(f"!!! AI response for {element_key} was empty or invalid.")
                if hasattr(ai_response, 'prompt_feedback'):
                    print(f"    Prompt Feedback: {ai_response.prompt_feedback}")
                draft_text = f"「{element_name_jp}」のAI提案生成に失敗しました (応答が空です)。"


            generated_drafts[element_key] = draft_text
            print(f"    Draft for {element_key}: {draft_text[:70]}...")
        except Exception as e_gen:
            print(f"!!! Exception generating draft for {element_key}: {e_gen}")
            traceback.print_exc()
            generated_drafts[element_key] = f"AIによる「{element_name_jp}」のドラフト生成中にエラーが発生しました: {str(e_gen)}"
            
    return jsonify(generated_drafts), 200





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

@app.route('/api/v1/chat/education-element', methods=['POST'])
@token_required
def chat_education_element():
    user = getattr(g, 'user', None); user_profile = getattr(g, 'profile', {})
    if not user: return jsonify({"message": "Auth error."}),401
    user_id = user.id
    
    if not supabase: return jsonify({"message": "Supabase client not init!"}),500
    
    data=request.json; 
    if not data: return jsonify({"message": "Invalid request: No JSON data provided."}), 400
    
    launch_id=data.get('launch_id')
    element_key=data.get('element_key')
    chat_history_frontend=data.get('chat_history',[])
    current_user_message_text=data.get('current_user_message')
    
    if not all([launch_id,element_key,current_user_message_text]):
        return jsonify({"message":"Missing params: launch_id, element_key, or current_user_message required."}),400
        
    print(f">>> POST /api/v1/chat/education-element for Launch: {launch_id}, Element: {element_key} by User: {user_id}")
    
    try:
        launch_res=supabase.table('launches').select("*,products(name,description,value_proposition,target_audience)").eq('id',launch_id).eq('user_id',user_id).maybe_single().execute()
        if not launch_res.data: return jsonify({"message":"Launch not found or access denied."}),404
        launch_info=launch_res.data
        product_info_data = launch_info.get('products')
        product_info = product_info_data if isinstance(product_info_data, dict) else (product_info_data[0] if isinstance(product_info_data, list) and product_info_data else {})

        strategy_res=supabase.table('education_strategies').select("*").eq('launch_id',launch_id).eq('user_id',user_id).maybe_single().execute()
        strategy_info=strategy_res.data if strategy_res.data else {}
        
        brand_voice=user_profile.get('brand_voice','設定されていません。フレンドリーかつ専門的に。')
        target_persona_profile=user_profile.get('target_persona','設定されていません。この商品やサービスに興味を持ちそうな一般的な顧客。')
        
        element_map={
            "product_analysis_summary":"商品分析の要点", "target_customer_summary":"ターゲット顧客分析の要点",
            "edu_s1_purpose":"目的の教育", "edu_s2_trust":"信用の教育", "edu_s3_problem":"問題点の教育", 
            "edu_s4_solution":"手段の教育", "edu_s5_investment":"投資の教育", "edu_s6_action":"行動の教育", 
            "edu_r1_engagement_hook":"読む・見る教育", "edu_r2_repetition":"何度も聞く教育", 
            "edu_r3_change_mindset":"変化の教育", "edu_r4_receptiveness":"素直の教育", 
            "edu_r5_output_encouragement":"アウトプットの教育", "edu_r6_baseline_shift":"基準値/覚悟の教育"
        }
        element_name_jp=element_map.get(element_key,element_key)
        current_element_memo=strategy_info.get(element_key,"")
        
        system_instruction_parts = [
            f"あなたは「EDS（Education Drive System）」のAIアシスタントです。ユーザーがX（旧Twitter）マーケティングにおける「{element_name_jp}」という教育戦略要素のメモを具体化し、深掘りするのを助ける役割を担います。",
            f"「{element_name_jp}」の基本的な目的は「{element_map.get(element_key,'顧客の特定の心理状態を醸成し、購入行動を促すこと')}」です。",
            f"ユーザーの現在のブランドボイスは「{brand_voice}」、主なターゲット顧客像は「{target_persona_profile}」です。",
            f"この対話は、ローンチ名「{launch_info.get('name','(名称未設定のローンチ)')}」（対象商品: 「{product_info.get('name','(商品名未設定)')}」）に関するものです。",
            f"現在の「{element_name_jp}」に関するユーザーのメモは以下の通りです（空の場合は未入力です）:\n-----\n{current_element_memo if current_element_memo else 'まだ何も書かれていません。'}\n-----",
            "あなたのタスクは、ユーザーの思考を整理し、より効果的な戦略メモが完成するように、具体的で建設的な質問を投げかけたり、アイデアを提案したりすることです。",
            "ユーザーが主体的に考え、言葉にできるように、短い質問や確認を繰り返しながら、対話をリードしてください。",
            "最終的には、ユーザーが「これだ！」と思えるような、質の高い戦略メモの断片、または完成形に近いアイデアを引き出すことを目指します。",
            "共感的かつサポート的な口調でお願いします。"
        ]
        system_instruction_text = "\n".join(system_instruction_parts)
        
        current_chat_model = get_current_ai_model(user_profile, system_instruction_text=system_instruction_text)
        if not current_chat_model: return jsonify({"message":"Gemini chat model could not be initialized with system instruction."}),500
        
        gemini_sdk_history=[]
        for entry in chat_history_frontend: 
            role_sdk = entry.get('role')
            parts_data_sdk = entry.get('parts')
            if role_sdk and parts_data_sdk and isinstance(parts_data_sdk, list) and parts_data_sdk:
                text_content_sdk = parts_data_sdk[0].get('text') if isinstance(parts_data_sdk[0], dict) else None
                if isinstance(text_content_sdk, str):
                    gemini_sdk_history.append({'role': role_sdk, 'parts': [{'text': text_content_sdk}]})
            
        chat_session = current_chat_model.start_chat(history=gemini_sdk_history)
        print(f">>> Sending to Gemini Chat (Model: {current_chat_model._model_name}, Element: {element_name_jp}, History Len: {len(gemini_sdk_history)}): User says: {current_user_message_text[:150]}...")
        
        response = chat_session.send_message(current_user_message_text)
        ai_response_text = ""
        try: ai_response_text = response.text
        except Exception: pass
        if not ai_response_text and hasattr(response,'candidates') and response.candidates: 
            ai_response_text = "".join([p.text for c in response.candidates for p in c.content.parts if hasattr(p,'text')])
        
        if not ai_response_text:
            feedback_message = "AIからの応答が空でした。"
            if hasattr(response,'prompt_feedback'): 
                feedback_message = f"AI応答エラー: {response.prompt_feedback}"
                print(f"!!! AI chat prompt feedback: {response.prompt_feedback}")
            return jsonify({"message": feedback_message, "ai_message": None}), 500

        print(f">>> Gemini Chat AI Response: {ai_response_text.strip()[:150]}...")
        return jsonify({"ai_message":ai_response_text.strip()})
        
    except Exception as e: 
        print(f"!!! Exception in chat_education_element: {e}")
        traceback.print_exc();
        return jsonify({"message":"Error processing chat with AI","error":str(e)}),500

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

@app.route('/api/v1/tweets/execute-scheduled/', methods=['POST'])
def execute_scheduled_tweets():
    # (推奨) Cronジョブからのリクエストを認証
    if CRON_JOB_SECRET: # 環境変数にシークレットが設定されていれば検証する
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f"Bearer {CRON_JOB_SECRET}":
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
        # 現在時刻より前の、ステータスが 'scheduled' のツイートを取得
        now_utc_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # image_urls カラムと、profiles テーブルの関連情報も取得
        
        scheduled_tweets_res = supabase.table('tweets').select(
    '*, x_account:x_account_id(*)'
).eq('status', 'scheduled').lte('scheduled_at', now_utc_str).execute()
       

        if hasattr(scheduled_tweets_res, 'error') and scheduled_tweets_res.error:
            print(f"!!! Error fetching scheduled tweets: {scheduled_tweets_res.error}")
            return jsonify({"message": "Error fetching scheduled tweets", "error": str(scheduled_tweets_res.error)}), 500

        if not scheduled_tweets_res.data:
            print("--- No scheduled tweets to post at this time.")
            return jsonify({"message": "No scheduled tweets to post at this time.", "processed_count": 0}), 200

        tweets_to_process = scheduled_tweets_res.data
        print(f">>> Found {len(tweets_to_process)} scheduled tweets to process.")

        for tweet_data in tweets_to_process:
            tweet_id = tweet_data.get('id')
            user_id = tweet_data.get('user_id')
            content = tweet_data.get('content')
            profile_data = tweet_data.get('profiles')
            image_urls = tweet_data.get('image_urls', [])

            if not content:
                print(f"--- Tweet ID {tweet_id} for user {user_id} has no content. Skipping and marking as error.")
                supabase.table('tweets').update({
                    "status": "error", 
                    "error_message": "Content was empty at scheduled time.",
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }).eq('id', tweet_id).execute()
                failed_posts += 1
                processed_tweets.append({"id": tweet_id, "status": "error", "reason": "Empty content"})
                continue

            if not profile_data:
                print(f"--- User profile with X API keys not found for tweet ID {tweet_id} (user_id: {user_id}). Skipping and marking as error.")
                supabase.table('tweets').update({
                    "status": "error", 
                    "error_message": "User profile or X API credentials not found.",
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }).eq('id', tweet_id).execute()
                failed_posts += 1
                processed_tweets.append({"id": tweet_id, "status": "error", "reason": "Profile/API keys not found"})
                continue
            
            media_ids = []
            if image_urls and isinstance(image_urls, list):
                try:
                    consumer_key = profile_data.get('x_api_key')
                    consumer_secret = profile_data.get('x_api_secret_key')
                    access_token = profile_data.get('x_access_token')
                    access_token_secret = profile_data.get('x_access_token_secret')

                    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
                        raise Exception("X API v1.1 credentials for media upload are missing.")

                    auth_v1 = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
                    api_v1 = tweepy.API(auth_v1)
                    
                    import requests
                    import tempfile
                    import os

                    for url in image_urls:
                        try:
                            response = requests.get(url, stream=True)
                            response.raise_for_status()
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                for chunk in response.iter_content(chunk_size=8192):
                                    tmp.write(chunk)
                                tmp_filename = tmp.name
                            print(f"--- Uploading media from {url} for tweet {tweet_id}...")
                            media = api_v1.media_upload(filename=tmp_filename)
                            media_ids.append(media.media_id_string)
                            print(f"--- Media uploaded for tweet {tweet_id}, media_id: {media.media_id_string}")
                        finally:
                            if 'tmp_filename' in locals() and os.path.exists(tmp_filename):
                                os.remove(tmp_filename)
                except Exception as e_media:
                    print(f"!!! Media upload failed for tweet {tweet_id}: {e_media}")
                    supabase.table('tweets').update({
                        "status": "error", 
                        "error_message": f"Media upload failed: {str(e_media)}",
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }).eq('id', tweet_id).execute()
                    failed_posts += 1
                    processed_tweets.append({"id": tweet_id, "status": "error", "reason": "Media upload failed"})
                    continue

            api_client_v2 = get_x_api_client(profile_data)
            if not api_client_v2:
                print(f"--- Failed to initialize X API client for tweet ID {tweet_id} (user_id: {user_id}). Skipping and marking as error.")
                supabase.table('tweets').update({
                    "status": "error", 
                    "error_message": "Failed to initialize X API client (check credentials).",
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }).eq('id', tweet_id).execute()
                failed_posts += 1
                processed_tweets.append({"id": tweet_id, "status": "error", "reason": "X API client init failed"})
                continue
            
            try:
                print(f">>> Attempting to post tweet ID {tweet_id} to X for user {user_id} with media_ids: {media_ids}...")
                created_x_tweet_response = api_client_v2.create_tweet(
                    text=content,
                    media_ids=media_ids if media_ids else None
                )
                
                x_tweet_id_str = None
                if created_x_tweet_response.data and created_x_tweet_response.data.get('id'):
                    x_tweet_id_str = created_x_tweet_response.data.get('id')
                    print(f">>> Tweet ID {tweet_id} posted successfully to X! X Tweet ID: {x_tweet_id_str}")
                    
                    supabase.table('tweets').update({
                        "status": "posted",
                        "posted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "x_tweet_id": x_tweet_id_str,
                        "error_message": None,
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }).eq('id', tweet_id).execute()
                    successful_posts += 1
                    processed_tweets.append({"id": tweet_id, "status": "posted", "x_tweet_id": x_tweet_id_str})
                else:
                    error_detail_x = "Unknown error or unexpected response structure from X API v2 while posting."
                    if hasattr(created_x_tweet_response, 'errors') and created_x_tweet_response.errors:
                        error_detail_x = str(created_x_tweet_response.errors)
                    elif hasattr(created_x_tweet_response, 'reason'): 
                        error_detail_x = created_x_tweet_response.reason
                    print(f"!!! Error in X API v2 tweet creation response for tweet ID {tweet_id}: {error_detail_x}")
                    
                    supabase.table('tweets').update({
                        "status": "error",
                        "error_message": f"X API Error: {error_detail_x}",
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }).eq('id', tweet_id).execute()
                    failed_posts += 1
                    processed_tweets.append({"id": tweet_id, "status": "error", "reason": f"X API Error: {error_detail_x}"})

            except tweepy.TweepyException as e_tweepy:
                error_message = str(e_tweepy)
                if hasattr(e_tweepy, 'response') and e_tweepy.response is not None:
                    try:
                        error_json = e_tweepy.response.json()
                        if 'errors' in error_json and error_json['errors']:
                             error_message = f"X API Error: {error_json['errors'][0].get('message', str(e_tweepy))}"
                        elif 'title' in error_json: 
                             error_message = f"X API Error: {error_json['title']}: {error_json.get('detail', '')}"
                        elif hasattr(e_tweepy.response, 'data') and e_tweepy.response.data:
                            error_message = f"X API Error (e.g., 403 Forbidden): {e_tweepy.response.data}"
                    except ValueError: pass
                elif hasattr(e_tweepy, 'api_codes') and hasattr(e_tweepy, 'api_messages'):
                     error_message = f"X API Error {e_tweepy.api_codes}: {e_tweepy.api_messages}"

                print(f"!!! TweepyException posting tweet ID {tweet_id}: {error_message}")
                traceback.print_exc()
                supabase.table('tweets').update({
                    "status": "error", 
                    "error_message": f"TweepyException: {error_message}",
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }).eq('id', tweet_id).execute()
                failed_posts += 1
                processed_tweets.append({"id": tweet_id, "status": "error", "reason": f"TweepyException: {error_message}"})
            except Exception as e_general:
                print(f"!!! General exception posting tweet ID {tweet_id}: {e_general}")
                traceback.print_exc()
                supabase.table('tweets').update({
                    "status": "error", 
                    "error_message": f"General Exception: {str(e_general)}",
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }).eq('id', tweet_id).execute()
                failed_posts += 1
                processed_tweets.append({"id": tweet_id, "status": "error", "reason": f"General Exception: {str(e_general)}"})
        
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

# --- Tweets API (Complete & Unabridged) ---
# --- Tweets API (Final Version - Unabridged) ---

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
#generate_educational_tweet

@app.route('/api/v1/educational-tweets/generate', methods=['POST'])
@token_required
def generate_educational_tweet():
    user = getattr(g, 'user', None)
    if not user:
        return jsonify({"message": "Authentication error."}), 401
    
    user_id = user.id

    try:
        data = request.json
        if not data:
            return jsonify({"message": "Invalid request: No JSON data provided."}), 400

        # --- ▼ここからが修正箇所▼ ---
        x_account_id = data.get('x_account_id')
        education_element_key = data.get('education_element_key')
        theme = data.get('theme')

        if not all([x_account_id, education_element_key, theme]):
            return jsonify({"error": "x_account_id, education_element_key, theme are required"}), 400

        # 1. Xアカウントに紐づく戦略情報を取得
        account_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = account_strategy_res.data or {}

        # 2. ユーザー全体のAIモデル設定を取得 (g.profileから)
        user_profile = getattr(g, 'profile', {})
        # --- ▲ここまでが修正箇所▲ ---

        print(f">>> POST /api/v1/educational-tweets/generate for x_account_id: {x_account_id}")
        
        current_text_model = get_current_ai_model(user_profile)
        if not current_text_model:
            return jsonify({"message": "AI model (Gemini) could not be initialized."}), 500

        element_map = {
            "product_analysis_summary": "商品分析の要点", "target_customer_summary": "ターゲット顧客分析の要点",
            "edu_s1_purpose": "目的の教育", "edu_s2_trust": "信用の教育", "edu_s3_problem": "問題点の教育", 
            "edu_s4_solution": "手段の教育", "edu_s5_investment": "投資の教育", "edu_s6_action": "行動の教育", 
            "edu_r1_engagement_hook": "読む・見る教育", "edu_r2_repetition": "何度も聞く教育", 
            "edu_r3_change_mindset": "変化の教育", "edu_r4_receptiveness": "素直の教育", 
            "edu_r5_output_encouragement": "アウトプットの教育", "edu_r6_baseline_shift": "基準値の教育／覚悟の教育"
        }
        education_element_name = element_map.get(education_element_key, education_element_key) 

        # --- ▼プロンプト構築部分の修正 (参照元をaccount_strategyに変更)▼ ---
        brand_voice_detail = account_strategy.get('brand_voice_detail', {})
        brand_voice_to_use = brand_voice_detail.get('tone') if isinstance(brand_voice_detail, dict) and brand_voice_detail.get('tone') else 'プロフェッショナルかつ親しみやすい'
        if isinstance(brand_voice_detail, dict):
            keywords_str = ", ".join(brand_voice_detail.get('keywords', []))
            ng_words_str = ", ".join(brand_voice_detail.get('ng_words', []))
            if keywords_str: brand_voice_to_use += f" (キーワード: {keywords_str})"
            if ng_words_str: brand_voice_to_use += f" (NGワード: {ng_words_str})"

        target_persona_to_use = "一般的な顧客"
        if account_strategy.get('main_target_audience') and isinstance(account_strategy.get('main_target_audience'), list):
            personas = account_strategy.get('main_target_audience', [])
            if len(personas) > 0 and isinstance(personas[0], dict):
                first_persona = personas[0]
                target_persona_to_use = f"ペルソナ「{first_persona.get('name', '未設定')}」({first_persona.get('age', '年齢不明')})のような、特に「{first_persona.get('悩み', '特定の悩み') }」を抱える層"
        
        base_policy_key = f"{education_element_key}_base"
        element_base_policy = account_strategy.get(base_policy_key)

        prompt_parts = [
            "あなたはプロのX（旧Twitter）マーケティングコンサルタントであり、エンゲージメントの高いツイートを作成する専門家です。",
            f"以下のユーザー設定と指示に基づいて、魅力的で具体的なXの投稿文案を1つ作成してください。",
            f"## ユーザーアカウント設定:",
            f"  - 発信のトーン（ブランドボイス）: {brand_voice_to_use}",
            f"  - 主なターゲット顧客像: {target_persona_to_use}",
            f"  - アカウントの目的・パーパス: {account_strategy.get('account_purpose', '未設定')}",
            f"  - アカウントのコア提供価値: {account_strategy.get('core_value_proposition', '未設定')}",
            f"## 今回のツイートのテーマと教育要素:",
            f"  - 重視する教育要素: 「{education_element_name}」 ({education_element_key})",
        ]
        if element_base_policy:
            prompt_parts.append(f"  - 上記教育要素に関するアカウントの基本方針（最重要参考情報）: {element_base_policy}")
        
        prompt_parts.extend([
            f"  - ユーザーが指定したツイートの具体的なテーマやキーワード: {theme}",
            f"## 作成指示:",
            "  - 上記の「アカウントの基本方針」を最優先の指針とし、それに沿った内容でツイートを作成してください。",
            "  - 次に「ユーザーが指定したツイートの具体的なテーマやキーワード」を具体的に盛り込んでください。",
            "  - ツイートは日本語で、Xの文字数制限を意識しつつ、簡潔で分かりやすいものにしてください。",
            "  - 読者の興味を引き、いいね、リツイート、返信などのエンゲージメントを促すような内容にしてください。",
            "  - 文脈に合わせて適切な絵文字を1～3個、効果的に使用してください。",
            "  - 関連性が高く効果的なハッシュタグを2～3個含めてください。",
            "  - 禁止事項: 誇大広告、誤解を招く表現、不適切な言葉遣いは避けること。",
            "  - 提供された情報を最大限活用し、最高のツイート案を1つだけ提案してください。"
        ])
        # --- ▲プロンプト構築部分の修正▲ ---

        prompt = "\n".join(filter(None, prompt_parts)) 
        print(f">>> Gemini Prompt for educational tweet (model: {current_text_model._model_name}):\n{prompt[:600]}...")

        ai_response = current_text_model.generate_content(prompt)
        generated_tweet_text = ""
        try:
            generated_tweet_text = ai_response.text
        except Exception: pass 
        if not generated_tweet_text and hasattr(ai_response, 'candidates') and ai_response.candidates:
            generated_tweet_text = "".join([part.text for c in ai_response.candidates for p in c.content.parts if hasattr(p, 'text')])
        
        if not generated_tweet_text:
            error_feedback_message = "AIからの応答が空でした。"
            if hasattr(ai_response, 'prompt_feedback'):
                error_feedback_message = f"AI応答エラー: {ai_response.prompt_feedback}"
            raise Exception(error_feedback_message)
            
        print(f">>> AI Generated Educational Tweet: {generated_tweet_text.strip()}")
        return jsonify({"generated_tweet": generated_tweet_text.strip()}), 200

    except Exception as e:
        print(f"!!! Exception during AI educational tweet generation: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによるツイート生成中に予期せぬエラーが発生しました。", "error": str(e)}), 500

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
    
   
  
# --- Block 5: 新しいAPIエンドポイント - 初期投稿生成 (Google検索対応) ---
@app.route('/api/v1/initial-tweets/generate', methods=['POST'])
@token_required
def generate_initial_tweet():
    user = getattr(g, 'user', None)
    if not user:
        return jsonify({"message": "Authentication error."}), 401
    user_id = user.id

    try:
        data = request.json
        if not data:
            return jsonify({"message": "Invalid request: No JSON data provided."}), 400

        # --- ▼ここからが修正箇所▼ ---
        x_account_id = data.get('x_account_id')
        initial_post_type = data.get('initial_post_type')
        theme = data.get('theme', '')
        use_Google_Search_flag = data.get('use_Google_Search', False)

        if not all([x_account_id, initial_post_type]):
            return jsonify({"error": "x_account_id and initial_post_type are required"}), 400

        # 1. Xアカウントに紐づく戦略情報を取得
        account_strategy_res = supabase.table('account_strategies').select('*').eq('x_account_id', x_account_id).eq('user_id', user_id).maybe_single().execute()
        account_strategy = account_strategy_res.data or {}

        # 2. ユーザー全体の基本情報を取得 (g.profileから)
        user_profile = getattr(g, 'profile', {})
        # --- ▲ここまでが修正箇所▲ ---

        print(f">>> POST /api/v1/initial-tweets/generate for x_account_id: {x_account_id}")
        
        current_text_model = get_current_ai_model(user_profile, use_Google_Search=use_Google_Search_flag)
        if not current_text_model:
            return jsonify({"message": "AI model could not be initialized."}), 500

        # --- ▼プロンプト構築部分の修正 (参照元を変更)▼ ---
        prompt_parts = ["あなたはプロのX（旧Twitter）コンテンツクリエイターです。アカウント立ち上げ初期のフォロワー獲得とエンゲージメント向上に特化しています。"]
        prompt_parts.append("## あなたのアカウント基本情報:")
        prompt_parts.append(f"  - アカウント名（仮）: {user_profile.get('username', '(あなたのXアカウント名)')}")
        prompt_parts.append(f"  - アカウントの目的/パーパス: {account_strategy.get('account_purpose', '(このアカウントで達成したいこと、提供したい価値)')}")
        prompt_parts.append(f"  - コア提供価値: {account_strategy.get('core_value_proposition', '(読者が得られる最も重要な価値)')}")

        main_target_audience_data = account_strategy.get('main_target_audience')
        if isinstance(main_target_audience_data, list) and main_target_audience_data:
            persona_summary_parts = []
            for i, p_data in enumerate(main_target_audience_data[:2]):
                 if isinstance(p_data, dict):
                    persona_summary_parts.append(f"ペルソナ{i+1}「{p_data.get('name', '未設定')}」({p_data.get('age', '年齢不明')})の主な悩み: {p_data.get('悩み', '未設定')}")
            prompt_parts.append(f"  - 主なターゲット顧客像: {'; '.join(persona_summary_parts)}")
        else:
            prompt_parts.append("  - 主なターゲット顧客像: (まだ具体的に設定されていません)")

        brand_voice_detail = account_strategy.get('brand_voice_detail')
        if isinstance(brand_voice_detail, dict) and brand_voice_detail.get('tone'):
            prompt_parts.append(f"  - ブランドボイス（トーン）: {brand_voice_detail.get('tone')}")
            keywords_list = brand_voice_detail.get('keywords', [])
            if keywords_list and isinstance(keywords_list, list):
                prompt_parts.append(f"    - 推奨キーワード例: {', '.join(keywords_list[:3])}")
        else:
            prompt_parts.append("  - ブランドボイス（トーン）: (まだ具体的に設定されていません。例: 親しみやすく、専門的)")

        prompt_parts.append("\n## 今回作成するツイートの指示:")
        if initial_post_type == "follow_reason":
            prompt_parts.append("  - ツイートの目的: このアカウントをフォローすべき理由、提供する独自の価値やフォロワーが得られる未来を明確に伝え、強いフォロー動機を喚起する。")
            prompt_parts.append(f"  - ユーザーが指定したツイートのテーマやキーワード（最重要）: {theme if theme else 'アカウントの強みや読者の具体的なベネフィットを中心に、独自性を強調してください。'}")
            if use_Google_Search_flag:
                prompt_parts.append("  - 追加指示: 最新の市場動向やターゲット顧客が関心を持つであろう新しい視点・情報をGoogle検索で調査し、それを踏まえて他のアカウントとの差別化ポイントを明確にし、より説得力のあるフォローメリットを訴求してください。")
        elif initial_post_type == "self_introduction":
            prompt_parts.append("  - ツイートの目的: 発信者の信頼性、専門性、そして共感を呼ぶような親しみやすい人となりが伝わる自己紹介を行う。なぜこの情報発信をしているのかという背景も示唆する。")
            prompt_parts.append(f"  - ユーザーが指定したツイートのテーマやキーワード（実績、経験、発信への想いなどの要点。最重要）: {theme if theme else 'あなたのユニークな経歴、専門分野での実績や経験、そしてこの情報発信を通じて伝えたい情熱や理念を中心に記述してください。'}")
        elif initial_post_type == "value_tips":
            prompt_parts.append("  - ツイートの目的: ターゲット顧客がすぐに役立つと感じ、保存・拡散したくなるような具体的なTipsや、ハッとするような本質的な気づきを提供する。")
            prompt_parts.append(f"  - ユーザーが指定したツイートのテーマやキーワード（最重要）: {theme if theme else 'あなたの専門分野に関する、読者が明日から実践できるような具体的で actionable なアドバイスを中心にしてください。'}")
            if use_Google_Search_flag:
                prompt_parts.append("  - 追加指示: 指定されたテーマに関する最新のテクニック、データ、ツール、または一般的な誤解を覆すような新しい情報などをGoogle検索で調査し、それを元に読者にとって価値の高い、独自性のあるTipsや気づきを提供してください。")
        else:
            prompt_parts.append(f"  - ユーザーが指定したツイートのテーマやキーワード: {theme if theme else '特に指定なし'}")
            prompt_parts.append(f"  - ツイートの目的: 「{initial_post_type}」という目的に沿った、アカウント初期のフォロワー獲得とエンゲージメント向上に貢献する、魅力的で具体的なツイートを作成してください。")

        prompt_parts.extend([
            "\n## ツイート作成ルール:",
            "  - 文字数: Xの現在の標準的な投稿文字数（140字以内を目安としつつ、状況に応じて多少の増減は可）で、簡潔かつインパクトのあるメッセージに。",
            "  - 絵文字: 文脈に合わせて1～3個程度、効果的に使用して親しみやすさや視認性を高める。",
            "  - ハッシュタグ: 関連性が高く、ターゲット層にリーチしやすいものを2～3個厳選して含める。",
            "  - CTA（Call To Action）: 読者にフォロー、いいね、リプライ、プロフィールの確認といった次のアクションを自然に促すような要素を subtly に含めること。",
            "  - 独自性: 提供されたアカウント情報を最大限に活かし、ありきたりではない、このアカウントならではのツイートを作成すること。",
            "  - 出力形式: 生成されたツイート本文のみを返してください。前置きや後書きは一切不要です。"
        ])
        # --- ▲プロンプト構築部分の修正▲ ---

        prompt = "\n".join(prompt_parts)
        model_name_for_log = getattr(current_text_model, '_model_name', 'N/A')
        print(f">>> Gemini Prompt for initial tweet (model: {model_name_for_log}, search: {use_Google_Search_flag}):\n{prompt[:600]}...")

        response = current_text_model.generate_content(prompt)

        generated_tweet_text = ""
        grounding_info_to_return = None

        if hasattr(response, 'text') and response.text:
            generated_tweet_text = response.text
        elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text'): generated_tweet_text += part.text

        if use_Google_Search_flag and response.candidates and hasattr(response.candidates[0], 'grounding_metadata') and response.candidates[0].grounding_metadata:
            grounding_metadata = response.candidates[0].grounding_metadata
            if hasattr(grounding_metadata, 'citations') and grounding_metadata.citations:
                grounding_info_to_return = [{"uri": getattr(c, 'uri', None), "title": getattr(c, 'title', None)} for c in grounding_metadata.citations]
            elif hasattr(grounding_metadata, 'web_search_queries') and grounding_metadata.web_search_queries:
                 grounding_info_to_return = {"retrieved_queries": grounding_metadata.web_search_queries}

        if not generated_tweet_text:
            error_feedback_message = "AIからの応答が空か、期待した形式ではありませんでした。"
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                 error_feedback_message = f"AI応答エラー: {response.prompt_feedback}"
            elif hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                 error_feedback_message += f" 処理終了理由: {str(response.candidates[0].finish_reason)}."
            raise Exception(error_feedback_message)
            
        return jsonify({
            "generated_tweet": generated_tweet_text.strip(),
            "grounding_info": grounding_info_to_return 
        }), 200

    except Exception as e:
        print(f"!!! Exception during AI initial tweet generation: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによる初期ツイート生成中に予期せぬエラーが発生しました。", "error": str(e)}), 500

# Flaskサーバーの起動
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)