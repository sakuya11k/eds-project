'use client'

import React, { useEffect, useState, FormEvent, useCallback, ChangeEvent } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useXAccount } from '@/context/XAccountContext'
import XAccountGuard from '@/components/XAccountGuard'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { toast } from 'react-hot-toast'

// --- 型定義と定数 ---
const educationElementsOptions = [
  { key: '', label: '教育要素を選択してください', disabled: true },
  { key: 'product_analysis_summary', label: '商品分析の要点' },
  { key: 'target_customer_summary', label: 'ターゲット顧客分析の要点' },
  { type: 'separator', label: 'A. 6つの必須教育' },
  { key: 'edu_s1_purpose', label: '1. 目的の教育' },
  { key: 'edu_s2_trust', label: '2. 信用の教育' },
  { key: 'edu_s3_problem', label: '3. 問題点の教育' },
  { key: 'edu_s4_solution', label: '4. 手段の教育' },
  { key: 'edu_s5_investment', label: '5. 投資の教育' },
  { key: 'edu_s6_action', label: '6. 行動の教育' },
  { type: 'separator', label: 'B. 6つの強化教育' },
  { key: 'edu_r1_engagement_hook', label: '7. 読む・見る教育' },
  { key: 'edu_r2_repetition', label: '8. 何度も聞く教育' },
  { key: 'edu_r3_change_mindset', label: '9. 変化の教育' },
  { key: 'edu_r4_receptiveness', label: '10. 素直の教育' },
  { key: 'edu_r5_output_encouragement', label: '11. アウトプットの教育' },
  { key: 'edu_r6_baseline_shift', label: '12. 基準値の教育／覚悟の教育' },
];

export default function EducationalTweetsPage() {
  const { user, session, loading: authLoading } = useAuth();
  const { activeXAccount, isLoading: isXAccountLoading } = useXAccount();
  const router = useRouter();

  const [selectedEducationElementKey, setSelectedEducationElementKey] = useState<string>('');
  const [tweetTheme, setTweetTheme] = useState<string>('');
  const [generatedTweet, setGeneratedTweet] = useState<string | null>(null);
  const [isLoadingAI, setIsLoadingAI] = useState<boolean>(false);
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

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

  const handleGenerateEducationalTweet = async (e: FormEvent) => {
    e.preventDefault();
    if (!user || !activeXAccount) { toast.error('アカウントを選択してください。'); return; }
    if (!selectedEducationElementKey) { toast.error('教育要素を選択してください。'); return; }
    if (!tweetTheme.trim()) { toast.error('ツイートのテーマやキーワードを入力してください。'); return; }

    setIsLoadingAI(true); setGeneratedTweet(null); setError(null);
    try {
      const payload = {
        x_account_id: activeXAccount.id,
        education_element_key: selectedEducationElementKey,
        theme: tweetTheme,
      };
      const response = await apiFetch('/api/v1/educational-tweets/generate', {
        method: 'POST',
        body: JSON.stringify(payload) // ★ JSON.stringify() を追加
      });
      if (response?.generated_tweet) {
        setGeneratedTweet(response.generated_tweet);
        toast.success('AIによるツイート案が生成されました！');
      } else {
        throw new Error(response?.message || 'AIからの応答が不正です。');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '教育ツイートの生成に失敗しました。';
      setError(errorMessage); toast.error(errorMessage);
    } finally {
      setIsLoadingAI(false);
    }
  };

  const handleSaveTweetDraft = async () => {
    if (!generatedTweet) { toast.error('保存するツイートがありません。'); return; }
    if (!user || !activeXAccount) { toast.error('アカウントを選択してください。'); return; }
    if (generatedTweet.length > 280) {
      toast.error(`ツイートが長すぎます（${generatedTweet.length}/280文字）。\nテキストエリアで編集してから保存してください。`);
      // エラーを分かりやすくするため、テキストエリアを編集可能にするか、
      // あるいは、ここで自動的に280文字に切り詰めるという選択肢もあります。
      // 今回はユーザーに編集を促す形にします。
      return; // 保存処理を中断
    }
    setIsSavingDraft(true); setError(null);
    try {
      const payload = {
        x_account_id: activeXAccount.id,
        content: generatedTweet,
        status: 'draft',
        education_element_key: selectedEducationElementKey,
      };
      await apiFetch('/api/v1/tweets', {
        method: 'POST',
        body: JSON.stringify(payload) // ★ JSON.stringify() を追加
      });
      toast.success('ツイートを下書きとして保存しました！');
      setGeneratedTweet(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ツイートの下書き保存に失敗しました。';
      setError(errorMessage); toast.error(errorMessage);
    } finally {
      setIsSavingDraft(false);
    }
  };
  
  if (authLoading || isXAccountLoading) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="ml-4 text-lg text-gray-600">読み込み中...</p>
      </div>
    );
  }
  
  return (
    <XAccountGuard>
      <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">教育ツイート作成</h1>
            {activeXAccount && <p className="text-indigo-600 font-semibold">対象アカウント: @{activeXAccount.x_username}</p>}
          </div>
          <Link href="/dashboard" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">ダッシュボードへ戻る</Link>
        </div>

        <form onSubmit={handleGenerateEducationalTweet} className="space-y-8 bg-white p-8 sm:p-10 shadow-2xl rounded-2xl border border-gray-200 mb-12">
          <div>
            <label htmlFor="educationElement" className="block text-sm font-semibold text-gray-700 mb-2">1. 教育要素を選択</label>
            <select id="educationElement" value={selectedEducationElementKey} onChange={(e) => setSelectedEducationElementKey(e.target.value)} required className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500">
              {educationElementsOptions.map((option, index) => {
                if (option.type === 'separator') { return <optgroup key={`${option.label}-${index}`} label={option.label}></optgroup> }
                return (<option key={option.key} value={option.key} disabled={option.disabled}>{option.label}</option>)
              })}
            </select>
          </div>
          <div>
            <label htmlFor="tweetTheme" className="block text-sm font-semibold text-gray-700 mb-2">2. ツイートのテーマやキーワードを入力</label>
            <textarea id="tweetTheme" rows={4} value={tweetTheme} onChange={(e) => setTweetTheme(e.target.value)} placeholder="例: 「目的の教育」なら「時間的自由を手に入れることの重要性について、具体的な事例を交えて」など" required className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500"/>
            <p className="mt-2 text-xs text-gray-500">選択した教育要素と、ここに入力したテーマに基づいてAIがツイート案を作成します。</p>
          </div>
          <div className="pt-2">
            <button type="submit" disabled={isLoadingAI || isSavingDraft} className="w-full flex justify-center py-3 px-6 border rounded-lg shadow-md text-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60">
              {isLoadingAI ? 'AIがツイート生成中...' : 'AIでツイート案を生成する'}
            </button>
          </div>
        </form>

        {error && (<div className="mb-6 bg-red-50 p-4 rounded-lg border text-red-700">エラー: {error}</div>)}

        {generatedTweet && !isLoadingAI && (
          <div className="mt-10 p-6 border rounded-lg bg-gray-50 shadow-lg">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">AIが生成したツイート案:</h3>
            <textarea
    value={generatedTweet}
    onChange={(e) => setGeneratedTweet(e.target.value)} // ★ onChangeを追加
    rows={7}
    className="w-full p-4 border border-gray-300 rounded-md bg-white focus:ring-2 focus:ring-indigo-500"
/>

            <div className="mt-6 flex justify-end">
              <button onClick={handleSaveTweetDraft} disabled={isSavingDraft || isLoadingAI} className="px-6 py-2 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 disabled:opacity-50">
                {isSavingDraft ? '保存中...' : '下書きとして保存'}
              </button>
            </div>
          </div>
        )}
      </div>
    </XAccountGuard>
  )
}