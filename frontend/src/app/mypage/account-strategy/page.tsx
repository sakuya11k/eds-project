// src/app/mypage/account-strategy/page.tsx
'use client';

import React, { useEffect, useState, FormEvent, ChangeEvent, useCallback, useRef } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useXAccount } from '@/context/XAccountContext';
import XAccountGuard from '@/components/XAccountGuard';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'react-hot-toast';

// --- 型定義 ---
type TargetAudienceItem = {
  id: string; name: string; age: string; 悩み: string;
};
type BrandVoiceDetail = {
  tone: string; keywords: string[]; ng_words: string[];
};
type AccountStrategyFormData = {
  account_purpose: string; main_target_audience: TargetAudienceItem[] | null;
  core_value_proposition: string; brand_voice_detail: BrandVoiceDetail;
  main_product_summary: string;
  edu_s1_purpose_base: string; edu_s2_trust_base: string; edu_s3_problem_base: string;
  edu_s4_solution_base: string; edu_s5_investment_base: string; edu_s6_action_base: string;
  edu_r1_engagement_hook_base: string; edu_r2_repetition_base: string;
  edu_r3_change_mindset_base: string; edu_r4_receptiveness_base: string;
  edu_r5_output_encouragement_base: string; edu_r6_baseline_shift_base: string;
};

// --- 初期データと定義 ---
const initialStrategyFormData: AccountStrategyFormData = {
  account_purpose: '', main_target_audience: [{ id: Date.now().toString(), name: '', age: '', 悩み: '' }],
  core_value_proposition: '', brand_voice_detail: { tone: '', keywords: [''], ng_words: [''] },
  main_product_summary: '',
  edu_s1_purpose_base: '', edu_s2_trust_base: '', edu_s3_problem_base: '',
  edu_s4_solution_base: '', edu_s5_investment_base: '', edu_s6_action_base: '',
  edu_r1_engagement_hook_base: '', edu_r2_repetition_base: '',
  edu_r3_change_mindset_base: '', edu_r4_receptiveness_base: '',
  edu_r5_output_encouragement_base: '', edu_r6_baseline_shift_base: '',
};
const basePolicyElementsDefinition = [
    { key: 'edu_s1_purpose_base', label: '1. 目的の教育 (基本方針)', description: "アカウント全体として、顧客が目指すべき理想の未来や提供する究極的な価値観についての方針。"},
    { key: 'edu_s2_trust_base', label: '2. 信用の教育 (基本方針)', description: "アカウント全体として、発信者やブランドへの信頼をどのように構築・維持していくかの方針。"},
    { key: 'edu_s3_problem_base', label: '3. 問題点の教育 (基本方針)', description: "ターゲット顧客が抱えるであろう、アカウント全体で共通して取り上げる問題意識や課題についての方針。"},
    { key: 'edu_s4_solution_base', label: '4. 手段の教育 (基本方針)', description: "アカウントが提供する情報や商品が、顧客の問題をどのように解決するかの基本的な考え方。"},
    { key: 'edu_s5_investment_base', label: '5. 投資の教育 (基本方針)', description: "自己投資の重要性や、情報・商品への投資をどのように正当化し促すかの全体的な方針。"},
    { key: 'edu_s6_action_base', label: '6. 行動の教育 (基本方針)', description: "顧客に具体的な行動を促すための、アカウントとしての一貫したメッセージやアプローチ。"},
    { key: 'edu_r1_engagement_hook_base', label: '7. 読む・見る教育 (基本方針)', description: "コンテンツの冒頭で読者の興味を惹きつけるための、アカウント共通のテクニックや考え方。"},
    { key: 'edu_r2_repetition_base', label: '8. 何度も聞く教育 (基本方針)', description: "重要なメッセージを繰り返し伝え、記憶に定着させるためのアカウント全体でのアプローチ。"},
    { key: 'edu_r3_change_mindset_base', label: '9. 変化の教育 (基本方針)', description: "現状維持からの脱却や、新しい価値観への変化を促すための、アカウントとしての基本的なスタンス。"},
    { key: 'edu_r4_receptiveness_base', label: '10. 素直の教育 (基本方針)', description: "情報やアドバイスを素直に受け入れることの重要性をどのように伝えるかの全体方針。"},
    { key: 'edu_r5_output_encouragement_base', label: '11. アウトプットの教育 (基本方針)', description: "顧客からの発信（UGC）を促すためのアカウント全体での働きかけや仕組み作りの考え方。"},
    { key: 'edu_r6_baseline_shift_base', label: '12. 基準値/覚悟の教育 (基本方針)', description: "顧客の常識や基準値を引き上げ、行動への覚悟を促すためのアカウントとしての一貫した姿勢。"},
];

// --- ヘルパーコンポーネント: 自動高さ調整テキストエリア ---
const AutoGrowTextarea = (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => {
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [props.value]);

    return <textarea ref={textareaRef} {...props} />;
};


// --- コンポーネント本体 ---
export default function AccountStrategyPage() {
  const { user, session, loading: authLoading } = useAuth();
  const { activeXAccount, isLoading: isXAccountLoading } = useXAccount();
  const router = useRouter();

  const [formData, setFormData] = useState<AccountStrategyFormData>(initialStrategyFormData);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [aiLoadingStates, setAiLoadingStates] = useState<Record<string, boolean>>({});
  const [aiKeywords, setAiKeywords] = useState<Record<string, string>>({});
  
  const [isGeneratingAllPolicies, setIsGeneratingAllPolicies] = useState(false);
  
  const apiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    if (!session?.access_token) throw new Error("認証セッションが無効です。");
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.access_token}`, ...options.headers };
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${url}`, { ...options, headers });
    if (!response.ok) {
        let errorBody;
        try { errorBody = await response.json(); } catch (e) { throw new Error(`サーバーエラー (Status: ${response.status})`); }
        throw new Error(errorBody?.message || errorBody?.error || `APIエラー (Status: ${response.status})`);
    }
    return response.status === 204 ? null : await response.json();
  }, [session]);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    const fetchStrategy = async () => {
      if (!activeXAccount) {
        if (!isXAccountLoading) setIsLoading(false);
        return;
      }
      setIsLoading(true);
      try {
        const fetchedStrategy = await apiFetch(`/api/v1/account-strategies/${activeXAccount.id}`);
        const newFormData = { ...initialStrategyFormData };
        if (fetchedStrategy && Object.keys(fetchedStrategy).length > 0) {
             for (const key in newFormData) {
                if (fetchedStrategy[key] !== undefined && fetchedStrategy[key] !== null) {
                    if (key === 'main_target_audience' && Array.isArray(fetchedStrategy[key]) && fetchedStrategy[key].length > 0) {
                       newFormData[key] = fetchedStrategy[key].map((p: any) => ({...p, id: p.id || Date.now().toString() + Math.random()}));
                    } else if (key === 'brand_voice_detail' && typeof fetchedStrategy[key] === 'object') {
                       newFormData[key] = {
                          tone: fetchedStrategy[key].tone || '',
                          keywords: fetchedStrategy[key].keywords?.length > 0 ? fetchedStrategy[key].keywords : [''],
                          ng_words: fetchedStrategy[key].ng_words?.length > 0 ? fetchedStrategy[key].ng_words : [''],
                       };
                    } else if (key in newFormData) {
                      (newFormData as any)[key] = fetchedStrategy[key];
                    }
                }
             }
        }
        setFormData(newFormData);
      } catch (error) { toast.error(error instanceof Error ? error.message : "戦略の読み込みに失敗しました。"); } 
      finally { setIsLoading(false); }
    };
    if (!isXAccountLoading) { fetchStrategy(); }
  }, [activeXAccount, isXAccountLoading, apiFetch]);

  const handleInputChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleNestedChange = (path: string, value: any) => {
    setFormData(prev => {
      const keys = path.split('.');
      const newState = JSON.parse(JSON.stringify(prev));
      let current = newState;
      for (let i = 0; i < keys.length - 1; i++) {
        if (typeof current[keys[i]] !== 'object' || current[keys[i]] === null) current[keys[i]] = {};
        current = current[keys[i]];
      }
      current[keys[keys.length - 1]] = value;
      return newState;
    });
  };
  
  const addTargetAudience = () => handleNestedChange('main_target_audience', [...(formData.main_target_audience || []), { id: Date.now().toString(), name: '', age: '', 悩み: '' }]);
  const removeTargetAudience = (index: number) => {
    if ((formData.main_target_audience || []).length <= 1) { toast.error('最低1つのペルソナが必要です。'); return; }
    handleNestedChange('main_target_audience', (formData.main_target_audience || []).filter((_, i) => i !== index));
  };

  const addKeyword = (type: 'keywords' | 'ng_words') => {
    const currentList = formData.brand_voice_detail[type] || [];
    if (currentList.length > 0 && currentList[currentList.length - 1].trim() === '') { toast('まず空の欄を埋めてください。', { icon: 'ℹ️' }); return; }
    handleNestedChange(`brand_voice_detail.${type}`, [...currentList, '']);
  };
  const removeKeyword = (index: number, type: 'keywords' | 'ng_words') => {
    const newList = (formData.brand_voice_detail[type] || []).filter((_, i) => i !== index);
    handleNestedChange(`brand_voice_detail.${type}`, newList.length > 0 ? newList : ['']);
  };

  const handleSuggestWithAI = async (targetField: keyof AccountStrategyFormData, apiEndpoint: string) => {
    if (!activeXAccount) {
      toast.error("操作対象のXアカウントを選択してください。");
      return;
    }
    const loadingKey = `${targetField}_loading`;
    setAiLoadingStates(prev => ({ ...prev, [loadingKey]: true }));
    try {
      const payload: Record<string, any> = { 
        ...formData,
        x_account_id: activeXAccount.id 
      };

      if (targetField === 'brand_voice_detail') {
        payload.adjectives = aiKeywords[targetField] || '';
      } else {
        payload.user_keywords = aiKeywords[targetField] || '';
      }
      
      const response = await apiFetch(apiEndpoint, { method: 'POST', body: JSON.stringify(payload) });
      
      if (targetField === 'main_target_audience') {
         if (response?.suggested_personas && Array.isArray(response.suggested_personas)) {
            const newPersonas = response.suggested_personas.map((p: any) => ({
                id: Date.now().toString() + Math.random(),
                name: p.name || '',
                age: p.age || '',
                悩み: p.悩み || '',
            }));
            setFormData(prev => ({
                ...prev,
                main_target_audience: newPersonas
            }));
            toast.success(`${newPersonas.length}件のペルソナ案を反映しました。`);
        } else {
            throw new Error('AIからのペルソナ提案が期待した配列形式ではありません。');
        }
      } else if (targetField === 'brand_voice_detail') {
        if (response?.suggestion && typeof response.suggestion === 'object') {
            const { tone, keywords, ng_words } = response.suggestion;
            handleNestedChange('brand_voice_detail', {
                tone: tone || '',
                keywords: keywords?.length > 0 ? keywords : [''],
                ng_words: ng_words?.length > 0 ? ng_words : [''],
            });
            toast.success(`ブランドボイスのAI提案を反映しました。`);
        } else throw new Error('AIからのブランドボイス提案の形式が不正です。');
      } else if (response?.suggestion && typeof response.suggestion === 'string') {
        setFormData(prev => ({...prev, [targetField]: response.suggestion }));
        toast.success(`AI提案を反映しました。`);
      } else {
        throw new Error('AIからの提案の形式が不正です。');
      }

    } catch (error) { 
      toast.error(error instanceof Error ? error.message : "AI提案の取得に失敗しました。");
    } finally { 
      setAiLoadingStates(prev => ({ ...prev, [loadingKey]: false })); 
    }
  };
  
  const handleGenerateBasePolicies = async () => {
    if (!activeXAccount) {
      toast.error("操作対象のXアカウントを選択してください。");
      return;
    }
    if (!window.confirm("現在の12の基本方針がAIによる提案で上書きされます。よろしいですか？")) {
      return;
    }
    setIsGeneratingAllPolicies(true);
    try {
      const payload = {
        x_account_id: activeXAccount.id,
        account_purpose: formData.account_purpose,
        core_value_proposition: formData.core_value_proposition,
        main_product_summary: formData.main_product_summary,
        main_target_audience_summary: formData.main_target_audience
            ?.map(p => `ペルソナ「${p.name}」(${p.age}): ${p.悩み}`)
            .join('; ') || '未設定'
      };
      
      const drafts = await apiFetch('/api/v1/profile/generate-base-policies-draft', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      
      if (drafts && typeof drafts === 'object') {
        setFormData(prev => ({ ...prev, ...drafts }));
        toast.success("12の基本方針のドラフトを生成しました！");
      } else {
        throw new Error("AIからの応答が予期した形式ではありませんでした。");
      }

    } catch (error) {
      toast.error(error instanceof Error ? error.message : "基本方針の生成に失敗しました。");
    } finally {
      setIsGeneratingAllPolicies(false);
    }
  };
  
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeXAccount) { toast.error("保存対象のアカウントが選択されていません。"); return; }
    setIsSubmitting(true);
    try {
      const cleanedFormData = { ...formData,
        brand_voice_detail: { ...formData.brand_voice_detail, 
          keywords: (formData.brand_voice_detail.keywords || []).filter(kw => kw && kw.trim()), 
          ng_words: (formData.brand_voice_detail.ng_words || []).filter(kw => kw && kw.trim()) }, 
        main_target_audience: (formData.main_target_audience || []).filter(p => p && (p.name.trim() || p.悩み.trim()))
      };
      await apiFetch(`/api/v1/account-strategies/${activeXAccount.id}`, { method: 'PUT', body: JSON.stringify(cleanedFormData) });
      toast.success(`@${activeXAccount.x_username} の戦略を保存しました！`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "保存に失敗しました。");
    } finally { setIsSubmitting(false); }
  };
  
  const renderTextAreaWithAI = (name: keyof AccountStrategyFormData, label: string, description: string, apiEndpoint: string) => {
    const loadingKey = `${name}_loading`;
    return (
        <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
            <div className="flex flex-wrap justify-between items-center mb-1 gap-2">
                <label htmlFor={name} className="block text-sm font-semibold text-gray-700">{label}</label>
                <div className="flex items-center space-x-2">
                    <input type="text" value={aiKeywords[name] || ''} onChange={(e) => setAiKeywords(prev => ({...prev, [name]: e.target.value}))} placeholder="AI提案用キーワード" className="px-2 py-1 text-xs border rounded-md"/>
                    <button type="button" onClick={() => handleSuggestWithAI(name, apiEndpoint)} disabled={aiLoadingStates[loadingKey]} className="px-2 py-1 text-xs font-medium text-purple-700 bg-purple-100 rounded-full hover:bg-purple-200">
                        {aiLoadingStates[loadingKey] ? '生成中...' : 'AI提案'}
                    </button>
                </div>
            </div>
            <p className="mb-2 text-xs text-gray-400 italic">{description}</p>
            <textarea id={name} name={name} rows={4} value={String(formData[name] ?? '')} onChange={handleInputChange} className="block w-full px-3 py-2 border rounded-md shadow-sm bg-white"/>
        </div>
    );
  };
  
  if (isXAccountLoading) {
    return <div className="flex justify-center items-center h-screen"><div className="animate-spin rounded-full h-24 w-24 border-t-2 border-b-2 border-indigo-500"></div></div>;
  }

  return (
    <XAccountGuard>
      <div className="max-w-4xl mx-auto py-12 px-4">
        <div className="mb-8"><Link href="/dashboard" className="text-indigo-600 hover:underline">← ダッシュボードへ戻る</Link></div>
        <h1 className="text-4xl font-extrabold text-gray-900 mb-2">アカウント戦略設定</h1>
        {activeXAccount && <p className="text-lg text-indigo-600 font-semibold mb-10">対象アカウント: <span className="font-bold">@{activeXAccount.x_username}</span></p>}
        
        {isLoading ? (
            <div className="flex justify-center items-center h-64"><div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-indigo-500"></div></div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-16">
            <section>
              <h2 className="text-2xl font-bold text-gray-800 pb-4 mb-6 border-b">主要戦略</h2>
              <div className="space-y-6">
                {renderTextAreaWithAI('account_purpose', 'アカウントの基本理念・パーパス', 'このアカウントを通じて何を達成したいか、どのような価値を提供したいのかを記述します。', '/api/v1/profile/suggest-purpose')}
                {renderTextAreaWithAI('core_value_proposition', 'アカウントのコア提供価値', '読者が継続的に得られる最も重要な価値（ベネフィット）は何ですか？', '/api/v1/profile/suggest-value-proposition')}
                {renderTextAreaWithAI('main_product_summary', '主要商品群の分析サマリー', '提供する商品やサービス群に共通する特徴や提供価値を記述します。', '/api/v1/profile/suggest-product-summary')}
              </div>
            </section>

            <section>
              <h2 className="text-2xl font-bold text-gray-800 pb-4 mb-6 border-b">ターゲット顧客 (ペルソナ)</h2>
              <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
                <label htmlFor="personaKeywords" className="block text-sm font-semibold text-gray-700 mb-1">ペルソナ提案用キーワード</label>
                <input type="text" id="personaKeywords" value={aiKeywords['main_target_audience'] || ''} onChange={(e) => setAiKeywords(prev=>({...prev, main_target_audience: e.target.value}))} placeholder="例: 30代 主婦 副業" className="mt-1 block w-full p-2 border rounded-md mb-2"/>
                <button type="button" onClick={() => handleSuggestWithAI('main_target_audience', '/api/v1/profile/suggest-persona-draft')} disabled={aiLoadingStates['main_target_audience_loading']} className="w-full sm:w-auto px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-md shadow-sm">
                    {aiLoadingStates['main_target_audience_loading'] ? "AIがペルソナ案作成中..." : "AIにペルソナドラフトを提案させる"}
                </button>
              </div>
              {(formData.main_target_audience || []).map((audience, index) => (
                <div key={audience.id} className="p-4 border rounded-lg space-y-3 bg-slate-100 shadow-sm mb-4">
                  <div className="flex justify-between items-center"><h4 className="font-semibold text-gray-700">ペルソナ {index + 1}</h4>{(formData.main_target_audience || []).length > 1 && (<button type="button" onClick={() => removeTargetAudience(index)} className="text-red-500 hover:text-red-700 text-xs font-medium">削除</button>)}</div>
                  <div><label htmlFor={`targetName-${index}`} className="block text-xs font-medium text-gray-600">ペルソナ名</label><input type="text" id={`targetName-${index}`} value={audience.name} onChange={(e) => handleNestedChange(`main_target_audience.${index}.name`, e.target.value)} required className="mt-1 block w-full p-2 border rounded-md"/></div>
                  <div><label htmlFor={`targetAge-${index}`} className="block text-xs font-medium text-gray-600">年齢層/属性</label><input type="text" id={`targetAge-${index}`} value={audience.age} onChange={(e) => handleNestedChange(`main_target_audience.${index}.age`, e.target.value)} className="mt-1 block w-full p-2 border rounded-md"/></div>
                  <div>
                    <label htmlFor={`targetProblem-${index}`} className="block text-xs font-medium text-gray-600">悩み/課題</label>
                    <AutoGrowTextarea 
                      id={`targetProblem-${index}`} 
                      value={audience.悩み} 
                      onChange={(e) => handleNestedChange(`main_target_audience.${index}.悩み`, e.target.value)} 
                      required 
                      rows={3}
                      className="mt-1 block w-full p-2 border rounded-md resize-none overflow-hidden"
                    />
                  </div>
                </div>
              ))}
              <button type="button" onClick={addTargetAudience} className="mt-1 w-full sm:w-auto px-4 py-2 border border-dashed rounded-md text-indigo-700 hover:bg-indigo-50">+ ペルソナを追加</button>
            </section>

            <section>
              <h2 className="text-2xl font-bold text-gray-800 pb-4 mb-6 border-b">ブランドボイス</h2>
              <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
                <label htmlFor="brandVoiceKeywords" className="block text-sm font-semibold text-gray-700 mb-1">ブランドボイス提案用キーワード（形容詞など）</label>
                <input type="text" id="brandVoiceKeywords" value={aiKeywords['brand_voice_detail'] || ''} onChange={(e) => setAiKeywords(prev=>({...prev, brand_voice_detail: e.target.value}))} placeholder="例: 親しみやすい, 専門的, 熱血" className="mt-1 block w-full p-2 border rounded-md mb-2"/>
                <button type="button" onClick={() => handleSuggestWithAI('brand_voice_detail', '/api/v1/profile/suggest-brand-voice')} disabled={aiLoadingStates['brand_voice_detail_loading']} className="w-full sm:w-auto px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-md shadow-sm">
                    {aiLoadingStates['brand_voice_detail_loading'] ? "AIが提案作成中..." : "AIにブランドボイスを提案させる"}
                </button>
              </div>
              <div className="p-4 border rounded-lg bg-slate-100 space-y-4">
                <div>
                  <label htmlFor="brandVoiceTone" className="block text-sm font-semibold text-gray-700 mb-1">基本トーン</label>
                  <input type="text" id="brandVoiceTone" value={formData.brand_voice_detail.tone} onChange={(e) => handleNestedChange('brand_voice_detail.tone', e.target.value)} required className="mt-1 block w-full p-2 border rounded-md"/>
                </div>
                {(['keywords', 'ng_words'] as const).map(type => (
                  <div key={type}>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">{type === 'keywords' ? 'よく使うキーワード' : '避けるべきNGワード'}</label>
                    {(formData.brand_voice_detail[type] || []).map((kw, index) => (
                      <div key={index} className="flex items-center space-x-2 mb-2">
                        <input type="text" value={kw} onChange={(e) => handleNestedChange(`brand_voice_detail.${type}.${index}`, e.target.value)} className="flex-grow p-2 border rounded-md"/>
                        <button type="button" onClick={() => removeKeyword(index, type)} className="text-red-500 hover:text-red-700 p-1">削除</button>
                      </div>
                    ))}
                    <button type="button" onClick={() => addKeyword(type)} className="mt-1 text-sm text-indigo-600 hover:underline">+ {type === 'keywords' ? 'キーワードを追加' : 'NGワードを追加'}</button>
                  </div>
                ))}
              </div>
            </section>
            
            <section>
              <div className="flex justify-between items-center pb-4 mb-6 border-b">
                  <h2 className="text-2xl font-bold text-gray-800">12の教育要素 - 基本方針</h2>
                  <button type="button" onClick={handleGenerateBasePolicies} disabled={isGeneratingAllPolicies} className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md shadow-sm">
                      {isGeneratingAllPolicies ? "AIがドラフト生成中..." : "12方針をAIで一括生成"}
                  </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {basePolicyElementsDefinition.map(el => (
                  <div key={el.key}>
                    <label className="text-lg font-semibold text-gray-700">{el.label}</label>
                    <p className="text-xs text-gray-500 mt-1 mb-2">{el.description}</p>
                    <textarea name={el.key} rows={5} value={String(formData[el.key as keyof AccountStrategyFormData] ?? '')} onChange={handleInputChange} className="w-full mt-1 p-3 border rounded-md"/>
                  </div>
                ))}
              </div>
            </section>

            <div className="pt-8"><button type="submit" disabled={isSubmitting} className="w-full py-4 px-6 bg-indigo-600 text-white font-bold rounded-lg shadow-lg hover:bg-indigo-700 disabled:opacity-50">{isSubmitting ? '保存中...' : `@${activeXAccount?.x_username} の戦略を保存する`}</button></div>
          </form>
        )}
      </div>
    </XAccountGuard>
  );
}