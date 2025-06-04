// src/app/mypage/page.tsx
'use client'

import React, { useEffect, useState, FormEvent, ChangeEvent } from 'react';
import { useAuth } from '@/context/AuthContext'; //
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import { supabase } from '@/lib/supabaseClient'; //
import { toast } from 'react-hot-toast'; //

// ★ 修正点: null を許容するフィールドを追加
export type MyPageProfileFormData = {
  username: string; // 必須とするなら string のまま
  website: string | null; // null許容
  preferred_ai_model: string;
  x_api_key: string | null; // null許容
  x_api_secret_key: string | null; // null許容
  x_access_token: string | null; // null許容
  x_access_token_secret: string | null; // null許容
};

const initialMyPageFormData: MyPageProfileFormData = {
  username: '',
  website: null,
  preferred_ai_model: 'gemini-1.5-flash-latest',
  x_api_key: null,
  x_api_secret_key: null,
  x_access_token: null,
  x_access_token_secret: null,
};

const aiModelOptions = [
  { value: 'gemini-1.5-flash-latest', label: 'Gemini 1.5 Flash (高速・標準)' },
  { value: 'gemini-1.5-pro-latest', label: 'Gemini 1.5 Pro (高性能・高品質)' },
];

// APIレスポンスの型も MyPageProfileFormData を基にする
type ProfileApiResponse = MyPageProfileFormData & {
  id?: string;
  updated_at?: string;
  // 他の (このページでは直接編集しない) アカウント戦略フィールドも含まれる可能性がある
  account_purpose?: string | null;
};


export default function MyPage() {
  const { user, loading: authLoading, signOut } = useAuth();
  const router = useRouter();

  const [formData, setFormData] = useState<MyPageProfileFormData>(initialMyPageFormData);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [apiLoading, setApiLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    const fetchProfile = async () => {
      if (user && !authLoading) {
        setApiLoading(true);
        setApiError(null);
        try {
          const { data: { session } } = await supabase.auth.getSession();
          if (!session) throw new Error("セッションが見つかりません。");

          const response = await axios.get<ProfileApiResponse>(
            'http://localhost:5001/api/v1/profile',
            { headers: { Authorization: `Bearer ${session.access_token}` } }
          );
          const fetchedProfile = response.data;
          
          setFormData({
            username: fetchedProfile.username || '', // usernameは必須なので空文字フォールバック
            website: fetchedProfile.website || null, // null許容なのでAPIの値そのままかnull
            preferred_ai_model: fetchedProfile.preferred_ai_model || initialMyPageFormData.preferred_ai_model,
            x_api_key: fetchedProfile.x_api_key || null,
            x_api_secret_key: fetchedProfile.x_api_secret_key || null,
            x_access_token: fetchedProfile.x_access_token || null,
            x_access_token_secret: fetchedProfile.x_access_token_secret || null,
          });
          setProfileId(fetchedProfile.id || null);
          if (fetchedProfile.updated_at) {
            setLastUpdated(new Date(fetchedProfile.updated_at).toLocaleString('ja-JP'));
          }

        } catch (error: unknown) { //
          console.error('プロファイル取得エラー (MyPage):', error);
          let errorMessage = 'プロファイルの取得に失敗しました。';
          if (axios.isAxiosError(error) && error.response) { //
            errorMessage = error.response.data?.message || error.message || errorMessage; //
            if (error.response.status === 401 && signOut) { //
              await signOut(); //
              router.push('/login'); //
            } else if (error.response.status === 404) { //
              // ★ 修正: toast.info を toast() に変更
              toast("プロフィールがまだ作成されていません。"); //
              setFormData(initialMyPageFormData); //
            }
          } else if (error instanceof Error) { //
            errorMessage = error.message; //
          }
          setApiError(errorMessage); //
          if (!(axios.isAxiosError(error) && error.response?.status === 404)){ //
             toast.error(errorMessage); //
          }
        } finally { //
          setApiLoading(false); //
        }
      } else if (!authLoading && !user) { //
        setApiLoading(false); //
      }
    };
    fetchProfile();
  }, [user, authLoading, router, signOut]);

  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!user) {
      toast.error('認証されていません。');
      return;
    }
    if (!formData.username.trim()) {
        toast.error('ユーザー名は必須です。');
        return;
    }
    setIsSubmitting(true);
    setApiError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession(); //
      if (!session) throw new Error("セッションが見つかりません。"); //

      // ★ 修正点: payload の各値が string | null になるように調整
      const payload: MyPageProfileFormData = { //
        username: formData.username.trim(), // usernameは必須なので string
        website: formData.website ? formData.website.trim() : null, //
        preferred_ai_model: formData.preferred_ai_model, //
        x_api_key: formData.x_api_key ? formData.x_api_key.trim() : null, //
        x_api_secret_key: formData.x_api_secret_key ? formData.x_api_secret_key.trim() : null, //
        x_access_token: formData.x_access_token ? formData.x_access_token.trim() : null, //
        x_access_token_secret: formData.x_access_token_secret ? formData.x_access_token_secret.trim() : null, //
      }; //

      const response = await axios.put<ProfileApiResponse>( //
        'http://localhost:5001/api/v1/profile', //
        payload, //
        { headers: { Authorization: `Bearer ${session.access_token}` } } //
      ); //
      
      const updatedProfile = response.data; //
      setFormData({ //
        username: updatedProfile.username || '', //
        website: updatedProfile.website || null, //
        preferred_ai_model: updatedProfile.preferred_ai_model || initialMyPageFormData.preferred_ai_model, //
        // ... 他のAPIキーも同様に || null でフォールバック
        x_api_key: updatedProfile.x_api_key || null,
        x_api_secret_key: updatedProfile.x_api_secret_key || null,
        x_access_token: updatedProfile.x_access_token || null,
        x_access_token_secret: updatedProfile.x_access_token_secret || null,
      });
      if (updatedProfile.updated_at) {
        setLastUpdated(new Date(updatedProfile.updated_at).toLocaleString('ja-JP'));
      }
      toast.success('プロフィールを更新しました！');
    } catch (error: unknown) {
      console.error('プロフィール更新エラー:', error);
      let errorMessage = 'プロファイルの更新に失敗しました。';
      if (axios.isAxiosError(error) && error.response) {
           errorMessage = error.response.data?.message || error.message || errorMessage;
      } else if (error instanceof Error) {
           errorMessage = error.message;
      }
      setApiError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading || apiLoading) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="ml-4 text-lg text-gray-600">読み込み中...</p>
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
    <div className="max-w-2xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="mb-6 flex justify-between items-center">
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">マイページ</h1>
        <Link href="/dashboard" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center group">
            <svg className="w-4 h-4 mr-1 text-indigo-500 group-hover:text-indigo-700" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd"></path></svg>
            ダッシュボードへ
        </Link>
      </div>
      
      <div className="mb-8 p-6 bg-blue-50 border border-blue-200 rounded-lg shadow">
        <h2 className="text-xl font-semibold text-blue-700 mb-3">アカウント全体の戦略設定</h2>
        <p className="text-sm text-blue-600 mb-4">
          アカウントの目的、ターゲット顧客、ブランドボイス、12の教育要素の基本方針など、より詳細なアカウント戦略は専用ページで設定できます。
        </p>
        <Link
          href="/mypage/account-strategy"
          className="inline-block px-6 py-2 bg-blue-600 text-white font-semibold rounded-lg shadow-md hover:bg-blue-700 transition duration-300 text-sm"
        >
          アカウント戦略を設定・編集する
        </Link>
      </div>

      {apiError && <p className="mb-6 bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded-md">エラー: {apiError}</p>}
      
      <form onSubmit={handleSubmit} className="space-y-8 bg-white p-8 sm:p-10 shadow-2xl rounded-2xl border border-gray-200">
        <h2 className="text-xl font-semibold text-gray-800 pb-3 border-b border-gray-200">基本設定・API連携</h2>
        <div>
          <label htmlFor="username" className="block text-sm font-semibold text-gray-700 mb-1">
            ユーザー名 *
          </label>
          <input
            type="text"
            name="username"
            id="username"
            value={formData.username} // stringなのでそのまま
            onChange={handleChange}
            required
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
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
            value={formData.website || ''} // nullの場合があるので || '' でフォールバック
            onChange={handleChange}
            placeholder="https://example.com や https://x.com/your_id など"
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          />
        </div>
        
        <fieldset className="pt-4">
          <legend className="text-base font-semibold text-gray-900 mb-2">AIモデル設定</legend>
          <p className="text-xs text-gray-500 mb-3">
            AIによるコンテンツ生成に使用するモデルを選択してください。
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
        
        <fieldset className="pt-6 mt-6 border-t border-gray-200">
            <legend className="text-base font-semibold text-gray-900 mb-2">X (旧Twitter) API連携設定</legend>
            <p className="text-xs text-gray-500 mb-3">
                ツイートの自動投稿機能を利用するには、X Developer Platformで取得したAPIキーとアクセストークンを設定してください。
                <Link href="https://developer.twitter.com/en/portal/projects-and-apps" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800 ml-1">
                    (X Developer Portal)
                </Link>
            </p>
            <div className="space-y-4">
                <div>
                    <label htmlFor="x_api_key" className="block text-xs font-medium text-gray-600">API Key (Consumer Key)</label>
                    <input type="password" name="x_api_key" id="x_api_key" value={formData.x_api_key || ''} onChange={handleChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" autoComplete="new-password" placeholder="API Key を入力"/>
                </div>
                <div>
                    <label htmlFor="x_api_secret_key" className="block text-xs font-medium text-gray-600">API Key Secret</label>
                    <input type="password" name="x_api_secret_key" id="x_api_secret_key" value={formData.x_api_secret_key || ''} onChange={handleChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" autoComplete="new-password" placeholder="API Key Secret を入力"/>
                </div>
                <div>
                    <label htmlFor="x_access_token" className="block text-xs font-medium text-gray-600">Access Token</label>
                    <input type="password" name="x_access_token" id="x_access_token" value={formData.x_access_token || ''} onChange={handleChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" autoComplete="new-password" placeholder="Access Token を入力"/>
                </div>
                <div>
                    <label htmlFor="x_access_token_secret" className="block text-xs font-medium text-gray-600">Access Token Secret</label>
                    <input type="password" name="x_access_token_secret" id="x_access_token_secret" value={formData.x_access_token_secret || ''} onChange={handleChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" autoComplete="new-password" placeholder="Access Token Secret を入力"/>
                </div>
            </div>
        </fieldset>
        
        {(profileId || lastUpdated) && (
            <div className="text-xs text-gray-400 mt-8 pt-6 border-t border-gray-200 text-right">
                {profileId && <p>ユーザー設定ID: {profileId}</p>}
                {lastUpdated && <p>最終更新: {lastUpdated}</p>}
            </div>
        )}

        <div className="pt-6">
          <button
            type="submit"
            disabled={isSubmitting || apiLoading}
            className="w-full flex justify-center py-3 px-6 border border-transparent rounded-lg shadow-md text-base font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition duration-150 ease-in-out"
          >
            {isSubmitting ? '更新中...' : '基本設定を更新'}
          </button>
        </div>
      </form>
    </div>
  );
}