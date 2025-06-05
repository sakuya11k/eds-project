// src/app/mypage/account-strategy/page.tsx

'use client';

import React, { useEffect, useState, FormEvent, ChangeEvent, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import { supabase } from '@/lib/supabaseClient';
import { toast } from 'react-hot-toast';

// --- 型定義 ---
export type TargetAudienceItem = {
  id?: string; name: string; age: string; 悩み: string;
};
export type BrandVoiceDetail = {
  tone: string; keywords: string[]; ng_words: string[];
};
export type AccountStrategyFormData = {
  username: string; website: string; preferred_ai_model: string;
  x_api_key: string | null; x_api_secret_key: string | null; x_access_token: string | null; x_access_token_secret: string | null;
  account_purpose: string; main_target_audience: TargetAudienceItem[] | null;
  core_value_proposition: string; brand_voice_detail: BrandVoiceDetail;
  main_product_summary: string;
  edu_s1_purpose_base: string; edu_s2_trust_base: string; edu_s3_problem_base: string;
  edu_s4_solution_base: string; edu_s5_investment_base: string; edu_s6_action_base: string;
  edu_r1_engagement_hook_base: string; edu_r2_repetition_base: string;
  edu_r3_change_mindset_base: string; edu_r4_receptiveness_base: string;
  edu_r5_output_encouragement_base: string; edu_r6_baseline_shift_base: string;
};
export const initialAccountStrategyFormData: AccountStrategyFormData = {
  username: '', website: '', preferred_ai_model: 'gemini-2.5-flash-preview-05-20',
  x_api_key: null, x_api_secret_key: null, x_access_token: null, x_access_token_secret: null,
  account_purpose: '', main_target_audience: [{ id: Date.now().toString(), name: '', age: '', 悩み: '' }],
  core_value_proposition: '', brand_voice_detail: { tone: '', keywords: [''], ng_words: [''] },
  main_product_summary: '',
  edu_s1_purpose_base: '', edu_s2_trust_base: '', edu_s3_problem_base: '',
  edu_s4_solution_base: '', edu_s5_investment_base: '', edu_s6_action_base: '',
  edu_r1_engagement_hook_base: '', edu_r2_repetition_base: '',
  edu_r3_change_mindset_base: '', edu_r4_receptiveness_base: '',
  edu_r5_output_encouragement_base: '', edu_r6_baseline_shift_base: '',
};
const aiModelOptions = [
  { value: 'gemini-2.5-flash-preview-05-20', label: 'Gemini 2.5 Flash (高速・標準)' },
  { value: 'gemini-2.5-pro-preview-05-06', label: 'Gemini 2.5 Pro (高性能・高品質)' },
];
type ChatMessage = {
  role: 'user' | 'model'; parts: { text: string }[];
};
// --- 型定義ここまで ---

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


export default function AccountStrategyPage() {
  const { user, loading: authLoading, signOut } = useAuth();
  const router = useRouter();

  const [formData, setFormData] = useState<AccountStrategyFormData>(initialAccountStrategyFormData);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const [isGeneratingPurpose, setIsGeneratingPurpose] = useState(false);
  const [purposeKeywords, setPurposeKeywords] = useState('');
  const [isGeneratingPersonas, setIsGeneratingPersonas] = useState(false);
  const [personaKeywords, setPersonaKeywords] = useState('');
  const [isGeneratingValueProp, setIsGeneratingValueProp] = useState(false);
  const [isGeneratingBrandVoice, setIsGeneratingBrandVoice] = useState(false);
  const [brandVoiceAdjectives, setBrandVoiceAdjectives] = useState('');
  const [isGeneratingProductSummary, setIsGeneratingProductSummary] = useState(false);
  const [isGeneratingBasePolicies, setIsGeneratingBasePolicies] = useState(false);

  const [isChatModalOpen, setIsChatModalOpen] = useState(false);
  const [chatTargetFieldKey, setChatTargetFieldKey] = useState<keyof AccountStrategyFormData | null>(null);
  const [chatTargetFieldLabel, setChatTargetFieldLabel] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentUserChatMessage, setCurrentUserChatMessage] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  const fetchProfileData = useCallback(async () => {
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
        
        setFormData({
          ...initialAccountStrategyFormData,
          username: fetchedProfile.username || '',
          website: fetchedProfile.website || '',
          preferred_ai_model: fetchedProfile.preferred_ai_model || initialAccountStrategyFormData.preferred_ai_model,
          x_api_key: fetchedProfile.x_api_key || null,
          x_api_secret_key: fetchedProfile.x_api_secret_key || null,
          x_access_token: fetchedProfile.x_access_token || null,
          x_access_token_secret: fetchedProfile.x_access_token_secret || null,
          account_purpose: fetchedProfile.account_purpose || '',
          main_target_audience: fetchedProfile.main_target_audience && fetchedProfile.main_target_audience.length > 0
              ? fetchedProfile.main_target_audience.map(p => ({...p, id: p.id || Date.now().toString() + Math.random() }))
              : initialAccountStrategyFormData.main_target_audience,
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
        });
      } catch (error: unknown) {
        console.error('プロファイル取得エラー (AccountStrategyPage):', error);
        let errorMessage = 'アカウント戦略の読み込みに失敗しました。';
        if (axios.isAxiosError(error) && error.response) {
             errorMessage = error.response.data?.message || error.message || errorMessage;
             if (error.response.status === 401 && signOut) {
                  await signOut(); 
                  router.push('/login');
             } else if (error.response.status === 404) {
                  toast("プロフィールデータがまだありません。新規作成してください。", { icon: 'ℹ️' });
                  setFormData(initialAccountStrategyFormData);
             }
        } else if (error instanceof Error) {
             errorMessage = error.message;
        }
        setApiError(errorMessage);
        if (!(axios.isAxiosError(error) && error.response?.status === 404)) {
          toast.error(errorMessage);
        }
      } finally {
        setIsLoadingData(false);
      }
    }
  }, [user, authLoading, router, signOut]); 

  useEffect(() => {
    fetchProfileData();
  }, [fetchProfileData]); 


  const handleInputChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };
  const handleBrandVoiceDetailChange = <K extends keyof BrandVoiceDetail>(key: K, value: BrandVoiceDetail[K]) => {
    setFormData(prev => ({ ...prev, brand_voice_detail: { ...prev.brand_voice_detail, [key]: value }}));
  };
  const handleKeywordChange = (index: number, value: string, type: 'keywords' | 'ng_words') => {
      const currentList = [...formData.brand_voice_detail[type]]; currentList[index] = value;
      handleBrandVoiceDetailChange(type, currentList);
  };
  const addKeyword = (type: 'keywords' | 'ng_words') => {
      const currentList = formData.brand_voice_detail[type];
      if (currentList.length === 0 || (currentList.length > 0 && currentList[currentList.length -1].trim() !== '')) {
        handleBrandVoiceDetailChange(type, [...currentList, '']);
      } else { toast('まず空の欄を埋めてください。', { icon: 'ℹ️' });}
  };
  const removeKeyword = (index: number, type: 'keywords' | 'ng_words') => {
      const currentList = [...formData.brand_voice_detail[type]]; currentList.splice(index, 1);
      handleBrandVoiceDetailChange(type, currentList.length > 0 ? currentList : ['']);
  };
  const handleTargetAudienceChange = (index: number, field: keyof Omit<TargetAudienceItem, 'id'>, value: string) => {
    const updatedAudiences = formData.main_target_audience ? formData.main_target_audience.map((item, i) => i === index ? { ...item, [field]: value } : item) : [];
    setFormData(prev => ({ ...prev, main_target_audience: updatedAudiences }));
  };
  const addTargetAudience = () => {
    setFormData(prev => ({ ...prev, main_target_audience: [...(prev.main_target_audience || []), { id: Date.now().toString(), name: '', age: '', 悩み: '' }]}));
  };
  const removeTargetAudience = (index: number) => {
    if (!formData.main_target_audience || formData.main_target_audience.length <= 1) { toast.error('最低1つのペルソナが必要です。'); return; }
    const updatedAudiences = formData.main_target_audience.filter((_, i) => i !== index);
    setFormData(prev => ({ ...prev, main_target_audience: updatedAudiences }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!user) { toast.error('認証されていません。'); return; }
    if (!formData.username.trim()) { toast.error('ユーザー名は必須です。'); return; }
    if (!formData.account_purpose.trim()) { toast.error('アカウントの目的は必須です。'); return;}
    setIsSubmitting(true); setApiError(null);
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
        main_target_audience: formData.main_target_audience 
            ? formData.main_target_audience.filter( 
                p => p.name.trim() !== '' || p.age.trim() !== '' || p.悩み.trim() !== '' 
              ) 
            : null, 
      }; 
      if (payloadToSubmit.main_target_audience?.length === 0) { 
        payloadToSubmit.main_target_audience = null; 
      } 
      await axios.put('http://localhost:5001/api/v1/profile', payloadToSubmit, { headers: { Authorization: `Bearer ${session.access_token}` } }); 
      toast.success('アカウント戦略を保存しました！'); 
      fetchProfileData();  
    } catch (error: unknown) { 
      console.error('アカウント戦略保存エラー:', error); 
      let errorMessage = 'アカウント戦略の保存に失敗しました。'; 
      if (axios.isAxiosError(error) && error.response) { errorMessage = error.response.data?.message || error.message || errorMessage; 
      } else if (error instanceof Error) { errorMessage = error.message; } 
      setApiError(errorMessage); toast.error(errorMessage); 
    } finally { setIsSubmitting(false); } 
  };

  const handleSuggestWithAI = async (
    targetField: keyof AccountStrategyFormData | 'main_target_audience_item',
    apiEndpoint: string,
    setLoadingState: React.Dispatch<React.SetStateAction<boolean>>,
    additionalPayload?: object,
    personaIndex?: number
  ) => {
    if (!user) { toast.error("まずログインしてください。"); return; }
    setLoadingState(true);
    setApiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションエラー");
      
      const requestPayload = {
        current_username: formData.username,
        current_account_purpose: formData.account_purpose,
        current_core_value_proposition: formData.core_value_proposition,
        current_product_summary: formData.main_product_summary,
        current_brand_voice_tone: formData.brand_voice_detail.tone,
        current_main_target_audience: targetField === 'main_target_audience' || targetField === 'main_target_audience_item' 
            ? formData.main_target_audience 
            : undefined, 
        ...additionalPayload,
      };

      const response = await axios.post(
        `http://localhost:5001${apiEndpoint}`,
        requestPayload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );

      if (targetField === 'main_target_audience') {
        if (response.data?.suggested_personas && Array.isArray(response.data.suggested_personas)) {
            const personasWithId = response.data.suggested_personas.map((p: Omit<TargetAudienceItem, 'id'>, index: number) => ({
                ...p, 
                id: formData.main_target_audience?.[index]?.id || Date.now().toString() + Math.random() 
            }));
            setFormData(prev => ({ ...prev, main_target_audience: personasWithId }));
            toast.success(`ペルソナのAI提案を反映しました。`);
        } else {  toast.error('AIからのペルソナ提案が期待した形式ではありませんでした。'); }
      } else if (targetField === 'main_target_audience_item' && typeof personaIndex === 'number' && formData.main_target_audience) {
        if (response.data?.suggested_persona_detail && typeof response.data.suggested_persona_detail === 'object') {
            const updatedAudiences = [...formData.main_target_audience];
            updatedAudiences[personaIndex] = { ...updatedAudiences[personaIndex], ...response.data.suggested_persona_detail};
            setFormData(prev => ({...prev, main_target_audience: updatedAudiences}));
            toast.success(`ペルソナ${personaIndex + 1}のAI提案を反映しました。`);
        } else { toast.error('AIからの個別ペルソナ提案が期待した形式ではありませんでした。');}
      }
      else if (targetField === 'brand_voice_detail' && typeof response.data.suggestion === 'object') {
          setFormData(prev => ({ ...prev, brand_voice_detail: { ...initialAccountStrategyFormData.brand_voice_detail, ...response.data.suggestion} }));
          toast.success(`ブランドボイスのAI提案を反映しました。`);
      }
      else if (typeof response.data.suggestion === 'string') {
          setFormData(prev => ({ ...prev, [targetField]: response.data.suggestion }));
          toast.success(`${targetField} のAI提案を反映しました。`);
      } else if (response.data?.suggestions && Array.isArray(response.data.suggestions)) {
        setFormData(prev => ({ ...prev, [targetField as string]: response.data.suggestions[0] || '' }));
        toast.success(`${targetField} のAI提案を反映しました。`);
      }
      else {
        toast.error('AIからの提案が期待した形式ではありませんでした。');
      }
    } catch (err: unknown) {
      let errorMsg = "AI提案の取得に失敗しました。";
      if (axios.isAxiosError(err) && err.response) errorMsg = err.response.data?.message || err.message || errorMsg;
      else if (err instanceof Error) errorMsg = err.message;
      setApiError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoadingState(false);
    }
  };
  
  const handleGenerateBasePoliciesDraft = async () => {
    if (!user) { toast.error("ログインしてください。"); return; }
    if (!formData.account_purpose || !formData.core_value_proposition || !formData.main_product_summary || !(formData.main_target_audience && formData.main_target_audience.length > 0 && formData.main_target_audience[0].悩み) ) {
        toast.error("基本方針のAIドラフト生成には、「アカウント目的」「提供価値」「商品概要」「ターゲット顧客の悩み」の入力が必要です。");
        return;
    }
    if (!window.confirm("AIに12の教育基本方針のドラフトを一括生成させますか？既存の内容は上書きされます。")) return;

    setIsGeneratingBasePolicies(true);
    setApiError(null);
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) throw new Error("セッションエラー");
        const response = await axios.post(
            `http://localhost:5001/api/v1/profile/generate-base-policies-draft`,
            { 
                account_purpose: formData.account_purpose,
                main_target_audience_summary: formData.main_target_audience?.map(p=>`ペルソナ「${p.name}」の悩み: ${p.悩み}`).join(';\n'),
                core_value_proposition: formData.core_value_proposition,
                main_product_summary: formData.main_product_summary,
                brand_voice_tone: formData.brand_voice_detail.tone,
            },
            { headers: { Authorization: `Bearer ${session.access_token}` } }
        );
        if (response.data && typeof response.data === 'object') {
            const updatedFormData = { ...formData };
            let updatedCount = 0;
            for (const key in response.data) {
                if (key.endsWith('_base') && key in updatedFormData) {
                    updatedFormData[key as keyof AccountStrategyFormData] = response.data[key] || '';
                    updatedCount++;
                }
            }
            if (updatedCount > 0) {
                setFormData(updatedFormData);
                toast.success("AIによる12の教育基本方針ドラフトをフォームに反映しました。");
            } else {
                toast.error("AIからの応答に有効な基本方針データが含まれていませんでした。");
            }
        } else {
            throw new Error("AIからの応答が期待した形式ではありません。");
        }
    } catch (err: unknown) {
        let errorMsg = "基本方針の一括ドラフト生成に失敗しました。";
        if (axios.isAxiosError(err) && err.response) errorMsg = err.response.data?.message || err.message || errorMsg;
        else if (err instanceof Error) errorMsg = err.message;
        setApiError(errorMsg);
        toast.error(errorMsg);
    } finally {
        setIsGeneratingBasePolicies(false);
    }
  };

  const openAiChat = (fieldKey: keyof AccountStrategyFormData, label: string, personaIndex?: number) => {
    setChatTargetFieldKey(fieldKey);
    setChatTargetFieldLabel(label);
    let currentMemo = '';
    if (fieldKey === 'main_target_audience' && typeof personaIndex === 'number' && formData.main_target_audience && formData.main_target_audience[personaIndex]) {
        const p = formData.main_target_audience[personaIndex];
        currentMemo = `ペルソナ名: ${p.name}\n年齢層/属性: ${p.age}\n主な悩み/欲求/課題: ${p.悩み}`;
    } else {
        currentMemo = String(formData[fieldKey] ?? '');
    }
    setChatHistory(currentMemo ? [{ role: 'user', parts: [{text: `「${label}」について、現在このように考えています。\n\n${currentMemo}\n\nこれをより具体的に、魅力的にするのを手伝ってください。`}]}] : []);
    setCurrentUserChatMessage('');
    setIsChatModalOpen(true);
  };

  const handleSendAccountStrategyChatMessage = async () => { 
    if (!currentUserChatMessage.trim() || !chatTargetFieldKey) return;
    const newMessage: ChatMessage = { role: 'user', parts: [{ text: currentUserChatMessage.trim() }] };
    const updatedChatHistory = [...chatHistory, newMessage];
    setChatHistory(updatedChatHistory);
    setCurrentUserChatMessage('');
    setIsChatLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("セッションエラー");
      
      let chatApiEndpoint = 'http://localhost:5001/api/v1/profile/chat-generic-field';
      let currentFieldValueForChat = String(formData[chatTargetFieldKey] ?? '');
      if (chatTargetFieldKey === 'main_target_audience') {
        const personaIndex = parseInt(chatTargetFieldLabel.split(' ')[1], 10) - 1; 
        if (formData.main_target_audience && formData.main_target_audience[personaIndex] !== undefined) {
            const p = formData.main_target_audience[personaIndex];
            currentFieldValueForChat = `ペルソナ名: ${p.name}, 年齢層/属性: ${p.age}, 主な悩み/欲求/課題: ${p.悩み}`;
        }
      }
      
      const payload = {
        field_key: chatTargetFieldKey,
        field_label: chatTargetFieldLabel,
        current_field_value: currentFieldValueForChat,
        chat_history: updatedChatHistory.slice(0, -1), 
        current_user_message: newMessage.parts[0].text,
        account_context: {
            purpose: formData.account_purpose,
            product_summary: formData.main_product_summary,
            core_value_proposition: formData.core_value_proposition,
            brand_voice_tone: formData.brand_voice_detail.tone,
        }
      };
      const response = await axios.post(chatApiEndpoint, payload, { headers: { Authorization: `Bearer ${session.access_token}` } });
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

  const applyChatResultToAccountStrategyForm = () => { 
    if (chatTargetFieldKey) { 
      const lastAiMessage = chatHistory.filter(m => m.role === 'model').pop()?.parts[0]?.text; 
      if (lastAiMessage) { 
        if (chatTargetFieldKey === 'main_target_audience') { 
            toast("ペルソナのチャット結果の反映は、現在手動コピー＆ペーストで行ってください。AIの提案を参考に各項目を更新してください。", { icon: 'ℹ️' }); 
        } else { 
            setFormData(prev => ({...prev, [chatTargetFieldKey]: lastAiMessage})); 
        }
        toast.success(`「${chatTargetFieldLabel}」にAIの提案を反映しました。内容を確認・調整してください。`); 
      }
    } 
    setIsChatModalOpen(false); 
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
  
  const renderTextAreaWithAi = (
    name: keyof AccountStrategyFormData, 
    label: string, 
    rows: number = 3, 
    placeholderFromDefinition?: string,
    description?: string,
    aiSuggestEndpoint?: string,
    isLoadingAiSuggest?: boolean,
    setLoadingAiSuggest?: React.Dispatch<React.SetStateAction<boolean>>,
    inputForAiSuggestSetter?: React.Dispatch<React.SetStateAction<string>>, 
    currentKeywordsForAiSuggest?: string
  ) => (
    <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
        <div className="flex flex-wrap justify-between items-center mb-1 gap-y-2">
            <label htmlFor={name} className="block text-sm font-semibold text-gray-700 basis-full sm:basis-auto">{label}</label>
            <div className="flex space-x-2 flex-wrap gap-y-1">
                {aiSuggestEndpoint && setLoadingAiSuggest && (
                     <>
                        {inputForAiSuggestSetter !== undefined && currentKeywordsForAiSuggest !== undefined && (
                            <input 
                                type="text"
                                value={currentKeywordsForAiSuggest}
                                onChange={(e) => inputForAiSuggestSetter(e.target.value)}
                                placeholder="AI提案用キーワード"
                                className="px-2 py-1 text-xs border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                            />
                        )}
                        <button
                            type="button"
                            onClick={() => handleSuggestWithAI(name, aiSuggestEndpoint, setLoadingAiSuggest, inputForAiSuggestSetter !== undefined ? { user_keywords: currentKeywordsForAiSuggest } : undefined)}
                            disabled={isLoadingAiSuggest || isSubmitting}
                            className="px-2 py-1 text-xs font-medium text-purple-700 bg-purple-100 rounded-full hover:bg-purple-200 transition whitespace-nowrap"
                            title={`${label} のドラフトをAIに提案させる`}
                        >
                            {isLoadingAiSuggest ? '生成中...' : 'AI提案'}
                        </button>
                     </>
                )}
                <button
                    type="button"
                    onClick={() => openAiChat(name, label)}
                    disabled={isSubmitting}
                    className="px-2 py-1 text-xs font-medium text-indigo-700 bg-indigo-100 rounded-full hover:bg-indigo-200 transition whitespace-nowrap"
                    title={`${label} についてAIと相談する`}
                >
                    AI相談
                </button>
            </div>
        </div>
        {description && !formData[name] && <p className="mb-2 text-xs text-gray-400 italic">{description}</p>}
        <textarea
            id={name}
            name={name}
            rows={rows}
            value={String(formData[name] ?? '')} 
            onChange={handleInputChange}
            placeholder={formData[name] ? '' : (placeholderFromDefinition || `アカウントの「${label}」を入力してください`)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white"
        />
    </div>
  );

  const sectionTitleClass = "text-xl font-semibold text-gray-800 pb-3 mb-6 border-b border-gray-300";
  const fieldSetClass = "space-y-1";

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
                <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
                     <label htmlFor="username" className="block text-sm font-semibold text-gray-700 mb-1">ユーザー名 *</label>
                    <input type="text" name="username" id="username" value={formData.username} onChange={handleInputChange} required className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" />
                </div>
                {renderTextAreaWithAi('account_purpose' as keyof AccountStrategyFormData, 'アカウントの基本理念・パーパス *', 3, undefined, "このアカウントを通じて何を達成したいか、どのような価値を提供したいのかを具体的に記述してください。", '/api/v1/profile/suggest-purpose', isGeneratingPurpose, setIsGeneratingPurpose, setPurposeKeywords, purposeKeywords)}
                {renderTextAreaWithAi('core_value_proposition' as keyof AccountStrategyFormData, 'アカウントのコア提供価値 *', 3, undefined, "あなたの発信をフォローすることで、読者が継続的に得られる最も重要な価値（ベネフィット）は何ですか？", '/api/v1/profile/suggest-value-proposition', isGeneratingValueProp, setIsGeneratingValueProp)}
            </div>
        </section>

        <section>
            <h2 className={sectionTitleClass}>ターゲット顧客 (ペルソナ)</h2>
            <div className={fieldSetClass}>
                <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
                    <label htmlFor="personaKeywords" className="block text-sm font-semibold text-gray-700 mb-1">ペルソナ提案用キーワード</label>
                    <input 
                        type="text"
                        id="personaKeywords"
                        value={personaKeywords}
                        onChange={(e) => setPersonaKeywords(e.target.value)}
                        placeholder="例: 30代 主婦 副業, 起業初心者 スキルアップ"
                        className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white mb-2"
                    />
                    <button
                        type="button"
                        onClick={() => handleSuggestWithAI('main_target_audience', '/api/v1/profile/suggest-persona-draft', setIsGeneratingPersonas, { user_keywords: personaKeywords, num_personas: 2 } )}
                        disabled={isGeneratingPersonas || isSubmitting}
                        className="w-full sm:w-auto mb-3 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-md shadow-sm transition"
                    >
                        {isGeneratingPersonas ? "AIがペルソナ案作成中..." : "AIにペルソナドラフトを提案させる"}
                    </button>
                    <p className="mt-1 text-xs text-gray-500">商品概要や上記のキーワードを元にAIがペルソナ案を作成します。</p>
                </div>
                {formData.main_target_audience && formData.main_target_audience.map((audience, index) => (
                    <div key={audience.id || index} className="p-4 border rounded-lg space-y-3 bg-slate-100 shadow-sm mb-4">
                        <div className="flex justify-between items-center">
                            <h4 className="font-semibold text-gray-700">ペルソナ {index + 1}</h4>
                            <div className="flex space-x-2">
                                <button type="button" onClick={() => openAiChat('main_target_audience', `ペルソナ ${index + 1} (ID: ${audience.id})`, index)} className="px-2 py-1 text-xs font-medium text-indigo-700 bg-indigo-100 rounded-full hover:bg-indigo-200 transition">AIと深掘り</button>
                                {formData.main_target_audience && formData.main_target_audience.length > 1 && (
                                    <button type="button" onClick={() => removeTargetAudience(index)} className="text-red-500 hover:text-red-700 text-xs font-medium px-2 py-1 rounded hover:bg-red-50 transition-colors">削除</button>
                                )}
                            </div>
                        </div>
                         <div>
                            <label htmlFor={`targetName-${index}`} className="block text-xs font-medium text-gray-600 mb-0.5">ペルソナ名 / 呼び名 *</label>
                            <input type="text" id={`targetName-${index}`} value={audience.name} onChange={(e) => handleTargetAudienceChange(index, 'name', e.target.value)} required className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" placeholder="例: 副業で月10万目指す太郎さん"/>
                        </div>
                        <div>
                            <label htmlFor={`targetAge-${index}`} className="block text-xs font-medium text-gray-600 mb-0.5">年齢層 / 属性</label>
                            <input type="text" id={`targetAge-${index}`} value={audience.age} onChange={(e) => handleTargetAudienceChange(index, 'age', e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" placeholder="例: 30代、会社員（子育て中）"/>
                        </div>
                        <div>
                            <label htmlFor={`targetProblem-${index}`} className="block text-xs font-medium text-gray-600 mb-0.5">主な悩み / 欲求 / 課題 *</label>
                            <textarea id={`targetProblem-${index}`} value={audience.悩み} onChange={(e) => handleTargetAudienceChange(index, '悩み', e.target.value)} required rows={3} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" placeholder="例: 毎日の残業で時間がない。今の給料だけでは将来が不安。新しいスキルを身につけたいが何から始めれば良いか分からない。"/>
                        </div>
                    </div>
                ))}
                <button type="button" onClick={addTargetAudience} className="mt-1 w-full sm:w-auto px-4 py-2 border border-dashed border-indigo-400 text-sm font-medium rounded-md text-indigo-700 hover:bg-indigo-50 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    + ペルソナを手動で追加する
                </button>
            </div>
        </section>

        <section>
            <h2 className={sectionTitleClass}>ブランドボイス詳細</h2>
            <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
                <label htmlFor="brandVoiceAdjectives" className="block text-sm font-semibold text-gray-700 mb-1">ブランドボイス提案用キーワード</label>
                 <input 
                    type="text"
                    id="brandVoiceAdjectives"
                    value={brandVoiceAdjectives}
                    onChange={(e) => setBrandVoiceAdjectives(e.target.value)}
                    placeholder="例: 親しみやすい, 専門的, 辛口"
                    className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white mb-2"
                />
                <button
                    type="button"
                    onClick={() => handleSuggestWithAI('brand_voice_detail', '/api/v1/profile/suggest-brand-voice', setIsGeneratingBrandVoice, { adjectives: brandVoiceAdjectives } )}
                    disabled={isGeneratingBrandVoice || isSubmitting}
                    className="w-full sm:w-auto mb-3 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-md shadow-sm transition"
                >
                    {isGeneratingBrandVoice ? "AIがブランドボイス案作成中..." : "AIにブランドボイス詳細を提案させる"}
                </button>
            </div>
            <div className="p-4 border rounded-lg shadow-sm bg-slate-100 mb-4 space-y-4">
                <div>
                    <label htmlFor="brandVoiceTone" className="block text-sm font-semibold text-gray-700 mb-1">基本トーン *</label>
                    <input type="text" id="brandVoiceTone" value={formData.brand_voice_detail.tone} onChange={(e) => handleBrandVoiceDetailChange('tone', e.target.value)} required className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" placeholder="例: 専門的だが親しみやすい、論理的で冷静、情熱的で励ますなど"/>
                </div>
                {(['keywords', 'ng_words'] as const).map(type => (
                    <div key={type}>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            {type === 'keywords' ? 'よく使うキーワード / フレーズ' : '避けるべきキーワード / フレーズ (NGワード)'}
                        </label>
                        {formData.brand_voice_detail[type].map((kw, index) => (
                            <div key={`${type}-${index}`} className="flex items-center space-x-2 mb-2">
                                <input type="text" value={kw} onChange={(e) => handleKeywordChange(index, e.target.value, type)} placeholder={type === 'keywords' ? "例: 再現性、時短、AI活用" : "例: 絶対儲かる、楽して稼ぐ"} className="flex-grow px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 bg-white"/>
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
                 <button type="button" onClick={() => openAiChat('brand_voice_detail', 'ブランドボイス詳細')} className="mt-2 w-full sm:w-auto px-3 py-1 text-xs font-medium text-indigo-700 bg-indigo-100 rounded-full hover:bg-indigo-200 transition">AIとブランドボイスを深掘り</button>
            </div>
        </section>

        <section>
            <h2 className={sectionTitleClass}>主要商品・サービス</h2>
            <div className={fieldSetClass}>
                {renderTextAreaWithAi('main_product_summary' as keyof AccountStrategyFormData, '主要商品群の分析サマリー', 4, undefined, "提供する主な商品やサービス群に共通する特徴、顧客への提供価値、市場でのポジショニングなど、アカウント戦略の基盤となる商品情報を記述してください。商品管理ページに登録された情報を元にAIが要約・分析します。", '/api/v1/profile/suggest-product-summary', isGeneratingProductSummary, setIsGeneratingProductSummary)}
            </div>
        </section>
        
        <section>
            <h2 className={sectionTitleClass}>12の教育要素 - アカウント基本方針</h2>
            <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
                 <button
                    type="button"
                    onClick={handleGenerateBasePoliciesDraft}
                    disabled={isGeneratingBasePolicies || isSubmitting}
                    className="w-full sm:w-auto px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-md shadow-sm transition"
                >
                    {isGeneratingBasePolicies ? "AIが基本方針ドラフト作成中..." : "AIに12の基本方針を一括ドラフトさせる"}
                </button>
                <p className="mt-2 text-xs text-gray-500">「アカウント目的」「提供価値」「商品概要」「ターゲット顧客」の入力後、AIが一括で基本方針のドラフトを作成します。</p>
            </div>
            <div className={`${fieldSetClass} grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1`}>
                <p className="text-sm text-gray-500 md:col-span-2 mb-3">各教育要素について、あなたのアカウント全体としての基本的な考え方やアプローチ、メッセージの方向性を記述してください。これが各ローンチ戦略の土台となります。</p>
                {basePolicyElementsDefinition.map(element => {
                     // ★ 修正: ここでユニークなキーを生成して渡す
                    const uniqueKey = element.key as string;
                    return (
                        <div key={uniqueKey}> {/* mapの各要素にkeyを追加 */}
                           {renderTextAreaWithAi(
                                element.key as keyof AccountStrategyFormData,
                                element.label,
                                4,
                                formData[element.key as keyof AccountStrategyFormData] ? '' : element.description,
                                formData[element.key as keyof AccountStrategyFormData] ? element.description : undefined,
                                undefined, 
                                undefined, 
                                undefined
                            )}
                        </div>
                    );
                })}
            </div>
        </section>

        <section>
            <h2 className={sectionTitleClass}>システム・API連携設定</h2>
            <div className={fieldSetClass}>
                <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
                    <label htmlFor="website" className="block text-sm font-semibold text-gray-700 mb-1">ウェブサイト/主要SNSリンク</label>
                    <input type="url" name="website" id="website" value={formData.website || ''} onChange={handleInputChange} placeholder="https://example.com や https://x.com/your_id など" className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white"/>
                </div>
                <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4">
                  <label htmlFor="preferred_ai_model" className="block text-sm font-semibold text-gray-700 mb-1">優先AIモデル</label>
                  <select id="preferred_ai_model" name="preferred_ai_model" value={formData.preferred_ai_model} onChange={handleInputChange} className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white appearance-none">
                    {aiModelOptions.map(option => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
                <div className="p-4 border rounded-lg shadow-sm bg-slate-50 mb-4 space-y-3">
                    <h3 className="text-sm font-semibold text-gray-700">X (旧Twitter) API 連携情報</h3>
                    <p className="text-xs text-gray-500">ツイートの自動投稿機能を利用するには、<Link href="https://developer.twitter.com/en/portal/projects-and-apps" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800">X Developer Portal</Link>で取得したAPIキーとアクセストークンを設定してください。</p>
                    <div>
                        <label htmlFor="x_api_key" className="block text-xs font-medium text-gray-600">API Key (Consumer Key)</label>
                        <input type="password" name="x_api_key" id="x_api_key" value={formData.x_api_key || ''} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" autoComplete="new-password" placeholder="入力してください"/>
                    </div>
                    <div>
                        <label htmlFor="x_api_secret_key" className="block text-xs font-medium text-gray-600">API Key Secret</label>
                        <input type="password" name="x_api_secret_key" id="x_api_secret_key" value={formData.x_api_secret_key || ''} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" autoComplete="new-password" placeholder="入力してください"/>
                    </div>
                    <div>
                        <label htmlFor="x_access_token" className="block text-xs font-medium text-gray-600">Access Token</label>
                        <input type="password" name="x_access_token" id="x_access_token" value={formData.x_access_token || ''} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" autoComplete="new-password" placeholder="入力してください"/>
                    </div>
                    <div>
                        <label htmlFor="x_access_token_secret" className="block text-xs font-medium text-gray-600">Access Token Secret</label>
                        <input type="password" name="x_access_token_secret" id="x_access_token_secret" value={formData.x_access_token_secret || ''} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white" autoComplete="new-password" placeholder="入力してください"/>
                    </div>
                </div>
            </div>
        </section>

        <div className="pt-8">
          <button
            type="submit"
            disabled={isSubmitting || isLoadingData || isGeneratingPurpose || isGeneratingPersonas || isGeneratingValueProp || isGeneratingBrandVoice || isGeneratingProductSummary || isGeneratingBasePolicies }
            className="w-full flex justify-center items-center py-3 px-6 border border-transparent rounded-lg shadow-lg text-lg font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 transition-all duration-150 ease-in-out transform hover:scale-105"
          >
            {isSubmitting ? '保存中...' : 'アカウント戦略を保存する'}
          </button>
        </div>
      </form>

      {isChatModalOpen && chatTargetFieldKey && (
        <div className="fixed inset-0 bg-gray-800 bg-opacity-75 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col my-auto">
            <div className="flex justify-between items-center p-5 border-b border-gray-200 sticky top-0 bg-white z-10">
              <h3 className="text-lg font-semibold text-gray-800">AIと「{chatTargetFieldLabel}」を深掘り</h3>
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
                <textarea value={currentUserChatMessage} onChange={(e) => setCurrentUserChatMessage(e.target.value)} placeholder="AIへのメッセージを入力 (Shift+Enterで改行)" rows={2} className="flex-grow p-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 resize-none text-sm" onKeyPress={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendAccountStrategyChatMessage(); }}} disabled={isChatLoading} />
                <button onClick={handleSendAccountStrategyChatMessage} disabled={isChatLoading || !currentUserChatMessage.trim()} className="px-4 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 text-sm"> 送信 </button>
              </div>
              <div className="mt-3 flex justify-end"> <button onClick={applyChatResultToAccountStrategyForm} className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"> この内容をフォームに反映 </button> </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}