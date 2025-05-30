import os
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from functools import wraps
import datetime
import traceback
import google.generativeai as genai

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

# JWT 検証デコレーター
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS': return f(*args, **kwargs)
        print(">>> Entering token_required decorator (actual request)...")
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']; parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer': token = parts[1]
        if not token: print("!!! Token is missing!"); return jsonify({"message": "Token is missing!"}), 401
        try:
            if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
            user_response = supabase.auth.get_user(token); g.user = user_response.user
            if g.user:
                # ★★★ x_api_key 等も g.profile に含める ★★★
                profile_res = supabase.table('profiles').select(
                    "id,username,preferred_ai_model,brand_voice,target_persona,"
                    "x_api_key,x_api_secret_key,x_access_token,x_access_token_secret"
                ).eq('id',g.user.id).maybe_single().execute()
                g.profile = profile_res.data if profile_res.data else {}
                print(f">>> Token validated for user: {g.user.id}, Pref AI: {g.profile.get('preferred_ai_model')}")
            else: g.profile = {}; print(f">>> Token validated but no user object.")
        except Exception as e: print(f"!!! Token validation error: {e}"); traceback.print_exc(); return jsonify({"message": "Token invalid!", "error": str(e)}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index(): print(">>> GET / called"); return jsonify({"message": "Welcome to EDS Backend API!"})

@app.route('/api/v1/profile', methods=['GET', 'PUT'])
@token_required
def handle_profile():
    user = getattr(g, 'user', None); user_id = user.id
    if not user: return jsonify({"message": "Auth error."}), 401
    if not supabase: return jsonify({"message": "Supabase client not init!"}), 500
    if request.method == 'GET':
        try:
            # ★★★ x_api_key 等も select に含める ★★★
            res = supabase.table('profiles').select(
                "id,username,website,avatar_url,brand_voice,target_persona,preferred_ai_model,"
                "x_api_key,x_api_secret_key,x_access_token,x_access_token_secret,updated_at"
            ).eq('id',user_id).maybe_single().execute()
            if res.data: return jsonify(res.data)
            return jsonify({"message":"Profile not found."}), 404
        except Exception as e: traceback.print_exc(); return jsonify({"message":"Error fetching profile","error":str(e)}),500
    elif request.method == 'PUT':
        data=request.json
        # ★★★ allowed_fields に x_api_key 等を追加 ★★★
        allowed_fields = [
            'username','website','avatar_url','brand_voice','target_persona','preferred_ai_model',
            'x_api_key', 'x_api_secret_key', 'x_access_token', 'x_access_token_secret'
        ]
        payload={k:v for k,v in data.items() if k in allowed_fields}
        if not payload: return jsonify({"message":"No valid fields for update."}),400
        payload['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            res=supabase.table('profiles').update(payload).eq('id',user_id).execute()
            if res.data:
                # g.profile も更新
                updated_res = supabase.table('profiles').select(
                    "id,username,preferred_ai_model,brand_voice,target_persona,"
                    "x_api_key,x_api_secret_key,x_access_token,x_access_token_secret"
                ).eq('id',user_id).maybe_single().execute()
                g.profile = updated_res.data if updated_res.data else {}
                return jsonify(res.data[0])
            elif hasattr(res,'error') and res.error: return jsonify({"message":"Error updating profile","error":str(res.error)}),500
            # 更新後のデータを再取得して返す方が確実
            updated_res = supabase.table('profiles').select(
                "id,username,website,avatar_url,brand_voice,target_persona,preferred_ai_model,"
                "x_api_key,x_api_secret_key,x_access_token,x_access_token_secret,updated_at"
            ).eq('id',user_id).maybe_single().execute()
            if updated_res.data: return jsonify(updated_res.data), 200
            return jsonify({"message":"Profile updated, but failed to retrieve updated data."}), 200
        except Exception as e: traceback.print_exc(); return jsonify({"message":"Error updating profile","error":str(e)}),500
    return jsonify({"message": "Method Not Allowed"}), 405

# --- 商品管理 API (省略なし) ---
@app.route('/api/v1/products', methods=['POST'])
@token_required
def create_product():
    user = getattr(g, 'user', None); data = request.json; user_id = user.id
    if not user: return jsonify({"message": "Authentication error."}), 401
    if 'name' not in data or not data['name']: return jsonify({"message": "Missing required field: name"}), 400
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        new_p = {**{k:data.get(k) for k in ['name','description','price','target_audience','value_proposition']}, "user_id": user_id, "currency": data.get("currency","JPY")}
        res = supabase.table('products').insert(new_p).execute()
        if res.data: return jsonify(res.data[0]), 201
        elif hasattr(res, 'error') and res.error: return jsonify({"message": "Error creating product", "error": str(res.error)}), 500
        return jsonify({"message": "Error creating product, unknown reason."}), 500
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error creating product", "error": str(e)}), 500

@app.route('/api/v1/products', methods=['GET'])
@token_required
def get_products():
    user = getattr(g, 'user', None); user_id = user.id
    if not user: return jsonify({"message": "Authentication error."}), 401
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
    user = getattr(g, 'user', None); data = request.json; user_id = user.id
    if not user: return jsonify({"message": "Authentication error."}), 401
    allowed=['name','description','price','currency','target_audience','value_proposition']; payload={k:v for k,v in data.items() if k in allowed}
    if not payload: return jsonify({"message": "No valid fields for update."}), 400
    payload['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        res = supabase.table('products').update(payload).eq('id',product_id).eq('user_id',user_id).execute()
        if res.data: return jsonify(res.data[0])
        elif hasattr(res, 'error') and res.error: return jsonify({"message": "Error updating product", "error": str(res.error)}), 500
        check_exists = supabase.table('products').select('id').eq('id', product_id).eq('user_id', user_id).maybe_single().execute()
        if not check_exists.data: return jsonify({"message":"Product not found to update."}),404
        return jsonify({"message":"Product updated (no data returned)."}),200
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error updating product", "error": str(e)}), 500

@app.route('/api/v1/products/<uuid:product_id>', methods=['DELETE'])
@token_required
def delete_product(product_id):
    user = getattr(g, 'user', None); user_id = user.id
    if not user: return jsonify({"message": "Authentication error."}), 401
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        res = supabase.table('products').delete().eq('id',product_id).eq('user_id',user_id).execute()
        if hasattr(res,'error') and res.error: return jsonify({"message": "Error deleting product", "error": str(res.error)}),500
        return '',204
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error deleting product", "error": str(e)}),500

# --- ローンチ計画と教育戦略 API (省略なし) ---
@app.route('/api/v1/launches', methods=['POST'])
@token_required
def create_launch():
    user = getattr(g, 'user', None); data = request.json; user_id = user.id
    if not user: return jsonify({"message": "Authentication error."}), 401
    if 'name' not in data or not data['name'] or 'product_id' not in data or not data['product_id']: return jsonify({"message": "Missing name or product_id"}),400
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}),500
        new_l={**{k:data.get(k) for k in ['name','product_id','description','start_date','end_date','goal']}, "user_id":user_id, "status":data.get("status","planning")}
        l_res=supabase.table('launches').insert(new_l).execute()
        if l_res.data:
            cl=l_res.data[0]
            try:
                s_data={"launch_id":cl['id'],"user_id":user_id}
                s_res=supabase.table('education_strategies').insert(s_data).execute()
                if hasattr(s_res,'error') and s_res.error: return jsonify({"message":"Launch created, but failed to create strategy.","launch":cl,"strategy_error":str(s_res.error)}),207
                return jsonify(cl),201
            except Exception as es: traceback.print_exc(); return jsonify({"message":"Launch created, but exception creating strategy.","launch":cl,"strategy_exception":str(es)}),207
        elif hasattr(l_res,'error') and l_res.error: return jsonify({"message":"Error creating launch","error":str(l_res.error)}),500
        return jsonify({"message":"Error creating launch"}),500
    except Exception as e: traceback.print_exc(); return jsonify({"message":"Error creating launch","error":str(e)}),500

@app.route('/api/v1/launches', methods=['GET'])
@token_required
def get_launches():
    user = getattr(g, 'user', None); user_id = user.id
    if not user: return jsonify({"message": "Authentication error."}), 401
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        res = supabase.table('launches').select("*, products(id, name)").eq('user_id', user_id).order('created_at', desc=True).execute()
        if res.data is not None: return jsonify(res.data)
        elif hasattr(res, 'error') and res.error: return jsonify({"message": "Error fetching launches", "error": str(res.error)}), 500
        return jsonify({"message": "Error fetching launches"}), 500
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error fetching launches", "error": str(e)}), 500

@app.route('/api/v1/launches/<uuid:launch_id>/strategy', methods=['GET', 'PUT'])
@token_required
def handle_launch_strategy(launch_id):
    user = getattr(g, 'user', None); user_id = user.id
    if not user: return jsonify({"message": "Auth error."}),401
    if not supabase: return jsonify({"message": "Supabase client not init!"}),500
    try: 
        l_check = supabase.table('launches').select("id,name").eq('id',launch_id).eq('user_id',user_id).maybe_single().execute()
        if not l_check.data: return jsonify({"message":"Launch not found or access denied."}),404
    except Exception as e: traceback.print_exc();return jsonify({"message":"Error verifying launch","error":str(e)}),500
    
    if request.method == 'GET':
        try:
            res=supabase.table('education_strategies').select("*").eq('launch_id',launch_id).eq('user_id',user_id).maybe_single().execute()
            if res.data: return jsonify(res.data)
            return jsonify({"message":"Education strategy not found."}),404
        except Exception as e: traceback.print_exc();return jsonify({"message":"Error fetching strategy","error":str(e)}),500
    
    elif request.method == 'PUT':
        data=request.json
        allowed=['product_analysis_summary','target_customer_summary','edu_s1_purpose','edu_s2_trust','edu_s3_problem','edu_s4_solution','edu_s5_investment','edu_s6_action','edu_r1_engagement_hook','edu_r2_repetition','edu_r3_change_mindset','edu_r4_receptiveness','edu_r5_output_encouragement','edu_r6_baseline_shift']
        payload={k:v for k,v in data.items() if k in allowed}
        if not payload: return jsonify({"message":"No valid fields."}),400
        payload['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            res = supabase.table('education_strategies').update(payload).eq('launch_id',launch_id).eq('user_id',user_id).execute()
            if res.data: return jsonify(res.data[0])
            elif hasattr(res,'error') and res.error: return jsonify({"message":"Error updating strategy","error":str(res.error)}),500
            check_exists=supabase.table('education_strategies').select('id').eq('launch_id',launch_id).eq('user_id',user_id).maybe_single().execute()
            if not check_exists.data: return jsonify({"message":"Strategy to update not found."}),404
            return jsonify({"message":"Strategy updated (no data returned)."}),200
        except Exception as e: traceback.print_exc();return jsonify({"message":"Error updating strategy","error":str(e)}),500
    return jsonify({"message": "Method Not Allowed"}), 405

# --- AI機能 API (省略なし) ---
def get_current_ai_model(user_profile, default_model_name='gemini-1.5-flash-latest', system_instruction_text=None):
    if not gemini_api_key: return None
    preferred_model = user_profile.get('preferred_ai_model', default_model_name)
    print(f">>> AI: Attempting to use model: {preferred_model}")
    model_kwargs = {}
    if system_instruction_text: model_kwargs['system_instruction'] = system_instruction_text; print(f">>> AI: System instruction for {preferred_model}: {system_instruction_text[:100]}...")
    try:
        config = genai.types.GenerationConfig(temperature=0.7)
        return genai.GenerativeModel(preferred_model, **model_kwargs, generation_config=config)
    except Exception as e_pref:
        print(f"!!! AI: Failed to init preferred model '{preferred_model}': {e_pref}. Trying default '{default_model_name}'.")
        try: return genai.GenerativeModel(default_model_name, **model_kwargs, generation_config=config)
        except Exception as e_default: print(f"!!! AI: Failed to init default model '{default_model_name}': {e_default}."); return None

@app.route('/api/v1/launches/<uuid:launch_id>/generate-tweet', methods=['POST'])
@token_required
def generate_tweet_for_launch(launch_id):
    user = getattr(g, 'user', None); user_id = user.id; user_profile = getattr(g, 'profile', {})
    if not user: return jsonify({"message": "Auth error."}),401
    if not supabase: return jsonify({"message": "Supabase client not init!"}),500
    current_text_model = get_current_ai_model(user_profile)
    if not current_text_model: return jsonify({"message":"Gemini model not initialized."}),500
    print(f">>> POST /api/v1/launches/{launch_id}/generate-tweet by user_id: {user_id}")
    try:
        launch_res = supabase.table('launches').select("*,products(name,value_proposition)").eq('id',launch_id).eq('user_id',user_id).maybe_single().execute()
        if not launch_res.data: return jsonify({"message":"Launch not found."}),404
        launch_info = launch_res.data
        strategy_res = supabase.table('education_strategies').select("*").eq('launch_id',launch_id).eq('user_id',user_id).maybe_single().execute()
        if not strategy_res.data: return jsonify({"message":"Strategy not found."}),404
        strategy_info = strategy_res.data
        db_profile_info = getattr(g, 'profile', {})
        brand_voice = db_profile_info.get('brand_voice','プロフェッショナルかつ親しみやすい')
        target_persona = db_profile_info.get('target_persona',strategy_info.get('target_customer_summary','設定なし'))
        request_data = request.json if request.is_json else {}
        purpose = request_data.get('purpose','一般的なローンチ告知ツイート')
        prompt_parts = [
            "あなたはプロのXマーケッターです。",
            f"ブランドボイス「{brand_voice}」でターゲット顧客「{target_persona}」に響くツイートを1つ提案。",
            f"ローンチ名: {launch_info.get('name','')}",
            f"商品名: {launch_info.get('products',{}).get('name','商品') if launch_info.get('products') else '商品'}",
            f"価値: {launch_info.get('products',{}).get('value_proposition',strategy_info.get('product_analysis_summary','価値あるもの')) if launch_info.get('products') else strategy_info.get('product_analysis_summary','価値あるもの')}","教育戦略:",
            f"- 目的: {strategy_info.get('edu_s1_purpose','')}", f"- 問題点: {strategy_info.get('edu_s3_problem','')}", f"- 解決策: {strategy_info.get('edu_s4_solution','')}",
            f"このツイートの目的: {purpose}", "具体的でエンゲージメントを促し140字以内で。絵文字も使用。"
        ]
        prompt="\n".join(filter(None,prompt_parts))
        print(f">>> Gemini Prompt (model: {current_text_model._model_name}):\n{prompt[:300]}...")
        ai_res=current_text_model.generate_content(prompt); tweet=""
        try: tweet=ai_res.text
        except : pass 
        if not tweet and hasattr(ai_res,'candidates') and ai_res.candidates: tweet="".join([p.text for c in ai_res.candidates for p in c.content.parts if hasattr(p,'text')])
        if not tweet and hasattr(ai_res,'prompt_feedback'): tweet=f"生成失敗: {ai_res.prompt_feedback}"
        return jsonify({"generated_tweet":tweet.strip()})
    except Exception as e: traceback.print_exc();return jsonify({"message":"Error generating tweet","error":str(e)}),500

@app.route('/api/v1/chat/education-element', methods=['POST'])
@token_required
def chat_education_element():
    user = getattr(g, 'user', None); user_id = user.id; user_profile = getattr(g, 'profile', {})
    if not user: return jsonify({"message": "Auth error."}),401
    if not supabase: return jsonify({"message": "Supabase client not init!"}),500
    data=request.json; launch_id=data.get('launch_id'); element_key=data.get('element_key'); chat_history_frontend=data.get('chat_history',[]); current_user_message_text=data.get('current_user_message')
    if not all([launch_id,element_key,current_user_message_text]):
        return jsonify({"message":"Missing params"}),400
    print(f">>> POST /api/v1/chat/education-element for L:{launch_id}, E:{element_key} by U:{user_id}")
    try:
        launch_res=supabase.table('launches').select("*,products(name,description,value_proposition,target_audience)").eq('id',launch_id).eq('user_id',user_id).maybe_single().execute()
        if not launch_res.data: return jsonify({"message":"Launch not found."}),404
        launch_info=launch_res.data
        product_info_list = launch_info.get('products', [])
        product_info = product_info_list[0] if isinstance(product_info_list, list) and len(product_info_list) > 0 else {}
        strategy_res=supabase.table('education_strategies').select("*").eq('launch_id',launch_id).eq('user_id',user_id).maybe_single().execute(); strategy_info=strategy_res.data if strategy_res.data else {}
        brand_voice=user_profile.get('brand_voice','未設定'); target_persona_profile=user_profile.get('target_persona','未設定')
        element_map={"edu_s1_purpose":"目的の教育", "edu_s2_trust":"信用の教育", "edu_s3_problem":"問題点の教育", "edu_s4_solution":"手段の教育", "edu_s5_investment":"投資の教育", "edu_s6_action":"行動の教育", "edu_r1_engagement_hook":"読む・見る教育", "edu_r2_repetition":"何度も聞く教育", "edu_r3_change_mindset":"変化の教育", "edu_r4_receptiveness":"素直の教育", "edu_r5_output_encouragement":"アウトプットの教育", "edu_r6_baseline_shift":"基準値/覚悟の教育", "product_analysis_summary":"商品分析", "target_customer_summary":"ターゲット顧客分析"}
        el_name_jp=element_map.get(element_key,element_key); current_el_memo=strategy_info.get(element_key,"")
        system_instruction_text = f"""あなたはEDSアシスタント、Xマーケティング専門家です。ユーザーが「{el_name_jp}」戦略を具体化するのを助けます。「{el_name_jp}」の目的は「{element_map.get(element_key,'目的達成')}」です。情報(ブランドボイス:{brand_voice},ターゲット顧客:{target_persona_profile},ローンチ:{launch_info.get('name','未設定')}(商品:{product_info.get('name','未設定')}),現在の「{el_name_jp}」メモ:{current_el_memo if current_el_memo else "未入力"})を参考にユーザーの思考を深める質問をし、最終的に質の高い戦略メモ完成を支援。短い質問や確認を繰り返し、ユーザーが自ら言葉にできるように。"""
        current_chat_model = get_current_ai_model(user_profile, system_instruction_text=system_instruction_text)
        if not current_chat_model: return jsonify({"message":"Gemini chat model not init with system instruction."}),500
        gemini_hist_sdk=[]
        for entry in chat_history_frontend:
            role=entry.get('role');parts_data=entry.get('parts')
            if role and parts_data and isinstance(parts_data,list) and len(parts_data)>0:
                txt_content=parts_data[0].get('text') if isinstance(parts_data[0],dict) else parts_data[0]
                if isinstance(txt_content,str): gemini_hist_sdk.append({'role':role,'parts':[{'text':txt_content}]})
        chat_session = current_chat_model.start_chat(history=gemini_hist_sdk)
        print(f">>> Sending to Gemini Chat (model: {current_chat_model._model_name}, element: {el_name_jp}, history_len: {len(gemini_hist_sdk)}): User says: {current_user_message_text[:100]}...")
        response=chat_session.send_message(current_user_message_text); ai_response_text=""
        try: ai_response_text=response.text
        except: pass
        if not ai_response_text and hasattr(response,'candidates') and response.candidates: ai_response_text="".join([p.text for c in response.candidates for p in c.content.parts if hasattr(p,'text')])
        if not ai_response_text and hasattr(response,'prompt_feedback'): ai_response_text=f"AI応答失敗: {response.prompt_feedback}"
        return jsonify({"ai_message":ai_response_text.strip()})
    except Exception as e: traceback.print_exc();return jsonify({"message":"Error processing chat","error":str(e)}),500

@app.route('/api/v1/launches/<uuid:launch_id>/strategy/generate-draft', methods=['POST'])
@token_required
def generate_strategy_draft(launch_id):
    user = getattr(g, 'user', None); user_id = user.id; user_profile = getattr(g, 'profile', {})
    if not user: return jsonify({"message": "Authentication error."}), 401
    if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
    current_text_model = get_current_ai_model(user_profile) 
    if not current_text_model: return jsonify({"message":"Gemini model not initialized."}),500
    print(f">>> POST /api/v1/launches/{launch_id}/strategy/generate-draft by user_id: {user_id}")
    try:
        launch_res = supabase.table('launches').select("*, products(*)").eq('id', launch_id).eq('user_id', user_id).maybe_single().execute()
        if not launch_res.data: return jsonify({"message": "Launch not found or access denied."}), 404
        launch_info = launch_res.data
        product_info_list = launch_info.get('products', [])
        product_info = product_info_list[0] if isinstance(product_info_list, list) and len(product_info_list) > 0 else {}
        brand_voice = user_profile.get('brand_voice', 'プロフェッショナルかつ親しみやすい'); target_persona_profile = user_profile.get('target_persona', '設定なし')
        strategy_elements_definition = [
            {'key': 'product_analysis_summary', 'name': '商品分析の要点', 'desc': 'このローンチにおける商品の強み、弱み、独自性、競合製品との比較など。'},
            {'key': 'target_customer_summary', 'name': 'ターゲット顧客分析の要点', 'desc': 'このローンチで狙う顧客層の具体的なペルソナ、悩み、欲求、価値観、情報収集方法など。'},
            {'key': 'edu_s1_purpose', 'name': '目的の教育', 'desc': '顧客がこの商品/サービスを通じて最終的に手に入れられる「理想の未来」や「究極のゴール」を鮮明に描く。'},
            {'key': 'edu_s2_trust', 'name': '信用の教育', 'desc': '発信者や商品・サービスへの信頼を構築するための要素（実績、専門性、顧客の声、理念など）。'},
            {'key': 'edu_s3_problem', 'name': '問題点の教育', 'desc': '顧客が現在抱えている、あるいはまだ気づいていない問題や課題、その深刻さを具体的に指摘する。'},
            {'key': 'edu_s4_solution', 'name': '手段の教育', 'desc': '提示した問題点を、この商品/サービスがどのように解決できるのか、その具体的な方法、優位性、独自性を示す。'},
            {'key': 'edu_s5_investment', 'name': '投資の教育', 'desc': 'この商品/サービスへの投資（金銭、時間、労力）が、将来得られるリターンと比較して合理的であることを示す。機会損失も示唆する。'},
            {'key': 'edu_s6_action', 'name': '行動の教育', 'desc': '顧客に具体的な次の行動（購入、問い合わせ、登録など）を促す。限定性、緊急性、保証などで後押しする。'},
            {'key': 'edu_r1_engagement_hook', 'name': '読む・見る教育', 'desc': '発信するコンテンツ（ツイート、記事、動画など）の冒頭で読者/視聴者を惹きつけ、続きを読む/見る価値があると思わせる工夫。'},
            {'key': 'edu_r2_repetition', 'name': '何度も聞く教育', 'desc': '重要なメッセージや教育内容を、異なる表現や媒体で繰り返し伝え、顧客の潜在意識に刷り込む戦略。'},
            {'key': 'edu_r3_change_mindset', 'name': '変化の教育', 'desc': '現状維持を望む顧客の心理的抵抗を減らし、新しい行動や考え方（変化）を受け入れることの重要性やメリットを理解させる。'},
            {'key': 'edu_r4_receptiveness', 'name': '素直の教育', 'desc': '専門家や成功者のアドバイス、実績のあるノウハウを素直に受け入れ、実践することの価値を伝える。'},
            {'key': 'edu_r5_output_encouragement', 'name': 'アウトプットの教育', 'desc': '顧客が学んだことや体験をSNSなどで発信（アウトプット）するよう促し、理解の深化、記憶の定着、UGC（ユーザー生成コンテンツ）による波及効果を狙う。'},
            {'key': 'edu_r6_baseline_shift', 'name': '基準値の教育／覚悟の教育', 'desc': '顧客の既存の常識や基準（価格観、努力量など）を意図的に揺さぶり、高額商品や困難な行動への心理的ハードルを下げる。本気の覚悟を示す。'}
        ]
        generated_drafts = {}
        for element in strategy_elements_definition:
            element_key = element['key']; element_name_jp = element['name']; element_desc = element['desc']
            prompt = f"""あなたはプロのマーケティング戦略家です。「{element_name_jp}」に関する簡潔なドラフト（箇条書き2-3点、または100字程度の説明文）を作成してください。
# 参考情報: ユーザープロファイル(ブランドボイス:{brand_voice}, ターゲット顧客:{target_persona_profile}), ローンチ情報(ローンチ名:{launch_info.get('name', 'N/A')}, 目標:{launch_info.get('goal', 'N/A')}), 商品情報(商品名:{product_info.get('name', 'N/A')}, 提供価値:{product_info.get('value_proposition', 'N/A')}), 「{element_name_jp}」の目的:{element_desc}
# 指示:「{element_name_jp}」のドラフトを生成。"""
            print(f"\n--- Generating draft for: {element_key} ---")
            try:
                ai_response = current_text_model.generate_content(prompt); draft_text = ""
                try: draft_text = ai_response.text
                except: pass
                if not draft_text and hasattr(ai_response,'candidates') and ai_response.candidates: draft_text = "".join([p.text for c in ai_response.candidates for p in c.content.parts if hasattr(p,'text')])
                if not draft_text and hasattr(ai_response,'prompt_feedback'): draft_text = f"生成失敗: {ai_response.prompt_feedback}"
                generated_drafts[element_key] = draft_text.strip()
                print(f">>> Draft for {element_key}: {draft_text.strip()[:100]}...")
            except Exception as e_gen: generated_drafts[element_key] = f"AIによる「{element_name_jp}」のドラフト生成に失敗しました: {str(e_gen)}"
        return jsonify(generated_drafts)
    except Exception as e: traceback.print_exc(); return jsonify({"message": "Error generating strategy draft", "error": str(e)}), 500

# --- ツイート管理API ---
@app.route('/api/v1/tweets', methods=['POST'])
@token_required
def save_tweet_draft():
    user = getattr(g, 'user', None); user_id = user.id
    if not user: return jsonify({"message": "Authentication error."}), 401
    data = request.json
    print(f">>> POST /api/v1/tweets (save draft) called by user_id: {user_id} with data: {data}")
    content = data.get('content')
    if not content: return jsonify({"message": "Tweet content is required."}), 400
    status = data.get('status', 'draft'); scheduled_at_str = data.get('scheduled_at')
    edu_el_key = data.get('education_element_key'); launch_id_fk = data.get('launch_id'); notes_int = data.get('notes_internal')
    scheduled_at_ts = None
    if scheduled_at_str:
        try:
            dt_obj = datetime.datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
            scheduled_at_ts = dt_obj.isoformat()
        except ValueError: return jsonify({"message": "Invalid scheduled_at format. Use ISO 8601."}), 400
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        new_tweet_data = {"user_id": user_id, "content": content, "status": status, "scheduled_at": scheduled_at_ts, "education_element_key": edu_el_key, "launch_id": launch_id_fk, "notes_internal": notes_int}
        payload_to_insert = {k: v for k, v in new_tweet_data.items() if v is not None}
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

@app.route('/api/v1/tweets', methods=['GET'])
@token_required
def get_saved_tweets():
    user = getattr(g, 'user', None); user_id = user.id
    if not user: return jsonify({"message": "Authentication error."}), 401
    status_filter = request.args.get('status')
    print(f">>> GET /api/v1/tweets called by user_id: {user_id}, status_filter: {status_filter}")
    try:
        if not supabase: return jsonify({"message": "Supabase client not initialized!"}), 500
        query = supabase.table('tweets').select("*").eq('user_id', user_id)
        if status_filter: query = query.eq('status', status_filter)
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

# Flaskサーバーの起動
if __name__ == '__main__':
    print("--- Starting Flask server on http://127.0.0.1:5001 ---")
    app.run(debug=True, host='127.0.0.1', port=5001)