'use client'

import React, { useEffect, useState, FormEvent, ChangeEvent, useCallback } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useXAccount } from '@/context/XAccountContext' // ★インポート
import XAccountGuard from '@/components/XAccountGuard' // ★インポート
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { toast } from 'react-hot-toast'

// --- 型定義 (元のまま) ---
type InitialPostType = "follow_reason" | "self_introduction" | "value_tips" | "other";
type InitialPostTypeOption = { value: InitialPostType | ""; label: string; placeholder: string; enableGoogleSearch?: boolean; };
const initialPostTypeOptions: InitialPostTypeOption[] = [
  { value: "", label: "初期投稿のタイプを選択してください", placeholder: "まずは投稿タイプを選択してください。", enableGoogleSearch: false },
  { value: "follow_reason", label: "フォローすべき理由（目的/価値提示）", placeholder: "あなたのアカウントをフォローすることで、読者はどんな未来や価値を得られますか？それを端的に示すキーワードを入力してください。", enableGoogleSearch: true },
  { value: "self_introduction", label: "自己紹介（信頼/パーソナリティ）", placeholder: "あなたは何者で、なぜこの情報を発信するのですか？実績やストーリーがあれば、その要点を入力してください。", enableGoogleSearch: false },
  { value: "value_tips", label: "即時的な価値提供（Tips/気づき）", placeholder: "あなたの専門分野に関する、読者が明日から実践できるような具体的でactionableなアドバイスのテーマを入力してください。", enableGoogleSearch: true },
  { value: "other", label: "その他・自由テーマ", placeholder: "AIに生成してほしいツイートのテーマや概要、キーワードなどを自由に入力してください。", enableGoogleSearch: true },
];
type GroundingCitation = { uri?: string | null; title?: string | null; publication_date?: string | null; };
type GroundingInfo = { retrieved_queries?: string[]; citations?: GroundingCitation[]; } | null;

export default function InitialPostGeneratorPage() {
  const { user, session, loading: authLoading } = useAuth();
  const { activeXAccount, isLoading: isXAccountLoading } = useXAccount(); // ★activeXAccountを取得
  const router = useRouter();

  const [selectedPostType, setSelectedPostType] = useState<InitialPostType | "">("");
  const [theme, setTheme] = useState<string>('');
  const [useGoogleSearch, setUseGoogleSearch] = useState<boolean>(false);
  const [generatedTweet, setGeneratedTweet] = useState<string | null>(null);
  const [groundingInfo, setGroundingInfo] = useState<GroundingInfo>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);
  
  // ★ API通信をfetchベースに統一
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

  const handlePostTypeChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const newType = e.target.value as InitialPostType | "";
    setSelectedPostType(newType);
    const selectedOption = initialPostTypeOptions.find(opt => opt.value === newType);
    if (selectedOption && !selectedOption.enableGoogleSearch) { setUseGoogleSearch(false); }
    setGeneratedTweet(null); setGroundingInfo(null);
  };

  // ★ AIツイート生成処理をactiveXAccountに連動
  const handleGenerateTweet = async (e: FormEvent) => {
    e.preventDefault();
    if (!user || !activeXAccount) { toast.error('アカウントを選択してください。'); return; }
    if (!selectedPostType) { toast.error('初期投稿のタイプを選択してください。'); return; }
    if (!theme.trim()) { toast.error('ツイートのテーマを入力してください。'); return; }

    setIsGenerating(true); setGeneratedTweet(null); setGroundingInfo(null); setApiError(null);
    try {
      const payload = {
        x_account_id: activeXAccount.id, // ★ activeXAccountのIDを渡す
        initial_post_type: selectedPostType,
        theme: theme,
        use_Google_Search: useGoogleSearch,
      };
      const response = await apiFetch('/api/v1/initial-tweets/generate', { method: 'POST', body: JSON.stringify(payload) });
      if (response?.generated_tweet) {
        setGeneratedTweet(response.generated_tweet);
        if (response?.grounding_info) { setGroundingInfo(response.grounding_info); }
        toast.success('AIによるツイート案が生成されました！');
      } else {
        throw new Error(response?.message || 'AIからの応答が不正です。');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '初期投稿ツイートの生成に失敗しました。';
      setApiError(errorMessage); toast.error(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  // ★ 下書き保存処理をactiveXAccountに連動
  const handleSaveTweetDraft = async () => {
    if (!generatedTweet) { toast.error('保存するツイートがありません。'); return; }
    if (!user || !activeXAccount) { toast.error('アカウントを選択してください。'); return; }

    setIsSavingDraft(true); setApiError(null);
    try {
      const payload = {
        x_account_id: activeXAccount.id, // ★ activeXAccountのIDを渡す
        content: generatedTweet,
        status: 'draft',
      };
      await apiFetch('/api/v1/tweets', { method: 'POST', body: JSON.stringify(payload) });
      toast.success('ツイートを下書きとして保存しました！');
      setGeneratedTweet(null); setGroundingInfo(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '下書きの保存に失敗しました。';
      setApiError(errorMessage); toast.error(errorMessage);
    } finally {
      setIsSavingDraft(false);
    }
  };
  
  const currentPlaceholder = initialPostTypeOptions.find(opt => opt.value === selectedPostType)?.placeholder || "まずは投稿タイプを選択してください。";
  const showGoogleSearchOption = initialPostTypeOptions.find(opt => opt.value === selectedPostType)?.enableGoogleSearch || false;

  if (authLoading || isXAccountLoading) {
    return <div className="text-center py-20">読み込み中...</div>;
  }

  return (
    <XAccountGuard>
      <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
        <div className="mb-8 flex justify-between items-center">
            <div>
                <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">初期投稿 AIジェネレーター</h1>
                {activeXAccount && <p className="text-indigo-600 font-semibold">対象アカウント: @{activeXAccount.x_username}</p>}
            </div>
            <Link href="/dashboard" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">ダッシュボードへ戻る</Link>
        </div>

        <form onSubmit={handleGenerateTweet} className="space-y-8 bg-white p-8 sm:p-10 shadow-2xl rounded-2xl border border-gray-200 mb-12">
          <div>
            <label htmlFor="initialPostType" className="block text-sm font-semibold text-gray-700 mb-2">1. 生成したい初期投稿のタイプを選択</label>
            <select id="initialPostType" value={selectedPostType} onChange={handlePostTypeChange} required className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500">
              {initialPostTypeOptions.map((option) => (<option key={option.value} value={option.value} disabled={option.value === ""}>{option.label}</option>))}
            </select>
          </div>
          <div>
            <label htmlFor="theme" className="block text-sm font-semibold text-gray-700 mb-2">2. ツイートのテーマやキーワードを入力</label>
            <textarea id="theme" rows={5} value={theme} onChange={(e) => setTheme(e.target.value)} placeholder={currentPlaceholder} required className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500" disabled={!selectedPostType}/>
          </div>
          {showGoogleSearchOption && selectedPostType && (
            <div className="flex items-center">
              <input id="useGoogleSearch" type="checkbox" checked={useGoogleSearch} onChange={(e) => setUseGoogleSearch(e.target.checked)} className="h-4 w-4 text-indigo-600 rounded focus:ring-indigo-500"/>
              <label htmlFor="useGoogleSearch" className="ml-2 block text-sm text-gray-900">最新の情報をGoogle検索して参考にする</label>
            </div>
          )}
          <div className="pt-2">
            <button type="submit" disabled={isGenerating || isSavingDraft || !selectedPostType} className="w-full flex justify-center items-center py-3 px-6 border rounded-lg shadow-md text-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60">
              {isGenerating ? 'AIがツイート生成中...' : 'AIでツイート案を生成する'}
            </button>
          </div>
        </form>

        {apiError && <div className="mb-6 bg-red-50 p-4 rounded-lg border text-red-700">エラー: {apiError}</div>}
        {generatedTweet && !isGenerating && (
          <div className="mt-10 p-6 border rounded-lg bg-gray-50 shadow-lg">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">AIが生成したツイート案:</h3>
            <textarea readOnly value={generatedTweet} rows={7} className="w-full p-4 border rounded-md bg-white focus:ring-2 focus:ring-indigo-500" onClick={(e) => (e.target as HTMLTextAreaElement).select()}/>
            {groundingInfo && (
              <div className="mt-4 p-3 border-t">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">AIが参照した可能性のある情報源:</h4>
                {groundingInfo.citations && groundingInfo.citations.length > 0 && (
                  <ul className="list-disc list-inside pl-2 space-y-1">
                    {groundingInfo.citations.map((cite, idx) => (<li key={`cite-${idx}`} className="text-xs text-gray-500">{cite.title && <span className="font-medium">{cite.title}</span>}{cite.uri && <a href={cite.uri} target="_blank" rel="noopener noreferrer" className="text-indigo-500 hover:underline ml-1">[リンク]</a>}</li>))}
                  </ul>
                )}
              </div>
            )}
            <div className="mt-6 flex justify-end space-x-3">
              <button onClick={() => { setGeneratedTweet(null); setGroundingInfo(null); }} className="px-6 py-2 bg-gray-200 text-gray-700 font-medium rounded-lg hover:bg-gray-300 text-sm">クリア</button>
              <button onClick={handleSaveTweetDraft} disabled={isSavingDraft || isGenerating} className="px-6 py-2 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 disabled:opacity-50 text-sm">
                {isSavingDraft ? '保存中...' : '下書きとして保存'}
              </button>
            </div>
          </div>
        )}
      </div>
    </XAccountGuard>
  );
}