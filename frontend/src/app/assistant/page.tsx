'use client'

import React, { useState, FormEvent, useCallback, useEffect } from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { useXAccount } from '@/context/XAccountContext'
import XAccountGuard from '@/components/XAccountGuard'
import { toast } from 'react-hot-toast'

// --- 型定義 ---
type Mode = 'rewrite' | 'reply' | 'quote';

interface DirectionButton {
  label: string; // ボタンに表示するテキスト
  value: string; // APIに送る値
}

// --- 定数定義 ---
const directionButtons: Record<Mode, DirectionButton[]> = {
  rewrite: [
    { label: 'より力強く', value: 'より力強く' },
    { label: 'より共感的に', value: 'より共感的に' },
    { label: '構成を整理', value: '構成を整理' },
    { label: '具体例を追加', value: '具体例を追加' },
  ],
  reply: [
    { label: '共感と肯定', value: '共感と肯定' },
    { label: '深掘りの質問', value: '深掘りの質問' },
    { label: '補足情報・別視点', value: '補足情報・別視点' },
    { label: '感謝を伝える', value: '感謝を伝える' },
  ],
  quote: [
    { label: '要約＆学びの提示', value: '要約＆学びの提示' },
    { label: '経験談との接続', value: '経験談との接続' },
    { label: '賛成と意見補強', value: '賛成と意見補強' },
    { label: '敬意ある反対意見', value: '敬意ある反対意見' },
  ],
};

// --- メインコンポーネント ---
export default function AssistantPage() {
  const { session } = useAuth();
  const { activeXAccount } = useXAccount();

  // --- State定義 ---
  const [mode, setMode] = useState<Mode>('reply');
  const [direction, setDirection] = useState<string>('');
  const [guideline, setGuideline] = useState(''); // 「作成の指針」用のState

  const [originalTweetUrl, setOriginalTweetUrl] = useState('');
  const [userText, setUserText] = useState(''); // リライト用の原文

  const [generatedTweet, setGeneratedTweet] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // モードが切り替わったらフォームと結果をリセットする
  useEffect(() => {
    setDirection('');
    setGuideline('');
    setOriginalTweetUrl('');
    setUserText('');
    setGeneratedTweet(null);
    setApiError(null);
  }, [mode]);
  
  // API通信用の共通関数
  const apiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    if (!session?.access_token) throw new Error("認証セッションが無効です。");
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.access_token}`, ...options.headers };
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${url}`, { ...options, headers });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({ message: `サーバーエラー (Status: ${response.status})` }));
      throw new Error(errorBody?.message || errorBody?.error || `APIエラー (Status: ${response.status})`);
    }
    return response.status === 204 || response.headers.get('content-length') === '0' ? null : await response.json();
  }, [session]);

  const handleGenerate = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeXAccount) { toast.error('アカウントを選択してください。'); return; }
    if (!direction) { toast.error('方向性を選択してください。'); return; }

    setIsGenerating(true);
    setApiError(null);
    setGeneratedTweet(null);
    
    // URLからツイートIDを抽出する関数
    const getTweetIdFromUrl = (url: string): string | undefined => {
        const match = url.match(/\/status\/(\d+)/);
        return match?.[1];
    };

    const original_tweet_id = mode !== 'rewrite' ? getTweetIdFromUrl(originalTweetUrl) : undefined;
    if (mode !== 'rewrite' && !original_tweet_id) {
        toast.error('有効なツイートURLを入力してください。');
        setIsGenerating(false);
        return;
    }

    try {
      const payload = {
        x_account_id: activeXAccount.id,
        mode: mode,
        direction: direction,
        guideline: guideline, // "作成の指針" をペイロードに含める
        user_text: mode === 'rewrite' ? userText : undefined,
        original_tweet_id: original_tweet_id,
      };

      const response = await apiFetch('/api/v1/tweets/generate-interactive', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      setGeneratedTweet(response.generated_tweet);
      toast.success('AIからの提案が届きました！');

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ツイートの生成に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!generatedTweet) { toast.error('保存するツイートがありません。'); return; }
    if (!activeXAccount) { toast.error('アカウントを選択してください。'); return; }
    
    setIsSavingDraft(true);
    setApiError(null);

    const getTweetIdFromUrl = (url: string): string | undefined => {
        const match = url.match(/\/status\/(\d+)/);
        return match?.[1];
    };
    
    try {
      const payload = {
        x_account_id: activeXAccount.id,
        content: generatedTweet,
        status: 'draft',
        tweet_type: mode === 'rewrite' ? 'normal' : mode,
        original_tweet_id: mode !== 'rewrite' ? getTweetIdFromUrl(originalTweetUrl) : undefined,
      };

      await apiFetch('/api/v1/tweets', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      toast.success('下書きを保存しました！');
      setGeneratedTweet(null);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '下書きの保存に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSavingDraft(false);
    }
  };


  return (
    <XAccountGuard>
      <div className="max-w-4xl mx-auto py-12 px-4">
        {/* --- ヘッダー --- */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900">インタラクティブ・アシスタント</h1>
            <p className="mt-2 text-gray-500">リプライ、引用、リライトをAIが強力にサポートします。</p>
            {activeXAccount && <p className="text-indigo-600 font-semibold mt-1">対象アカウント: @{activeXAccount.x_username}</p>}
          </div>
          <Link href="/dashboard" className="text-sm text-indigo-600 hover:underline">← ダッシュボード</Link>
        </div>
        
        {/* --- セクションA: モード選択タブ --- */}
        <div className="flex space-x-1 bg-gray-200 p-1 rounded-lg mb-8">
          {(['reply', 'quote', 'rewrite'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`w-full py-2 px-4 rounded-md text-sm font-semibold transition-colors ${mode === m ? 'bg-white shadow text-gray-900' : 'bg-transparent text-gray-600 hover:bg-gray-300'}`}
            >
              {m === 'reply' ? 'リプライ' : m === 'quote' ? '引用リツイート' : 'リライト'}
            </button>
          ))}
        </div>

        <form onSubmit={handleGenerate} className="space-y-8 bg-white p-8 shadow-xl rounded-2xl border">
          
          {/* --- セクションB: 入力フォーム --- */}
          <div>
            <label htmlFor="input-text" className="block text-lg font-semibold text-gray-800 mb-2">
              1. {mode === 'rewrite' ? 'リライトしたい文章' : '対象のツイートURL'}
            </label>
            {mode === 'rewrite' ? (
              <textarea id="input-text" rows={5} value={userText} onChange={(e) => setUserText(e.target.value)} placeholder="ここにあなたのツイート原文を入力してください..." required className="w-full p-3 border rounded-md"/>
            ) : (
              <input id="input-text" type="url" value={originalTweetUrl} onChange={(e) => setOriginalTweetUrl(e.target.value)} placeholder="https://x.com/user/status/12345..." required className="w-full p-3 border rounded-md"/>
            )}
          </div>
          
          {/* --- セクションC: AIへの指示 --- */}
          <div>
            <label className="block text-lg font-semibold text-gray-800 mb-2">2. AIへの指示</label>
            <div className="p-4 border rounded-lg space-y-4 bg-gray-50">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">基本方針を選択してください</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {directionButtons[mode].map((btn) => (
                      <button
                        key={btn.value}
                        type="button"
                        onClick={() => setDirection(btn.value)}
                        className={`py-2 px-3 text-sm rounded-md border transition-all ${direction === btn.value ? 'bg-blue-600 text-white border-blue-600 ring-2 ring-blue-300' : 'bg-white hover:bg-gray-100'}`}
                      >
                        {btn.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">作成の指針 (任意)</h3>
                  <input 
                    type="text" 
                    value={guideline} 
                    onChange={(e) => setGuideline(e.target.value)} 
                    placeholder="例: 元の意見に少し皮肉を込めて反論してほしい" 
                    className="w-full p-2 border rounded-md text-sm" 
                  />
                  <p className="text-xs text-gray-500 mt-1">AIに対する追加の指示や、文章のニュアンスなどを自由に入力します。</p>
                </div>
            </div>
          </div>
          
          {/* --- セクションD: 生成実行ボタン --- */}
          <div>
            <button type="submit" disabled={isGenerating || !direction} className="w-full py-3 px-6 bg-indigo-600 text-white font-bold rounded-lg shadow-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed">
              {isGenerating ? 'AIが思考中...' : '提案を生成する'}
            </button>
          </div>
        </form>
        
        {apiError && <div className="mt-6 bg-red-100 p-4 rounded-lg border border-red-200 text-red-800">{apiError}</div>}
        
        {/* --- 生成結果エリア --- */}
        {generatedTweet !== null && (
          <div className="mt-12 space-y-6">
            <section>
              <h2 className="text-2xl font-bold text-gray-800 mb-4">生成された提案</h2>
              <textarea 
                value={generatedTweet} 
                onChange={(e) => setGeneratedTweet(e.target.value)} 
                rows={8} 
                className="w-full p-4 border rounded-md bg-gray-50 focus:ring-2 focus:ring-indigo-500"
              />
            </section>

            <div className="pt-4 flex justify-end gap-4">
              <button 
                onClick={handleSaveDraft} 
                disabled={isSavingDraft || isGenerating} 
                className="px-8 py-3 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 disabled:opacity-50"
              >
                {isSavingDraft ? '保存中...' : '下書きとして保存'}
              </button>
            </div>
          </div>
        )}
      </div>
    </XAccountGuard>
  );
}