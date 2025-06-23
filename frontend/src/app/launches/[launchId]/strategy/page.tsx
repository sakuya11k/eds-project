
'use client'

import React, { useEffect, useState, FormEvent, ChangeEvent, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useXAccount } from '@/context/XAccountContext';
import XAccountGuard from '@/components/XAccountGuard';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'react-hot-toast';

// --- 型定義  ---
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
type StrategyFormData = {
  product_analysis_summary: string;
  target_customer_summary: string;
  edu_s1_purpose: string;
  edu_s2_trust: string;
  edu_s3_problem: string;
  edu_s4_solution: string;
  edu_s5_investment: string;
  edu_s6_action: string;
  edu_r1_engagement_hook: string;
  edu_r2_repetition: string;
  edu_r3_change_mindset: string;
  edu_r4_receptiveness: string;
  edu_r5_output_encouragement: string;
  edu_r6_baseline_shift: string;
};
const initialStrategyFormData: StrategyFormData = {
  product_analysis_summary: '', target_customer_summary: '', edu_s1_purpose: '',
  edu_s2_trust: '', edu_s3_problem: '', edu_s4_solution: '', edu_s5_investment: '',
  edu_s6_action: '', edu_r1_engagement_hook: '', edu_r2_repetition: '',
  edu_r3_change_mindset: '', edu_r4_receptiveness: '', edu_r5_output_encouragement: '',
  edu_r6_baseline_shift: '',
};
type AccountStrategyBases = {
  account_purpose?: string | null; main_target_audience?: TargetAudienceItem[] | null;
  core_value_proposition?: string | null; brand_voice_detail?: BrandVoiceDetail | null;
  main_product_summary?: string | null; edu_s1_purpose_base?: string | null;
  edu_s2_trust_base?: string | null; edu_s3_problem_base?: string | null;
  edu_s4_solution_base?: string | null; edu_s5_investment_base?: string | null;
  edu_s6_action_base?: string | null; edu_r1_engagement_hook_base?: string | null;
  edu_r2_repetition_base?: string | null; edu_r3_change_mindset_base?: string | null;
  edu_r4_receptiveness_base?: string | null; edu_r5_output_encouragement_base?: string | null;
  edu_r6_baseline_shift_base?: string | null;
};
type ChatMessage = { role: 'user' | 'model'; parts: { text: string }[]; };
type LaunchStrategyApiResponse = {
    launch_info: { id: string, name: string, product_name: string, x_account_id: string, x_username: string };
    launch_strategy: Partial<StrategyFormData>;
    account_strategy: AccountStrategyBases;
};
type EducationElementField = { key: keyof StrategyFormData; baseKey?: keyof AccountStrategyBases; label: string; placeholder: string; type?: undefined; };
type EducationElementSeparator = { type: 'separator'; label: string; key?: undefined; };
type EducationElementDefinitionItem = EducationElementField | EducationElementSeparator;

export default function StrategyEditPage() {
  const { user, session, loading: authLoading } = useAuth();
  const { activeXAccount, isLoading: isXAccountLoading } = useXAccount();
  const router = useRouter();
  const params = useParams();
  const launchId = params.launchId as string;

  const [launchName, setLaunchName] = useState<string>('');
  const [formData, setFormData] = useState<StrategyFormData>(initialStrategyFormData);
  const [accountBases, setAccountBases] = useState<AccountStrategyBases | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmittingStrategy, setIsSubmittingStrategy] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [generatedTweet, setGeneratedTweet] = useState<string | null>(null);
  const [isGeneratingTweet, setIsGeneratingTweet] = useState(false);
  const [tweetPurpose, setTweetPurpose] = useState<string>('このローンチと商品に関する汎用的な告知ツイート');
  const [aiError, setAiError] = useState<string | null>(null);
  const [isChatModalOpen, setIsChatModalOpen] = useState(false);
  const [chatTargetElementKey, setChatTargetElementKey] = useState<keyof StrategyFormData | null>(null);
  const [chatTargetElementLabel, setChatTargetElementLabel] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentUserChatMessage, setCurrentUserChatMessage] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isGeneratingBulkDraft, setIsGeneratingBulkDraft] = useState(false);
  const [isSavingTweet, setIsSavingTweet] = useState(false);

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
    const fetchData = async () => {
      if (!user || !launchId || !activeXAccount) {
        if (!isXAccountLoading) setIsLoading(false);
        return;
      }
      setIsLoading(true); setApiError(null); setAiError(null);
      try {
        const apiResponse: LaunchStrategyApiResponse = await apiFetch(`/api/v1/launches/${launchId}/strategy`);
        const { launch_info, launch_strategy, account_strategy } = apiResponse;

        if (!launch_info || launch_info.x_account_id !== activeXAccount.id) {
          toast.error("指定されたローンチが見つからないか、アクセス権がありません。");
          router.push('/launches');
          return;
        }

        setLaunchName(launch_info.name);
        setAccountBases(account_strategy);
        
        const newFormDataState = { ...initialStrategyFormData };
        // 基本方針を適用
        if (account_strategy) {
          (Object.keys(initialStrategyFormData) as Array<keyof StrategyFormData>).forEach(key => {
            let actualBaseKey: keyof AccountStrategyBases | undefined;
            if (key === 'product_analysis_summary') actualBaseKey = 'main_product_summary';
            else if (key === 'target_customer_summary') actualBaseKey = 'main_target_audience';
            else actualBaseKey = `${key}_base` as keyof AccountStrategyBases;

            if (actualBaseKey && account_strategy[actualBaseKey]) {
                const baseValue = account_strategy[actualBaseKey];
                if (typeof baseValue === 'string') { newFormDataState[key] = baseValue; }
            }
          });
        }
        // ローンチ固有戦略で上書き
        if (launch_strategy) { Object.assign(newFormDataState, launch_strategy); }
        setFormData(newFormDataState);

      } catch (err) {
        const fetchErrMessage = err instanceof Error ? err.message : '戦略データの取得に失敗しました。';
        setApiError(fetchErrMessage); toast.error(fetchErrMessage);
        router.push('/launches');
      } finally { 
        setIsLoading(false); 
      }
    };
    if (user && !isXAccountLoading) fetchData();
  }, [user, launchId, activeXAccount, isXAccountLoading, router, apiFetch]);

  const handleStrategyInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name in initialStrategyFormData) {
      setFormData(prev => ({ ...prev, [name as keyof StrategyFormData]: value }));
    }
  };

  const handleStrategySubmit = async (e: FormEvent) => {
    e.preventDefault(); 
    if (!user || !launchId) { toast.error('ユーザー情報またはローンチIDが不足しています。'); return; }
    setIsSubmittingStrategy(true); setApiError(null);
    try {
      await apiFetch(`/api/v1/launches/${launchId}/strategy`, { method: 'PUT', body: JSON.stringify(formData) });
      toast.success('教育戦略を保存しました！');
    } catch (err) {
        const saveErrMessage = err instanceof Error ? err.message : '戦略の保存に失敗しました。';
        setApiError(saveErrMessage); toast.error(saveErrMessage);
    } finally { setIsSubmittingStrategy(false); }
  };

  const handleGenerateTweet = async () => {
    if (!user || !launchId || !activeXAccount) { toast.error('情報不足'); return; }
    setIsGeneratingTweet(true); setGeneratedTweet(null); setAiError(null);
    try {
      const res = await apiFetch(`/api/v1/launches/${launchId}/generate-tweet`, {
        method: 'POST',
        body: JSON.stringify({ purpose: tweetPurpose, x_account_id: activeXAccount.id })
      });
      if (res?.generated_tweet) { setGeneratedTweet(res.generated_tweet); toast.success('AIツイート案生成！'); }
      else { throw new Error(res?.message || 'AIからの応答が不正です。'); }
    } catch (err) { 
        const genTweetErrMessage = err instanceof Error ? err.message : 'AIツイート生成失敗';
        setAiError(genTweetErrMessage); toast.error(genTweetErrMessage);
    } finally { setIsGeneratingTweet(false); }
  };

  const openChatModal = (elementKey: keyof StrategyFormData, elementLabel: string) => {
    setChatTargetElementKey(elementKey); setChatTargetElementLabel(elementLabel);
    const currentMemo = formData[elementKey];
    setChatHistory([{ role: 'user', parts: [{text: `「${elementLabel}」について、現在このように考えています...\n${currentMemo}` }] }]);
    setCurrentUserChatMessage(''); setIsChatModalOpen(true);
  };

  const handleSendChatMessage = async () => {
    if (!currentUserChatMessage.trim() || !chatTargetElementKey || !launchId || !activeXAccount) return;
    const newMessage: ChatMessage = { role: 'user', parts: [{ text: currentUserChatMessage.trim() }] };
    setChatHistory(prev => [...prev, newMessage]); setCurrentUserChatMessage(''); setIsChatLoading(true);
    try {
      const payload = { launch_id: launchId, x_account_id: activeXAccount.id, element_key: chatTargetElementKey, chat_history: chatHistory.slice(1), current_user_message: newMessage.parts[0].text, launch_context: formData, account_context: accountBases };
      const response = await apiFetch('/api/v1/chat/education-element', { method: 'POST', body: JSON.stringify(payload) });
      if (response?.ai_message) { setChatHistory(prev => [...prev, { role: 'model', parts: [{ text: response.ai_message }] }]); } 
      else { throw new Error('AIからの応答がありません。'); }
    } catch (err) {
      const chatApiErrMessage = err instanceof Error ? err.message : "AIとの通信に失敗しました。";
      toast.error(chatApiErrMessage); setChatHistory(prev => [...prev, {role: 'model', parts: [{text: `エラー: ${chatApiErrMessage}`}]}]);
    } finally { setIsChatLoading(false); }
  };

  const applyChatResultToForm = () => {
    if (chatTargetElementKey) {
      const lastAiMessage = chatHistory.filter(m => m.role === 'model').pop()?.parts[0]?.text;
      if (lastAiMessage) { setFormData(prev => ({...prev, [chatTargetElementKey]: lastAiMessage})); toast.success(`「${chatTargetElementLabel}」にAIの提案を反映しました。`); }
    }
    setIsChatModalOpen(false);
  };

  const handleGenerateBulkDraft = async () => {
    if (!user || !launchId || !activeXAccount) { toast.error('情報不足です。'); return; }
    if (!window.confirm("AIに全戦略要素のドラフトを作成させますか？現在のフォーム内容は上書きされます。")) return;
    setIsGeneratingBulkDraft(true); setApiError(null);
    try {
      const response = await apiFetch(`/api/v1/launches/${launchId}/strategy/generate-draft`, { method: 'POST', body: JSON.stringify({ x_account_id: activeXAccount.id }) });
      if (response && typeof response === 'object') {
        setFormData(prev => ({...prev, ...response}));
        toast.success('AIによる戦略ドラフトを反映しました。');
      } else { throw new Error('AIドラフトの応答が期待した形式ではありません。'); }
    } catch (err) { 
        const bulkDraftErrMessage = err instanceof Error ? err.message : '戦略ドラフトの一括生成に失敗しました。';
        setApiError(bulkDraftErrMessage); toast.error(bulkDraftErrMessage);
    } finally { setIsGeneratingBulkDraft(false); }
  };

  const handleSaveTweetDraft = async () => {
    if (!generatedTweet || !user || !launchId || !activeXAccount) { toast.error('情報が不足しています。'); return; }
    setIsSavingTweet(true); setApiError(null);
    try {
      await apiFetch('/api/v1/tweets', { method: 'POST', body: JSON.stringify({ content: generatedTweet, status: 'draft', launch_id: launchId, x_account_id: activeXAccount.id }) });
      toast.success('ツイートを下書きとして保存しました！'); setGeneratedTweet(null); 
    } catch (err) { 
        const saveTweetErrMessage = err instanceof Error ? err.message : 'ツイートの下書き保存に失敗しました。';
        setApiError(saveTweetErrMessage); toast.error(saveTweetErrMessage);
    } finally { setIsSavingTweet(false); }
  };

  const educationElementsDefinition: EducationElementDefinitionItem[] = [
    { key: 'product_analysis_summary', baseKey: 'main_product_summary', label: '商品分析の要点 (このローンチ向け)', placeholder: '例: このローンチにおける商品の強み、弱み、ユニークな特徴、競合との比較など' },
    { key: 'target_customer_summary', baseKey: 'main_target_audience', label: 'ターゲット顧客分析の要点 (このローンチ向け)', placeholder: '例: このローンチで狙う顧客層、具体的なペルソナ、悩み、欲求、価値観など' },
    { type: 'separator', label: 'A. 6つの必須教育 (このローンチでの具体的な訴求)' },
    { key: 'edu_s1_purpose', baseKey: 'edu_s1_purpose_base', label: '1. 目的の教育', placeholder: '顧客が目指すべき理想の未来、このローンチ/商品で何が得られるか' },
    { key: 'edu_s2_trust', baseKey: 'edu_s2_trust_base', label: '2. 信用の教育', placeholder: '発信者や商品への信頼をどう構築するか (実績、理念、お客様の声など)' },
    { key: 'edu_s3_problem', baseKey: 'edu_s3_problem_base', label: '3. 問題点の教育', placeholder: '顧客が抱える問題の本質、まだ気づいていない課題の指摘' },
    { key: 'edu_s4_solution', baseKey: 'edu_s4_solution_base', label: '4. 手段の教育', placeholder: '商品がどう問題を解決するか、その優位性、他との違い' },
    { key: 'edu_s5_investment', baseKey: 'edu_s5_investment_base', label: '5. 投資の教育', placeholder: '商品への投資をどう正当化するか、機会損失の提示' },
    { key: 'edu_s6_action', baseKey: 'edu_s6_action_base', label: '6. 行動の教育', placeholder: '顧客に具体的な行動を促すメッセージ、先延ばし防止策' },
    { type: 'separator', label: 'B. 6つの強化教育 (このローンチでの具体的な訴求)' },
    { key: 'edu_r1_engagement_hook', baseKey: 'edu_r1_engagement_hook_base', label: '7. 読む・見る教育', placeholder: 'コンテンツの冒頭でどう惹きつけるか、続きを読む/見るメリット' },
    { key: 'edu_r2_repetition', baseKey: 'edu_r2_repetition_base', label: '8. 何度も聞く教育', placeholder: '重要なメッセージをどう繰り返し伝え、刷り込むか' },
    { key: 'edu_r3_change_mindset', baseKey: 'edu_r3_change_mindset_base', label: '9. 変化の教育', placeholder: '現状維持のリスク、変化への抵抗感をどう克服させるか' },
    { key: 'edu_r4_receptiveness', baseKey: 'edu_r4_receptiveness_base', label: '10. 素直の教育', placeholder: '成功者の教えやノウハウを素直に受け入れることの重要性をどう伝えるか' },
    { key: 'edu_r5_output_encouragement', baseKey: 'edu_r5_output_encouragement_base', label: '11. アウトプットの教育', placeholder: '顧客からの発信(UGC)をどう促すか、そのメリット' },
    { key: 'edu_r6_baseline_shift', baseKey: 'edu_r6_baseline_shift_base', label: '12. 基準値の教育／覚悟の教育', placeholder: '顧客の常識や基準値をどう変えるか、行動への覚悟をどう促すか' },
  ];

  const renderTextAreaWithBase = (field: EducationElementDefinitionItem) => {
    if (field.type === 'separator') {
      return (<React.Fragment key={field.label}><hr className="my-8 border-t-2 border-indigo-100" /><h2 className="text-lg sm:text-xl font-semibold text-indigo-700 mt-6 mb-4 -translate-y-3">{field.label}</h2></React.Fragment>);
    }
    const { key: fieldKey, label, placeholder, baseKey } = field;
    let basePolicyText: string | null = null;
    if (accountBases && baseKey && (accountBases as any)[baseKey]) { basePolicyText = String((accountBases as any)[baseKey]); }

    return (
        <div key={fieldKey} className="mb-6 p-4 border rounded-lg shadow-sm bg-slate-50">
            <div className="flex justify-between items-center mb-2">
                <label htmlFor={fieldKey} className="block text-sm sm:text-base font-semibold text-gray-800">{label}</label>
                <button type="button" onClick={() => openChatModal(fieldKey, label)} className="px-3 py-1 text-xs font-medium text-indigo-700 bg-indigo-100 rounded-full hover:bg-indigo-200" disabled={isSubmittingStrategy}>AIと相談</button>
            </div>
            {basePolicyText && (<div className="mb-3 p-3 bg-indigo-50 border rounded-md text-xs text-indigo-700"><p className="font-semibold">関連するアカウント基本方針:</p><p className="whitespace-pre-wrap">{basePolicyText}</p></div>)}
            <textarea
    name={fieldKey}
    id={fieldKey}
    rows={7}
    value={formData[fieldKey] || ''} 
    onChange={handleStrategyInputChange}
    placeholder={placeholder}
    className="mt-1 block w-full p-3 border rounded-md"
/>
        </div>
    );
  };
  
  return (
    <XAccountGuard>
      <div className="max-w-4xl mx-auto py-10 px-4">
        <div className="mb-8"><Link href="/launches" className="text-indigo-600 hover:underline">← ローンチ計画一覧へ戻る</Link></div>
        <h1 className="text-4xl font-extrabold text-gray-900 mb-2">教育戦略編集</h1>
        {launchName && activeXAccount && <p className="text-lg text-gray-600 mb-10">対象: <span className="font-semibold text-indigo-600">@{activeXAccount.x_username}</span> / <span className="font-semibold text-indigo-600">{launchName}</span></p>}
        
        {(isLoading || isXAccountLoading) ? ( <div className="text-center py-20">データを読み込んでいます...</div> ) : (
          <>
            <div className="mb-10"><button onClick={handleGenerateBulkDraft} disabled={isGeneratingBulkDraft} className="w-full py-3 bg-teal-600 text-white font-bold rounded-lg hover:bg-teal-700 disabled:opacity-50">{isGeneratingBulkDraft ? 'AIがドラフト作成中...' : 'AIに全戦略要素のドラフトを一括作成させる'}</button></div>
            <form onSubmit={handleStrategySubmit} className="space-y-2 mb-16">
              {educationElementsDefinition.map(field => renderTextAreaWithBase(field))}
              <div className="pt-6"><button type="submit" disabled={isSubmittingStrategy} className="w-full py-3 bg-indigo-600 text-white font-bold rounded-lg hover:bg-indigo-700 disabled:opacity-50">{isSubmittingStrategy ? '保存中...' : 'このローンチの教育戦略を保存'}</button></div>
            </form>
            <div className="bg-white p-8 shadow-2xl rounded-2xl border">
              <h2 className="text-2xl font-bold text-gray-800 mb-6">AIツイート生成</h2>
              <div className="mb-4"><label htmlFor="tweetPurpose" className="block text-sm font-semibold text-gray-700 mb-1">ツイートの目的・テーマ:</label><input type="text" id="tweetPurpose" value={tweetPurpose} onChange={(e) => setTweetPurpose(e.target.value)} className="mt-1 block w-full p-2 border rounded-md"/></div>
              <button onClick={() => handleGenerateTweet()} disabled={isGeneratingTweet} className="w-full py-3 bg-green-600 text-white font-bold rounded-lg hover:bg-green-700 disabled:opacity-50">{isGeneratingTweet ? '生成中...' : 'AIでツイート案を生成'}</button>
              {isGeneratingTweet && <div className="mt-4 text-center">AIが考案中です...</div>}
              {aiError && <div className="mt-4 text-red-500">{aiError}</div>}
              {generatedTweet && (<div className="mt-6 p-4 border rounded bg-gray-50"><h3 className="font-semibold mb-2">AIが生成したツイート案:</h3><textarea readOnly value={generatedTweet} rows={6} className="w-full p-2 border rounded bg-white"/><div className="mt-4 flex justify-end"><button onClick={handleSaveTweetDraft} disabled={isSavingTweet} className="px-6 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-700 disabled:opacity-50">{isSavingTweet ? '保存中...' : '下書き保存'}</button></div></div>)}
            </div>
          </>
        )}
      </div>
      {isChatModalOpen && (<div className="fixed inset-0 bg-gray-800 bg-opacity-75 flex items-center justify-center z-50 p-4"><div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col"><div className="flex justify-between items-center p-5 border-b"><h3 className="text-lg font-semibold">{chatTargetElementLabel}</h3><button onClick={() => setIsChatModalOpen(false)}>×</button></div><div className="p-6 space-y-4 overflow-y-auto flex-grow">{chatHistory.map((msg, index) => ( <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : ''}`}><div className={`max-w-lg px-4 py-2 rounded-lg ${ msg.role === 'user' ? 'bg-indigo-500 text-white' : 'bg-gray-200' }`}><p className="whitespace-pre-wrap">{msg.parts.map(p => p.text).join('')}</p></div></div> ))}{isChatLoading && <p>AIが応答中...</p>}</div><div className="p-4 border-t"><div className="flex space-x-2"><textarea value={currentUserChatMessage} onChange={(e) => setCurrentUserChatMessage(e.target.value)} placeholder="AIへのメッセージを入力" rows={2} className="flex-grow p-2 border rounded-md" disabled={isChatLoading} /><button onClick={handleSendChatMessage} disabled={isChatLoading || !currentUserChatMessage.trim()} className="px-4 py-2 bg-indigo-600 text-white rounded-md disabled:opacity-50">送信</button></div><div className="mt-3 flex justify-end"><button onClick={applyChatResultToForm} className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700">フォームに反映</button></div></div></div></div>)}
    </XAccountGuard>
  );
}