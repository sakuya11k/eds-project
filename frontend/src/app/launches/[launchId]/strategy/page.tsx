'use client'

import React, { useEffect, useState, FormEvent } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient'
import { toast } from 'react-hot-toast'

// 型定義
type Launch = {
  id: string;
  name: string;
  product_name?: string;
}

type EducationStrategy = {
  id?: string;
  launch_id: string;
  user_id?: string;
  product_analysis_summary?: string | null;
  target_customer_summary?: string | null;
  edu_s1_purpose?: string | null;
  edu_s2_trust?: string | null;
  edu_s3_problem?: string | null;
  edu_s4_solution?: string | null;
  edu_s5_investment?: string | null;
  edu_s6_action?: string | null;
  edu_r1_engagement_hook?: string | null;
  edu_r2_repetition?: string | null;
  edu_r3_change_mindset?: string | null;
  edu_r4_receptiveness?: string | null;
  edu_r5_output_encouragement?: string | null;
  edu_r6_baseline_shift?: string | null;
  created_at?: string;
  updated_at?: string;
}

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
}

const initialStrategyFormData: StrategyFormData = {
  product_analysis_summary: '',
  target_customer_summary: '',
  edu_s1_purpose: '',
  edu_s2_trust: '',
  edu_s3_problem: '',
  edu_s4_solution: '',
  edu_s5_investment: '',
  edu_s6_action: '',
  edu_r1_engagement_hook: '',
  edu_r2_repetition: '',
  edu_r3_change_mindset: '',
  edu_r4_receptiveness: '',
  edu_r5_output_encouragement: '',
  edu_r6_baseline_shift: '',
}

type ChatMessage = {
  role: 'user' | 'model'
  parts: { text: string }[]
}

export default function StrategyEditPage() {
  const { user, loading: authLoading, signOut } = useAuth()
  const router = useRouter()
  const params = useParams()
  const launchId = params.launchId as string

  const [launchName, setLaunchName] = useState<string>('')
  const [formData, setFormData] = useState<StrategyFormData>(initialStrategyFormData)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmittingStrategy, setIsSubmittingStrategy] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const [generatedTweet, setGeneratedTweet] = useState<string | null>(null)
  const [isGeneratingTweet, setIsGeneratingTweet] = useState(false)
  const [tweetPurpose, setTweetPurpose] = useState<string>('このローンチと商品に関する汎用的な告知ツイート')
  const [aiError, setAiError] = useState<string | null>(null);

  const [isChatModalOpen, setIsChatModalOpen] = useState(false)
  const [chatTargetElementKey, setChatTargetElementKey] = useState<keyof StrategyFormData | null>(null)
  const [chatTargetElementLabel, setChatTargetElementLabel] = useState<string>('')
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [currentUserChatMessage, setCurrentUserChatMessage] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)

  const [isGeneratingBulkDraft, setIsGeneratingBulkDraft] = useState(false)
  const [isSavingTweet, setIsSavingTweet] = useState(false)


  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  useEffect(() => {
    const fetchData = async () => {
      if (!user || authLoading || !launchId) return;
      setIsLoading(true); setApiError(null); setAiError(null);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("セッションが見つかりません。");
        const token = session.access_token;
        try {
            const launchResponse = await axios.get(`http://localhost:5001/api/v1/launches`, { headers: { Authorization: `Bearer ${token}` } });
            const currentLaunch = launchResponse.data.find((l: Launch) => l.id === launchId);
            if (currentLaunch) setLaunchName(currentLaunch.name);
            else { toast.error("指定ローンチ計画が見つかりません。"); router.push('/launches'); return; }
        } catch (e:any) { 
            const LerrorMessage = e.response?.data?.message||e.message||"ローンチ情報取得失敗。";
            setApiError(LerrorMessage); toast.error(LerrorMessage); router.push('/launches'); return;
        }
        const strategyResponse = await axios.get(`http://localhost:5001/api/v1/launches/${launchId}/strategy`,{ headers: { Authorization: `Bearer ${token}` } });
        const d = strategyResponse.data;
        if (d && d.launch_id) {
            setFormData({
              product_analysis_summary: d.product_analysis_summary || '', target_customer_summary: d.target_customer_summary || '',
              edu_s1_purpose: d.edu_s1_purpose || '', edu_s2_trust: d.edu_s2_trust || '', edu_s3_problem: d.edu_s3_problem || '',
              edu_s4_solution: d.edu_s4_solution || '', edu_s5_investment: d.edu_s5_investment || '', edu_s6_action: d.edu_s6_action || '',
              edu_r1_engagement_hook: d.edu_r1_engagement_hook || '', edu_r2_repetition: d.edu_r2_repetition || '',
              edu_r3_change_mindset: d.edu_r3_change_mindset || '', edu_r4_receptiveness: d.edu_r4_receptiveness || '',
              edu_r5_output_encouragement: d.edu_r5_output_encouragement || '', edu_r6_baseline_shift: d.edu_r6_baseline_shift || '',
            });
        } else { setFormData(initialStrategyFormData); }
      } catch (err: any) {
        if (err.response?.status !== 404) { 
            const fetchErrMessage = err.response?.data?.message || err.message || '戦略データ取得失敗。';
            setApiError(fetchErrMessage); toast.error(fetchErrMessage); 
        } else { 
            console.log("教育戦略データ(404): 新規作成モードです。");
            setFormData(initialStrategyFormData); 
        }
      } finally { setIsLoading(false); }
    };
    if (user && !authLoading && launchId) fetchData();
  }, [user, authLoading, launchId, router, signOut]);


  const handleStrategyInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const { name, value } = e.target; setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleStrategySubmit = async (e: FormEvent) => {
    e.preventDefault(); if (!user || !launchId) { toast.error('情報不足'); return; }
    setIsSubmittingStrategy(true); setApiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションなし");
      await axios.put(`http://localhost:5001/api/v1/launches/${launchId}/strategy`, formData, { headers: { Authorization: `Bearer ${session.access_token}` } });
      toast.success('教育戦略を保存！');
    } catch (err:any) { 
        const saveErrMessage = err.response?.data?.message||err.message||'戦略保存失敗';
        setApiError(saveErrMessage); toast.error(saveErrMessage);
    }
    finally { setIsSubmittingStrategy(false); }
  };

  const handleGenerateTweet = async () => {
    if (!user || !launchId) { toast.error('情報不足'); return; }
    // MODIFIED: 型安全なチェック
    const hasContent = Object.values(formData).some(value => typeof value === 'string' && value.trim() !== '');
    if (!hasContent) { if(!window.confirm("戦略未入力。AIは一般的内容を生成しますが良いですか？")) return; }
    setIsGeneratingTweet(true); setGeneratedTweet(null); setAiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションなし");
      const payload = { purpose: tweetPurpose };
      const res = await axios.post(`http://localhost:5001/api/v1/launches/${launchId}/generate-tweet`, payload, { headers: { Authorization: `Bearer ${session.access_token}` } });
      if (res.data?.generated_tweet) { setGeneratedTweet(res.data.generated_tweet); toast.success('AIツイート案生成！');}
      else { throw new Error(res.data.message || 'AI応答不正'); }
    } catch (err:any) { 
        const genTweetErrMessage = err.response?.data?.message||err.message||'AIツイート生成失敗';
        setAiError(genTweetErrMessage); toast.error(genTweetErrMessage);
    }
    finally { setIsGeneratingTweet(false); }
  };

  const openChatModal = (elementKey: keyof StrategyFormData, elementLabel: string) => {
    setChatTargetElementKey(elementKey); setChatTargetElementLabel(elementLabel);
    const currentMemo = formData[elementKey];
    setChatHistory(currentMemo ? [{ role: 'user', parts: [{text: `「${elementLabel}」について、現在このように考えています。\n\n${currentMemo}\n\nこれを深掘りするのを手伝ってください。`}]}] : []);
    setCurrentUserChatMessage(''); setIsChatModalOpen(true);
  };

  const handleSendChatMessage = async () => {
    if (!currentUserChatMessage.trim() || !chatTargetElementKey || !launchId) return;
    const newMessage: ChatMessage = { role: 'user', parts: [{ text: currentUserChatMessage.trim() }] };
    const updatedChatHistory = [...chatHistory, newMessage];
    setChatHistory(updatedChatHistory); setCurrentUserChatMessage(''); setIsChatLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションが見つかりません。");
      const payload = { launch_id: launchId, element_key: chatTargetElementKey, chat_history: updatedChatHistory.slice(0, -1), current_user_message: newMessage.parts[0].text };
      const response = await axios.post('http://localhost:5001/api/v1/chat/education-element', payload, { headers: { Authorization: `Bearer ${session.access_token}` } });
      if (response.data?.ai_message) { setChatHistory(prev => [...prev, { role: 'model', parts: [{ text: response.data.ai_message }] }]); }
      else { throw new Error('AIからの応答がありません。'); }
    } catch (err: any) {
      const chatApiErrMessage = err.response?.data?.message || err.message || "AIとの通信に失敗しました。";
      toast.error(chatApiErrMessage); setChatHistory(prev => [...prev, {role: 'model', parts: [{text: `エラー: ${chatApiErrMessage}`}]}]);
    } finally { setIsChatLoading(false); }
  };
  
  const applyChatResultToForm = () => {
    if (chatTargetElementKey) {
      const lastAiMessage = chatHistory.filter(m => m.role === 'model').pop()?.parts[0]?.text;
      if (lastAiMessage) { setFormData(prev => ({...prev, [chatTargetElementKey]: lastAiMessage})); toast.success(`「${chatTargetElementLabel}」にAIの提案を反映しました。`);}
    }
    setIsChatModalOpen(false);
  };

  const handleGenerateBulkDraft = async () => {
    if (!user || !launchId) { toast.error('情報不足'); return; }
    if (!window.confirm("AIに全戦略ドラフトを作成させますか？フォーム内容は上書きされます。")) return;
    setIsGeneratingBulkDraft(true); setApiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションなし");
      const response = await axios.post(`http://localhost:5001/api/v1/launches/${launchId}/strategy/generate-draft`, {}, { headers: { Authorization: `Bearer ${session.access_token}` } });
      
      if (response.data) {
        const newFormDataPayload: Partial<StrategyFormData> = {};
        // initialStrategyFormData のキーを基準にして、response.data から値を取得
        for (const key of Object.keys(initialStrategyFormData) as Array<keyof StrategyFormData>) {
            if (response.data[key] !== undefined && response.data[key] !== null) {
                newFormDataPayload[key] = String(response.data[key]); // 文字列に変換
            } else {
                newFormDataPayload[key] = ''; // 存在しないかnullなら空文字
            }
        }
        setFormData(newFormDataPayload as StrategyFormData);
        toast.success('AI戦略ドラフトをフォームにセット！確認・編集してください。');
      } else { throw new Error('AIドラフト応答が空。'); }
    } catch (err:any) { 
        const bulkDraftErrMessage = err.response?.data?.message||err.message||'戦略ドラフト一括生成失敗';
        setApiError(bulkDraftErrMessage); toast.error(bulkDraftErrMessage);
    }
    finally { setIsGeneratingBulkDraft(false); }
  };

  const handleSaveTweetDraft = async () => {
    if (!generatedTweet) { toast.error('保存ツイートなし'); return; }
    if (!user || !launchId) { toast.error('情報不足'); return; }
    setIsSavingTweet(true);
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("セッションなし");
        const payload = { content: generatedTweet, status: 'draft', launch_id: launchId, education_element_key: tweetPurpose };
        await axios.post('http://localhost:5001/api/v1/tweets', payload, { headers: { Authorization: `Bearer ${session.access_token}` } });
        toast.success('ツイートを下書き保存！'); setGeneratedTweet(null);
    } catch (err: any) {
        const saveTweetErrMessage = err.response?.data?.message || err.message || 'ツイート保存失敗';
        toast.error(saveTweetErrMessage);
    } finally { setIsSavingTweet(false); }
  };

  if (authLoading || isLoading) { 
    return ( <div className="flex justify-center items-center min-h-screen"> <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div> <p className="ml-4 text-lg text-gray-600">読み込み中...</p> </div> );
  }
  if (!user) { 
    return ( <div className="flex justify-center items-center min-h-screen"> <p className="text-lg text-gray-600">ログインページへリダイレクトします...</p> </div> );
  }

  const educationElementsDefinition = [
    { key: 'product_analysis_summary', label: '商品分析の要点', placeholder: '例: このローンチにおける商品の強み、弱み、ユニークな特徴、競合との比較など' },
    { key: 'target_customer_summary', label: 'ターゲット顧客分析の要点', placeholder: '例: このローンチで狙う顧客層、具体的なペルソナ、悩み、欲求、価値観など' },
    { type: 'separator', label: 'A. 6つの必須教育' },
    { key: 'edu_s1_purpose', label: '1. 目的の教育', placeholder: '顧客が目指すべき理想の未来、このローンチ/商品で何が得られるか' },
    { key: 'edu_s2_trust', label: '2. 信用の教育', placeholder: '発信者や商品への信頼をどう構築するか (実績、理念、お客様の声など)' },
    { key: 'edu_s3_problem', label: '3. 問題点の教育', placeholder: '顧客が抱える問題の本質、まだ気づいていない課題の指摘' },
    { key: 'edu_s4_solution', label: '4. 手段の教育', placeholder: '商品がどう問題を解決するか、その優位性、他との違い' },
    { key: 'edu_s5_investment', label: '5. 投資の教育', placeholder: '商品への投資をどう正当化するか、機会損失の提示' },
    { key: 'edu_s6_action', label: '6. 行動の教育', placeholder: '顧客に具体的な行動を促すメッセージ、先延ばし防止策' },
    { type: 'separator', label: 'B. 6つの強化教育' },
    { key: 'edu_r1_engagement_hook', label: '7. 読む・見る教育', placeholder: 'コンテンツの冒頭でどう惹きつけるか、続きを読む/見るメリット' },
    { key: 'edu_r2_repetition', label: '8. 何度も聞く教育', placeholder: '重要なメッセージをどう繰り返し伝え、刷り込むか' },
    { key: 'edu_r3_change_mindset', label: '9. 変化の教育', placeholder: '現状維持のリスク、変化への抵抗感をどう克服させるか' },
    { key: 'edu_r4_receptiveness', label: '10. 素直の教育', placeholder: '成功者の教えやノウハウを素直に受け入れることの重要性をどう伝えるか' },
    { key: 'edu_r5_output_encouragement', label: '11. アウトプットの教育', placeholder: '顧客からの発信(UGC)をどう促すか、そのメリット' },
    { key: 'edu_r6_baseline_shift', label: '12. 基準値の教育／覚悟の教育', placeholder: '顧客の常識や基準値をどう変えるか、行動への覚悟をどう促すか' },
  ];

  return (
    <div className="max-w-4xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="mb-8">
        <Link href="/launches" className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center group">
          <svg className="w-5 h-5 mr-2 text-indigo-500 group-hover:text-indigo-700" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd"></path></svg>
          ローンチ計画一覧へ戻る
        </Link>
      </div>
      <h1 className="text-4xl font-extrabold text-gray-900 mb-3 tracking-tight">教育戦略編集</h1>
      {launchName && <p className="text-xl text-gray-700 mb-6">ローンチ計画: <span className="font-semibold text-indigo-600">{launchName}</span></p>}
      
      <div className="mb-10">
        <button
            onClick={handleGenerateBulkDraft}
            disabled={isGeneratingBulkDraft || isSubmittingStrategy || isGeneratingTweet || isChatLoading}
            className="w-full flex justify-center items-center py-3 px-6 border border-transparent rounded-lg shadow-md text-lg font-medium text-white bg-teal-600 hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500 disabled:opacity-60 transition duration-150 ease-in-out"
        >
            <svg className="w-5 h-5 mr-2 animate-pulse" fill="currentColor" viewBox="0 0 20 20"><path d="M10 3.5a1.5 1.5 0 011.303 2.253l.005.008a12.003 12.003 0 000 8.478l-.005.008A1.5 1.5 0 0110 16.5a1.5 1.5 0 01-1.303-2.253l-.005-.008a12.003 12.003 0 000-8.478l.005-.008A1.5 1.5 0 0110 3.5zM6.5 10a1.5 1.5 0 012.253-1.303l.008-.005a12.003 12.003 0 008.478 0l.008.005A1.5 1.5 0 0119.5 10a1.5 1.5 0 01-2.253 1.303l-.008.005a12.003 12.003 0 00-8.478 0l-.008-.005A1.5 1.5 0 016.5 10z"></path></svg>
            {isGeneratingBulkDraft ? 'AIが全要素のドラフトを作成中...' : 'AIに全戦略要素のドラフトを一括作成させる'}
        </button>
        {apiError && ( 
            <div className="mt-4 bg-red-50 p-3 rounded-md border border-red-200">
                <p className="text-sm font-medium text-red-700">{apiError}</p>
            </div>
        )}
      </div>

      <form onSubmit={handleStrategySubmit} className="space-y-10 bg-white p-8 sm:p-10 shadow-2xl rounded-2xl border border-gray-200 mb-16">
        {educationElementsDefinition.map(field => {
          if (field.type === 'separator') {
            return ( 
              <React.Fragment key={field.label}> {/* React.Fragment を使用 */}
                <hr className="my-6 border-t-2 border-indigo-100" /> 
                <h2 className="text-xl font-semibold text-indigo-700 mt-6 mb-4 -translate-y-3">
                  {field.label}
                </h2>
              </React.Fragment>
            );
          }
          return (
            <div key={field.key}>
              <div className="flex justify-between items-center mb-2">
                <label htmlFor={field.key} className="block text-base sm:text-lg font-semibold text-gray-800">
                  {field.label}
                </label>
                <button 
                  type="button" 
                  onClick={() => openChatModal(field.key as keyof StrategyFormData, field.label)} 
                  className="px-3 py-1 text-xs font-medium text-indigo-700 bg-indigo-100 rounded-full hover:bg-indigo-200 transition" 
                  title={`${field.label} についてAIと相談する`} 
                  disabled={isGeneratingBulkDraft || isSubmittingStrategy || isGeneratingTweet || isChatLoading}
                >
                  AIと相談
                </button>
              </div>
              <textarea
                name={field.key}
                id={field.key}
                rows={6}
                value={formData[field.key as keyof StrategyFormData]}
                onChange={handleStrategyInputChange}
                placeholder={field.placeholder}
                className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm leading-relaxed"
              />
            </div>
          )
        })}
        <div className="pt-2">
          <button 
            type="submit" 
            disabled={isSubmittingStrategy || isGeneratingBulkDraft || isGeneratingTweet} 
            className="w-full flex justify-center py-3 px-6 border border-transparent rounded-lg shadow-md text-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition duration-150 ease-in-out"
          >
            {isSubmittingStrategy ? '保存中...' : '教育戦略を保存する'}
          </button>
        </div>
      </form>

      <div className="bg-white p-8 sm:p-10 shadow-2xl rounded-2xl border border-gray-200">
        <h2 className="text-2xl sm:text-3xl font-bold text-gray-800 mb-8">AIツイート生成</h2>
        <div className="mb-6">
            <label htmlFor="tweetPurpose" className="block text-sm font-semibold text-gray-700 mb-2">ツイートの目的・テーマ（AIへの指示）:</label>
            <input type="text" id="tweetPurpose" name="tweetPurpose" value={tweetPurpose} onChange={(e) => setTweetPurpose(e.target.value)} placeholder="例: 商品の緊急性を伝えるツイート" className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"/>
        </div>
        <button onClick={handleGenerateTweet} disabled={isGeneratingTweet || isSubmittingStrategy || isGeneratingBulkDraft} className="w-full flex justify-center py-3 px-6 border border-transparent rounded-lg shadow-md text-lg font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-60 transition duration-150 ease-in-out">
          {isGeneratingTweet ? 'ツイート生成中...' : 'AIでツイート案を生成する'}
        </button>
        {isGeneratingTweet && ( <div className="mt-8 flex flex-col justify-center items-center text-center"> <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-green-500 mb-3"></div> <p className="text-gray-600">AIが最適なツイートを考案中です...</p> </div> )}
        {aiError && !isGeneratingTweet && ( <div className="mt-6 bg-red-50 p-4 rounded-lg border border-red-200"><p className="text-sm font-medium text-red-700">{aiError}</p></div>)}
        {generatedTweet && !isGeneratingTweet && (
          <div className="mt-8 p-6 border rounded-lg bg-gray-50">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">AIが生成したツイート案:</h3>
            <textarea readOnly value={generatedTweet} rows={6} className="w-full p-3 border border-gray-300 rounded-md bg-white text-gray-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" onClick={(e) => (e.target as HTMLTextAreaElement).select()} />
            <div className="mt-4 flex justify-end">
                <button onClick={handleSaveTweetDraft} disabled={isSavingTweet} className="px-6 py-2 bg-sky-600 text-white font-semibold rounded-lg shadow-md hover:bg-sky-700 transition duration-300 disabled:opacity-50">
                    {isSavingTweet ? '保存中...' : '下書きとして保存'}
                </button>
            </div>
          </div>
        )}
      </div>

      {/* チャットモーダル */}
      {isChatModalOpen && chatTargetElementKey && (
        <div className="fixed inset-0 bg-gray-800 bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-gray-200">
              <h3 className="text-xl font-semibold text-gray-800">AIと「{chatTargetElementLabel}」を深掘り</h3>
              <button onClick={() => setIsChatModalOpen(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>
            <div className="p-6 space-y-4 overflow-y-auto flex-grow h-96">
              {chatHistory.map((msg, index) => ( <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}> <div className={`max-w-xl px-4 py-2 rounded-lg shadow ${ msg.role === 'user' ? 'bg-indigo-500 text-white' : 'bg-gray-100 text-gray-800' }`}> <p className="whitespace-pre-wrap">{msg.parts.map(part => part.text).join('\n')}</p> </div> </div> ))}
              {isChatLoading && ( <div className="flex justify-start"> <div className="max-w-xl px-4 py-2 rounded-lg shadow bg-gray-100 text-gray-800 animate-pulse"> AIが応答を考えています... </div> </div> )}
            </div>
            <div className="p-6 border-t border-gray-200">
              <div className="flex space-x-3">
                <textarea value={currentUserChatMessage} onChange={(e) => setCurrentUserChatMessage(e.target.value)} placeholder="AIへのメッセージを入力..." rows={2} className="flex-grow p-3 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 resize-none" onKeyPress={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendChatMessage(); }}} disabled={isChatLoading} />
                <button onClick={handleSendChatMessage} disabled={isChatLoading || !currentUserChatMessage.trim()} className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"> 送信 </button>
              </div>
              <div className="mt-4 flex justify-end"> <button onClick={applyChatResultToForm} className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"> この内容をフォームに反映 </button> </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}