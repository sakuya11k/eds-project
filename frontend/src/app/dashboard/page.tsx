

'use client';

import { useXAccount, XAccount } from '@/context/XAccountContext'; // XAccount型をインポート
import { FormEvent, useState } from 'react';



export default function DashboardPage() {
  const { 
    xAccounts, 
    activeXAccount, 
    isLoading, 
    addXAccount, 
    deleteXAccount, 
    setActiveXAccount 
  } = useXAccount();

  const [newAccount, setNewAccount] = useState({
    x_username: '',
    api_key: '',
    api_key_secret: '',
    access_token: '',
    access_token_secret: '',
  });

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setNewAccount(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      if (Object.values(newAccount).some(field => field === '')) {
        throw new Error('すべてのフィールドを入力してください。');
      }
      await addXAccount(newAccount);
      setIsModalOpen(false);
      setNewAccount({ x_username: '', api_key: '', api_key_secret: '', access_token: '', access_token_secret: '' });
    } catch (err: unknown) {
      console.error(err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('アカウントの追加中に不明なエラーが発生しました。');
      }
    } finally {
      setIsSubmitting(false);
    }
  };
  
  if (isLoading) {
    return <div className="p-8 text-center">読み込み中...</div>;
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6">アカウント管理</h1>

      <div className="mb-8 p-4 border rounded-lg bg-gray-50 dark:bg-gray-800 dark:border-gray-700">
        <h2 className="text-xl font-semibold mb-2">現在のアクティブアカウント</h2>
        {activeXAccount ? (
          <p className="text-lg font-mono bg-blue-100 text-blue-800 px-3 py-1 rounded-md inline-block">
            @{activeXAccount.x_username}
          </p>
        ) : (
          <p className="text-gray-500">Xアカウントを登録または選択してください。</p>
        )}
      </div>

      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-semibold">登録済みアカウント</h2>
        <button onClick={() => setIsModalOpen(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300" disabled={isSubmitting}>
          ＋ 新しいアカウントを追加
        </button>
      </div>

      <div className="space-y-4">
        {xAccounts.length > 0 ? (
          xAccounts.map((account: XAccount) => (
            <div key={account.id} className="flex items-center justify-between p-4 border rounded-lg shadow-sm bg-white dark:bg-gray-800 dark:border-gray-700">
              <div>
                <p className="font-bold text-lg">@{account.x_username}</p>
                <p className="text-sm text-gray-500">ID: {account.id}</p>
              </div>
              <div className="flex items-center space-x-4">
                {account.is_active ? (
                  <span className="px-3 py-1 text-sm font-semibold text-green-800 bg-green-100 rounded-full">
                    アクティブ
                  </span>
                ) : (
                  <button onClick={() => setActiveXAccount(account.id)} className="px-3 py-1 text-sm text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 dark:bg-gray-600 dark:text-gray-200 dark:hover:bg-gray-500">
                    アクティブにする
                  </button>
                )}
                <button onClick={() => deleteXAccount(account.id)} className="px-3 py-1 text-sm text-red-600 hover:text-red-800">
                  削除
                </button>
              </div>
            </div>
          ))
        ) : (
          <p className="text-center text-gray-500 py-8">登録されているアカウントはありません。</p>
        )}
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
          <div className="bg-white dark:bg-gray-900 p-8 rounded-lg shadow-2xl w-full max-w-lg">
            <h2 className="text-2xl font-bold mb-4">新しいXアカウントを追加</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <input type="text" name="x_username" value={newAccount.x_username} onChange={handleInputChange} placeholder="Xのユーザー名 (@なし)" className="w-full p-2 border rounded dark:bg-gray-800 dark:border-gray-700" required />
              <input type="password" name="api_key" value={newAccount.api_key} onChange={handleInputChange} placeholder="API Key" className="w-full p-2 border rounded dark:bg-gray-800 dark:border-gray-700" required />
              <input type="password" name="api_key_secret" value={newAccount.api_key_secret} onChange={handleInputChange} placeholder="API Key Secret" className="w-full p-2 border rounded dark:bg-gray-800 dark:border-gray-700" required />
              <input type="password" name="access_token" value={newAccount.access_token} onChange={handleInputChange} placeholder="Access Token" className="w-full p-2 border rounded dark:bg-gray-800 dark:border-gray-700" required />
              <input type="password" name="access_token_secret" value={newAccount.access_token_secret} onChange={handleInputChange} placeholder="Access Token Secret" className="w-full p-2 border rounded dark:bg-gray-800 dark:border-gray-700" required />
              
              {error && <p className="text-red-500 text-sm">{error}</p>}

              <div className="flex justify-end space-x-4 mt-6">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600" disabled={isSubmitting}>
                  キャンセル
                </button>
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-400" disabled={isSubmitting}>
                  {isSubmitting ? '追加中...' : '追加する'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}