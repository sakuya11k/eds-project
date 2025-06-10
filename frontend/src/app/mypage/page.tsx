// src/app/mypage/page.tsx
'use client';

import React, { useEffect, useState, FormEvent, ChangeEvent, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'react-hot-toast';

// --- 型定義 ---
// このページで扱うフォームデータを定義。APIキー関連は削除。
export type ProfileFormData = {
  username: string;
  website: string | null;
  preferred_ai_model: string;
};

// APIレスポンスもこの型を基本とする
type ProfileApiResponse = ProfileFormData & {
  id?: string;
  updated_at?: string;
};

// フォームの初期状態
const initialFormData: ProfileFormData = {
  username: '',
  website: '', // 初期値は空文字でOK
  preferred_ai_model: 'gemini-1.5-flash-latest', // 最新モデルをデフォルトに
};

// AIモデルの選択肢
const aiModelOptions = [
  { value: 'gemini-1.5-flash-latest', label: 'Gemini 1.5 Flash (高速・標準)' },
  { value: 'gemini-1.5-pro-latest', label: 'Gemini 1.5 Pro (高性能・高品質)' },
];


export default function MyPage() {
  const { user, session, loading: authLoading, signOut } = useAuth();
  const router = useRouter();

  const [formData, setFormData] = useState<ProfileFormData>(initialFormData);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // --- apiFetch関数をこのコンポーネント内で定義 ---
  // XAccountContextから拝借し、このページ専用に調整
  const apiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    if (!session?.access_token) {
      throw new Error("認証セッションが無効です。再度ログインしてください。");
    }
    
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
      ...options.headers,
    };

    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${url}`, { ...options, headers });
      
    if (!response.ok) {
        let errorBody;
        try {
          errorBody = await response.json();
        } catch (e) {
          throw new Error(`サーバーから予期せぬ応答がありました (Status: ${response.status})`);
        }
        const errorMessage = errorBody?.message || errorBody?.error || `APIリクエストエラー (Status: ${response.status})`;
        throw new Error(errorMessage);
    }
    
    return response.status === 204 ? null : response.json();
  }, [session]);


  // --- プロフィール取得ロジック ---
  useEffect(() => {
    const fetchProfile = async () => {
      // ユーザーセッションがなければ何もしない
      if (!session) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        const fetchedProfile: ProfileApiResponse = await apiFetch('/api/v1/profile');
        if (fetchedProfile) {
          setFormData({
            username: fetchedProfile.username || '',
            website: fetchedProfile.website || '',
            preferred_ai_model: fetchedProfile.preferred_ai_model || initialFormData.preferred_ai_model,
          });
        }
      } catch (error) {
        if (error instanceof Error && error.message.includes('404')) {
          // 404の場合は新規ユーザーなのでエラー表示せず、フォームは初期状態のまま
          toast("ようこそ！まずはプロフィールを設定してください。");
        } else {
          // その他のエラーはトーストで通知
          const errorMessage = error instanceof Error ? error.message : 'プロファイルの取得に失敗しました。';
          toast.error(errorMessage);
          console.error('プロファイル取得エラー (MyPage):', error);
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfile();
  }, [session, apiFetch]);


  // ユーザーがいない場合の早期リダイレクト
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);


  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };


  // --- プロフィール更新ロジック ---
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!formData.username.trim()) {
        toast.error('ユーザー名は必須です。');
        return;
    }
    setIsSubmitting(true);
    try {
      const payload: ProfileFormData = {
        username: formData.username.trim(),
        website: formData.website ? formData.website.trim() : null,
        preferred_ai_model: formData.preferred_ai_model,
      };

      const updatedProfile: ProfileApiResponse = await apiFetch('/api/v1/profile', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });

      if (updatedProfile) {
        setFormData({
          username: updatedProfile.username || '',
          website: updatedProfile.website || '',
          preferred_ai_model: updatedProfile.preferred_ai_model || initialFormData.preferred_ai_model,
        });
      }
      toast.success('プロフィールを更新しました！');

    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'プロファイルの更新に失敗しました。';
      toast.error(errorMessage);
      console.error('プロフィール更新エラー:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // --- レンダリング ---
  if (authLoading || isLoading) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="ml-4 text-lg text-gray-600">読み込み中...</p>
      </div>
    );
  }

  if (!user) return null; // 早期リダイレクトが動作するまでの間の表示

  return (
    <div className="max-w-2xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="mb-6 flex justify-between items-center">
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">マイページ</h1>
        <Link href="/dashboard" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
            ダッシュボードへ →
        </Link>
      </div>
      
      <div className="mb-8 p-6 bg-blue-50 border border-blue-200 rounded-lg shadow">
        <h2 className="text-xl font-semibold text-blue-700 mb-3">アカウント全体の戦略設定</h2>
        <p className="text-sm text-blue-600 mb-4">
          アカウントの目的、ターゲット顧客、ブランドボイスなどの詳細な戦略は、専用ページで設定できます。
        </p>
        <Link
          href="/mypage/account-strategy"
          className="inline-block px-6 py-2 bg-blue-600 text-white font-semibold rounded-lg shadow-md hover:bg-blue-700 transition duration-300 text-sm"
        >
          アカウント戦略を設定・編集する
        </Link>
      </div>
    

<div className="mb-8 p-6 bg-green-50 border border-green-200 rounded-lg shadow">
  <h2 className="text-xl font-semibold text-green-700 mb-3">商品・サービス管理</h2>
  <p className="text-sm text-green-600 mb-4">
    ローンチ計画の対象となる、あなたの提供する商品やサービスを管理します。
  </p>
  <Link
    href="/mypage/products" // 商品管理ページへのパス
    className="inline-block px-6 py-2 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 transition duration-300 text-sm"
  >
    商品を登録・編集する
  </Link>
</div>
      <form onSubmit={handleSubmit} className="space-y-8 bg-white p-8 sm:p-10 shadow-xl rounded-2xl border border-gray-200">
        <h2 className="text-xl font-semibold text-gray-800 pb-3 border-b border-gray-200">基本設定</h2>
        <div>
          <label htmlFor="username" className="block text-sm font-semibold text-gray-700 mb-1">
            ユーザー名 *
          </label>
          <input
            type="text"
            name="username"
            id="username"
            value={formData.username}
            onChange={handleChange}
            required
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label htmlFor="website" className="block text-sm font-semibold text-gray-700 mb-1">
            ウェブサイト/主要SNSリンク
          </label>
          <input
            type="url"
            name="website"
            id="website"
            value={formData.website || ''}
            onChange={handleChange}
            placeholder="https://example.com"
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        
        <fieldset className="pt-4">
          <legend className="text-base font-semibold text-gray-900 mb-2">AIモデル設定</legend>
          <p className="text-xs text-gray-500 mb-3">
            AIによるコンテンツ生成に使用するモデルを選択します。
          </p>
          <div className="space-y-2">
            {aiModelOptions.map((option) => (
              <div key={option.value} className="flex items-center">
                <input
                  id={`mypage-${option.value}`}
                  name="preferred_ai_model"
                  type="radio"
                  value={option.value}
                  checked={formData.preferred_ai_model === option.value}
                  onChange={handleChange}
                  className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300"
                />
                <label htmlFor={`mypage-${option.value}`} className="ml-3 block text-sm font-medium text-gray-700 cursor-pointer">
                  {option.label}
                </label>
              </div>
            ))}
          </div>
        </fieldset>
        
        <div className="pt-6">
          <button
            type="submit"
            disabled={isSubmitting || isLoading}
            className="w-full flex justify-center py-3 px-6 border border-transparent rounded-lg shadow-md text-base font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60"
          >
            {isSubmitting ? '更新中...' : '基本設定を更新'}
          </button>
        </div>
      </form>
    </div>
  );
}