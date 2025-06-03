import os
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from functools import wraps
import datetime # 予約日時の比較やDBへのタイムスタンプ記録に使用します
import traceback # エラー発生時の詳細なトレースバック取得に使用します
import google.generativeai as genai # 既存のAI機能で使用
import tweepy # Xへの投稿に使用します
import traceback

# .envファイルを読み込む
load_dotenv()
app = Flask(__name__)

# CORS設定
CORS(
    app,
    origins=["http://localhost:3000"],
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    supports_credentials=True,
    expose_headers=["Content-Length"]
)
print(">>> CORS configured.")

# ↓↓↓ここから追記・変更↓↓↓
PROFILE_COLUMNS_TO_SELECT = [
    "id", "username", "website", "avatar_url",
    "brand_voice", "target_persona", # 既存の簡易版カラム。新しい詳細カラムへの移行を検討。
    "preferred_ai_model",
    "x_api_key", "x_api_secret_key", "x_access_token", "x_access_token_secret",
    "updated_at",
    # 新しく追加したアカウント戦略関連カラム
    "account_purpose",
    "main_target_audience",
    "core_value_proposition",
    "brand_voice_detail",
    "main_product_summary",
    "edu_s1_purpose_base",
    "edu_s2_trust_base",
    "edu_s3_problem_base",
    "edu_s4_solution_base",
    "edu_s5_investment_base",
    "edu_s6_action_base",
    "edu_r1_engagement_hook_base",
    "edu_r2_repetition_base",
    "edu_r3_change_mindset_base",
    "edu_r4_receptiveness_base",
    "edu_r5_output_encouragement_base",
    "edu_r6_baseline_shift_base"
]

# g.profile に格納する主要な情報 (AIプロンプト生成などで頻繁に使うもの)
G_PROFILE_KEYS = [
    "id", "username", "preferred_ai_model",
    "brand_voice", "target_persona", # 既存の簡易版。詳細版への移行を検討。
    "x_api_key", "x_api_secret_key", "x_access_token", "x_access_token_secret",
    # 新しいアカウント戦略関連カラム
    "account_purpose",
    "main_target_audience", # JSONB
    "core_value_proposition",
    "brand_voice_detail",   # JSONB
    "main_product_summary",
    # 教育基本方針 (代表的なものやAIで特に重要なものを選定。全て含めるとg.profileが大きくなりすぎる可能性も)
    "edu_s1_purpose_base",
    "edu_s3_problem_base",
    "edu_s4_solution_base",
    "edu_s6_action_base",
    "edu_r1_engagement_hook_base",
    "edu_r3_change_mindset_base"
]
# ↑↑↑ここまで追記・変更↑↑↑

# Supabase クライアント初期化
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
print(f">>> SUPABASE_URL: {url}")
print(f">>> SUPABASE_KEY: {'Set (Hidden)' if key else '!!! Not Set !!!'}")
supabase: Client = None
if not url or not key: print("!!! FATAL ERROR: SUPABASE_URL or SUPABASE_KEY is not set.")
else:
    try: supabase = create_client(url, key); print(">>> Supabase client initialized.")
    except Exception as e: print(f"!!! FATAL ERROR: Failed to initialize Supabase client: {e}")

# Gemini API キー設定
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key: print("!!! WARNING: GEMINI_API_KEY is not set. AI features will be disabled.")
else:
    try: genai.configure(api_key=gemini_api_key); print(">>> Gemini API key configured.")
    except Exception as e: print(f"!!! WARNING: Failed to configure Gemini API key: {e}. AI features might fail.")

# Cronジョブからのリクエストを認証するためのシークレットキーを環境変数から読み込む (推奨)
CRON_JOB_SECRET = os.environ.get("CRON_JOB_SECRET")
if not CRON_JOB_SECRET:
    print("!!! WARNING: CRON_JOB_SECRET is not set. Scheduled tweet endpoint will be insecure if not protected otherwise.")

# JWT 検証デコレーター
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        
        print(">>> Entering token_required decorator (actual request)...")
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        
        if not token:
            print("!!! Token is missing!")
            return jsonify({"message": "Token is missing!"}), 401
        
        try: # tryブロックの開始
            if not supabase:
                print("!!! Supabase client not initialized in token_required!")
                return jsonify({"message": "Supabase client not initialized!"}), 500
            
            user_response = supabase.auth.get_user(token)
            g.user = user_response.user # g.user に代入
            
            if g.user: #
                profile_res = supabase.table('profiles').select(
                    ",".join(G_PROFILE_KEYS) 
                ).eq('id', g.user.id).maybe_single().execute() #
                g.profile = profile_res.data if profile_res.data else {} #
                
                log_g_profile_summary = {
                    k: (str(v)[:30] + '...' if isinstance(v, (str, dict, list)) and len(str(v)) > 35 else v)
                    for k, v in g.profile.items()
                } #
                
                print(f">>> Token validated for user: {g.user.id}. g.profile keys loaded: {list(g.profile.keys())}") #
                
                if 'main_target_audience' in g.profile: #
                    print(f"    g.profile sample (main_target_audience): {log_g_profile_summary.get('main_target_audience')}") #
                
                if 'brand_voice_detail' in g.profile: #
                     print(f"    g.profile sample (brand_voice_detail): {log_g_profile_summary.get('brand_voice_detail')}") #
            
            else: # if g.user: に対応する else
                g.profile = {} #
                print(f">>> Token validated but no user object returned by supabase.auth.get_user().") #

        except Exception as e: # tryに対応するexcept
            print(f"!!! Token validation error: {e}") #
            traceback.print_exc() #
            return jsonify({"message": "Token invalid or expired!", "error": str(e)}), 401 #
        
        # tryブロックが正常に終了した場合（except に入らなかった場合）に実行される
        return f(*args, **kwargs) # この return は try-except ブロックの外側（同じインデントレベル）であるべき

    return decorated

@app.route('/')
def index():
    print(">>> GET / called")
    return jsonify({"message": "Welcome to the EDS Backend API!"})



@app.route('/api/v1/profile', methods=['GET', 'PUT'])
@token_required
def handle_profile():
    user = getattr(g, 'user', None)
    if not user: 
        print("!!! Auth error in handle_profile: No user object in g after token_required.")
        return jsonify({"message": "Authentication error: User context not found."}), 401
    user_id = user.id
    
    if not supabase: 
        print("!!! Supabase client not initialized in handle_profile")
        return jsonify({"message": "Supabase client not initialized!"}), 500

    if request.method == 'GET':
        try:
            print(f">>> GET /api/v1/profile for user_id: {user_id}. Selecting columns: {PROFILE_COLUMNS_TO_SELECT}")
            res = supabase.table('profiles').select(
                ",".join(PROFILE_COLUMNS_TO_SELECT) # 更新されたカラムリストを使用
            ).eq('id',user_id).maybe_single().execute()
            
            if res.data: 
                return jsonify(res.data)
            print(f"--- Profile not found for user_id: {user_id} during GET")
            return jsonify({"message":"Profile not found."}), 404
        except Exception as e: 
            print(f"!!! Error fetching profile for user_id {user_id}: {e}")
            traceback.print_exc()
            return jsonify({"message":"Error fetching profile","error":str(e)}),500
            
    elif request.method == 'PUT':
        data=request.json
        if not data:
            print("!!! Bad request in handle_profile PUT: No JSON data received")
            return jsonify({"message": "Invalid request: No JSON data provided."}), 400

        # 更新を許可するフィールドリスト (PROFILE_COLUMNS_TO_SELECTからid, updated_at等を除いたものに相当)
        allowed_fields_for_update = [
            'username', 'website', 'avatar_url', 'brand_voice', 'target_persona',
            'preferred_ai_model', 'x_api_key', 'x_api_secret_key',
            'x_access_token', 'x_access_token_secret',
            "account_purpose", "main_target_audience", "core_value_proposition",
            "brand_voice_detail", "main_product_summary",
            "edu_s1_purpose_base", "edu_s2_trust_base", "edu_s3_problem_base",
            "edu_s4_solution_base", "edu_s5_investment_base", "edu_s6_action_base",
            "edu_r1_engagement_hook_base", "edu_r2_repetition_base",
            "edu_r3_change_mindset_base", "edu_r4_receptiveness_base",
            "edu_r5_output_encouragement_base", "edu_r6_baseline_shift_base"
        ]
        payload={k:v for k,v in data.items() if k in allowed_fields_for_update}

        if not payload: 
            print("!!! No valid fields for profile update.")
            return jsonify({"message":"No valid fields for update."}),400
            
        payload['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        log_payload = {
            k: (str(v)[:20] + '...' if isinstance(v, (str, dict, list)) and len(str(v)) > 25 else v) 
            for k,v in payload.items()
        }
        print(f">>> Attempting to update profile for user_id: {user_id} with payload: {log_payload}")

        try:
            res=supabase.table('profiles').update(payload).eq('id',user_id).execute()
            
            if res.data and isinstance(res.data, list) and len(res.data) > 0:
                print(f">>> Profile updated successfully for user_id: {user_id}.")
                # g.profile の更新ロジックも新しいキーを考慮
                updated_profile_data_for_g = {
                    key: res.data[0].get(key) for key in G_PROFILE_KEYS if res.data[0].get(key) is not None
                }
                g.profile = updated_profile_data_for_g # g.profileを更新
                log_g_profile_summary_put = {
                    k: (str(v)[:30] + '...' if isinstance(v, (str, dict, list)) and len(str(v)) > 35 else v)
                    for k, v in g.profile.items()
                }
                print(f"    g.profile updated with keys: {list(g.profile.keys())}")
                print(f"    Sample g.profile content after PUT: {log_g_profile_summary_put}")
                return jsonify(res.data[0])
            elif hasattr(res,'error') and res.error:
                print(f"!!! Supabase error updating profile for user_id {user_id}: {res.error}")
                return jsonify({"message":"Error updating profile","error":str(res.error)}),500
            else:
                # 更新成功したが res.data が空の場合の再フェッチ処理
                print(f"--- Profile update for user_id {user_id} returned no data in res.data (or not a list), attempting re-fetch.")
                updated_res = supabase.table('profiles').select(
                     ",".join(PROFILE_COLUMNS_TO_SELECT)
                ).eq('id',user_id).maybe_single().execute()
                if updated_res.data:
                    print(f">>> Profile re-fetched successfully for user_id: {user_id}")
                    updated_profile_for_g_refetch = {
                        key: updated_res.data.get(key) for key in G_PROFILE_KEYS if updated_res.data.get(key) is not None
                    }
                    g.profile = updated_profile_for_g_refetch # g.profileを更新
                    log_g_profile_summary_refetch = {
                        k: (str(v)[:30] + '...' if isinstance(v, (str, dict, list)) and len(str(v)) > 35 else v)
                        for k, v in g.profile.items()
                    }
                    print(f"    g.profile updated (after re-fetch) with keys: {list(g.profile.keys())}")
                    print(f"    Sample g.profile content after re-fetch: {log_g_profile_summary_refetch}")
                    return jsonify(updated_res.data), 200
                else:
                    print(f"!!! Failed to re-fetch profile for user_id {user_id} after update. Error: {updated_res.error if hasattr(updated_res, 'error') else 'Unknown'}")
                    return jsonify({"message":"Profile updated, but failed to retrieve updated data."}), 200 # 成功したがデータは返せない場合
        except Exception as e: 
            print(f"!!! Exception updating profile for user_id {user_id}: {e}")
            traceback.print_exc()
            return jsonify({"message":"Error updating profile","error":str(e)}),500
            
    return jsonify({"message": "Method Not Allowed"}), 405

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
    user = getattr(g, 'user', None); data = request.json
    if not user: return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    if not data or 'name' not in data or not data['name'] or 'product_id' not in data or not data['product_id']: 
        return jsonify({"message": "Missing required fields: name and product_id"}),400
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}),500
        new_l_data = {
            "name": data.get("name"),
            "product_id": data.get("product_id"),
            "description": data.get("description"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "goal": data.get("goal"),
            "user_id": user_id, 
            "status": data.get("status","planning")
        }
        l_res=supabase.table('launches').insert(new_l_data).execute()
        if l_res.data:
            created_launch=l_res.data[0]
            try:
                strategy_data={"launch_id":created_launch['id'],"user_id":user_id}
                s_res=supabase.table('education_strategies').insert(strategy_data).execute()
                if hasattr(s_res,'error') and s_res.error: 
                    print(f"!!! Launch {created_launch['id']} created, but failed to create strategy: {s_res.error}")
                    return jsonify({"message":"Launch created, but failed to automatically create its education strategy.","launch":created_launch,"strategy_error":str(s_res.error)}),207
                print(f">>> Launch {created_launch['id']} and its strategy created successfully.")
                return jsonify(created_launch),201
            except Exception as es_strat: 
                print(f"!!! Launch {created_launch['id']} created, but exception occurred creating strategy: {es_strat}")
                traceback.print_exc(); 
                return jsonify({"message":"Launch created, but an exception occurred while creating its education strategy.","launch":created_launch,"strategy_exception":str(es_strat)}),207
        elif hasattr(l_res,'error') and l_res.error: 
            print(f"!!! Error creating launch: {l_res.error}")
            return jsonify({"message":"Error creating launch","error":str(l_res.error)}),500
        print("!!! Error creating launch, unknown reason (no data and no error from Supabase).")
        return jsonify({"message":"Error creating launch, unknown reason."}),500
    except Exception as e: 
        print(f"!!! Exception creating launch: {e}")
        traceback.print_exc(); 
        return jsonify({"message":"Error creating launch due to an exception","error":str(e)}),500

# app.py の get_launches 関数
@app.route('/api/v1/launches', methods=['GET'])
@token_required
def get_launches():
    user = getattr(g, 'user', None)
    if not user: return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        # productsテーブルからidとnameをJOINして取得 (launches.product_id と products.id を結合)
        # SupabaseのPythonクライアントの記法でJOINを行う
        # .select("*, products(id, name)") のようにリレーションを指定
        res = supabase.table('launches').select(
            "*, products!inner(id, name)"
        ).eq('user_id', user_id).order('created_at', desc=True).execute()

        if res.data is not None:
            # product_id に紐づく products の name を launch オブジェクトのトップレベルに product_nameとして追加する処理
            # (SupabaseのJOINの仕方によっては、ネストされた形で返ってくるので整形が必要な場合がある)
            # 以下は、res.data の各 launch オブジェクトに 'products' というキーで商品情報がネストされていると仮定
            # (Supabase の foreignTable!inner(columns) の場合、通常はネストされる)

            # 注: Supabase の .select("*, products!inner(id, name)") の結果、
            # launch オブジェクト内に 'products': {'id': '...', 'name': '...'} のように
            # ネストされた辞書として商品情報が含まれるはずです。
            # フロントエンド側でこの構造をそのまま利用するか、ここで整形します。
            # ここでは、フロントエンドが期待する形に合わせて整形する例も示します（必要に応じて）。

            # 例：フロントエンドが launch.product_name を期待している場合
            # launches_with_product_name = []
            # for launch in res.data:
            #     if launch.get('products') and isinstance(launch.get('products'), dict):
            #         launch['product_name'] = launch['products'].get('name')
            #     else:
            #         launch['product_name'] = '不明な商品 (JOIN失敗 or 商品なし)'
            #     launches_with_product_name.append(launch)
            # return jsonify(launches_with_product_name)

            # そのまま返す場合 (フロントエンドで launch.products.name のようにアクセス)
            return jsonify(res.data)

        elif hasattr(res, 'error') and res.error:
            return jsonify({"message": "Error fetching launches", "error": str(res.error)}), 500
        return jsonify({"message": "Error fetching launches, unknown reason."}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "Error fetching launches", "error": str(e)}), 500
    
@app.route('/api/v1/launches/<uuid:launch_id>/strategy', methods=['GET', 'PUT'])
@token_required
def handle_launch_strategy(launch_id):
    user = getattr(g, 'user', None)
    if not user: 
        print("!!! Auth error in handle_launch_strategy: No user object in g.")
        return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    
    if not supabase: 
        print("!!! Supabase client not initialized in handle_launch_strategy.")
        return jsonify({"message": "Supabase client not initialized!"}), 500

    # まず、リクエストされた launch_id が現在のユーザーのものであるかを確認
    try: 
        launch_check_res = supabase.table('launches').select("id, name").eq('id', launch_id).eq('user_id', user_id).maybe_single().execute()
        if not launch_check_res.data:
            print(f"!!! Launch ID {launch_id} not found or access denied for user_id {user_id}.")
            return jsonify({"message": "Launch not found or access denied."}), 404
        # g.current_launch_name = launch_check_res.data.get('name') # 必要ならgに格納
    except Exception as e_launch_check:
        print(f"!!! Exception while verifying launch {launch_id} for user {user_id}: {e_launch_check}")
        traceback.print_exc()
        return jsonify({"message": "Error verifying launch ownership", "error": str(e_launch_check)}), 500

    # --- GETリクエストの処理 ---
    if request.method == 'GET': #
        try:
            # ローンチ固有の戦略を取得
            strategy_res = supabase.table('education_strategies').select("*").eq('launch_id', launch_id).eq('user_id', user_id).maybe_single().execute()
            launch_strategy_data = strategy_res.data if strategy_res.data else {} 
            
            if hasattr(strategy_res, 'error') and strategy_res.error:
                 print(f"!!! Supabase error fetching specific launch strategy for launch {launch_id}: {strategy_res.error}")
                 # エラーがあっても、アカウント基本方針は返せるように、ここでは処理を中断しない
                 launch_strategy_data = {"error_fetching_launch_strategy": str(strategy_res.error)}


            account_profile = getattr(g, 'profile', {}) 
            if not account_profile:
                 print(f"!!! Warning: g.profile is empty in handle_launch_strategy GET for user {user_id}. Account bases will be empty.")

            account_strategy_bases = {
                "account_purpose": account_profile.get("account_purpose"),
                "main_target_audience": account_profile.get("main_target_audience"),
                "core_value_proposition": account_profile.get("core_value_proposition"),
                "brand_voice_detail": account_profile.get("brand_voice_detail"),
                "main_product_summary": account_profile.get("main_product_summary"),
                "edu_s1_purpose_base": account_profile.get("edu_s1_purpose_base"),
                "edu_s2_trust_base": account_profile.get("edu_s2_trust_base"),
                "edu_s3_problem_base": account_profile.get("edu_s3_problem_base"),
                "edu_s4_solution_base": account_profile.get("edu_s4_solution_base"),
                "edu_s5_investment_base": account_profile.get("edu_s5_investment_base"),
                "edu_s6_action_base": account_profile.get("edu_s6_action_base"),
                "edu_r1_engagement_hook_base": account_profile.get("edu_r1_engagement_hook_base"),
                "edu_r2_repetition_base": account_profile.get("edu_r2_repetition_base"),
                "edu_r3_change_mindset_base": account_profile.get("edu_r3_change_mindset_base"),
                "edu_r4_receptiveness_base": account_profile.get("edu_r4_receptiveness_base"),
                "edu_r5_output_encouragement_base": account_profile.get("edu_r5_output_encouragement_base"),
                "edu_r6_baseline_shift_base": account_profile.get("edu_r6_baseline_shift_base")
            }
            account_strategy_bases_cleaned = {k: v for k, v in account_strategy_bases.items() if v is not None}
            
            print(f">>> GET /api/v1/launches/{launch_id}/strategy. Specific strategy found: {'Yes' if launch_strategy_data and not launch_strategy_data.get('error_fetching_launch_strategy') else 'No/Error'}")
            # ログ出力は簡潔に
            # log_account_bases_summary = {
            #     k: (str(v)[:30] + '...' if v and len(str(v)) > 35 else v) 
            #     for k, v in account_strategy_bases_cleaned.items()
            # }
            # print(f"    Account strategy bases loaded for response: {log_account_bases_summary}")

            return jsonify({
                "launch_strategy": launch_strategy_data,
                "account_strategy_bases": account_strategy_bases_cleaned
            })

        except Exception as e_get_strat: 
            print(f"!!! Exception in GET handle_launch_strategy for launch {launch_id}: {e_get_strat}")
            traceback.print_exc()
            return jsonify({"message":"Error fetching strategy data","error":str(e_get_strat)}),500
    
    # --- PUTリクエストの処理 ---
    elif request.method == 'PUT': #
        data=request.json
        if not data: 
            print(f"!!! PUT /api/v1/launches/{launch_id}/strategy: No JSON data.")
            return jsonify({"message": "Invalid request: No JSON data provided."}), 400
        
        # ローンチ固有の戦略で更新を許可するフィールド
        allowed_launch_strategy_fields=[
            'product_analysis_summary','target_customer_summary',
            'edu_s1_purpose','edu_s2_trust','edu_s3_problem',
            'edu_s4_solution','edu_s5_investment','edu_s6_action',
            'edu_r1_engagement_hook','edu_r2_repetition','edu_r3_change_mindset',
            'edu_r4_receptiveness','edu_r5_output_encouragement','edu_r6_baseline_shift'
        ]
        payload={k:v for k,v in data.items() if k in allowed_launch_strategy_fields}
        
        if not payload: 
            print(f"!!! PUT /api/v1/launches/{launch_id}/strategy: No valid fields for strategy update in payload.")
            return jsonify({"message":"No valid fields for strategy update."}),400
            
        payload['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # launch_id と user_id はWHERE句で使うのでpayloadには不要だが、
        # upsertやinsertを考慮するならpayloadに含めても良い
        # payload['launch_id'] = launch_id
        # payload['user_id'] = user_id
        
        log_payload_put_strat = {
            k: (str(v)[:30] + '...' if v and len(str(v)) > 35 else v)
            for k,v in payload.items()
        }
        print(f">>> Attempting to update strategy for launch_id: {launch_id}, user_id: {user_id} with payload: {log_payload_put_strat}")
        
        try:
            # education_strategies テーブルにレコードが存在するか確認
            # 存在すればUPDATE、存在しなければINSERT (Upsertの挙動)
            # SupabaseのPythonクライアントで直接upsertは .upsert() を使う
            # ここでは、まず launch 作成時に strategy レコードも作られる前提なので、基本は update
            
            # 更新対象のレコードが存在するかをまず確認 (所有権チェックも兼ねる)
            check_strat_res = supabase.table('education_strategies').select("id").eq('launch_id', launch_id).eq('user_id', user_id).maybe_single().execute()

            if hasattr(check_strat_res, 'error') and check_strat_res.error:
                print(f"!!! Supabase error checking existing strategy for launch {launch_id}: {check_strat_res.error}")
                return jsonify({"message": "Error checking existing strategy", "error": str(check_strat_res.error)}), 500

            if not check_strat_res.data:
                # 通常、ローンチ作成時に戦略レコードも作られるはず。もしなければINSERTも考慮するか、エラーとする。
                # ここではエラーとして扱う (ローンチ作成時のロジックに依存)
                print(f"!!! Strategy record for launch_id {launch_id} (user_id: {user_id}) not found. It should have been created with the launch.")
                # 必要ならここでINSERT処理を試みる
                # payload_insert = payload.copy()
                # payload_insert['launch_id'] = launch_id
                # payload_insert['user_id'] = user_id
                # insert_res = supabase.table('education_strategies').insert(payload_insert).execute()
                # if insert_res.data: return jsonify(insert_res.data[0]), 201
                # else: return jsonify({"message": "Strategy not found, and failed to create new one.", "error": str(insert_res.error if hasattr(insert_res,'error') else 'Unknown insert error')}), 500
                return jsonify({"message": "Strategy record not found. Please ensure launch creation also creates a strategy entry."}), 404

            # レコードが存在するのでUPDATE
            res = supabase.table('education_strategies').update(payload).eq('launch_id',launch_id).eq('user_id',user_id).execute() #
            
            if res.data and isinstance(res.data, list) and len(res.data) > 0: #
                print(f">>> Strategy updated successfully for launch_id: {launch_id}. Data: {res.data[0]}") #
                return jsonify(res.data[0]) #
            elif hasattr(res,'error') and res.error: #
                print(f"!!! Supabase error updating strategy for launch_id {launch_id}: {res.error}") #
                return jsonify({"message":"Error updating strategy","error":str(res.error)}),500 #
            else: #
                # 更新は成功したが res.data が空の場合 (Supabaseの挙動による)
                print(f"--- Strategy for launch_id {launch_id} updated (res.data empty or not list), re-fetching for confirmation.")
                updated_strat_res = supabase.table('education_strategies').select("*").eq('launch_id',launch_id).eq('user_id',user_id).single().execute()
                if updated_strat_res.data: 
                    return jsonify(updated_strat_res.data)
                else:
                    err_msg_refetch = str(updated_strat_res.error) if hasattr(updated_strat_res,'error') and updated_strat_res.error else "Failed to re-fetch after update."
                    print(f"!!! Failed to re-fetch strategy after update for launch {launch_id}: {err_msg_refetch}")
                    return jsonify({"message":"Strategy updated, but failed to retrieve confirmation.", "error_detail": err_msg_refetch}), 200 # 200 OKだが詳細はエラー

        except Exception as e_put_strat: 
            print(f"!!! Exception updating strategy for launch_id {launch_id}: {e_put_strat}")
            traceback.print_exc()
            return jsonify({"message":"Error updating strategy","error":str(e_put_strat)}),500
            
    # --- ここに到達する場合はメソッドがGETでもPUTでもない ---
    print(f"!!! Method {request.method} not allowed for /api/v1/launches/{launch_id}/strategy")
    return jsonify({"message": "Method Not Allowed"}), 405

# --- AI機能 API ---
def get_current_ai_model(user_profile, default_model_name='gemini-1.5-flash-latest', system_instruction_text=None):
    if not gemini_api_key: 
        print("!!! AI features disabled: GEMINI_API_KEY is not set.")
        return None
    preferred_model = user_profile.get('preferred_ai_model', default_model_name)
    print(f">>> AI: Attempting to use model: {preferred_model}")
    model_kwargs = {}
    if system_instruction_text: 
        model_kwargs['system_instruction'] = system_instruction_text
        print(f">>> AI: Using System instruction for {preferred_model}: {system_instruction_text[:150]}...")
    try:
        generation_config = genai.types.GenerationConfig(
            temperature=0.7,
        )
        model = genai.GenerativeModel(
            preferred_model, 
            generation_config=generation_config,
            **model_kwargs
        )
        print(f">>> AI: Successfully initialized model: {preferred_model}")
        return model
    except Exception as e_pref:
        print(f"!!! AI: Failed to initialize preferred model '{preferred_model}': {e_pref}. Trying default '{default_model_name}'.")
        try: 
            model = genai.GenerativeModel(
                default_model_name, 
                generation_config=generation_config, 
                **model_kwargs
            )
            print(f">>> AI: Successfully initialized default model: {default_model_name}")
            return model
        except Exception as e_default: 
            print(f"!!! AI: Failed to initialize default model '{default_model_name}': {e_default}.")
            traceback.print_exc()
            return None

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
@app.route('/api/v1/tweets', methods=['POST'])
@token_required
def save_tweet_draft():
    user = getattr(g, 'user', None)
    if not user: return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    data = request.json
    if not data: return jsonify({"message": "Invalid request: No JSON data provided."}), 400
    print(f">>> POST /api/v1/tweets (save draft) called by user_id: {user_id} with data: {data}")
    content = data.get('content')
    if not content: return jsonify({"message": "Tweet content is required."}), 400
    
    status = data.get('status', 'draft')
    scheduled_at_str = data.get('scheduled_at')
    edu_el_key = data.get('education_element_key')
    launch_id_fk = data.get('launch_id')
    notes_int = data.get('notes_internal')
    
    scheduled_at_ts = None
    if scheduled_at_str:
        try:
            if 'T' in scheduled_at_str and not scheduled_at_str.endswith('Z'):
                 dt_obj_naive = datetime.datetime.fromisoformat(scheduled_at_str)
                 dt_obj_utc = dt_obj_naive.astimezone(datetime.timezone.utc)
            else: 
                 dt_obj_utc = datetime.datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
            scheduled_at_ts = dt_obj_utc.isoformat()
        except ValueError as ve: 
            print(f"!!! Invalid scheduled_at format: {scheduled_at_str}. Error: {ve}")
            return jsonify({"message": f"Invalid scheduled_at format: {scheduled_at_str}. Use ISO 8601 (e.g., YYYY-MM-DDTHH:MM:SSZ)."}), 400
    
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        new_tweet_data = {
            "user_id": user_id, 
            "content": content, 
            "status": status, 
            "scheduled_at": scheduled_at_ts, 
            "education_element_key": edu_el_key, 
            "launch_id": launch_id_fk, 
            "notes_internal": notes_int
        }
        payload_to_insert = new_tweet_data

        query_response = supabase.table('tweets').insert(payload_to_insert).execute()
        if query_response.data:
            print(f">>> Tweet draft saved: {query_response.data[0]}")
            return jsonify(query_response.data[0]), 201
        elif hasattr(query_response, 'error') and query_response.error:
             print(f"!!! Supabase tweet insert error: {query_response.error}")
             return jsonify({"message": "Error saving tweet draft", "error": str(query_response.error)}), 500
        else:
            print("!!! Tweet draft save failed, no data and no error from Supabase.")
            return jsonify({"message": "Error saving tweet draft, unknown reason."}), 500
    except Exception as e:
        print(f"!!! Tweet draft save exception: {e}"); traceback.print_exc()
        return jsonify({"message": "Error saving tweet draft", "error": str(e)}), 500


# --- ★ ここから予約投稿実行APIを追加 ★ ---
@app.route('/api/v1/tweets/execute-scheduled', methods=['POST'])
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
        
        # scheduled_at が null でないこと、かつ現在時刻以前であることを確認
        # Supabaseのクエリでは、直接的な時刻比較が文字列型に対して難しい場合があるため、
        # 取得後にPython側でフィルタリングすることも検討するか、DBの型をtimestampにする。
        # ここでは、まず 'scheduled' のものを取得し、Python側で時刻比較する方針も考えられるが、
        # まずはDBクエリで絞り込みを試みる。
        # 注意: 'lte' (less than or equal) を使うために scheduled_at は timestamp 型である方が望ましい。
        #       もし text 型なら、このクエリは期待通りに動かない可能性がある。
        #       text型の場合は、一旦広めに取得してPython側で正確にフィルタリングする。
        
        # 仮にscheduled_atがISO文字列としてtext型に保存されている場合、
        # 一旦'scheduled'のものを取得し、Python側でパースして比較する方が安全かもしれません。
        # ここでは、まずDBにフィルタを試みる形にします。
        scheduled_tweets_res = supabase.table('tweets').select(
            "*, profiles(x_api_key, x_api_secret_key, x_access_token, x_access_token_secret)" # ユーザーの認証情報をJOIN
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
            profile_data = tweet_data.get('profiles') # JOINされたprofilesテーブルのデータ

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
                print(f">>> Attempting to post tweet ID {tweet_id} to X for user {user_id}...")
                created_x_tweet_response = api_client_v2.create_tweet(text=content)
                
                x_tweet_id_str = None
                if created_x_tweet_response.data and created_x_tweet_response.data.get('id'):
                    x_tweet_id_str = created_x_tweet_response.data.get('id')
                    print(f">>> Tweet ID {tweet_id} posted successfully to X! X Tweet ID: {x_tweet_id_str}")
                    
                    supabase.table('tweets').update({
                        "status": "posted",
                        "posted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "x_tweet_id": x_tweet_id_str,
                        "error_message": None, # エラーが解消された場合クリア
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }).eq('id', tweet_id).execute()
                    successful_posts += 1
                    processed_tweets.append({"id": tweet_id, "status": "posted", "x_tweet_id": x_tweet_id_str})
                else:
                    # X APIからのエラーレスポンスの処理 (post_tweet_now から流用)
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
                # TweepyExceptionのエラーメッセージ整形 (post_tweet_now から流用)
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
# --- 予約投稿実行APIはここまで ★ ---



@app.route('/api/v1/tweets', methods=['GET'])
@token_required
def get_saved_tweets():
    user = getattr(g, 'user', None)
    if not user: return jsonify({"message": "Authentication error."}), 401
    user_id = user.id
    status_filter = request.args.get('status') 
    launch_id_filter = request.args.get('launch_id')

    print(f">>> GET /api/v1/tweets called by user_id: {user_id}, status_filter: {status_filter}, launch_id_filter: {launch_id_filter}")
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        query = supabase.table('tweets').select("*").eq('user_id', user_id)
        if status_filter: 
            query = query.eq('status', status_filter)
        if launch_id_filter:
            query = query.eq('launch_id', launch_id_filter)
            
        query_response = query.order('created_at', desc=True).execute()
        
        if query_response.data is not None:
            print(f">>> Saved tweets fetched: {len(query_response.data)} items")
            return jsonify(query_response.data)
        elif hasattr(query_response, 'error') and query_response.error:
            print(f"!!! Supabase tweets fetch error: {query_response.error}")
            return jsonify({"message": "Error fetching tweets", "error": str(query_response.error)}), 500
        else:
            print("!!! Tweets fetch failed, no data and no error from Supabase.")
            return jsonify({"message": "Error fetching tweets, unknown reason."}), 500
    except Exception as e:
        print(f"!!! Tweets fetch exception: {e}"); traceback.print_exc()
        return jsonify({"message": "Error fetching tweets", "error": str(e)}), 500

# --- ★ ここからツイート更新API ★ ---
@app.route('/api/v1/tweets/<uuid:tweet_id_param>', methods=['PUT'])
@token_required
def update_tweet(tweet_id_param):
    user = getattr(g, 'user', None)
    user_id = user.id 
    
    data = request.json
    if not data:
        print(f"!!! PUT /api/v1/tweets/{tweet_id_param}: No JSON data provided.")
        return jsonify({"message": "Invalid request: No JSON data provided."}), 400

    print(f">>> PUT /api/v1/tweets/{tweet_id_param} called by user_id: {user_id} with data: {data}")

    allowed_update_fields = ['content', 'status', 'scheduled_at', 'education_element_key', 'launch_id', 'notes_internal']
    payload_to_update = {}
    
    for field in allowed_update_fields:
        if field in data:
            payload_to_update[field] = data[field]

    if not payload_to_update:
        print(f"--- PUT /api/v1/tweets/{tweet_id_param}: No valid fields provided for update.")
        return jsonify({"message": "No valid fields provided for update."}), 400

    if 'scheduled_at' in payload_to_update:
        scheduled_at_str = payload_to_update['scheduled_at']
        if scheduled_at_str: 
            try:
                if 'T' in scheduled_at_str and not scheduled_at_str.endswith('Z'):
                     dt_obj_naive = datetime.datetime.fromisoformat(scheduled_at_str)
                     dt_obj_utc = dt_obj_naive.astimezone(datetime.timezone.utc)
                else: 
                     dt_obj_utc = datetime.datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
                payload_to_update['scheduled_at'] = dt_obj_utc.isoformat()
            except ValueError as ve:
                print(f"!!! Invalid scheduled_at format during update for tweet {tweet_id_param}: {scheduled_at_str}. Error: {ve}")
                return jsonify({"message": f"Invalid scheduled_at format: {scheduled_at_str}. Use ISO 8601 (e.g., YYYY-MM-DDTHH:MM:SSZ)."}), 400
        else: 
            payload_to_update['scheduled_at'] = None

    payload_to_update['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    log_payload_update = {k: (v[:20] + '...' if isinstance(v, str) and len(v) > 25 else v) for k,v in payload_to_update.items()}
    print(f">>> Attempting to update tweet_id: {tweet_id_param} with payload: {log_payload_update}")

    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        
        existing_tweet_res = supabase.table('tweets').select('id, user_id').eq('id', tweet_id_param).eq('user_id', user_id).maybe_single().execute()
        if not existing_tweet_res.data:
            print(f"!!! Tweet {tweet_id_param} not found or access denied for user {user_id} during update.")
            return jsonify({"message": "Tweet not found or access denied."}), 404

        update_response = supabase.table('tweets').update(payload_to_update).eq('id', tweet_id_param).eq('user_id', user_id).execute()

        if update_response.data:
            print(f">>> Tweet {tweet_id_param} updated successfully: {update_response.data[0]}")
            return jsonify(update_response.data[0]), 200
        elif hasattr(update_response, 'error') and update_response.error:
            print(f"!!! Supabase tweet update error for tweet_id {tweet_id_param}: {update_response.error}")
            return jsonify({"message": "Error updating tweet", "error": str(update_response.error)}), 500
        else:
            print(f"--- Tweet {tweet_id_param} update may have succeeded (no data in response), re-fetching for confirmation.")
            updated_tweet_data_res = supabase.table('tweets').select("*").eq('id', tweet_id_param).eq('user_id', user_id).single().execute()
            if updated_tweet_data_res.data:
                 print(f">>> Tweet {tweet_id_param} re-fetched successfully after update.")
                 return jsonify(updated_tweet_data_res.data), 200
            else:
                 print(f"!!! Failed to re-fetch tweet {tweet_id_param} after update. Error: {updated_tweet_data_res.error if hasattr(updated_tweet_data_res, 'error') else 'Unknown'}")
                 return jsonify({"message": "Tweet updated, but failed to retrieve current state."}), 200

    except Exception as e:
        print(f"!!! Exception updating tweet {tweet_id_param}: {e}"); traceback.print_exc()
        return jsonify({"message": "An unexpected error occurred while updating the tweet", "error": str(e)}), 500
# --- ツイート更新APIはここまで ★ ---

# --- ★ ここからツイート削除APIを追加 ★ ---
@app.route('/api/v1/tweets/<uuid:tweet_id_param>', methods=['DELETE'])
@token_required
def delete_tweet(tweet_id_param):
    user = getattr(g, 'user', None)
    user_id = user.id # token_required で user は存在するはず
    
    print(f">>> DELETE /api/v1/tweets/{tweet_id_param} called by user_id: {user_id}")

    if not supabase:
        print(f"!!! Supabase client not initialized in delete_tweet for tweet {tweet_id_param}")
        return jsonify({"message": "Supabase client not initialized!"}), 500

    try:
        # 削除対象のツイートが本当にそのユーザーのものかを確認 (重要)
        existing_tweet_res = supabase.table('tweets').select('id, user_id').eq('id', tweet_id_param).eq('user_id', user_id).maybe_single().execute()
        
        if not existing_tweet_res.data:
            print(f"!!! Tweet {tweet_id_param} not found or access denied for user {user_id} during delete.")
            return jsonify({"message": "Tweet not found or access denied."}), 404

        # ツイートを削除
        delete_response = supabase.table('tweets').delete().eq('id', tweet_id_param).eq('user_id', user_id).execute()

        # delete().execute() は成功時、通常 res.data が空のリスト [] になるか、影響を受けた行数を示す。
        # res.error があればエラー。
        if hasattr(delete_response, 'error') and delete_response.error:
            print(f"!!! Supabase tweet delete error for tweet_id {tweet_id_param}: {delete_response.error}")
            return jsonify({"message": "Error deleting tweet", "error": str(delete_response.error)}), 500
        
        # SupabaseのPythonクライアントのdelete操作では、成功時に data には削除されたレコードが含まれないことが多い。
        # そのため、エラーがないことをもって成功と判断する。
        # 影響を受けた行数を確認するなら delete_response.count (もしあれば) などを見る。
        # ここではエラーがないことで成功とみなし、204 No Content を返す。
        print(f">>> Tweet {tweet_id_param} deleted successfully by user {user_id}.")
        return '', 204 # 成功時はボディなしで204 No Contentを返すのが一般的

    except Exception as e:
        print(f"!!! Exception deleting tweet {tweet_id_param}: {e}"); traceback.print_exc()
        return jsonify({"message": "An unexpected error occurred while deleting the tweet", "error": str(e)}), 500
# --- ツイート削除APIはここまで ★ ---

# --- ★ ここからツイート即時投稿APIを追加 ★ ---
@app.route('/api/v1/tweets/<uuid:tweet_id_param>/post-now', methods=['POST'])
@token_required
def post_tweet_now(tweet_id_param):
    user = getattr(g, 'user', None)
    user_id = user.id # token_required で user は存在するはず
    user_profile = getattr(g, 'profile', {})

    print(f">>> POST /api/v1/tweets/{tweet_id_param}/post-now called by user_id: {user_id}")

    if not supabase:
        print(f"!!! Supabase client not initialized in post_tweet_now for tweet {tweet_id_param}")
        return jsonify({"message": "Supabase client not initialized!"}), 500

    try:
        # 1. 投稿対象のツイートをDBから取得し、ユーザー所有か確認
        tweet_to_post_res = supabase.table('tweets').select('id, user_id, content, status').eq('id', tweet_id_param).eq('user_id', user_id).maybe_single().execute()

        if not tweet_to_post_res.data:
            print(f"!!! Tweet {tweet_id_param} not found or access denied for user {user_id} during post-now.")
            return jsonify({"message": "Tweet not found or access denied."}), 404
        
        tweet_data = tweet_to_post_res.data
        tweet_content = tweet_data.get('content')

        if not tweet_content:
            print(f"!!! Tweet {tweet_id_param} has no content to post for user {user_id}.")
            return jsonify({"message": "Tweet content is empty, cannot post."}), 400
        
        # (任意)既に投稿済みならエラーにするか、再投稿を許可するかなどの制御
        # if tweet_data.get('status') == 'posted':
        #     return jsonify({"message": "This tweet has already been posted.", "x_tweet_id": tweet_data.get('x_tweet_id')}), 409 # Conflict

        # 2. X APIクライアントを取得
        api_client_v2 = get_x_api_client(user_profile)
        if not api_client_v2:
            return jsonify({"message": "Failed to initialize X API client. Check credentials in MyPage or X API version compatibility."}), 500

        # 3. Xにツイートを投稿
        print(f">>> Attempting to post tweet_id: {tweet_id_param} to X for user_id: {user_id}. Content: {tweet_content[:50]}...")
        created_x_tweet_response = api_client_v2.create_tweet(text=tweet_content)
        
        x_tweet_id_str = None
        if created_x_tweet_response.data and created_x_tweet_response.data.get('id'):
            x_tweet_id_str = created_x_tweet_response.data.get('id')
            print(f">>> Tweet {tweet_id_param} posted successfully to X! X Tweet ID: {x_tweet_id_str}")
        else:
            error_detail_x = "Unknown error or unexpected response structure from X API v2 while posting."
            if hasattr(created_x_tweet_response, 'errors') and created_x_tweet_response.errors:
                error_detail_x = str(created_x_tweet_response.errors)
            elif hasattr(created_x_tweet_response, 'reason'): 
                error_detail_x = created_x_tweet_response.reason
            print(f"!!! Error in X API v2 tweet creation response for user_id {user_id}, tweet_id {tweet_id_param}: {error_detail_x}")
            return jsonify({"message": "Failed to post tweet to X.", "error_detail_from_x": error_detail_x}), 502 # Bad Gateway or use custom code

        # 4. DBのツイート情報を更新 (ステータス、XのツイートID、投稿日時)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        update_payload = {
            "status": "posted",
            "posted_at": now_utc.isoformat(),
            "x_tweet_id": x_tweet_id_str,
            "updated_at": now_utc.isoformat()
        }
        
        db_update_res = supabase.table('tweets').update(update_payload).eq('id', tweet_id_param).eq('user_id', user_id).execute()

        if hasattr(db_update_res, 'error') and db_update_res.error:
            print(f"!!! Tweet {tweet_id_param} posted to X (ID: {x_tweet_id_str}), but failed to update DB status: {db_update_res.error}")
            # Xには投稿成功したがDB更新失敗。この状態をどう扱うか検討が必要（例：エラーログに残し手動対応を促すなど）
            return jsonify({
                "message": "Tweet posted to X successfully, but failed to update its status in the database.", 
                "x_tweet_id": x_tweet_id_str,
                "db_update_error": str(db_update_res.error)
            }), 207 # Multi-Status
        
        # 更新後のツイート情報を取得して返す
        final_tweet_data_res = supabase.table('tweets').select("*").eq('id', tweet_id_param).eq('user_id', user_id).single().execute()
        if final_tweet_data_res.data:
            print(f">>> Tweet {tweet_id_param} status updated in DB. Final data: {final_tweet_data_res.data}")
            return jsonify(final_tweet_data_res.data), 200
        else:
            # ここに来ることは稀だが、DB更新後に再取得失敗した場合
            print(f"!!! Tweet {tweet_id_param} posted to X (ID: {x_tweet_id_str}) and DB update likely succeeded, but failed to re-fetch for confirmation.")
            return jsonify({
                "message": "Tweet posted to X successfully and database status likely updated, but failed to retrieve final confirmation.",
                "x_tweet_id": x_tweet_id_str
            }), 200


    except tweepy.TweepyException as e_tweepy: 
        error_message = str(e_tweepy)
        print(f"!!! TweepyException posting tweet_id {tweet_id_param} for user_id {user_id}: {error_message}")
        if hasattr(e_tweepy, 'response') and e_tweepy.response is not None:
            try:
                error_json = e_tweepy.response.json()
                if 'errors' in error_json and error_json['errors']:
                     error_message = f"X API Error: {error_json['errors'][0].get('message', str(e_tweepy))}"
                elif 'title' in error_json: 
                     error_message = f"X API Error: {error_json['title']}: {error_json.get('detail', '')}"
                elif hasattr(e_tweepy.response, 'data') and e_tweepy.response.data: # For 403 errors etc.
                    error_message = f"X API Error (e.g., 403 Forbidden): {e_tweepy.response.data}"
            except ValueError: 
                pass 
        elif hasattr(e_tweepy, 'api_codes') and hasattr(e_tweepy, 'api_messages'):
             error_message = f"X API Error {e_tweepy.api_codes}: {e_tweepy.api_messages}"
        traceback.print_exc()
        return jsonify({"message": "Failed to post tweet to X (TweepyException).", "error": error_message}), 502 # Bad Gateway
    except Exception as e: 
        print(f"!!! General Exception posting tweet_id {tweet_id_param} for user_id {user_id}: {e}")
        traceback.print_exc()
        return jsonify({"message": "An unexpected error occurred while posting the tweet.", "error": str(e)}), 500
# --- ツイート即時投稿APIはここまで ★ ---

@app.route('/api/v1/educational-tweets/generate', methods=['POST'])
@token_required
def generate_educational_tweet():
    user = getattr(g, 'user', None)
    user_id = user.id
    user_profile = getattr(g, 'profile', {})

    if not supabase:
        print("!!! Supabase client not initialized in generate_educational_tweet")
        return jsonify({"message": "Supabase client not initialized!"}), 500

    data = request.json
    if not data:
        print("!!! Bad request in generate_educational_tweet: No JSON data received")
        return jsonify({"message": "Invalid request: No JSON data provided."}), 400

    education_element_key = data.get('education_element_key')
    theme = data.get('theme')

    if not education_element_key:
        print("!!! Bad request in generate_educational_tweet: education_element_key is missing")
        return jsonify({"message": "Missing required field: education_element_key"}), 400
    if not theme: 
        print("!!! Bad request in generate_educational_tweet: theme is missing or empty")
        return jsonify({"message": "Missing or empty required field: theme"}), 400

    print(f">>> POST /api/v1/educational-tweets/generate called by user_id: {user_id}")
    print(f"    education_element_key: {education_element_key}, theme: {theme}")

    current_text_model = get_current_ai_model(user_profile)
    if not current_text_model:
        print("!!! Gemini model not initialized in generate_educational_tweet")
        return jsonify({"message": "AI model (Gemini) could not be initialized."}), 500

    element_map = {
        "product_analysis_summary": "商品分析の要点",
        "target_customer_summary": "ターゲット顧客分析の要点",
        "edu_s1_purpose": "目的の教育",
        "edu_s2_trust": "信用の教育",
        "edu_s3_problem": "問題点の教育",
        "edu_s4_solution": "手段の教育",
        "edu_s5_investment": "投資の教育",
        "edu_s6_action": "行動の教育",
        "edu_r1_engagement_hook": "読む・見る教育",
        "edu_r2_repetition": "何度も聞く教育",
        "edu_r3_change_mindset": "変化の教育",
        "edu_r4_receptiveness": "素直の教育",
        "edu_r5_output_encouragement": "アウトプットの教育",
        "edu_r6_baseline_shift": "基準値の教育／覚悟の教育"
    }
    education_element_name = element_map.get(education_element_key, education_element_key) 

    brand_voice = user_profile.get('brand_voice', 'プロフェッショナルかつ親しみやすい')
    target_persona = user_profile.get('target_persona', '一般的なインターネットユーザー')

    prompt_parts = [
        "あなたはプロのX（旧Twitter）マーケティングコンサルタントです。",
        f"以下の情報に基づいて、Xの投稿文案を1つ作成してください。",
        f"・投稿のトーン（ブランドボイス）: {brand_voice}",
        f"・ターゲット顧客像: {target_persona}",
        f"・重視する教育要素: {education_element_name} ({education_element_key})",
        f"・ツイートの主なテーマやキーワード: {theme}",
        "・指示: ユーザーエンゲージメント（いいね、リツイート、返信など）を促すような、具体的で魅力的な内容にしてください。ツイートは日本語で140字以内で、適切な絵文字を1～3個使用してください。"
    ]
    prompt = "\n".join(filter(None, prompt_parts)) 

    print(f">>> Gemini Prompt for educational tweet (model: {current_text_model._model_name}):\n{prompt[:500]}...")

    try:
        ai_response = current_text_model.generate_content(prompt)
        generated_tweet_text = ""
        
        try:
            generated_tweet_text = ai_response.text
        except Exception:
            pass 

        if not generated_tweet_text and hasattr(ai_response, 'candidates') and ai_response.candidates:
            generated_tweet_text = "".join([part.text for candidate in ai_response.candidates for part in candidate.content.parts if hasattr(part, 'text')])
        
        if not generated_tweet_text and hasattr(ai_response, 'prompt_feedback'):
            error_feedback = str(ai_response.prompt_feedback)
            print(f"!!! AI generation failed with feedback: {error_feedback}")
            return jsonify({"message": f"AIによるツイート生成に失敗しました: {error_feedback}"}), 500
            
        if not generated_tweet_text:
            print("!!! AI response does not contain usable text.")
            return jsonify({"message": "AIからの応答にツイート文案が含まれていませんでした。"}), 500

        print(f">>> AI Generated Tweet: {generated_tweet_text.strip()}")
        return jsonify({"generated_tweet": generated_tweet_text.strip()}), 200

    except Exception as e:
        print(f"!!! Exception during AI tweet generation: {e}")
        traceback.print_exc()
        return jsonify({"message": "AIによるツイート生成中にエラーが発生しました。", "error": str(e)}), 500

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

# Flaskサーバーの起動
if __name__ == '__main__':
    print("--- Starting Flask server on http://127.0.0.1:5001 ---")
    app.run(debug=True, host='127.0.0.1', port=5001)