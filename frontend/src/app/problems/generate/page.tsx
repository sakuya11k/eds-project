'use client'

import React, { useState, useCallback, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useXAccount } from '@/context/XAccountContext';
import XAccountGuard from '@/components/XAccountGuard';
import Link from 'next/link';
import { toast } from 'react-hot-toast';

// 型定義
interface Problem {
  id: string;
  created_at: string;
  problem_text: string;
  pain_point: string;
  status: string;
  // UI用のプロパティ
  isChecked?: boolean;
}

export default function GenerateProblemsPage() {
  const { session } = useAuth();
  const { activeXAccount } = useXAccount();

  const [draftProblems, setDraftProblems] = useState<Problem[]>([]);
  const [savedProblems, setSavedProblems] = useState<Problem[]>([]); 

  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // --- API通信 (共通) ---
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
  
  // --- データ取得・操作 ---
  const fetchSavedProblems = useCallback(async () => {
    if (!activeXAccount) return;
    try {
      const data = await apiFetch(`/api/v1/problems?x_account_id=${activeXAccount.id}`);
      const problemsWithCheckbox = data.map((p: Problem) => ({ ...p, isChecked: false }));
      setSavedProblems(problemsWithCheckbox);
    } catch (err) {
      toast.error('保存済み悩みリストの読み込みに失敗しました。');
    }
  }, [activeXAccount, apiFetch]);

  useEffect(() => {
    fetchSavedProblems();
  }, [fetchSavedProblems]);

  const handleGenerateProblems = async () => {
    if (!activeXAccount) { toast.error('対象のアカウントを選択してください。'); return; }
    setIsGenerating(true);
    setApiError(null);
    setDraftProblems([]);
    try {
      const payload = { x_account_id: activeXAccount.id };
      const response = await apiFetch('/api/v1/problems/generate', { method: 'POST', body: JSON.stringify(payload) });
      const problemsWithCheckbox = response.generated_problems.map((p: Problem) => ({ ...p, isChecked: true }));
      setDraftProblems(problemsWithCheckbox);
      toast.success('AIによる悩みリストのドラフトが生成されました！');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '悩みリストの生成に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveProblems = async () => {
    if (!activeXAccount) { toast.error('対象のアカウントを選択してください。'); return; }
    const problemsToSave = draftProblems.filter(p => p.isChecked);
    if (problemsToSave.length === 0) { toast.error('保存する悩みを1つ以上選択してください。'); return; }
    setIsSaving(true);
    setApiError(null);
    try {
      const payload = { x_account_id: activeXAccount.id, problems_to_save: problemsToSave, };
      await apiFetch('/api/v1/problems/save', { method: 'POST', body: JSON.stringify(payload) });
      toast.success(`${problemsToSave.length}件の悩みをデータベースに保存しました！`);
      setDraftProblems([]);
      await fetchSavedProblems();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '悩みの保存に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteProblems = async (problemIds: string[]) => {
    if (problemIds.length === 0) { toast.error('削除する悩みを1つ以上選択してください。'); return; }
    if (!window.confirm(`${problemIds.length}件の悩みを本当に削除しますか？この操作は元に戻せません。`)) { return; }
    setIsDeleting(true);
    setApiError(null);
    try {
      await apiFetch('/api/v1/problems', { method: 'DELETE', body: JSON.stringify({ problem_ids: problemIds }) });
      toast.success(`${problemIds.length}件の悩みを削除しました。`);
      await fetchSavedProblems();
    } catch (err) {
       const errorMessage = err instanceof Error ? err.message : '悩みの削除に失敗しました。';
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  // --- UI操作のためのロジック ---
  const handleDraftCheckboxChange = (index: number) => {
    const updated = [...draftProblems];
    updated[index].isChecked = !updated[index].isChecked;
    setDraftProblems(updated);
  };
  
  const handleSavedCheckboxChange = (index: number) => {
    const updated = [...savedProblems];
    updated[index].isChecked = !updated[index].isChecked;
    setSavedProblems(updated);
  };

  // ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
  // ★ 「すべて選択」のためのロジックを追加 ★
  // ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
  const handleSelectAllDrafts = (checked: boolean) => {
    const updated = draftProblems.map(p => ({ ...p, isChecked: checked }));
    setDraftProblems(updated);
  };
  
  const handleSelectAllSaved = (checked: boolean) => {
    const updated = savedProblems.map(p => ({ ...p, isChecked: checked }));
    setSavedProblems(updated);
  };

  const selectedSavedProblemIds = savedProblems.filter(p => p.isChecked).map(p => p.id);
  const allDraftsSelected = draftProblems.length > 0 && draftProblems.every(p => p.isChecked);
  const allSavedSelected = savedProblems.length > 0 && savedProblems.every(p => p.isChecked);


  return (
    <XAccountGuard>
      <div className="max-w-4xl mx-auto py-12 px-4 space-y-12">
        {/* --- 生成エリア --- */}
        <section>
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-3xl font-extrabold text-gray-900">悩みリスト生成 (AI)</h1>
            <Link href="/dashboard" className="text-sm text-indigo-600 hover:underline">← ダッシュボード</Link>
          </div>
          {activeXAccount && <p className="text-indigo-600 font-semibold mb-8">対象: @{activeXAccount.x_username}</p>}
          <div className="bg-white p-8 shadow-xl rounded-2xl border">
            <p className="text-gray-600 mb-4">AIがペルソナ設定を元に、ツイートのネタになる具体的な悩みを50個生成します。</p>
            <button onClick={handleGenerateProblems} disabled={isGenerating || isSaving || isDeleting} className="w-full py-3 px-6 bg-indigo-600 text-white font-bold rounded-lg shadow-lg hover:bg-indigo-700 disabled:opacity-50">
              {isGenerating ? 'AIがマインドマップ思考で悩みを生成中...' : '悩みリストを50件生成する'}
            </button>
          </div>
        </section>

        {apiError && <div className="mt-6 bg-red-50 p-4 rounded-lg border text-red-700">エラー: {apiError}</div>}
        
        {/* --- ドラフト表示・保存エリア --- */}
        {draftProblems.length > 0 && (
          <section className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-800">生成された悩みリスト (ドラフト)</h2>
              <p className="text-sm text-gray-500">保存したい悩みだけをチェックして保存ボタンを押してください。</p>
            </div>
            {/* ★★★ 「すべて選択」チェックボックスを追加 ★★★ */}
            <div className="flex items-center border-b pb-2">
              <input type="checkbox" id="select-all-drafts" checked={allDraftsSelected} onChange={(e) => handleSelectAllDrafts(e.target.checked)} className="h-5 w-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"/>
              <label htmlFor="select-all-drafts" className="ml-3 font-semibold text-gray-700">すべて選択 / 解除</label>
            </div>
            <div className="space-y-3 max-h-96 overflow-y-auto p-4 border rounded-lg bg-gray-50">
              {draftProblems.map((problem, index) => (
                <div key={index} className="flex items-start">
                  <input type="checkbox" id={`draft-${index}`} checked={problem.isChecked} onChange={() => handleDraftCheckboxChange(index)} className="h-5 w-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 mt-1" />
                  <label htmlFor={`draft-${index}`} className="ml-3 text-gray-700">
                    <span className="font-mono text-xs bg-gray-200 text-gray-600 rounded px-1 py-0.5 mr-2">{problem.pain_point}</span>
                    {problem.problem_text}
                  </label>
                </div>
              ))}
            </div>
             <div className="flex justify-end">
              <button onClick={handleSaveProblems} disabled={isSaving || isGenerating || draftProblems.filter(p => p.isChecked).length === 0} className="px-8 py-3 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 disabled:opacity-50">
                {isSaving ? '保存中...' : `選択した ${draftProblems.filter(p => p.isChecked).length} 件を保存`}
              </button>
            </div>
          </section>
        )}
        
        {/* --- 保存済みリスト表示・削除エリア --- */}
        <section className="space-y-6 pt-8 border-t">
            <div>
              <h2 className="text-2xl font-bold text-gray-800">保存済み悩みリスト ({savedProblems.length}件)</h2>
              <p className="text-sm text-gray-500">削除したい悩みを選択して削除ボタンを押してください。</p>
            </div>

            {savedProblems.length > 0 ? (
              <>
                {/* ★★★ 「すべて選択」チェックボックスを追加 ★★★ */}
                <div className="flex items-center border-b pb-2">
                  <input type="checkbox" id="select-all-saved" checked={allSavedSelected} onChange={(e) => handleSelectAllSaved(e.target.checked)} className="h-5 w-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"/>
                  <label htmlFor="select-all-saved" className="ml-3 font-semibold text-gray-700">すべて選択 / 解除</label>
                </div>
                <div className="space-y-3 max-h-96 overflow-y-auto p-4 border rounded-lg bg-white">
                  {savedProblems.map((problem, index) => (
                    <div key={problem.id} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded">
                      <div className="flex items-start">
                        <input type="checkbox" id={`saved-${index}`} checked={problem.isChecked} onChange={() => handleSavedCheckboxChange(index)} className="h-5 w-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 mt-1"/>
                        <label htmlFor={`saved-${index}`} className="ml-3 text-gray-700">
                           <span className="font-mono text-xs bg-gray-200 text-gray-600 rounded px-1 py-0.5 mr-2">{problem.pain_point}</span>
                           {problem.problem_text}
                        </label>
                      </div>
                      <button onClick={() => handleDeleteProblems([problem.id])} disabled={isDeleting} className="text-red-500 hover:text-red-700 text-sm font-semibold disabled:opacity-50 ml-4 flex-shrink-0">削除</button>
                    </div>
                  ))}
                </div>
                <div className="flex justify-end">
                  <button onClick={() => handleDeleteProblems(selectedSavedProblemIds)} disabled={isDeleting || selectedSavedProblemIds.length === 0} className="px-8 py-3 bg-red-600 text-white font-semibold rounded-lg shadow-md hover:bg-red-700 disabled:opacity-50">
                    {isDeleting ? '削除中...' : `選択した ${selectedSavedProblemIds.length} 件を一括削除`}
                  </button>
                </div>
              </>
            ) : (
              <p className="text-center text-gray-500 py-8">保存されている悩みはありません。</p>
            )}
        </section>

      </div>
    </XAccountGuard>
  );
}