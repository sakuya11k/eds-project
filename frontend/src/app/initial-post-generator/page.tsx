'use client'

import React, { useEffect, useState, FormEvent, useCallback } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useXAccount } from '@/context/XAccountContext'
import XAccountGuard from '@/components/XAccountGuard'
import Link from 'next/link'
import { toast } from 'react-hot-toast'

// --- 型定義 ---
interface Inspiration {
  id: string;
  text: string;
  type: string;
  genre: 'author' | 'familiarity';
}
interface PersonaProblem {
  id: string;
  problem_text: string;
  pain_point: string;
}
interface GroundingInfo {
  uri: string;
  title: string;
}
interface TweetResult {
  tweet: string;
  sources: GroundingInfo[];
}
type GenerationMode = 'persona' | 'author';
type AuthorTweetMode = 'A' | 'B';

// --- 定数定義 ---
const SESSION_STORAGE_KEY_PREFIX = 'tweetGeneratorDraft_';
const personaFormatOptions = [
  { value: "【問題解決型】", label: "問題解決型" },
  { value: "【ノウハウ公開型】", label: "ノウハウ公開型" },
  { value: "【気づき共有型】", label: "気づき共有型" },
  { value: "【比較検証型】", label: "比較検証型" },
];
const authorTemplates = [
    { value: "問題提起・深掘り型", label: "問題提起・深掘り型" },
    { value: "持論・逆説型", label: "持論・逆説型" },
    { value: "教訓・ストーリー型", label: "教訓・ストーリー型" },
];
const familiarityTemplates = [
    { value: "あるある失敗談型", label: "あるある失敗談型" },
    { value: "正直な告白型", label: "正直な告白型" },
    { value: "日常の発見型", label: "日常の発見型" },
];


// --- モーダルコンポーネント群 ---

const PersonaProblemSelectModal = ({ 
  isOpen, onClose, onSelect, apiFetch, activeXAccount
}: { 
  isOpen: boolean; onClose: () => void; onSelect: (problemText: string) => void; apiFetch: Function; activeXAccount: any;
}) => {
  const [problems, setProblems] = useState<PersonaProblem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && activeXAccount) {
      const fetchProblems = async () => {
        setIsLoading(true);
        try {
          const data = await apiFetch(`/api/v1/problems?x_account_id=${activeXAccount.id}`);
          setProblems(data || []);
        } catch (error) { toast.error("悩みリストの読み込みに失敗しました。"); }
        finally { setIsLoading(false); }
      };
      fetchProblems();
    }
  }, [isOpen, activeXAccount, apiFetch]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex justify-center items-center p-4">
      <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col relative">
        <div className="flex justify-between items-center border-b pb-3 mb-4">
          <h2 className="text-2xl font-bold">悩みリストからテーマを選択</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-3xl leading-none">×</button>
        </div>
        <div className="overflow-y-auto flex-grow">
          {isLoading ? ( <p className="text-center py-8">読み込み中...</p> ) 
           : problems.length > 0 ? (
            <ul className="space-y-2">
              {problems.map((problem) => (
                <li key={problem.id} onClick={() => onSelect(problem.problem_text)} className="p-3 rounded-md hover:bg-blue-100 cursor-pointer border">
                  <span className="font-mono text-xs bg-gray-200 text-gray-600 rounded px-1 py-0.5 mr-2">{problem.pain_point}</span>
                  {problem.problem_text}
                </li>
              ))}
            </ul>
          ) : ( <p className="text-center py-8 text-gray-500">保存されている悩みがありません。<br /><Link href="/problems/generate" className="text-indigo-600 hover:underline">悩みリスト生成ページ</Link>で作成してください。</p> )}
        </div>
      </div>
    </div>
  );
};

const InspirationSelectModal = ({ 
  isOpen, onClose, onSelect, apiFetch, activeXAccount, genre
}: { 
  isOpen: boolean; onClose: () => void; onSelect: (inspiration: Inspiration) => void; apiFetch: Function; activeXAccount: any; genre: 'author' | 'familiarity';
}) => {
  const [inspirations, setInspirations] = useState<Inspiration[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && activeXAccount) {
      const fetchInspirations = async () => {
        setIsLoading(true);
        try {
          const url = `/api/v1/inspirations?x_account_id=${activeXAccount.id}&genre=${genre}`;
          const data = await apiFetch(url);
          setInspirations(data || []);
        } catch (error) { toast.error("ネタリストの読み込みに失敗しました。"); }
        finally { setIsLoading(false); }
      };
      fetchInspirations();
    }
  }, [isOpen, activeXAccount, apiFetch, genre]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex justify-center items-center p-4">
      <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col relative">
        <div className="flex justify-between items-center border-b pb-3 mb-4">
          <h2 className="text-2xl font-bold">投稿ネタを選択</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-3xl leading-none">×</button>
        </div>
        <div className="overflow-y-auto flex-grow">
          {isLoading ? ( <p className="text-center py-8">読み込み中...</p> ) 
           : inspirations.length > 0 ? (
            <ul className="space-y-2">
              {inspirations.map((item) => (
                <li key={item.id} onClick={() => onSelect(item)} className="p-3 rounded-md hover:bg-blue-100 cursor-pointer border">
                  <span className="font-mono text-xs bg-gray-200 text-gray-600 rounded px-1 py-0.5 mr-2">{item.type}</span>
                  {item.text}
                </li>
              ))}
            </ul>
          ) : ( <p className="text-center py-8 text-gray-500">保存されているネタがありません。<br /><Link href="/problems/generate" className="text-indigo-600 hover:underline">投稿ネタ生成ページ</Link>で作成してください。</p> )}
        </div>
      </div>
    </div>
  );
};


// --- メインコンポーネント ---
export default function UniversalTweetGeneratorPage() {
  const { session } = useAuth();
  const { activeXAccount } = useXAccount();

  // --- State定義 ---
  const [activeTab, setActiveTab] = useState<GenerationMode>('persona');
  const [authorTweetMode, setAuthorTweetMode] = useState<AuthorTweetMode>('A');
  const [selectedTemplate, setSelectedTemplate] = useState(authorTemplates[0].value);
  
  const [theme, setTheme] = useState('');
  const [selectedPersonaFormat, setSelectedPersonaFormat] = useState(personaFormatOptions[0].value);
  const [inspirationText, setInspirationText] = useState('');
  const [selectedInspiration, setSelectedInspiration] = useState<Inspiration | null>(null);
  
  const [tweetResult, setTweetResult] = useState<TweetResult | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false);
  const [personaModalOpen, setPersonaModalOpen] = useState(false);
  const [inspirationModalOpen, setInspirationModalOpen] = useState(false);
  const [modalGenre, setModalGenre] = useState<'author' | 'familiarity'>('author');
  const [apiError, setApiError] = useState<string | null>(null);

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
  
  const updateTweetResult = (result: TweetResult | null) => {
    const key = `${SESSION_STORAGE_KEY_PREFIX}${activeTab}`;
    setTweetResult(result);
    if (typeof window !== 'undefined') {
      if (result) {
        sessionStorage.setItem(key, JSON.stringify(result));
      } else {
        sessionStorage.removeItem(key);
      }
    }
  };
  
  useEffect(() => {
    setTheme('');
    setSelectedInspiration(null);
    setInspirationText('');
    setApiError(null);
    const key = `${SESSION_STORAGE_KEY_PREFIX}${activeTab}`;
    if (typeof window !== 'undefined') {
      const savedResult = sessionStorage.getItem(key);
      setTweetResult(savedResult ? JSON.parse(savedResult) : null);
    }
  }, [activeTab]);

  const handleGenerateTweet = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeXAccount) { toast.error('アカウントを選択してください。'); return; }
    
    setIsGenerating(true);
    setApiError(null);
    updateTweetResult(null);

    try {
      let endpoint = '';
      let payload: any = { x_account_id: activeXAccount.id };

      if (activeTab === 'persona') {
        if (!theme.trim()) { toast.error('テーマを入力してください。'); setIsGenerating(false); return; }
        endpoint = '/api/v1/initial-tweets/generate';
        payload = { ...payload, theme: theme, initial_post_type: 'value_tips', selected_authority_format_by_user: selectedPersonaFormat };
      } else {
        const finalInspirationText = selectedInspiration?.text || inspirationText;
        if (!finalInspirationText.trim()) { toast.error('投稿ネタを選択または入力してください。'); setIsGenerating(false); return; }
        
        endpoint = '/api/v1/tweets/generate-from-inspiration';
        payload = { ...payload, 
          inspiration: selectedInspiration || { text: finalInspirationText, genre: 'author', type: '手動入力' }, 
          tweet_mode: authorTweetMode, 
          template_name: authorTweetMode === 'B' ? selectedTemplate : null 
        };
      }
      
      const response = await apiFetch(endpoint, { method: 'POST', body: JSON.stringify(payload) });
      const newResult: TweetResult = {
        tweet: response.generated_tweet,
        sources: response.grounding_info || [],
      };
      updateTweetResult(newResult);
      toast.success('AIによるツイート案が生成されました！');

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ツイートの生成に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveTweetDraft = async () => {
    if (!tweetResult?.tweet) { toast.error('保存するツイートがありません。'); return; }
    if (!activeXAccount) { toast.error('アカウントを選択してください。'); return; }
    setIsSavingDraft(true);
    setApiError(null);
    try {
      const payload = { x_account_id: activeXAccount.id, content: tweetResult.tweet, status: 'draft' };
      await apiFetch('/api/v1/tweets', { method: 'POST', body: JSON.stringify(payload) });
      toast.success('ツイートを下書きとして保存しました！');
      updateTweetResult(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '下書きの保存に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleTweetTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (tweetResult) {
      updateTweetResult({ ...tweetResult, tweet: e.target.value });
    }
  };

  const openInspirationModal = (genre: 'author' | 'familiarity') => {
    setModalGenre(genre);
    setInspirationModalOpen(true);
  };

  return (
    <XAccountGuard>
      <PersonaProblemSelectModal 
        isOpen={personaModalOpen}
        onClose={() => setPersonaModalOpen(false)}
        onSelect={(problemText) => {
          setTheme(problemText);
          setPersonaModalOpen(false);
        }}
        apiFetch={apiFetch}
        activeXAccount={activeXAccount}
      />
      <InspirationSelectModal 
        isOpen={inspirationModalOpen}
        onClose={() => setInspirationModalOpen(false)}
        onSelect={(inspiration) => {
          setSelectedInspiration(inspiration);
          setInspirationText('');
          if (inspiration.genre === 'author') setSelectedTemplate(authorTemplates[0].value);
          if (inspiration.genre === 'familiarity') setSelectedTemplate(familiarityTemplates[0].value);
          setInspirationModalOpen(false);
        }}
        apiFetch={apiFetch}
        activeXAccount={activeXAccount}
        genre={modalGenre}
      />

      <div className="max-w-4xl mx-auto py-12 px-4">
        <div className="mb-8 flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-extrabold text-gray-900">AIツイートアシスタント</h1>
              {activeXAccount && <p className="text-indigo-600 font-semibold">対象: @{activeXAccount.x_username}</p>}
            </div>
            <Link href="/dashboard" className="text-sm text-indigo-600 hover:underline">← ダッシュボード</Link>
        </div>
        
        <div className="flex space-x-1 bg-gray-200 p-1 rounded-lg mb-8">
          <button onClick={() => setActiveTab('persona')} className={`w-full py-2 px-4 rounded-md text-sm font-semibold transition-colors ${activeTab === 'persona' ? 'bg-white shadow text-gray-900' : 'bg-transparent text-gray-600 hover:bg-gray-300'}`}>ペルソナ向け</button>
          <button onClick={() => setActiveTab('author')} className={`w-full py-2 px-4 rounded-md text-sm font-semibold transition-colors ${activeTab === 'author' ? 'bg-white shadow text-gray-900' : 'bg-transparent text-gray-600 hover:bg-gray-300'}`}>筆者向け (権威性/親近感)</button>
        </div>

        <form onSubmit={handleGenerateTweet} className="space-y-6 bg-white p-8 shadow-xl rounded-2xl border">
          {activeTab === 'persona' ? (
            <>
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label htmlFor="theme" className="block text-sm font-semibold text-gray-800">1. 解決したい「悩み」や「テーマ」</label>
                  <button type="button" onClick={() => setPersonaModalOpen(true)} className="text-sm bg-blue-100 text-blue-800 font-semibold px-3 py-1 rounded-md hover:bg-blue-200">悩みリストから選ぶ</button>
                </div>
                <textarea id="theme" rows={3} value={theme} onChange={(e) => setTheme(e.target.value)} placeholder="ここに自由記述、またはリストから選択" required className="w-full p-3 border rounded-md"/>
              </div>
              <div>
                <label htmlFor="personaFormat" className="block text-sm font-semibold text-gray-800 mb-2">2. 「権威性の型」を選択</label>
                <select id="personaFormat" value={selectedPersonaFormat} onChange={(e) => setSelectedPersonaFormat(e.target.value)} className="w-full p-3 border rounded-md bg-white">
                  {personaFormatOptions.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
                </select>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-gray-800">1. 投稿の元ネタ</label>
                <div className="p-4 border rounded-lg space-y-4 bg-gray-50">
                  <p className="text-xs text-gray-500">下のボタンからリストで選択するか、テキストエリアに直接入力してください。</p>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => openInspirationModal('author')} className="flex-1 text-sm bg-white p-2 rounded-md hover:bg-gray-100 border">権威性のネタから選ぶ</button>
                    <button type="button" onClick={() => openInspirationModal('familiarity')} className="flex-1 text-sm bg-white p-2 rounded-md hover:bg-gray-100 border">親近感のネタから選ぶ</button>
                  </div>
                  <textarea 
                    value={selectedInspiration ? selectedInspiration.text : inspirationText} 
                    onChange={(e) => {
                      setInspirationText(e.target.value);
                      setSelectedInspiration(null);
                    }} 
                    placeholder="ここに自由記述、またはリストから選択" 
                    rows={3} 
                    className="w-full p-3 border rounded-md"
                    readOnly={!!selectedInspiration}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-gray-800">2. ツイート生成モードを選択</label>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setAuthorTweetMode('A')} className={`flex-1 py-2 px-3 text-sm rounded-md border ${authorTweetMode === 'A' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white hover:bg-gray-50'}`}>モードA: ネタを整理</button>
                  <button type="button" onClick={() => setAuthorTweetMode('B')} className={`flex-1 py-2 px-3 text-sm rounded-md border ${authorTweetMode === 'B' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white hover:bg-gray-50'}`}>モードB: 型で構成</button>
                </div>
              </div>

              {authorTweetMode === 'B' && (
                <div className="space-y-2">
                  <label htmlFor="templateSelect" className="block text-sm font-semibold text-gray-800">3. 構成テンプレートを選択</label>
                  <select id="templateSelect" value={selectedTemplate} onChange={(e) => setSelectedTemplate(e.target.value)} className="w-full p-3 border rounded-md bg-white">
                    {(selectedInspiration?.genre === 'author' || (!selectedInspiration && modalGenre === 'author') ? authorTemplates : familiarityTemplates).map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}
          
          <div>
            <button type="submit" disabled={isGenerating} className="w-full py-3 px-6 bg-indigo-600 text-white font-bold rounded-lg shadow-lg hover:bg-indigo-700 disabled:opacity-50">
              {isGenerating ? 'AIが思考中...' : 'ツイートを生成する'}
            </button>
          </div>
        </form>
        
        {apiError && <div className="mt-6 bg-red-50 p-4 rounded-lg border text-red-700">エラー: {apiError}</div>}
        
        {tweetResult && (
          <div className="mt-12 space-y-8">
            <section>
              <h2 className="text-2xl font-bold text-gray-800 mb-4">生成されたツイート案</h2>
              <textarea value={tweetResult.tweet} onChange={handleTweetTextChange} rows={10} className="w-full p-4 border rounded-md bg-gray-50"/>
            </section>

            {tweetResult.sources.length > 0 && (
              <section>
                <h3 className="text-lg font-semibold text-gray-700">参照元情報 (Google検索)</h3>
                <ul className="list-disc list-inside mt-2 space-y-1 text-sm text-gray-500">
                  {tweetResult.sources.map((source, index) => (
                    <li key={index}>
                      <a href={source.uri} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        {source.title || source.uri}
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <div className="pt-6 flex justify-end">
              <button onClick={handleSaveTweetDraft} disabled={isSavingDraft || isGenerating} className="px-8 py-3 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 disabled:opacity-50">
                {isSavingDraft ? '保存中...' : '下書きとして保存'}
              </button>
            </div>
          </div>
        )}
      </div>
    </XAccountGuard>
  );
}