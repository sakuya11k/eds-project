// src/app/launches/page.tsx
'use client';

import { useEffect, useState, FormEvent, useCallback, ChangeEvent } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useXAccount } from '@/context/XAccountContext'; // ★ XAccountコンテキストをインポート
import XAccountGuard from '@/components/XAccountGuard'; // ★ XAccountGuardをインポート
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'react-hot-toast';

// --- 型定義 (大きな変更はなし) ---
type Product = { id: string; name: string; };
type Launch = {
  id: string;
  x_account_id: string; // ★ x_account_idが必須に
  name: string;
  products?: { name: string; } | null; // JOINで取得する商品情報
  product_name?: string; // 整形後の商品名
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  status: string;
  created_at: string;
};
type LaunchFormData = {
  name: string; product_id: string; description: string;
  start_date: string; end_date: string; goal: string; status: string;
};
const initialLaunchFormData: LaunchFormData = {
  name: '', product_id: '', description: '',
  start_date: '', end_date: '', goal: '', status: 'planning',
};
// --- 型定義ここまで ---


export default function LaunchesPage() {
  const { user, session, loading: authLoading } = useAuth();
  const { activeXAccount, isLoading: isXAccountLoading } = useXAccount(); // ★ activeXAccountを取得
  const router = useRouter();

  const [launches, setLaunches] = useState<Launch[]>([]);
  const [userProducts, setUserProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState<LaunchFormData>(initialLaunchFormData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeletingLaunch, setIsDeletingLaunch] = useState<string | null>(null);

  // --- API通信 (fetchベースに統一) ---
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

  // --- データ取得ロジック (activeXAccountに依存するように変更) ---
  const fetchData = useCallback(async () => {
    // ★ activeXAccountがなければ取得処理を行わない
    if (!user || !activeXAccount) {
        if (!isXAccountLoading) setIsLoading(false);
        return;
    }
    setIsLoading(true);
    try {
      // ★ APIにx_account_idをクエリパラメータとして渡す
      const launchesData = await apiFetch(`/api/v1/launches?x_account_id=${activeXAccount.id}`);
      const populatedLaunches = (launchesData || []).map((launch: Launch) => ({
        ...launch,
        product_name: launch.products?.name || '商品情報なし',
      }));
      setLaunches(populatedLaunches);

      // 商品一覧はユーザーに紐づくので変更なし
      const productsData = await apiFetch('/api/v1/products');
      setUserProducts(productsData || []);

    } catch (err) {
      toast.error(err instanceof Error ? err.message : "データ取得に失敗しました。");
    } finally {
      setIsLoading(false);
    }
  }, [user, activeXAccount, isXAccountLoading, apiFetch]);

  useEffect(() => {
    // ★ activeXAccountが確定してからデータを取得
    if (!isXAccountLoading) {
        fetchData();
    }
  }, [isXAccountLoading, fetchData]);

  // --- フォーム操作 ---
  const handleInputChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;setFormData(prev => ({ ...prev, [name]: e.target.value }));
  };
  const openModalForCreate = () => {
    setFormData(initialLaunchFormData);
    setIsModalOpen(true);
  };
  const closeModal = () => setIsModalOpen(false);

  // --- 作成処理 (activeXAccountを紐付けるように変更) ---
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!user || !activeXAccount) { toast.error('アカウントが選択されていません。'); return; }
    if (!formData.product_id) { toast.error('商品を選択してください。'); return; }
    
    setIsSubmitting(true);
    try {
      const payload = {
        ...formData,
        x_account_id: activeXAccount.id, // ★ activeXAccountのIDをpayloadに含める
        start_date: formData.start_date || null,
        end_date: formData.end_date || null,
      };

      await apiFetch('/api/v1/launches', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      toast.success(`@${activeXAccount.x_username} の新規ローンチを登録しました！`);
      
      fetchData();
      closeModal();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'ローンチの登録に失敗しました。');
    } finally {
      setIsSubmitting(false);
    }
  };

  // --- 削除処理 (変更なし) ---
  const handleDeleteLaunch = async (launchId: string, launchName: string) => {
    if (!window.confirm(`本当にローンチ計画「${launchName}」を削除しますか？`)) return;
    setIsDeletingLaunch(launchId);
    try {
      await apiFetch(`/api/v1/launches/${launchId}`, { method: 'DELETE' });
      toast.success(`ローンチ計画「${launchName}」を削除しました。`);
      fetchData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '削除に失敗しました。');
    } finally {
      setIsDeletingLaunch(null);
    }
  };
  
  if (authLoading) return <div className="text-center py-10">認証情報を確認中...</div>;

  return (
    // ★ ページ全体をXAccountGuardで保護
    <XAccountGuard>
      <div className="max-w-5xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-800">ローンチ計画管理</h1>
            {/* ★ 現在の対象アカウントを表示 */}
            {activeXAccount && <p className="text-indigo-600 font-semibold">対象アカウント: @{activeXAccount.x_username}</p>}
          </div>
          <button onClick={openModalForCreate} className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700">
            新規ローンチ計画作成
          </button>
        </div>

        {(isLoading || isXAccountLoading) && <div className="text-center py-10">データを読み込み中...</div>}
        
        {!isLoading && !isXAccountLoading && launches.length === 0 && (
          <div className="text-center py-10 bg-white shadow-lg rounded-lg p-6">
            <h3 className="mt-2 text-sm font-medium text-gray-900">このアカウントのローンチ計画はまだありません</h3>
            <p className="mt-1 text-sm text-gray-500">最初のローンチ計画を作成しましょう。</p>
          </div>
        )}

        <div className="space-y-6">
          {!isLoading && launches.map(launch => (
            <div key={launch.id} className="bg-white p-6 shadow-lg rounded-xl border">
              <div className="flex flex-col sm:flex-row justify-between items-start">
                <div className="flex-grow mb-4 sm:mb-0">
                  <h2 className="text-xl font-semibold text-indigo-700">{launch.name}</h2>
                  <p className="text-sm text-gray-600">商品: {launch.product_name}</p>
                  <p className="text-sm text-gray-600">期間: {launch.start_date ? new Date(launch.start_date).toLocaleDateString() : '未定'} - {launch.end_date ? new Date(launch.end_date).toLocaleDateString() : '未定'}</p>
                  <p className="text-sm text-gray-600">ステータス: {launch.status}</p>
                </div>
                <div className="flex-shrink-0 sm:ml-4 space-x-2 flex items-center">
                  <Link href={`/launches/${launch.id}/strategy`} className="px-3 py-2 text-sm bg-green-500 text-white rounded-md hover:bg-green-600">戦略編集</Link>
                  <button onClick={() => handleDeleteLaunch(launch.id, launch.name)} disabled={isDeletingLaunch === launch.id} className="px-3 py-2 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 disabled:opacity-50">
                    {isDeletingLaunch === launch.id ? '削除中...' : '削除'}
                  </button>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-3 text-right">作成日: {new Date(launch.created_at).toLocaleString()}</p>
            </div>
          ))}
        </div>

        {isModalOpen && (
          <div className="fixed inset-0 bg-gray-600 bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-lg">
              <h2 className="text-2xl font-bold mb-6">新規ローンチ計画を作成</h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* ... (フォームの中身は変更なし) ... */}
                <div><label htmlFor="name">ローンチ名 *</label><input type="text" name="name" id="name" value={formData.name} onChange={handleInputChange} required className="mt-1 block w-full border-gray-300 rounded-md"/></div>
                <div><label htmlFor="product_id">対象商品 *</label><select name="product_id" id="product_id" value={formData.product_id} onChange={handleInputChange} required className="mt-1 block w-full border-gray-300 rounded-md"><option value="" disabled>選択してください</option>{userProducts.map(p => (<option key={p.id} value={p.id}>{p.name}</option>))}</select></div>
                {/* ... 他のフォーム要素 ... */}
                <div className="flex justify-end space-x-3 pt-4">
                  <button type="button" onClick={closeModal} className="px-4 py-2 bg-gray-200 rounded-md">キャンセル</button>
                  <button type="submit" disabled={isSubmitting} className="px-4 py-2 bg-indigo-600 text-white rounded-md disabled:opacity-50">{isSubmitting ? '登録中...' : '登録する'}</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </XAccountGuard>
  );
}