'use client'

import React, { useEffect, useState, FormEvent, useCallback } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useXAccount } from '@/context/XAccountContext'
import XAccountGuard from '@/components/XAccountGuard'
import Link from 'next/link'
import { toast } from 'react-hot-toast'

// 型定義
interface SavedProblem {
  id: string;
  problem_text: string;
  pain_point: string;
}

// 「権威性の型」の選択肢
const authorityFormatOptions = [
  { value: "【問題解決型】", label: "問題解決型" },
  { value: "【ノウハウ公開型】", label: "ノウハウ公開型" },
  { value: "【気づき共有型】", label: "気づき共有型" },
  { value: "【比較検証型】", label: "比較検証型" },
];

// ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
// ★ 悩みリスト選択モーダルコンポーネント ★
// ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
const ProblemSelectModal = ({ 
  isOpen, 
  onClose, 
  onSelect,
  apiFetch,
  activeXAccount,
}: { 
  isOpen: boolean; 
  onClose: () => void; 
  onSelect: (problemText: string) => void;
  apiFetch: (url: string, options?: RequestInit) => Promise<any>;
  activeXAccount: { id: string } | null;
}) => {
  const [savedProblems, setSavedProblems] = useState<SavedProblem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && activeXAccount) {
      const fetchProblems = async () => {
        setIsLoading(true);
        try {
          const data = await apiFetch(`/api/v1/problems?x_account_id=${activeXAccount.id}`);
          setSavedProblems(data);
        } catch (error) {
          toast.error("悩みリストの読み込みに失敗しました。");
        } finally {
          setIsLoading(false);
        }
      };
      fetchProblems();
    }
  }, [isOpen, activeXAccount, apiFetch]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex justify-center items-center">
      <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex justify-between items-center border-b pb-3 mb-4">
          <h2 className="text-2xl font-bold">悩みリストからテーマを選択</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-2xl">×</button>
        </div>
        <div className="overflow-y-auto flex-grow">
          {isLoading ? (
            <p className="text-center py-8">読み込み中...</p>
          ) : savedProblems.length > 0 ? (
            <ul className="space-y-2">
              {savedProblems.map((problem) => (
                <li 
                  key={problem.id} 
                  onClick={() => onSelect(problem.problem_text)}
                  className="p-3 rounded-md hover:bg-blue-100 cursor-pointer border"
                >
                  <span className="font-mono text-xs bg-gray-200 text-gray-600 rounded px-1 py-0.5 mr-2">{problem.pain_point}</span>
                  {problem.problem_text}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-center py-8 text-gray-500">保存されている悩みがありません。<br /><Link href="/problems/generate" className="text-indigo-600 hover:underline">悩みリスト生成ページ</Link>で作成してください。</p>
          )}
        </div>
      </div>
    </div>
  );
};


export default function InitialPostGeneratorPage() {
  const { session } = useAuth();
  const { activeXAccount } = useXAccount();

  // --- State定義 ---
  const [problemToSolve, setProblemToSolve] = useState<string>('');
  const [selectedAuthorityFormat, setSelectedAuthorityFormat] = useState<string>("【問題解決型】");
  const [generatedTweet, setGeneratedTweet] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  
  // ★★★ モーダルの開閉を管理するStateを追加 ★★★
  const [isModalOpen, setIsModalOpen] = useState(false);

  // --- API通信 ---
  const apiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    if (!session?.access_token) throw new Error("認証セッションが無効です。");
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.access_token}`, ...options.headers };
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${url}`, { ...options, headers });
    if (!response.ok) {
        const errorBody = await response.json().catch(() => ({ message: `サーバーエラー (Status: ${response.status})` }));
        throw new Error(errorBody?.message || errorBody?.error || `APIエラー (Status: ${response.status})`);
    }
    return response.status === 204 ? null : await response.json();
  }, [session]);

  // --- イベントハンドラ ---
  const handleGenerateTweet = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeXAccount || !problemToSolve.trim()) {
      toast.error('アカウントと「解決したい悩み」は必須です。');
      return;
    }
    setIsGenerating(true);
    setApiError(null);
    setGeneratedTweet("");
    try {
      const payload = {
        x_account_id: activeXAccount.id,
        initial_post_type: "value_tips",
        theme: problemToSolve,
        selected_authority_format_by_user: selectedAuthorityFormat,
      };
      const response = await apiFetch('/api/v1/initial-tweets/generate', { method: 'POST', body: JSON.stringify(payload) });
      if (response?.generated_tweet) {
        setGeneratedTweet(response.generated_tweet);
        toast.success('AIによるツイートが生成されました！');
      } else {
        throw new Error('AIからの応答が不正です。');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ツイートの生成に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };
  
  const handleSaveTweetDraft = async () => {
    // (変更なし)
    if (!generatedTweet) { toast.error('保存するツイートがありません。'); return; }
    if (!activeXAccount) { toast.error('アカウントを選択してください。'); return; }
    setIsSavingDraft(true);
    setApiError(null);
    try {
      const payload = { x_account_id: activeXAccount.id, content: generatedTweet, status: 'draft' };
      await apiFetch('/api/v1/tweets', { method: 'POST', body: JSON.stringify(payload) });
      toast.success('ツイートを下書きとして保存しました！');
      setGeneratedTweet("");
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
      {/* ★★★ モーダルコンポーネントを配置 ★★★ */}
      <ProblemSelectModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSelect={(problemText) => {
          setProblemToSolve(problemText);
          setIsModalOpen(false);
        }}
        apiFetch={apiFetch}
        activeXAccount={activeXAccount}
      />

      <div className="max-w-4xl mx-auto py-12 px-4">
        <div className="mb-8 flex justify-between items-center">
            <div>
                <h1 className="text-3xl font-extrabold text-gray-900">価値提供ツイート生成 (AIアシスタント)</h1>
                {activeXAccount && <p className="text-indigo-600 font-semibold">対象: @{activeXAccount.x_username}</p>}
            </div>
            <Link href="/dashboard" className="text-sm text-indigo-600 hover:underline">← ダッシュボード</Link>
        </div>

        <form onSubmit={handleGenerateTweet} className="space-y-6 bg-white p-8 shadow-xl rounded-2xl border">
          <div>
            {/* ★★★ ラベルとボタンを横並びに ★★★ */}
            <div className="flex justify-between items-center mb-2">
              <label htmlFor="problemToSolve" className="block text-sm font-semibold text-gray-800">1. 解決したい「悩み」や「テーマ」を入力</label>
              <button 
                type="button" 
                onClick={() => setIsModalOpen(true)}
                className="text-sm bg-blue-100 text-blue-800 font-semibold px-3 py-1 rounded-md hover:bg-blue-200"
              >
                悩みリストから選ぶ
              </button>
            </div>
            <textarea id="problemToSolve" rows={3} value={problemToSolve} onChange={(e) => setProblemToSolve(e.target.value)} placeholder="例：『PCの使い方がわからない』『効果的なSNS運用のコツ』" required className="w-full p-3 border rounded-md"/>
          </div>
          <div>
            <label htmlFor="authorityFormat" className="block text-sm font-semibold text-gray-800 mb-2">2. 「権威性の型」を選択</label>
            <select id="authorityFormat" value={selectedAuthorityFormat} onChange={(e) => setSelectedAuthorityFormat(e.target.value)} className="w-full p-3 border rounded-md bg-white">
              {authorityFormatOptions.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
            </select>
          </div>
          <div>
            <button type="submit" disabled={isGenerating} className="w-full py-3 px-6 bg-indigo-600 text-white font-bold rounded-lg shadow-lg hover:bg-indigo-700 disabled:opacity-50">
              {isGenerating ? 'AIが思考・リサーチ・改善を繰り返しています...' : 'ツイートを生成する'}
            </button>
          </div>
        </form>

        {apiError && <div className="mt-6 bg-red-50 p-4 rounded-lg border text-red-700">エラー: {apiError}</div>}

        {generatedTweet && (
          <div className="mt-12 space-y-8">
            <section>
              <h2 className="text-2xl font-bold text-gray-800 mb-4">生成されたツイート案</h2>
              <textarea value={generatedTweet} onChange={e => setGeneratedTweet(e.target.value)} rows={10} className="w-full p-4 border rounded-md bg-gray-50"/>
            </section>
            <div className="pt-6 flex justify-end">
              <button onClick={handleSaveTweetDraft} disabled={isSavingDraft} className="px-8 py-3 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 disabled:opacity-50">
                {isSavingDraft ? '保存中...' : '下書きとして保存'}
              </button>
            </div>
          </div>
        )}
      </div>
    </XAccountGuard>
  );
}