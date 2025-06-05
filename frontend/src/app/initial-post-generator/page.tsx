// src/app/initial-post-generator/page.tsx
'use client'

import React, { useEffect, useState, FormEvent, ChangeEvent } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient'
import { toast } from 'react-hot-toast'

// 初期投稿タイプの定義
type InitialPostType = "follow_reason" | "self_introduction" | "value_tips" | "other";

type InitialPostTypeOption = {
  value: InitialPostType | "";
  label: string;
  placeholder: string;
  enableGoogleSearch?: boolean; // Google検索オプションを表示するかどうか
};

const initialPostTypeOptions: InitialPostTypeOption[] = [
  { value: "", label: "初期投稿のタイプを選択してください", placeholder: "まずは投稿タイプを選択してください。", enableGoogleSearch: false },
  { 
    value: "follow_reason", 
    label: "フォローすべき理由（目的/価値提示）", 
    placeholder: "あなたのアカウントをフォローすることで、読者はどんな未来や価値を得られますか？それを端的に示すキーワードを入力してください。",
    enableGoogleSearch: true
  },
  { 
    value: "self_introduction", 
    label: "自己紹介（信頼/パーソナリティ）", 
    placeholder: "あなたは何者で、なぜこの情報を発信するのですか？実績やストーリーがあれば、その要点を入力してください。",
    enableGoogleSearch: false
  },
  { 
    value: "value_tips", 
    label: "即時的な価値提供（Tips/気づき）", 
    placeholder: "あなたの専門分野に関する、読者が明日から実践できるような具体的でactionableなアドバイスのテーマを入力してください。",
    enableGoogleSearch: true
  },
  { 
    value: "other", 
    label: "その他・自由テーマ", 
    placeholder: "AIに生成してほしいツイートのテーマや概要、キーワードなどを自由に入力してください。",
    enableGoogleSearch: true // その他でも検索オプションは有効にしておく
  },
];

// APIからのグラウンディング情報の型（仮）
type GroundingCitation = {
  uri?: string | null;
  title?: string | null;
  publication_date?: string | null;
};
type GroundingInfo = {
  retrieved_queries?: string[];
  citations?: GroundingCitation[];
  // 他の可能性のあるフィールド
} | null;


export default function InitialPostGeneratorPage() {
  const { user, loading: authLoading, signOut } = useAuth();
  const router = useRouter();

  const [selectedPostType, setSelectedPostType] = useState<InitialPostType | "">("");
  const [theme, setTheme] = useState<string>('');
  const [useGoogleSearch, setUseGoogleSearch] = useState<boolean>(false);
  
  const [generatedTweet, setGeneratedTweet] = useState<string | null>(null);
  const [groundingInfo, setGroundingInfo] = useState<GroundingInfo>(null);
  
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // 認証チェック
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  const handlePostTypeChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const newType = e.target.value as InitialPostType | "";
    setSelectedPostType(newType);
    // タイプの変更時にGoogle検索オプションのデフォルト値をリセットする（任意）
    const selectedOption = initialPostTypeOptions.find(opt => opt.value === newType);
    if (selectedOption && !selectedOption.enableGoogleSearch) {
        setUseGoogleSearch(false);
    }
    setGeneratedTweet(null); // タイプ変更時は生成結果をクリア
    setGroundingInfo(null);
  };

  const handleGenerateTweet = async (e: FormEvent) => {
    e.preventDefault();
    if (!user) {
      toast.error('ログインが必要です。');
      return;
    }
    if (!selectedPostType) {
      toast.error('初期投稿のタイプを選択してください。');
      return;
    }
    if (!theme.trim()) {
      toast.error('ツイートのテーマやキーワードを入力してください。');
      return;
    }

    setIsGenerating(true);
    setGeneratedTweet(null);
    setGroundingInfo(null);
    setApiError(null);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。");
      }

      const payload = {
        initial_post_type: selectedPostType,
        theme: theme,
        use_Google_Search: useGoogleSearch,
      };

      const response = await axios.post(
        'http://localhost:5001/api/v1/initial-tweets/generate',
        payload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );

      if (response.data?.generated_tweet) {
        setGeneratedTweet(response.data.generated_tweet);
        if(response.data?.grounding_info) {
            setGroundingInfo(response.data.grounding_info);
        }
        toast.success('AIによるツイート案が生成されました！');
      } else {
        throw new Error(response.data?.message || 'AIからの応答が不正です。');
      }
    } catch (err: unknown) {
      console.error('初期投稿ツイート生成エラー:', err);
      let errorMessage = '初期投稿ツイートの生成に失敗しました。';
      if (axios.isAxiosError(err) && err.response?.data?.error) {
        errorMessage = err.response.data.error;
      } else if (axios.isAxiosError(err) && err.response?.data?.message) {
        errorMessage = err.response.data.message;
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveTweetDraft = async () => {
    if (!generatedTweet) {
      toast.error('保存するツイートがありません。');
      return;
    }
    if (!user) {
      toast.error('ログインが必要です。');
      return;
    }

    setIsSavingDraft(true);
    setApiError(null);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。");
      }
      const payload = {
        content: generatedTweet,
        status: 'draft',
        // education_element_key や launch_id は初期投稿では基本的に null
      };
      await axios.post(
        'http://localhost:5001/api/v1/tweets',
        payload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      toast.success('ツイートを下書きとして保存しました！');
      setGeneratedTweet(null); // 保存後はクリア
      setGroundingInfo(null);
    } catch (err: unknown) {
      console.error('ツイート下書き保存エラー:', err);
      let errorMessage = 'ツイートの下書き保存に失敗しました。';
       if (axios.isAxiosError(err) && err.response?.data?.message) {
           errorMessage = err.response.data.message;
      } else if (err instanceof Error) {
           errorMessage = err.message;
      }
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSavingDraft(false);
    }
  };
  
  const currentPlaceholder = initialPostTypeOptions.find(opt => opt.value === selectedPostType)?.placeholder || "まずは投稿タイプを選択してください。";
  const showGoogleSearchOption = initialPostTypeOptions.find(opt => opt.value === selectedPostType)?.enableGoogleSearch || false;

  if (authLoading) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="ml-4 text-lg text-gray-600">認証情報を確認中...</p>
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

  return (
    <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="mb-8">
        <Link href="/dashboard" className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center group">
          <svg className="w-5 h-5 mr-2 text-indigo-500 group-hover:text-indigo-700" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd"></path></svg>
          ダッシュボードへ戻る
        </Link>
      </div>
      <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-8 tracking-tight">
        アカウント初期投稿 AIジェネレーター
      </h1>

      <form onSubmit={handleGenerateTweet} className="space-y-8 bg-white p-8 sm:p-10 shadow-2xl rounded-2xl border border-gray-200 mb-12">
        <div>
          <label htmlFor="initialPostType" className="block text-sm font-semibold text-gray-700 mb-2">
            1. 生成したい初期投稿のタイプを選択
          </label>
          <select
            id="initialPostType"
            name="initialPostType"
            value={selectedPostType}
            onChange={handlePostTypeChange}
            required
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white"
          >
            {initialPostTypeOptions.map((option) => (
              <option key={option.value} value={option.value} disabled={option.value === ""} className={option.value === "" ? "text-gray-400" : ""}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="theme" className="block text-sm font-semibold text-gray-700 mb-2">
            2. ツイートのテーマやキーワードを入力
          </label>
          <textarea
            id="theme"
            name="theme"
            rows={5}
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            placeholder={currentPlaceholder}
            required
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm leading-relaxed"
            disabled={!selectedPostType}
          />
        </div>

        {showGoogleSearchOption && selectedPostType && (
          <div className="flex items-center">
            <input
              id="useGoogleSearch"
              name="useGoogleSearch"
              type="checkbox"
              checked={useGoogleSearch}
              onChange={(e) => setUseGoogleSearch(e.target.checked)}
              className="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            />
            <label htmlFor="useGoogleSearch" className="ml-2 block text-sm text-gray-900">
              最新の情報をGoogle検索して参考にする (より具体的な提案が期待できますが、生成に時間がかかる場合があります)
            </label>
          </div>
        )}

        <div className="pt-2">
          <button
            type="submit"
            disabled={isGenerating || isSavingDraft || !selectedPostType}
            className="w-full flex justify-center items-center py-3 px-6 border border-transparent rounded-lg shadow-md text-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition duration-150 ease-in-out"
          >
            {isGenerating ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                AIがツイート生成中...
              </>
            ) : (
              'AIでツイート案を生成する'
            )}
          </button>
        </div>
      </form>

      {apiError && (
        <div className="mb-6 bg-red-50 p-4 rounded-lg border border-red-200">
          <p className="text-sm font-medium text-red-700">エラー: {apiError}</p>
        </div>
      )}

      {generatedTweet && !isGenerating && (
        <div className="mt-10 p-6 border rounded-lg bg-gray-50 shadow-lg">
          <h3 className="text-xl font-semibold text-gray-800 mb-4">AIが生成したツイート案:</h3>
          <textarea
            readOnly
            value={generatedTweet}
            rows={7}
            className="w-full p-4 border border-gray-300 rounded-md bg-white text-gray-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none leading-relaxed"
            onClick={(e) => (e.target as HTMLTextAreaElement).select()}
            aria-label="AIが生成したツイート案"
          />
          {groundingInfo && (
            <div className="mt-4 p-3 border-t border-gray-200">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">AIが参照した可能性のある情報源 (Google検索結果より):</h4>
              {groundingInfo.retrieved_queries && groundingInfo.retrieved_queries.length > 0 && (
                <div className="mb-2">
                  <p className="text-xs text-gray-600 font-medium">実行された検索クエリ:</p>
                  <ul className="list-disc list-inside pl-2">
                    {groundingInfo.retrieved_queries.map((query, idx) => (
                      <li key={`query-${idx}`} className="text-xs text-gray-500">{query}</li>
                    ))}
                  </ul>
                </div>
              )}
              {groundingInfo.citations && groundingInfo.citations.length > 0 && (
                 <div className="mb-2">
                  <p className="text-xs text-gray-600 font-medium">参照された可能性のある引用元:</p>
                  <ul className="list-disc list-inside pl-2">
                    {groundingInfo.citations.map((cite, idx) => (
                      <li key={`cite-${idx}`} className="text-xs text-gray-500">
                        {cite.title && <span className="font-medium">{cite.title}</span>}
                        {cite.uri && <a href={cite.uri} target="_blank" rel="noopener noreferrer" className="text-indigo-500 hover:underline ml-1"> [リンク]</a>}
                        {cite.publication_date && <span className="text-gray-400 ml-1"> ({cite.publication_date})</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {!(groundingInfo.retrieved_queries?.length || groundingInfo.citations?.length) && (
                <p className="text-xs text-gray-500">具体的な参照情報は取得できませんでした。</p>
              )}
            </div>
          )}
          <div className="mt-6 flex justify-end space-x-3">
            <button
              onClick={() => { setGeneratedTweet(null); setGroundingInfo(null); setTheme(''); /* setSelectedPostType(""); */ }}
              className="px-6 py-2 bg-gray-200 text-gray-700 font-medium rounded-lg shadow-sm hover:bg-gray-300 transition duration-150 text-sm"
            >
              クリア
            </button>
            <button
              onClick={handleSaveTweetDraft}
              disabled={isSavingDraft || isGenerating}
              className="px-6 py-2 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 transition duration-300 disabled:opacity-50 text-sm"
            >
              {isSavingDraft ? (
                <>
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  保存中...
                </>
              ) : (
                '下書きとして保存'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}