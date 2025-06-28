'use client'

import React, { useState, useCallback, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useXAccount } from '@/context/XAccountContext';
import XAccountGuard from '@/components/XAccountGuard';
import Link from 'next/link';
import { toast } from 'react-hot-toast';

// ★★★ 型定義を汎用的な「Inspiration」に統一 ★★★
interface Inspiration {
  id?: string;
  created_at?: string;
  text: string;
  // problem_text と text を統一し、type と pain_point を統一
  type: string; 
  genre: 'persona' | 'author' | 'familiarity';
  status?: string;
  isChecked?: boolean;
}

// ★★★ タブの種類を定義 ★★★
type TabType = 'persona' | 'author' | 'familiarity';

const TAB_CONFIG = {
  persona: {
    label: 'ペルソナの悩み',
    endpoint: '/api/v1/problems',
    generateEndpoint: '/api/v1/problems/generate',
    sessionKey: 'personaProblemsDraft',
    responseKey: 'generated_problems',
    saveKey: 'problems_to_save',
  },
  author: {
    label: '権威性のネタ',
    endpoint: '/api/v1/inspirations',
    generateEndpoint: '/api/v1/inspirations/generate',
    sessionKey: 'authorInspirationsDraft',
    responseKey: 'generated_inspirations',
    saveKey: 'inspirations_to_save',
  },
  familiarity: {
    label: '親近感のネタ',
    endpoint: '/api/v1/inspirations',
    generateEndpoint: '/api/v1/inspirations/generate',
    sessionKey: 'familiarityInspirationsDraft',
    responseKey: 'generated_inspirations',
    saveKey: 'inspirations_to_save',
  },
};

export default function GenerateInspirationsPage() {
  const { session } = useAuth();
  const { activeXAccount } = useXAccount();

  // ★★★ Stateをタブごとに管理 ★★★
  const [activeTab, setActiveTab] = useState<TabType>('persona');
  const [drafts, setDrafts] = useState<Inspiration[]>([]);
  const [savedItems, setSavedItems] = useState<Inspiration[]>([]);
  const [newText, setNewText] = useState('');

  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  
  const currentConfig = TAB_CONFIG[activeTab];

  // ★★★ sessionStorageとstateを同時に更新するヘルパー関数 ★★★
  const updateDrafts = (newDrafts: Inspiration[]) => {
    setDrafts(newDrafts);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem(currentConfig.sessionKey, JSON.stringify(newDrafts));
    }
  };

  const apiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    if (!session?.access_token) throw new Error("認証セッションが無効です。");
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.access_token}`, ...options.headers };
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${url}`, { ...options, headers });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({ message: `サーバーエラー (Status: ${response.status})` }));
      throw new Error(errorBody?.message || errorBody?.error || `APIエラー (Status: ${response.status})`);
    }
    return response.status === 204 || response.headers.get('content-length') === '0' ? null : response.json();
  }, [session]);
  
  // ★★★ 保存済みリストの取得処理をタブに応じて変更 ★★★
  const fetchSavedItems = useCallback(async () => {
    if (!activeXAccount) return;
    try {
      let url = `${currentConfig.endpoint}?x_account_id=${activeXAccount.id}`;
      if (activeTab !== 'persona') {
        url += `&genre=${activeTab}`;
      }
      const data = await apiFetch(url);
      const itemsWithCheckbox = data.map((p: any) => ({ 
        ...p,
        text: p.problem_text || p.text, // データソースの違いを吸収
        type: p.pain_point || p.type,
        isChecked: false 
      }));
      setSavedItems(itemsWithCheckbox);
    } catch (err) {
      toast.error('保存済みリストの読み込みに失敗しました。');
    }
  }, [activeXAccount, apiFetch, activeTab, currentConfig.endpoint]);

  // ★★★ タブが切り替わった時に、データを再取得＆ドラフトを復元 ★★★
  useEffect(() => {
    fetchSavedItems();
    if (typeof window !== 'undefined') {
      const savedDrafts = sessionStorage.getItem(currentConfig.sessionKey);
      setDrafts(savedDrafts ? JSON.parse(savedDrafts) : []);
    }
  }, [fetchSavedItems, currentConfig.sessionKey]);

  const handleGenerate = async () => {
    if (!activeXAccount) { toast.error('対象のアカウントを選択してください。'); return; }
    setIsGenerating(true);
    setApiError(null);
    updateDrafts([]);
    try {
      const payload: { x_account_id: string; genre?: TabType } = { x_account_id: activeXAccount.id };
      if (activeTab !== 'persona') {
        payload.genre = activeTab;
      }
      const response = await apiFetch(currentConfig.generateEndpoint, { method: 'POST', body: JSON.stringify(payload) });
      const newItems = (response[currentConfig.responseKey] || []).map((p: any) => ({
        text: p.problem_text || p.text,
        type: p.pain_point || p.type,
        genre: activeTab,
        isChecked: true,
      }));
      updateDrafts(newItems);
      toast.success(`AIによる${currentConfig.label}が生成されました！`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '生成に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!activeXAccount) { toast.error('対象のアカウントを選択してください。'); return; }
    const itemsToSave = drafts.filter(p => p.isChecked);
    if (itemsToSave.length === 0) { toast.error('保存する項目を1つ以上選択してください。'); return; }
    setIsSaving(true);
    setApiError(null);
    try {
      const payload = {
        x_account_id: activeXAccount.id,
        [currentConfig.saveKey]: itemsToSave,
      };
      await apiFetch(currentConfig.endpoint, { method: 'POST', body: JSON.stringify(payload) });
      toast.success(`${itemsToSave.length}件の項目を保存しました！`);
      updateDrafts([]);
      await fetchSavedItems();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '保存に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (itemIds: string[]) => {
    if (itemIds.length === 0) { toast.error('削除する項目を1つ以上選択してください。'); return; }
    if (!window.confirm(`${itemIds.length}件の項目を本当に削除しますか？`)) { return; }
    setIsDeleting(true);
    setApiError(null);
    try {
      // ★★★ 削除キーを動的に変更 ★★★
      const idKey = activeTab === 'persona' ? 'problem_ids' : 'inspiration_ids';
      const payload = { [idKey]: itemIds };
      await apiFetch(currentConfig.endpoint, { method: 'DELETE', body: JSON.stringify(payload) });
      toast.success(`${itemIds.length}件の項目を削除しました。`);
      await fetchSavedItems();
    } catch (err) {
       const errorMessage = err instanceof Error ? err.message : '削除に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleManualAdd = () => {
    if (newText.trim() === '') {
      toast.error('追加する内容を入力してください。');
      return;
    }
    const newItem: Inspiration = {
      text: newText.trim(),
      type: '手動追加',
      genre: activeTab,
      isChecked: true,
    };
    updateDrafts([newItem, ...drafts]);
    setNewText('');
    toast.success('ドラフトに追加しました。');
  };

  const handleDraftCheckboxChange = (index: number) => {
    const updated = [...drafts];
    updated[index].isChecked = !updated[index].isChecked;
    updateDrafts(updated);
  };
  
  const handleSavedCheckboxChange = (index: number) => {
    const updated = [...savedItems];
    updated[index].isChecked = !updated[index].isChecked;
    setSavedItems(updated);
  };

  const handleSelectAllDrafts = (checked: boolean) => {
    updateDrafts(drafts.map(p => ({ ...p, isChecked: checked })));
  };
  
  const handleSelectAllSaved = (checked: boolean) => {
    setSavedItems(savedItems.map(p => ({ ...p, isChecked: checked })));
  };

  const selectedSavedItemIds = savedItems.filter(p => p.isChecked).map(p => p.id!);
  const allDraftsSelected = drafts.length > 0 && drafts.every(p => p.isChecked);
  const allSavedSelected = savedItems.length > 0 && savedItems.every(p => p.isChecked);

  return (
    <XAccountGuard>
      <div className="max-w-4xl mx-auto py-12 px-4 space-y-12">
        <section>
          <div className="flex justify-between items-center mb-4">
            {/* ★★★ ページタイトルを変更 ★★★ */}
            <h1 className="text-3xl font-extrabold text-gray-900">投稿ネタ生成 (AI)</h1>
            <Link href="/dashboard" className="text-sm text-indigo-600 hover:underline">← ダッシュボード</Link>
          </div>
          {activeXAccount && <p className="text-indigo-600 font-semibold mb-4">対象: @{activeXAccount.x_username}</p>}

          {/* ★★★ タブ切り替えUI ★★★ */}
          <div className="flex space-x-1 bg-gray-200 p-1 rounded-lg mb-8">
            {Object.entries(TAB_CONFIG).map(([key, config]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key as TabType)}
                className={`w-full py-2 px-4 rounded-md text-sm font-semibold transition-colors ${
                  activeTab === key ? 'bg-white shadow text-gray-900' : 'bg-transparent text-gray-600 hover:bg-gray-300'
                }`}
              >
                {config.label}
              </button>
            ))}
          </div>

          <div className="bg-white p-8 shadow-xl rounded-2xl border">
            <p className="text-gray-600 mb-4">AIがアカウント戦略に基づき、ツイートのネタになるアイデアを複数生成します。</p>
            <button onClick={handleGenerate} disabled={isGenerating || isSaving || isDeleting} className="w-full py-3 px-6 bg-indigo-600 text-white font-bold rounded-lg shadow-lg hover:bg-indigo-700 disabled:opacity-50">
              {isGenerating ? 'AIが思考中...' : `${currentConfig.label}を生成する`}
            </button>
          </div>
        </section>

        {apiError && <div className="mt-6 bg-red-50 p-4 rounded-lg border text-red-700">エラー: {apiError}</div>}
        
        <section className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-800">ドラフトリスト</h2>
          <div className="flex gap-2">
            <input type="text" value={newText} onChange={(e) => setNewText(e.target.value)} placeholder="新しいネタをここに入力..." className="flex-grow p-2 border rounded-lg" onKeyDown={(e) => e.key === 'Enter' && handleManualAdd()}/>
            <button onClick={handleManualAdd} className="px-6 py-2 bg-blue-500 text-white font-semibold rounded-lg hover:bg-blue-600">追加</button>
          </div>
          {drafts.length > 0 && (
            <>
              <div className="flex items-center border-b pb-2"><input type="checkbox" id="select-all-drafts" checked={allDraftsSelected} onChange={(e) => handleSelectAllDrafts(e.target.checked)} className="h-5 w-5 rounded"/><label htmlFor="select-all-drafts" className="ml-3 font-semibold">すべて選択 / 解除</label></div>
              <div className="space-y-3 max-h-96 overflow-y-auto p-4 border rounded-lg bg-gray-50">
                {drafts.map((item, index) => (
                  <div key={`${activeTab}-draft-${index}`} className="flex items-start">
                    <input type="checkbox" id={`draft-${index}`} checked={item.isChecked} onChange={() => handleDraftCheckboxChange(index)} className="h-5 w-5 rounded mt-1" />
                    <label htmlFor={`draft-${index}`} className="ml-3 text-gray-700"><span className="font-mono text-xs bg-gray-200 text-gray-600 rounded px-1 py-0.5 mr-2">{item.type}</span>{item.text}</label>
                  </div>
                ))}
              </div>
              <div className="flex justify-end"><button onClick={handleSave} disabled={isSaving || isGenerating || drafts.filter(p => p.isChecked).length === 0} className="px-8 py-3 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 disabled:opacity-50">{isSaving ? '保存中...' : `選択した ${drafts.filter(p => p.isChecked).length} 件を保存`}</button></div>
            </>
          )}
        </section>
        
        <section className="space-y-6 pt-8 border-t">
            <h2 className="text-2xl font-bold text-gray-800">保存済みリスト ({savedItems.length}件)</h2>
            {savedItems.length > 0 ? (
              <>
                <div className="flex items-center border-b pb-2"><input type="checkbox" id="select-all-saved" checked={allSavedSelected} onChange={(e) => handleSelectAllSaved(e.target.checked)} className="h-5 w-5 rounded"/><label htmlFor="select-all-saved" className="ml-3 font-semibold">すべて選択 / 解除</label></div>
                <div className="space-y-3 max-h-96 overflow-y-auto p-4 border rounded-lg bg-white">
                  {savedItems.map((item, index) => (
                    <div key={item.id} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded">
                      <div className="flex items-start">
                        <input type="checkbox" id={`saved-${index}`} checked={item.isChecked} onChange={() => handleSavedCheckboxChange(index)} className="h-5 w-5 rounded mt-1"/>
                        <label htmlFor={`saved-${index}`} className="ml-3 text-gray-700"><span className="font-mono text-xs bg-gray-200 text-gray-600 rounded px-1 py-0.5 mr-2">{item.type}</span>{item.text}</label>
                      </div>
                      <button onClick={() => handleDelete([item.id!])} disabled={isDeleting} className="text-red-500 hover:text-red-700 text-sm font-semibold disabled:opacity-50 ml-4 flex-shrink-0">削除</button>
                    </div>
                  ))}
                </div>
                <div className="flex justify-end"><button onClick={() => handleDelete(selectedSavedItemIds)} disabled={isDeleting || selectedSavedItemIds.length === 0} className="px-8 py-3 bg-red-600 text-white font-semibold rounded-lg shadow-md hover:bg-red-700 disabled:opacity-50">{isDeleting ? '削除中...' : `選択した ${selectedSavedItemIds.length} 件を一括削除`}</button></div>
              </>
            ) : (
              <p className="text-center text-gray-500 py-8">保存されている項目はありません。</p>
            )}
        </section>
      </div>
    </XAccountGuard>
  );
}