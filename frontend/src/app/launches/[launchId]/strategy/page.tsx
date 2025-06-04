// src/app/launches/[launchId]/strategy/page.tsx
'use client'

import React, { useEffect, useState, FormEvent, ChangeEvent } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import { supabase } from '@/lib/supabaseClient';
import { toast } from 'react-hot-toast';

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

type Launch = {
  id: string;
  name: string;
  product_name?: string;
};

type StrategyFormData = { // ローンチ固有の戦略項目
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
};

type AccountStrategyBases = {
  account_purpose?: string | null;
  main_target_audience?: TargetAudienceItem[] | null;
  core_value_proposition?: string | null;
  brand_voice_detail?: BrandVoiceDetail | null;
  main_product_summary?: string | null;
  edu_s1_purpose_base?: string | null;
  edu_s2_trust_base?: string | null;
  edu_s3_problem_base?: string | null;
  edu_s4_solution_base?: string | null;
  edu_s5_investment_base?: string | null;
  edu_s6_action_base?: string | null;
  edu_r1_engagement_hook_base?: string | null;
  edu_r2_repetition_base?: string | null;
  edu_r3_change_mindset_base?: string | null;
  edu_r4_receptiveness_base?: string | null;
  edu_r5_output_encouragement_base?: string | null;
  edu_r6_baseline_shift_base?: string | null;
};

type ChatMessage = {
  role: 'user' | 'model';
  parts: { text: string }[];
};

type LaunchStrategyApiResponse = {
    launch_strategy: Partial<StrategyFormData> & { id?: string; launch_id?: string; user_id?:string; created_at?: string; updated_at?:string; };
    account_strategy_bases: AccountStrategyBases;
};

type EducationElementField = {
    key: keyof StrategyFormData;
    baseKey?: keyof AccountStrategyBases; 
    label: string;
    placeholder: string;
    type?: undefined; 
};
type EducationElementSeparator = {
    type: 'separator';
    label: string;
    key?: undefined; 
};
type EducationElementDefinitionItem = EducationElementField | EducationElementSeparator;
// --- 型定義ここまで ---


export default function StrategyEditPage() {
  const { user, loading: authLoading, signOut } = useAuth();
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

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    const fetchData = async () => {
      if (!user || authLoading || !launchId) return;
      setIsLoading(true); 
      setApiError(null); 
      setAiError(null);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("セッションが見つかりません。");
        const token = session.access_token;

        try {
            const launchListResponse = await axios.get<{id: string; name: string}[]>(
                `http://localhost:5001/api/v1/launches`, 
                { headers: { Authorization: `Bearer ${token}` } }
            );
            const currentLaunch = launchListResponse.data.find((l) => l.id === launchId);
            if (currentLaunch) {
                setLaunchName(currentLaunch.name);
            } else { 
                toast.error("指定されたローンチ計画が見つかりませんでした。一覧に戻ります。"); 
                router.push('/launches'); 
                return; 
            }
        } catch (e:unknown) { 
            let LerrorMessage = "ローンチ情報の取得に失敗しました。";
            if(axios.isAxiosError(e) && e.response) LerrorMessage = e.response.data?.message || e.message || LerrorMessage;
            else if (e instanceof Error) LerrorMessage = e.message;
            setApiError(LerrorMessage); toast.error(LerrorMessage); router.push('/launches'); return;
        }

        const strategyApiResponse = await axios.get<LaunchStrategyApiResponse>(
            `http://localhost:5001/api/v1/launches/${launchId}/strategy`,
            { headers: { Authorization: `Bearer ${token}` } }
        );
        const { launch_strategy, account_strategy_bases } = strategyApiResponse.data;

        // --- ▼ デフォルト値設定ロジック (修正版) ▼ ---
        const newFormDataState = { ...initialStrategyFormData }; 

        // 1. アカウント共通基本方針があれば、それをStateに保存し、デフォルト値としてフォームデータに適用
        if (account_strategy_bases) {
            setAccountBases(account_strategy_bases);
            console.log("アカウント共通基本方針をstateに保存しました。", account_strategy_bases);

            (Object.keys(initialStrategyFormData) as Array<keyof StrategyFormData>).forEach(key => {
                let actualBaseKey: keyof AccountStrategyBases | undefined;
                // 特殊なキーのマッピング (ローンチ戦略のキーとアカウント基本方針のキーが異なる場合)
                if (key === 'product_analysis_summary') {
                    actualBaseKey = 'main_product_summary';
                } else if (key === 'target_customer_summary') {
                    // target_customer_summary は main_target_audience (配列) を参照する可能性があるが、
                    // ここでは文字列型の基本方針のみを転写対象とする。
                    // 必要であれば、別途 account_strategy_bases.main_target_audience を参照して
                    // この項目の初期値をリッチにする処理を追加できる。
                    // (例: 最初のペルソナの悩みを要約するなど)
                    // 今回は、もし target_customer_summary_base のようなキーがあればそれを使うイメージ。
                    // なければ、この項目は基本方針からの自動転写対象外とする。
                    actualBaseKey = undefined; // 明示的に対象外にするか、対応する文字列ベースキーがあれば設定
                } else {
                    actualBaseKey = `${key}_base` as keyof AccountStrategyBases;
                }

                if (actualBaseKey && account_strategy_bases[actualBaseKey]) {
                    const baseValue = account_strategy_bases[actualBaseKey];
                    if (typeof baseValue === 'string' && baseValue.trim() !== '') { // 文字列でかつ空でない場合のみ
                        newFormDataState[key] = baseValue;
                        console.log(`フィールド「${key}」の初期値として基本方針「${actualBaseKey}」の値「${baseValue.substring(0,30)}...」をセットしました。`);
                    }
                }
            });
        } else {
            console.warn("アカウント基本戦略がAPIから取得できませんでした。");
            setAccountBases(null);
        }

        // 2. 既存のローンチ固有戦略があれば、それでフォームデータの値を「上書き」
        //    (空文字やnullの場合は上書きしないようにし、基本方針の値が残るようにする)
        if (launch_strategy && typeof launch_strategy === 'object' && Object.keys(launch_strategy).length > 0) {
            (Object.keys(initialStrategyFormData) as Array<keyof StrategyFormData>).forEach(key => {
                if (launch_strategy[key] !== undefined && launch_strategy[key] !== null) { 
                    const specificValue = String(launch_strategy[key]);
                    if (specificValue.trim() !== '') { // ローンチ固有の値が実質的に存在する場合のみ上書き
                        newFormDataState[key] = specificValue;
                        console.log(`フィールド「${key}」をローンチ固有戦略の値「${specificValue.substring(0,30)}...」で上書きしました。`);
                    }
                }
            });
             console.log("既存のローンチ固有戦略をフォームに反映しました。", newFormDataState);
        } else {
            console.log("ローンチ固有の戦略データはまだありません。アカウント基本方針（あれば）がデフォルト値として使用されます。");
        }
        
        setFormData(newFormDataState);
        // --- ▲ デフォルト値設定ロジックここまで ▲ ---

      } catch (err: unknown) {
        console.error("戦略データ取得エラー:", err)
        let fetchErrMessage = '戦略データの取得に失敗しました。';
        if (axios.isAxiosError(err) && err.response?.status !== 404) { 
            fetchErrMessage = err.response?.data?.message || err.message || fetchErrMessage;
            setApiError(fetchErrMessage); 
            toast.error(fetchErrMessage); 
        } else if (err instanceof Error && !(axios.isAxiosError(err) && err.response?.status === 404)) {
            fetchErrMessage = err.message;
            setApiError(fetchErrMessage); 
            toast.error(fetchErrMessage);
        } else if (axios.isAxiosError(err) && err.response?.status === 404) {
            console.log("教育戦略データ(404): 新規作成モードまたは一部データ欠損の可能性があります。");
        }
      } finally { 
        setIsLoading(false); 
      }
    };
    if (user && !authLoading && launchId) fetchData();
  }, [user, authLoading, launchId, router, signOut]);


  const handleStrategyInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const { name, value } = e.target; 
    setFormData(prev => ({ ...prev, [name]: value as string }));
  };

  const handleStrategySubmit = async (e: FormEvent) => {
    e.preventDefault(); 
    if (!user || !launchId) { toast.error('ユーザー情報またはローンチIDが不足しています。'); return; }
    setIsSubmittingStrategy(true); 
    setApiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションが見つかりません。");
      await axios.put(
        `http://localhost:5001/api/v1/launches/${launchId}/strategy`, 
        formData, 
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      toast.success('教育戦略を保存しました！');
    } catch (err:unknown) {
        let saveErrMessage = '戦略の保存に失敗しました。';
        if (axios.isAxiosError(err) && err.response) {
            saveErrMessage = err.response.data?.message || err.message || saveErrMessage;
        } else if (err instanceof Error) {
            saveErrMessage = err.message;
        }
        setApiError(saveErrMessage); 
        toast.error(saveErrMessage);
    }
    finally { setIsSubmittingStrategy(false); }
  };

  const handleGenerateTweet = async () => {
    if (!user || !launchId) { toast.error('情報不足'); return; }
    const hasLaunchStrategyContent = Object.values(formData).some(value => typeof value === 'string' && value.trim() !== '');
    let hasAccountBaseContent = false;
    if(accountBases){
        hasAccountBaseContent = Object.values(accountBases).some(value => {
            if(typeof value === 'string') return value.trim() !== '';
            if(Array.isArray(value)) return value.length > 0;
            if(typeof value === 'object' && value !== null) return Object.keys(value).length > 0;
            return false;
        });
    }

    if (!hasLaunchStrategyContent && !hasAccountBaseContent) {
        if(!window.confirm("戦略情報がほとんど入力されていません。AIは一般的な内容を生成しますが良いですか？")) return; 
    }
    setIsGeneratingTweet(true); setGeneratedTweet(null); setAiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションなし");
      const payload = { 
        purpose: tweetPurpose,
      };
      const res = await axios.post(
        `http://localhost:5001/api/v1/launches/${launchId}/generate-tweet`, 
        payload, 
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      if (res.data?.generated_tweet) { 
        setGeneratedTweet(res.data.generated_tweet); 
        toast.success('AIツイート案生成！');
      } else { 
        throw new Error(res.data?.message || 'AIからの応答が不正です。'); 
      }
    } catch (err:any) { 
        const genTweetErrMessage = err.response?.data?.message || err.message ||'AIツイート生成失敗';
        setAiError(genTweetErrMessage); 
        toast.error(genTweetErrMessage);
    }
    finally { setIsGeneratingTweet(false); }
  };

  const openChatModal = (elementKey: keyof StrategyFormData, elementLabel: string) => {
    setChatTargetElementKey(elementKey); 
    setChatTargetElementLabel(elementLabel);
    const currentMemo = formData[elementKey];
    let initialUserMessage = `「${elementLabel}」(このローンチ向け)について、現在このように考えています。\n\n${currentMemo || '(まだ具体的に記述していません。基本方針を参考に深掘りを手伝ってください。)'}\n\n`;
    
    if (accountBases) {
        let actualBaseKey: keyof AccountStrategyBases | undefined;
        if (elementKey === 'product_analysis_summary') actualBaseKey = 'main_product_summary';
        else if (elementKey === 'target_customer_summary') actualBaseKey = 'main_target_audience';
        else actualBaseKey = `${elementKey}_base` as keyof AccountStrategyBases;

        if (actualBaseKey && accountBases[actualBaseKey]) {
            const baseValue = accountBases[actualBaseKey];
            let basePolicyTextForChat = '';
            if (typeof baseValue === 'string') {
                basePolicyTextForChat = baseValue;
            } else if (actualBaseKey === 'main_target_audience' && Array.isArray(baseValue)) {
                const audiences = baseValue as TargetAudienceItem[];
                basePolicyTextForChat = audiences.map(p => `${p.name || '未設定ペルソナ'}(${p.age || '年齢不明'}): ${p.悩み || '悩み未設定'}`).join('\n');
            } else if (actualBaseKey === 'brand_voice_detail' && typeof baseValue === 'object' && baseValue !== null) {
                const voiceDetail = baseValue as BrandVoiceDetail;
                basePolicyTextForChat = `トーン: ${voiceDetail.tone || '未設定トーン'}, キーワード: ${(voiceDetail.keywords || []).join(', ')}`;
            } else if (baseValue !== null && baseValue !== undefined) {
                basePolicyTextForChat = String(baseValue);
            }
            if (basePolicyTextForChat) {
                initialUserMessage += `ちなみに、このアカウントの「${elementLabel}」に関する共通の基本方針は以下の通りです。\n「${basePolicyTextForChat}」\n\nこれを踏まえて、今回のローンチ用に「${elementLabel}」をさらに具体化・深掘りするのを手伝ってください。`;
            } else {
                 initialUserMessage += `このローンチ用に「${elementLabel}」を具体化・深掘りするのを手伝ってください。`;
            }
        } else {
             initialUserMessage += `このローンチ用に「${elementLabel}」を具体化・深掘りするのを手伝ってください。`;
        }
    } else {
        initialUserMessage += `このローンチ用に「${elementLabel}」を具体化・深掘りするのを手伝ってください。`;
    }
    setChatHistory([{ role: 'user', parts: [{text: initialUserMessage }] }]);
    setCurrentUserChatMessage(''); 
    setIsChatModalOpen(true);
  };

  const handleSendChatMessage = async () => {
    if (!currentUserChatMessage.trim() || !chatTargetElementKey || !launchId) return;
    const newMessage: ChatMessage = { role: 'user', parts: [{ text: currentUserChatMessage.trim() }] };
    const updatedChatHistory = [...chatHistory, newMessage];
    setChatHistory(updatedChatHistory); 
    setCurrentUserChatMessage(''); 
    setIsChatLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションが見つかりません。");
      
      const currentLaunchStrategyElementValue = formData[chatTargetElementKey] || '';
      let accountBasePolicyForChat = '';
      if (accountBases) {
        let actualBaseKey: keyof AccountStrategyBases | undefined;
        if (chatTargetElementKey === 'product_analysis_summary') actualBaseKey = 'main_product_summary';
        else if (chatTargetElementKey === 'target_customer_summary') actualBaseKey = 'main_target_audience';
        else actualBaseKey = `${chatTargetElementKey}_base` as keyof AccountStrategyBases;

        if (actualBaseKey && accountBases[actualBaseKey]) {
            const baseValue = accountBases[actualBaseKey];
            if (typeof baseValue === 'string') accountBasePolicyForChat = baseValue;
            else if (actualBaseKey === 'main_target_audience' && Array.isArray(baseValue)) {
                const audiences = baseValue as TargetAudienceItem[];
                accountBasePolicyForChat = audiences.map(p => `${p.name}(${p.age}): ${p.悩み}`).join('\n');
            } else if (actualBaseKey === 'brand_voice_detail' && typeof baseValue === 'object' && baseValue !== null) {
                const voiceDetail = baseValue as BrandVoiceDetail;
                accountBasePolicyForChat = `トーン: ${voiceDetail.tone}, キーワード: ${voiceDetail.keywords.join(', ')}`;
            } else if (baseValue !== null && baseValue !== undefined) accountBasePolicyForChat = String(baseValue);
        }
      }

      const payload = { 
        launch_id: launchId, 
        element_key: chatTargetElementKey, 
        chat_history: updatedChatHistory.slice(0, -1), 
        current_user_message: newMessage.parts[0].text,
        current_launch_element_value: currentLaunchStrategyElementValue,
        account_base_policy_for_element: accountBasePolicyForChat,
        launch_context: { ...formData }, 
        account_context: { 
            account_purpose: accountBases?.account_purpose,
            core_value_proposition: accountBases?.core_value_proposition,
            main_product_summary: accountBases?.main_product_summary,
            brand_voice_tone: accountBases?.brand_voice_detail?.tone,
        }
      };

      const response = await axios.post(
        'http://localhost:5001/api/v1/chat/education-element', 
        payload, 
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );

      if (response.data?.ai_message) { 
        setChatHistory(prev => [...prev, { role: 'model', parts: [{ text: response.data.ai_message }] }]); 
      } else { 
        throw new Error('AIからの応答がありません。'); 
      }
    } catch (err: any) {
      const chatApiErrMessage = err.response?.data?.message || err.message || "AIとの通信に失敗しました。";
      toast.error(chatApiErrMessage); 
      setChatHistory(prev => [...prev, {role: 'model', parts: [{text: `エラー: ${chatApiErrMessage}`}]}]);
    } finally { 
      setIsChatLoading(false); 
    }
  };

  const applyChatResultToForm = () => {
    if (chatTargetElementKey) {
      const lastAiMessage = chatHistory.filter(m => m.role === 'model').pop()?.parts[0]?.text;
      if (lastAiMessage) { 
        setFormData(prev => ({...prev, [chatTargetElementKey]: lastAiMessage}));
        toast.success(`「${chatTargetElementLabel}」にAIの提案を反映しました。`);
      }
    }
    setIsChatModalOpen(false);
  };

  const handleGenerateBulkDraft = async () => {
    if (!user || !launchId) { toast.error('情報不足です。ログインしているか、ローンチIDが有効か確認してください。'); return; }
    if (!window.confirm("AIにこのローンチの全戦略要素のドラフトを作成させますか？現在のフォーム内容は上書きされます。")) return;
    
    setIsGeneratingBulkDraft(true); 
    setApiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションが見つかりません。");
      
      const response = await axios.post(
        `http://localhost:5001/api/v1/launches/${launchId}/strategy/generate-draft`, 
        {}, 
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      
      if (response.data && typeof response.data === 'object') {
        const newFormDataPayload: Partial<StrategyFormData> = {};
        let updatedCount = 0;
        for (const key of Object.keys(initialStrategyFormData) as Array<keyof StrategyFormData>) {
            if (response.data[key] !== undefined && response.data[key] !== null) {
                newFormDataPayload[key] = String(response.data[key]);
                updatedCount++;
            } else {
                newFormDataPayload[key] = ''; 
            }
        }

        if (updatedCount > 0) {
            setFormData(newFormDataPayload as StrategyFormData);
            toast.success('AIによる戦略ドラフトをフォームに反映しました。内容を確認・編集してください。');
        } else {
            toast.error('AIからの応答に有効な戦略要素データが含まれていませんでした。');
        }
      } else { 
        throw new Error('AIドラフトの応答が期待した形式ではありません。'); 
      }
    } catch (err:any) { 
        const bulkDraftErrMessage = err.response?.data?.message || err.message ||'戦略ドラフトの一括生成に失敗しました。';
        setApiError(bulkDraftErrMessage); 
        toast.error(bulkDraftErrMessage);
    }
    finally { setIsGeneratingBulkDraft(false); }
  };

  const handleSaveTweetDraft = async () => {
    if (!generatedTweet) { toast.error('保存するツイートがありません。'); return; }
    if (!user || !launchId) { toast.error('ユーザー情報またはローンチIDが不足しています。'); return; }
    
    setIsSavingTweet(true);
    setApiError(null);
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("セッションが見つかりません。");
        
        const payload = { 
            content: generatedTweet, 
            status: 'draft', 
            launch_id: launchId, 
            education_element_key: tweetPurpose,
        };
        
        await axios.post(
            'http://localhost:5001/api/v1/tweets', 
            payload, 
            { headers: { Authorization: `Bearer ${session.access_token}` } }
        );
        toast.success('ツイートを下書きとして保存しました！'); 
        setGeneratedTweet(null); 
    } catch (err: any) { 
        const saveTweetErrMessage = err.response?.data?.message || err.message || 'ツイートの下書き保存に失敗しました。';
        setApiError(saveTweetErrMessage); 
        toast.error(saveTweetErrMessage);
    } finally { 
        setIsSavingTweet(false); 
    }
  };
  // --- ▲ AI関連関数の実装ここまで ▲ ---

  // ... (残りのJSXレンダリング部分は前回提示したコードと同様のため省略) ...
  // educationElementsDefinition, renderTextAreaWithBase, return (...) JSX
  // これらの部分は前回から変更ありません。

  if (authLoading || isLoading) { 
    return ( <div className="flex justify-center items-center min-h-[calc(100vh-200px)]"> <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div> <p className="ml-4 text-lg text-gray-600">読み込み中...</p> </div> );
  }
  if (!user) { 
    return ( <div className="flex justify-center items-center min-h-[calc(100vh-200px)]"> <p className="text-lg text-gray-600">ログインページへリダイレクトします...</p> </div> );
  }

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

  const renderTextAreaWithBase = (
    fieldDefinition: EducationElementField
  ) => {
    const { key: fieldKey, label, placeholder, baseKey } = fieldDefinition;
    let basePolicyText: string | null | undefined = undefined;

    if (accountBases && baseKey) {
        const policyValue = accountBases[baseKey];
        if (typeof policyValue === 'string') {
            basePolicyText = policyValue;
        } else if (baseKey === 'main_target_audience' && Array.isArray(policyValue)) {
            const audiences = policyValue as TargetAudienceItem[];
            basePolicyText = audiences.map(p => `${p.name || '未設定ペルソナ'}(${p.age || '年齢不明'}): ${p.悩み || '悩み未設定'}`).join('\n');
        } else if (baseKey === 'brand_voice_detail' && typeof policyValue === 'object' && policyValue !== null) {
            const voiceDetail = policyValue as BrandVoiceDetail;
            basePolicyText = `トーン: ${voiceDetail.tone || '未設定トーン'}, キーワード: ${(voiceDetail.keywords || []).join(', ')}`;
        } else if (policyValue !== null && policyValue !== undefined) {
            basePolicyText = String(policyValue);
        }
    }

    return (
        <div key={fieldKey} className="mb-6 p-4 border rounded-lg shadow-sm bg-slate-50">
            <div className="flex justify-between items-center mb-2">
                <label htmlFor={fieldKey} className="block text-sm sm:text-base font-semibold text-gray-800">
                    {label}
                </label>
                <button 
                    type="button" 
                    onClick={() => openChatModal(fieldKey, label)} 
                    className="px-3 py-1 text-xs font-medium text-indigo-700 bg-indigo-100 rounded-full hover:bg-indigo-200 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-400" 
                    title={`${label} についてAIと相談する`} 
                    disabled={isGeneratingBulkDraft || isSubmittingStrategy || isGeneratingTweet || isChatLoading}
                >
                    AIと相談
                </button>
            </div>
            {basePolicyText && (
                <div className="mb-3 p-3 bg-indigo-50 border border-indigo-200 rounded-md text-xs text-indigo-700">
                    <p className="font-semibold">関連するアカウント基本方針:</p>
                    <p className="whitespace-pre-wrap">{basePolicyText}</p>
                </div>
            )}
            <textarea
                name={fieldKey}
                id={fieldKey}
                rows={7}
                value={formData[fieldKey]}
                onChange={handleStrategyInputChange}
                placeholder={formData[fieldKey] ? '' : (placeholder || `アカウント基本方針を参考に、このローンチでの「${label}」を具体的に記述してください。`)}
                className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm leading-relaxed bg-white"
            />
        </div>
      );
  };


  return (
    <div className="max-w-4xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="mb-8">
        <Link href="/launches" className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center group">
          <svg className="w-5 h-5 mr-2 text-indigo-500 group-hover:text-indigo-700" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd"></path></svg>
          ローンチ計画一覧へ戻る
        </Link>
      </div>
      <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-2 tracking-tight">教育戦略編集</h1>
      {launchName && <p className="text-lg text-gray-600 mb-6">ローンチ計画: <span className="font-semibold text-indigo-600">{launchName}</span></p>}
      
      {apiError && ( 
            <div className="my-4 bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded-md">
                <p className="font-bold">エラーが発生しました</p>
                <p className="text-sm">{apiError}</p>
            </div>
        )}

      <div className="mb-10">
        <button
            onClick={handleGenerateBulkDraft}
            disabled={isGeneratingBulkDraft || isSubmittingStrategy || isGeneratingTweet || isChatLoading || isLoading}
            className="w-full flex justify-center items-center py-3 px-6 border border-transparent rounded-lg shadow-md text-base sm:text-lg font-medium text-white bg-teal-600 hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500 disabled:opacity-60 transition duration-150 ease-in-out"
        >
            <svg className="w-5 h-5 mr-2 animate-pulse" fill="currentColor" viewBox="0 0 20 20"><path d="M10 3.5a1.5 1.5 0 011.303 2.253l.005.008a12.003 12.003 0 000 8.478l-.005.008A1.5 1.5 0 0110 16.5a1.5 1.5 0 01-1.303-2.253l-.005-.008a12.003 12.003 0 000-8.478l.005-.008A1.5 1.5 0 0110 3.5zM6.5 10a1.5 1.5 0 012.253-1.303l.008-.005a12.003 12.003 0 008.478 0l.008.005A1.5 1.5 0 0119.5 10a1.5 1.5 0 01-2.253 1.303l-.008.005a12.003 12.003 0 00-8.478 0l-.008-.005A1.5 1.5 0 016.5 10z"></path></svg>
            {isGeneratingBulkDraft ? 'AIが全要素のドラフトを作成中...' : 'AIに全戦略要素のドラフトを一括作成させる'}
        </button>
      </div>

      <form onSubmit={handleStrategySubmit} className="space-y-2 bg-white p-6 sm:p-8 shadow-2xl rounded-2xl border border-gray-200 mb-16">
        {educationElementsDefinition.map((field, index) => {
          if (field.type === 'separator') {
            return ( 
              <React.Fragment key={field.label + '-' + index}>
                <hr className="my-8 border-t-2 border-indigo-100" /> 
                <h2 className="text-lg sm:text-xl font-semibold text-indigo-700 mt-6 mb-4 -translate-y-3">
                  {field.label}
                </h2>
              </React.Fragment>
            );
          }
          return renderTextAreaWithBase(field as EducationElementField);
        })}
        <div className="pt-6">
          <button 
            type="submit" 
            disabled={isSubmittingStrategy || isGeneratingBulkDraft || isGeneratingTweet || isLoading}
            className="w-full flex justify-center py-3 px-6 border border-transparent rounded-lg shadow-md text-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition duration-150 ease-in-out"
          >
            {isSubmittingStrategy ? '保存中...' : 'このローンチの教育戦略を保存する'}
          </button>
        </div>
      </form>

      <div className="bg-white p-6 sm:p-8 shadow-2xl rounded-2xl border border-gray-200">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-800 mb-6">AIツイート生成 (このローンチ向け)</h2>
        <div className="mb-6">
            <label htmlFor="tweetPurpose" className="block text-sm font-semibold text-gray-700 mb-2">ツイートの目的・テーマ（AIへの指示）:</label>
            <input type="text" id="tweetPurpose" name="tweetPurpose" value={tweetPurpose} onChange={(e) => setTweetPurpose(e.target.value)} placeholder="例: 商品の緊急性を伝えるツイート" className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"/>
        </div>
        <button onClick={handleGenerateTweet} disabled={isGeneratingTweet || isSubmittingStrategy || isGeneratingBulkDraft || isLoading} className="w-full flex justify-center py-3 px-6 border border-transparent rounded-lg shadow-md text-lg font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-60 transition duration-150 ease-in-out">
          {isGeneratingTweet ? 'ツイート生成中...' : 'AIでツイート案を生成する'}
        </button>
        {isGeneratingTweet && ( <div className="mt-8 flex flex-col justify-center items-center text-center"> <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-green-500 mb-3"></div> <p className="text-gray-600">AIが最適なツイートを考案中です...</p> </div> )}
        {aiError && !isGeneratingTweet && ( <div className="mt-6 bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded-md"><p className="font-bold">AIエラー</p><p className="text-sm">{aiError}</p></div>)}
        {generatedTweet && !isGeneratingTweet && (
          <div className="mt-8 p-6 border rounded-lg bg-gray-50 shadow">
            <h3 className="text-base font-semibold text-gray-800 mb-3">AIが生成したツイート案:</h3>
            <textarea readOnly value={generatedTweet} rows={6} className="w-full p-3 border border-gray-300 rounded-md bg-white text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none leading-relaxed" onClick={(e) => (e.target as HTMLTextAreaElement).select()} />
            <div className="mt-4 flex justify-end">
                <button onClick={handleSaveTweetDraft} disabled={isSavingTweet} className="px-6 py-2 bg-sky-600 text-white font-semibold rounded-lg shadow-md hover:bg-sky-700 transition duration-300 disabled:opacity-50 text-sm">
                    {isSavingTweet ? '保存中...' : '下書きとして保存'}
                </button>
            </div>
          </div>
        )}
      </div>

      {isChatModalOpen && chatTargetElementKey && (
        <div className="fixed inset-0 bg-gray-800 bg-opacity-75 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col my-auto">
            <div className="flex justify-between items-center p-5 border-b border-gray-200 sticky top-0 bg-white z-10">
              <h3 className="text-lg font-semibold text-gray-800">AIと「{chatTargetElementLabel}」を深掘り</h3>
              <button onClick={() => setIsChatModalOpen(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>
            <div className="p-6 space-y-4 overflow-y-auto flex-grow min-h-[300px] bg-slate-50">
              {chatHistory.map((msg, index) => ( <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} mb-2`}> <div className={`max-w-lg lg:max-w-xl px-4 py-3 rounded-xl shadow ${ msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-800 border' }`}> <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.parts.map(part => part.text).join('\n')}</p> </div> </div> ))}
              {isChatLoading && ( <div className="flex justify-start"> <div className="max-w-xl px-4 py-3 rounded-xl shadow bg-gray-200 text-gray-600 animate-pulse"> AIが応答を考えています... </div> </div> )}
            </div>
            <div className="p-4 border-t border-gray-200 bg-gray-100 sticky bottom-0 z-10">
              <div className="flex space-x-2">
                <textarea value={currentUserChatMessage} onChange={(e) => setCurrentUserChatMessage(e.target.value)} placeholder="AIへのメッセージを入力 (Shift+Enterで改行)" rows={2} className="flex-grow p-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 resize-none text-sm" onKeyPress={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendChatMessage(); }}} disabled={isChatLoading} />
                <button onClick={handleSendChatMessage} disabled={isChatLoading || !currentUserChatMessage.trim()} className="px-4 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 text-sm"> 送信 </button>
              </div>
              <div className="mt-3 flex justify-end"> <button onClick={applyChatResultToForm} className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"> この内容をフォームに反映 </button> </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}