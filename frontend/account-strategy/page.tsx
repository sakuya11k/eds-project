// src/app/mypage/account-strategy/page.tsx

'use client';

import React, { useEffect, useState, FormEvent, ChangeEvent } from 'react';
import { useAuth } from '@/context/AuthContext'; //
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import { supabase } from '@/lib/supabaseClient'; //
import { toast } from 'react-hot-toast'; //

// --- 型定義 ---
export type TargetAudienceItem = {
  id?: string;
  name: string;
  age: string;
  悩み: string;
};

export type BrandVoiceDetail = {
  tone: string;
  keywords: string[];
  ng_words: string[];
};

export type AccountStrategyFormData = {
  username: string;
  website: string;
  preferred_ai_model: string;
  x_api_key: string;
  x_api_secret_key: string;
  x_access_token: string;
  x_access_token_secret: string;

  account_purpose: string;
  main_target_audience: TargetAudienceItem[] | null; // ★ 修正点1: null を許容
  core_value_proposition: string;
  brand_voice_detail: BrandVoiceDetail;
  main_product_summary: string;

  edu_s1_purpose_base: string;
  edu_s2_trust_base: string;
  edu_s3_problem_base: string;
  edu_s4_solution_base: string;
  edu_s5_investment_base: string;
  edu_s6_action_base: string;
  edu_r1_engagement_hook_base: string;
  edu_r2_repetition_base: string;
  edu_r3_change_mindset_base: string;
  edu_r4_receptiveness_base: string;
  edu_r5_output_encouragement_base: string;
  edu_r6_baseline_shift_base: string;
};

export const initialAccountStrategyFormData: AccountStrategyFormData = {
  username: '',
  website: '',
  preferred_ai_model: 'gemini-1.5-flash-latest',
  x_api_key: '',
  x_api_secret_key: '',
  x_access_token: '',
  x_access_token_secret: '',
  account_purpose: '',
  main_target_audience: [{ id: Date.now().toString(), name: '', age: '', 悩み: '' }],
  core_value_proposition: '',
  brand_voice_detail: { tone: '', keywords: [''], ng_words: [''] },
  main_product_summary: '',
  edu_s1_purpose_base: '',
  edu_s2_trust_base: '',
  edu_s3_problem_base: '',
  edu_s4_solution_base: '',
  edu_s5_investment_base: '',
  edu_s6_action_base: '',
  edu_r1_engagement_hook_base: '',
  edu_r2_repetition_base: '',
  edu_r3_change_mindset_base: '',
  edu_r4_receptiveness_base: '',
  edu_r5_output_encouragement_base: '',
  edu_r6_baseline_shift_base: '',
};

const aiModelOptions = [
  { value: 'gemini-1.5-flash-latest', label: 'Gemini 1.5 Flash (高速・標準)' },
  { value: 'gemini-1.5-pro-latest', label: 'Gemini 1.5 Pro (高性能・高品質)' },
];
// --- 型定義ここまで ---


export default function AccountStrategyPage() {
  const { user, loading: authLoading, signOut } = useAuth();
  const router = useRouter();

  const [formData, setFormData] = useState<AccountStrategyFormData>(initialAccountStrategyFormData);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    const fetchProfileData = async () => {
      if (user && !authLoading) {
        setIsLoadingData(true);
        setApiError(null);
        try {
          const { data: { session } } = await supabase.auth.getSession();
          if (!session) throw new Error("セッションが見つかりません。再度ログインしてください。");

          const response = await axios.get(
            'http://localhost:5001/api/v1/profile',
            { headers: { Authorization: `Bearer ${session.access_token}` } }
          );
          const fetchedProfile: Partial<AccountStrategyFormData> & { id?: string; updated_at?: string } = response.data;
          
          setFormData(prev => ({ // prev はここでは使わないので initial... のみでOK
            ...initialAccountStrategyFormData,
            username: fetchedProfile.username || '',
            website: fetchedProfile.website || '',
            preferred_ai_model: fetchedProfile.preferred_ai_model || initialAccountStrategyFormData.preferred_ai_model,
            x_api_key: fetchedProfile.x_api_key || '',
            x_api_secret_key: fetchedProfile.x_api_secret_key || '',
            x_access_token: fetchedProfile.x_access_token || '',
            x_access_token_secret: fetchedProfile.x_access_token_secret || '',
            account_purpose: fetchedProfile.account_purpose || '',
            main_target_audience: fetchedProfile.main_target_audience && fetchedProfile.main_target_audience.length > 0
                ? fetchedProfile.main_target_audience.map(p => ({...p, id: p.id || Date.now().toString() + Math.random() }))
                : initialAccountStrategyFormData.main_target_audience, // null の場合も初期値
            core_value_proposition: fetchedProfile.core_value_proposition || '',
            brand_voice_detail: fetchedProfile.brand_voice_detail
                ? {
                    tone: fetchedProfile.brand_voice_detail.tone || '',
                    keywords: fetchedProfile.brand_voice_detail.keywords && fetchedProfile.brand_voice_detail.keywords.length > 0 ? fetchedProfile.brand_voice_detail.keywords : [''],
                    ng_words: fetchedProfile.brand_voice_detail.ng_words && fetchedProfile.brand_voice_detail.ng_words.length > 0 ? fetchedProfile.brand_voice_detail.ng_words : [''],
                  }
                : initialAccountStrategyFormData.brand_voice_detail,
            main_product_summary: fetchedProfile.main_product_summary || '',
            edu_s1_purpose_base: fetchedProfile.edu_s1_purpose_base || '',
            edu_s2_trust_base: fetchedProfile.edu_s2_trust_base || '',
            edu_s3_problem_base: fetchedProfile.edu_s3_problem_base || '',
            edu_s4_solution_base: fetchedProfile.edu_s4_solution_base || '',
            edu_s5_investment_base: fetchedProfile.edu_s5_investment_base || '',
            edu_s6_action_base: fetchedProfile.edu_s6_action_base || '',
            edu_r1_engagement_hook_base: fetchedProfile.edu_r1_engagement_hook_base || '',
            edu_r2_repetition_base: fetchedProfile.edu_r2_repetition_base || '',
            edu_r3_change_mindset_base: fetchedProfile.edu_r3_change_mindset_base || '',
            edu_r4_receptiveness_base: fetchedProfile.edu_r4_receptiveness_base || '',
            edu_r5_output_encouragement_base: fetchedProfile.edu_r5_output_encouragement_base || '',
            edu_r6_baseline_shift_base: fetchedProfile.edu_r6_baseline_shift_base || '',
          }));
        } catch (error: unknown) { //
          console.error('プロファイル取得エラー (AccountStrategyPage):', error); //
          let errorMessage = 'アカウント戦略の読み込みに失敗しました。'; //
          if (axios.isAxiosError(error) && error.response) { //
               errorMessage = error.response.data?.message || error.message || errorMessage; //
               if (error.response.status === 401 && signOut) { //
                    await signOut(); //
                    router.push('/login'); //
               } else if (error.response.status === 404) { //
                    // ★ 修正点2: toast.info を toast に変更
                    toast("プロフィールデータがまだありません。新規作成してください。"); //
                    setFormData(initialAccountStrategyFormData); //
               }
          } else if (error instanceof Error) { //
               errorMessage = error.message; //
          }
          setApiError(errorMessage); //
          if (!(axios.isAxiosError(error) && error.response?.status === 404)) { //
            toast.error(errorMessage); //
          }
        } finally { //
          setIsLoadingData(false); //
        }
      }
    }; //
    fetchProfileData(); //
  }, [user, authLoading, router, signOut]); //


  const handleInputChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleBrandVoiceDetailChange = <K extends keyof BrandVoiceDetail>(
    key: K,
    value: BrandVoiceDetail[K]
  ) => {
    setFormData(prev => ({
      ...prev,
      brand_voice_detail: {
        ...prev.brand_voice_detail,
        [key]: value,
      },
    }));
  };
  
  const handleKeywordChange = (index: number, value: string, type: 'keywords' | 'ng_words') => {
      const currentList = [...formData.brand_voice_detail[type]];
      currentList[index] = value;
      handleBrandVoiceDetailChange(type, currentList);
  };

  const addKeyword = (type: 'keywords' | 'ng_words') => {
      const currentList = formData.brand_voice_detail[type];
      if (currentList.length === 0 || (currentList.length > 0 && currentList[currentList.length -1].trim() !== '')) {
        handleBrandVoiceDetailChange(type, [...currentList, '']);
      } else {
        toast('まず空の欄を埋めてください。', { icon: 'ℹ️' }); // アイコン付きの通常toast
      }
  };

  const removeKeyword = (index: number, type: 'keywords' | 'ng_words') => {
      const currentList = [...formData.brand_voice_detail[type]];
      currentList.splice(index, 1);
      handleBrandVoiceDetailChange(type, currentList.length > 0 ? currentList : ['']);
  };


  const handleTargetAudienceChange = (index: number, field: keyof Omit<TargetAudienceItem, 'id'>, value: string) => {
    const updatedAudiences = formData.main_target_audience 
        ? formData.main_target_audience.map((item, i) =>
            i === index ? { ...item, [field]: value } : item
          )
        : [];
    setFormData(prev => ({ ...prev, main_target_audience: updatedAudiences }));
  };

  const addTargetAudience = () => {
    setFormData(prev => ({
      ...prev,
      main_target_audience: [
        ...(prev.main_target_audience || []), // 既存がnullの場合も考慮
        { id: Date.now().toString(), name: '', age: '', 悩み: '' }
      ],
    }));
  };

  const removeTargetAudience = (index: number) => {
    if (!formData.main_target_audience || formData.main_target_audience.length <= 1) {
        toast.error('最低1つのペルソナが必要です。');
        return;
    }
    const updatedAudiences = formData.main_target_audience.filter((_, i) => i !== index);
    setFormData(prev => ({ ...prev, main_target_audience: updatedAudiences }));
  };


  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!user) {
      toast.error('認証されていません。');
      return;
    }
    if (!formData.username.trim()) {
        toast.error('ユーザー名は必須です。');
        return;
    }
    if (!formData.account_purpose.trim()) {
        toast.error('アカウントの目的は必須です。');
        return;
    }

    setIsSubmitting(true);
    setApiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションが見つかりません。");

      const payloadToSubmit: Partial<AccountStrategyFormData> = {
        ...formData,
        brand_voice_detail: {
            ...formData.brand_voice_detail,
            keywords: formData.brand_voice_detail.keywords.filter(kw => kw.trim() !== ''),
            ng_words: formData.brand_voice_detail.ng_words.filter(kw => kw.trim() !== ''),
        },
        main_target_audience: formData.main_target_audience //
            ? formData.main_target_audience.filter( //
                p => p.name.trim() !== '' || p.age.trim() !== '' || p.悩み.trim() !== '' //
              ) //
            : null, //
      };
      
      // ★ 修正点3: main_target_audience がフィルタリングの結果、空配列になったら null を設定
      if (payloadToSubmit.main_target_audience?.length === 0) { //
        payloadToSubmit.main_target_audience = null; //
      } //

      await axios.put( //
        'http://localhost:5001/api/v1/profile',  //
        payloadToSubmit, //
        { headers: { Authorization: `Bearer ${session.access_token}` } } //
      ); //
      toast.success('アカウント戦略を保存しました！'); //
      // TODO: AuthContextのprofileを更新する (例: 再フェッチやレスポンスで) //
    } catch (error: unknown) { //
      console.error('アカウント戦略保存エラー:', error); //
      let errorMessage = 'アカウント戦略の保存に失敗しました。'; //
      if (axios.isAxiosError(error) && error.response) { //
           errorMessage = error.response.data?.message || error.message || errorMessage; //
      } else if (error instanceof Error) { //
           errorMessage = error.message; //
      }
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading || isLoadingData) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="ml-4 text-lg text-gray-600">読み込み中...</p>
      </div>
    );
  }

  if (!user) {
    return (
        <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
            <p className="text-lg text-gray-600">ログインページへリダイレクトします...</p>
        </div>
    );
  }
  
  const renderTextArea = (
    name: keyof AccountStrategyFormData, 
    label: string, 
    rows: number = 3, 
    placeholder?: string,
    description?: string
  ) => (
    <div>
        <label htmlFor={name} className="block text-sm font-semibold text-gray-700 mb-1">{label}</label>
        <textarea
            id={name}
            name={name}
            rows={rows}
            value={String(formData[name] ?? '')} 
            onChange={handleInputChange}
            placeholder={placeholder}
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm leading-relaxed"
        />
        {description && <p className="mt-2 text-xs text-gray-500">{description}</p>}
    </div>
  );

  const sectionTitleClass = "text-xl font-semibold text-gray-800 pb-3 mb-6 border-b border-gray-300";
  const fieldSetClass = "space-y-6";


  return (
    <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="mb-6">
        <Link href="/dashboard" className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center group">
          <svg className="w-5 h-5 mr-2 text-indigo-500 group-hover:text-indigo-700" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd"></path></svg>
          ダッシュボードへ戻る
        </Link>
      </div>
      <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-10 tracking-tight">
        アカウント戦略設定
      </h1>
      
      {apiError && (
        <div className="mb-6 bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded-md" role="alert">
          <p className="font-bold">エラー</p>
          <p>{apiError}</p>
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="space-y-12 bg-white p-6 sm:p-8 md:p-10 shadow-xl rounded-xl border border-gray-200">
        
        <section>
            <h2 className={sectionTitleClass}>アカウント基本情報</h2>
            <div className={fieldSetClass}>
                <div>
                    <label htmlFor="username" className="block text-sm font-semibold text-gray-700 mb-1">ユーザー名 *</label>
                    <input type="text" name="username" id="username" value={formData.username} onChange={handleInputChange} required className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
                </div>
                {renderTextArea('account_purpose' as keyof AccountStrategyFormData, 'アカウントの基本理念・パーパス *', 3, "このアカウントを通じて何を達成したいか", "例: X運用に悩む個人起業家が、再現性のある方法で収益化を達成し、時間と場所に縛られない自由な働き方を手に入れるための実践的ノウハウを提供する。")}
                {renderTextArea('core_value_proposition' as keyof AccountStrategyFormData, 'アカウントのコア提供価値 *', 3, "あなたの発信をフォローすることで、読者が継続的に得られる最も重要な価値（ベネフィット）は何ですか？", "例: 最新のAIツール活用法と具体的なマネタイズ戦略を、初心者にも分かりやすく解説し、実践的なスキルアップを支援する。")}
            </div>
        </section>

        <section>
            <h2 className={sectionTitleClass}>ターゲット顧客 (ペルソナ)</h2>
            <div className={fieldSetClass}>
            {formData.main_target_audience && formData.main_target_audience.map((audience, index) => ( // formData.main_target_audience が null でないことを確認
                <div key={audience.id || index} className="p-4 border rounded-lg space-y-3 bg-slate-50 shadow-sm">
                <h4 className="font-semibold text-gray-700 flex justify-between items-center">
                    <span>ペルソナ {index + 1}</span>
                    {formData.main_target_audience && formData.main_target_audience.length > 1 && (
                        <button type="button" onClick={() => removeTargetAudience(index)} className="text-red-500 hover:text-red-700 text-xs font-medium px-2 py-1 rounded hover:bg-red-50 transition-colors">削除</button>
                    )}
                </h4>
                <div>
                    <label htmlFor={`targetName-${index}`} className="block text-xs font-medium text-gray-600 mb-0.5">ペルソナ名 / 呼び名 *</label>
                    <input type="text" id={`targetName-${index}`} value={audience.name} onChange={(e) => handleTargetAudienceChange(index, 'name', e.target.value)} required className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="例: 30代前半の副業ママ"/>
                </div>
                <div>
                    <label htmlFor={`targetAge-${index}`} className="block text-xs font-medium text-gray-600 mb-0.5">年齢層 / 属性</label>
                    <input type="text" id={`targetAge-${index}`} value={audience.age} onChange={(e) => handleTargetAudienceChange(index, 'age', e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="例: 30代、会社員、子育て中など"/>
                </div>
                <div>
                    <label htmlFor={`targetProblem-${index}`} className="block text-xs font-medium text-gray-600 mb-0.5">主な悩み / 欲求 / 課題 *</label>
                    <textarea id={`targetProblem-${index}`} value={audience.悩み} onChange={(e) => handleTargetAudienceChange(index, '悩み', e.target.value)} required rows={3} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="例: 時間がない中で効率的に収益を上げたい。専門知識はないが新しいことに挑戦したい。"/>
                </div>
                </div>
            ))}
            <button type="button" onClick={addTargetAudience} className="mt-3 w-full sm:w-auto px-4 py-2 border border-dashed border-indigo-400 text-sm font-medium rounded-md text-indigo-700 hover:bg-indigo-50 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500">
                + ペルソナを追加する
            </button>
            </div>
        </section>

        <section>
            <h2 className={sectionTitleClass}>ブランドボイス詳細</h2>
            <div className={fieldSetClass}>
                <div>
                    <label htmlFor="brandVoiceTone" className="block text-sm font-semibold text-gray-700 mb-1">基本トーン *</label>
                    <input type="text" id="brandVoiceTone" value={formData.brand_voice_detail.tone} onChange={(e) => handleBrandVoiceDetailChange('tone', e.target.value)} required className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" placeholder="例: 専門的だが親しみやすい、論理的で冷静、情熱的で励ますなど"/>
                </div>
                {(['keywords', 'ng_words'] as const).map(type => (
                    <div key={type}>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            {type === 'keywords' ? 'よく使うキーワード / フレーズ' : '避けるべきキーワード / フレーズ (NGワード)'}
                        </label>
                        {formData.brand_voice_detail[type].map((kw, index) => (
                            <div key={`${type}-${index}`} className="flex items-center space-x-2 mb-2">
                                <input type="text" value={kw} onChange={(e) => handleKeywordChange(index, e.target.value, type)} placeholder={type === 'keywords' ? "例: 再現性、時短、AI活用" : "例: 絶対儲かる、楽して稼ぐ"} className="flex-grow px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"/>
                                <button type="button" onClick={() => removeKeyword(index, type)} className="text-red-500 hover:text-red-700 p-1 rounded-full hover:bg-red-100 transition-colors" aria-label={type === 'keywords' ? "キーワード削除" : "NGワード削除"}>
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9a1 1 0 000 2h6a1 1 0 100-2H7z" clipRule="evenodd" /></svg>
                                </button>
                            </div>
                        ))}
                        <button type="button" onClick={() => addKeyword(type)} className="mt-1 text-sm text-indigo-600 hover:text-indigo-800 font-medium flex items-center">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z" clipRule="evenodd" /></svg>
                            {type === 'keywords' ? 'キーワードを追加' : 'NGワードを追加'}
                        </button>
                    </div>
                ))}
            </div>
        </section>

        <section>
            <h2 className={sectionTitleClass}>主要商品・サービス</h2>
            <div className={fieldSetClass}>
                {renderTextArea('main_product_summary' as keyof AccountStrategyFormData, '主要商品群の分析サマリー', 4, "提供する主な商品やサービス群に共通する特徴、顧客への提供価値、市場でのポジショニングなど、アカウント戦略の基盤となる商品情報を記述してください。")}
            </div>
        </section>
        
        <section>
            <h2 className={sectionTitleClass}>12の教育要素 - アカウント基本方針</h2>
            <div className={`${fieldSetClass} grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6`}>
                <p className="text-sm text-gray-600 md:col-span-2">各教育要素について、あなたのアカウント全体としての基本的な考え方やアプローチ、メッセージの方向性を記述してください。これが各ローンチ戦略の土台となります。</p>
                {renderTextArea('edu_s1_purpose_base' as keyof AccountStrategyFormData, '1. 目的の教育 (基本方針)', 4)}
                {renderTextArea('edu_s2_trust_base' as keyof AccountStrategyFormData, '2. 信用の教育 (基本方針)', 4)}
                {renderTextArea('edu_s3_problem_base' as keyof AccountStrategyFormData, '3. 問題点の教育 (基本方針)', 4)}
                {renderTextArea('edu_s4_solution_base' as keyof AccountStrategyFormData, '4. 手段の教育 (基本方針)', 4)}
                {renderTextArea('edu_s5_investment_base' as keyof AccountStrategyFormData, '5. 投資の教育 (基本方針)', 4)}
                {renderTextArea('edu_s6_action_base' as keyof AccountStrategyFormData, '6. 行動の教育 (基本方針)', 4)}
                {renderTextArea('edu_r1_engagement_hook_base' as keyof AccountStrategyFormData, '7. 読む・見る教育 (基本方針)', 4)}
                {renderTextArea('edu_r2_repetition_base' as keyof AccountStrategyFormData, '8. 何度も聞く教育 (基本方針)', 4)}
                {renderTextArea('edu_r3_change_mindset_base' as keyof AccountStrategyFormData, '9. 変化の教育 (基本方針)', 4)}
                {renderTextArea('edu_r4_receptiveness_base' as keyof AccountStrategyFormData, '10. 素直の教育 (基本方針)', 4)}
                {renderTextArea('edu_r5_output_encouragement_base' as keyof AccountStrategyFormData, '11. アウトプットの教育 (基本方針)', 4)}
                {renderTextArea('edu_r6_baseline_shift_base' as keyof AccountStrategyFormData, '12. 基準値/覚悟の教育 (基本方針)', 4)}
            </div>
        </section>

        <section>
            <h2 className={sectionTitleClass}>システム・API連携設定</h2>
            <div className={fieldSetClass}>
                <div>
                    <label htmlFor="website" className="block text-sm font-semibold text-gray-700 mb-1">ウェブサイト/主要SNSリンク</label>
                    <input type="url" name="website" id="website" value={formData.website} onChange={handleInputChange} placeholder="https://example.com や https://x.com/your_id など" className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"/>
                </div>
                <div>
                  <label htmlFor="preferred_ai_model" className="block text-sm font-semibold text-gray-700 mb-1">優先AIモデル</label>
                  <select id="preferred_ai_model" name="preferred_ai_model" value={formData.preferred_ai_model} onChange={handleInputChange} className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white appearance-none">
                    {aiModelOptions.map(option => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-3 pt-2">
                    <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider">X (旧Twitter) API 連携情報</h3>
                    <div>
                        <label htmlFor="x_api_key" className="block text-xs font-medium text-gray-600">API Key (Consumer Key)</label>
                        <input type="password" name="x_api_key" id="x_api_key" value={formData.x_api_key} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" autoComplete="new-password" placeholder="入力してください"/>
                    </div>
                    <div>
                        <label htmlFor="x_api_secret_key" className="block text-xs font-medium text-gray-600">API Key Secret</label>
                        <input type="password" name="x_api_secret_key" id="x_api_secret_key" value={formData.x_api_secret_key} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" autoComplete="new-password" placeholder="入力してください"/>
                    </div>
                    <div>
                        <label htmlFor="x_access_token" className="block text-xs font-medium text-gray-600">Access Token</label>
                        <input type="password" name="x_access_token" id="x_access_token" value={formData.x_access_token} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" autoComplete="new-password" placeholder="入力してください"/>
                    </div>
                    <div>
                        <label htmlFor="x_access_token_secret" className="block text-xs font-medium text-gray-600">Access Token Secret</label>
                        <input type="password" name="x_access_token_secret" id="x_access_token_secret" value={formData.x_access_token_secret} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" autoComplete="new-password" placeholder="入力してください"/>
                    </div>
                </div>
            </div>
        </section>

        <div className="pt-8">
          <button
            type="submit"
            disabled={isSubmitting || isLoadingData}
            className="w-full flex justify-center items-center py-3 px-6 border border-transparent rounded-lg shadow-lg text-lg font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 transition-all duration-150 ease-in-out transform hover:scale-105"
          >
            {isSubmitting ? (
                <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                保存中...
                </>
            ) : (
                'アカウント戦略を保存する'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}