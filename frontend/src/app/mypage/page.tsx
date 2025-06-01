'use client'

import React, { useEffect, useState, FormEvent } from 'react'
import { useAuth } from '@/context/AuthContext' //
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient' //
import { toast } from 'react-hot-toast'

// プロファイルの型定義 (バックエンドからの応答、X APIキー関連を含む)
type Profile = {
  id?: string;
  username: string | null;
  website: string | null;
  avatar_url: string | null;
  brand_voice: string | null;
  target_persona: string | null;
  preferred_ai_model: string | null;
  x_api_key: string | null;
  x_api_secret_key: string | null;
  x_access_token: string | null;
  x_access_token_secret: string | null;
  updated_at?: string;
}

// フォームデータの型 (X APIキー関連を含む)
type ProfileFormData = {
  username: string;
  website: string;
  brand_voice: string;
  target_persona: string;
  preferred_ai_model: string;
  x_api_key: string;
  x_api_secret_key: string;
  x_access_token: string;
  x_access_token_secret: string;
}

const initialFormData: ProfileFormData = {
  username: '',
  website: '',
  brand_voice: '',
  target_persona: '',
  preferred_ai_model: 'gemini-1.5-flash-latest',
  x_api_key: '',
  x_api_secret_key: '',
  x_access_token: '',
  x_access_token_secret: '',
}

// AIモデルの選択肢
const aiModelOptions = [
  { value: 'gemini-1.5-flash-latest', label: 'Gemini 1.5 Flash (高速・標準)' },
  { value: 'gemini-1.5-pro-latest', label: 'Gemini 1.5 Pro (高性能・高品質)' },
]

export default function MyPage() {
  const { user, loading: authLoading, signOut } = useAuth() //
  const router = useRouter()

  const [profile, setProfile] = useState<Profile | null>(null)
  const [formData, setFormData] = useState<ProfileFormData>(initialFormData)
  const [apiLoading, setApiLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  useEffect(() => {
    const fetchProfile = async () => {
      if (user && !authLoading) {
        setApiLoading(true)
        setApiError(null)
        try {
          const { data: { session } } = await supabase.auth.getSession() //
          if (!session) throw new Error("セッションが見つかりません。")

          const response = await axios.get(
            'http://localhost:5001/api/v1/profile', //
            { headers: { Authorization: `Bearer ${session.access_token}` } }
          )
          const fetchedProfile: Profile = response.data
          setProfile(fetchedProfile)
          
          setFormData({
            username: fetchedProfile.username || '',
            website: fetchedProfile.website || '',
            brand_voice: fetchedProfile.brand_voice || '',
            target_persona: fetchedProfile.target_persona || '',
            preferred_ai_model: fetchedProfile.preferred_ai_model || 'gemini-1.5-flash-latest',
            x_api_key: fetchedProfile.x_api_key || '',
            x_api_secret_key: fetchedProfile.x_api_secret_key || '',
            x_access_token: fetchedProfile.x_access_token || '',
            x_access_token_secret: fetchedProfile.x_access_token_secret || '',
          })
        } catch (error: any) {
          console.error('プロファイル取得エラー (MyPage):', error)
          const errorMessage = error.response?.data?.message || error.message || 'プロファイルの取得に失敗しました。'
          setApiError(errorMessage)
          toast.error(errorMessage)
          if (axios.isAxiosError(error) && error.response?.status === 401) {
            await signOut()
            router.push('/login')
          } else if (axios.isAxiosError(error) && error.response?.status === 404) {
            toast.error("プロフィールデータが見つかりません。新規作成扱いになります。");
          }
        } finally {
          setApiLoading(false)
        }
      } else if (!authLoading && !user) {
        setApiLoading(false)
      }
    }
    fetchProfile()
  }, [user, authLoading, router, signOut])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) {
      toast.error('認証されていません。')
      return
    }
    setIsSubmitting(true)
    setApiError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession() //
      if (!session) throw new Error("セッションが見つかりません。")

      const payload: Partial<Profile> = {
        username: formData.username.trim() === '' ? null : formData.username.trim(),
        website: formData.website.trim() === '' ? null : formData.website.trim(),
        brand_voice: formData.brand_voice.trim() === '' ? null : formData.brand_voice.trim(),
        target_persona: formData.target_persona.trim() === '' ? null : formData.target_persona.trim(),
        preferred_ai_model: formData.preferred_ai_model,
        x_api_key: formData.x_api_key.trim() === '' ? null : formData.x_api_key.trim(),
        x_api_secret_key: formData.x_api_secret_key.trim() === '' ? null : formData.x_api_secret_key.trim(),
        x_access_token: formData.x_access_token.trim() === '' ? null : formData.x_access_token.trim(),
        x_access_token_secret: formData.x_access_token_secret.trim() === '' ? null : formData.x_access_token_secret.trim(),
      };

      const response = await axios.put(
        'http://localhost:5001/api/v1/profile', //
        payload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      )
      const updatedProfile: Profile = response.data;
      setProfile(updatedProfile)
      setFormData({
        username: updatedProfile.username || '',
        website: updatedProfile.website || '',
        brand_voice: updatedProfile.brand_voice || '',
        target_persona: updatedProfile.target_persona || '',
        preferred_ai_model: updatedProfile.preferred_ai_model || 'gemini-1.5-flash-latest',
        x_api_key: updatedProfile.x_api_key || '',
        x_api_secret_key: updatedProfile.x_api_secret_key || '',
        x_access_token: updatedProfile.x_access_token || '',
        x_access_token_secret: updatedProfile.x_access_token_secret || '',
      });
      toast.success('プロフィールを更新しました！')
    } catch (error: any) {
      console.error('プロフィール更新エラー:', error)
      const errorMessage = error.response?.data?.message || error.message || 'プロファイルの更新に失敗しました。'
      setApiError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (authLoading || apiLoading) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="ml-4 text-lg text-gray-600">読み込み中...</p>
      </div>
    )
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
      <Link href="/dashboard" className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center group mb-6">
          <svg className="w-5 h-5 mr-2 text-indigo-500 group-hover:text-indigo-700" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd"></path></svg>
          ダッシュボードへ戻る
      </Link>
      <h1 className="text-3xl font-extrabold text-gray-900 mb-8 tracking-tight">マイページ - プロフィール編集</h1>
      {apiError && <p className="text-red-500 bg-red-100 p-3 rounded-md mb-6 border border-red-200">エラー: {apiError}</p>}
      
      <form onSubmit={handleSubmit} className="space-y-8 bg-white p-8 sm:p-10 shadow-2xl rounded-2xl border border-gray-200">
        <div>
          <label htmlFor="username" className="block text-sm font-semibold text-gray-700 mb-1">
            ユーザー名
          </label>
          <input
            type="text"
            name="username"
            id="username"
            value={formData.username}
            onChange={handleChange}
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
            value={formData.website}
            onChange={handleChange}
            placeholder="https://example.com や https://twitter.com/your_id など"
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          />
        </div>

        <div>
          <label htmlFor="brand_voice" className="block text-sm font-semibold text-gray-700 mb-1">
            ブランドボイス (発信のトーン)
          </label>
          <textarea
            name="brand_voice"
            id="brand_voice"
            rows={3}
            value={formData.brand_voice}
            onChange={handleChange}
            placeholder="例: 優しく励ます姉御肌、論理的で専門的、フレンドリーで親しみやすい"
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm leading-relaxed"
          />
        </div>

        <div>
          <label htmlFor="target_persona" className="block text-sm font-semibold text-gray-700 mb-1">
            ターゲット顧客のペルソナ (概要)
          </label>
          <textarea
            name="target_persona"
            id="target_persona"
            rows={3}
            value={formData.target_persona}
            onChange={handleChange}
            placeholder="例: 30代の起業初心者女性で、新しいスキルを学びたいと考えている会社員"
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm leading-relaxed"
          />
        </div>

        <fieldset className="pt-4">
          <legend className="text-base font-semibold text-gray-900 mb-3">AIモデル設定</legend>
          <p className="text-sm text-gray-500 mb-4">
            AIによるコンテンツ生成に使用するモデルを選択してください。
            Proモデルはより高品質な結果を期待できますが、Flashモデルはより高速に応答します。
          </p>
          <div className="space-y-3">
            {aiModelOptions.map((option) => (
              <div key={option.value} className="flex items-center">
                <input
                  id={option.value}
                  name="preferred_ai_model"
                  type="radio"
                  value={option.value}
                  checked={formData.preferred_ai_model === option.value}
                  onChange={handleChange}
                  className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300"
                />
                <label htmlFor={option.value} className="ml-3 block text-sm font-medium text-gray-700 cursor-pointer">
                  {option.label}
                </label>
              </div>
            ))}
          </div>
        </fieldset>
        
        <fieldset className="pt-6 mt-6 border-t border-gray-200">
            <legend className="text-base font-semibold text-gray-900 mb-3">X (旧Twitter) API連携設定</legend>
            <p className="text-sm text-gray-500 mb-4">
                ツイートの自動投稿機能を利用するには、X Developer Platformで取得したAPIキーとアクセストークンを設定してください。
                <Link href="https://developer.twitter.com/en/portal/projects-and-apps" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800 ml-1">
                    (X Developer Portal)
                </Link>
            </p>
            <div className="space-y-6">
                <div>
                    <label htmlFor="x_api_key" className="block text-sm font-medium text-gray-700">
                        API Key (Consumer Key)
                    </label>
                    <input
                        type="password"
                        name="x_api_key"
                        id="x_api_key"
                        value={formData.x_api_key}
                        onChange={handleChange}
                        placeholder="X API Keyを入力"
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                        autoComplete="off" 
                    />
                </div>
                <div>
                    <label htmlFor="x_api_secret_key" className="block text-sm font-medium text-gray-700">
                        API Key Secret (Consumer Secret)
                    </label>
                    <input
                        type="password"
                        name="x_api_secret_key"
                        id="x_api_secret_key"
                        value={formData.x_api_secret_key}
                        onChange={handleChange}
                        placeholder="X API Key Secretを入力"
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                        autoComplete="off"
                    />
                </div>
                <div>
                    <label htmlFor="x_access_token" className="block text-sm font-medium text-gray-700">
                        Access Token
                    </label>
                    <input
                        type="password"
                        name="x_access_token"
                        id="x_access_token"
                        value={formData.x_access_token}
                        onChange={handleChange}
                        placeholder="X Access Tokenを入力"
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                        autoComplete="off"
                    />
                </div>
                <div>
                    <label htmlFor="x_access_token_secret" className="block text-sm font-medium text-gray-700">
                        Access Token Secret
                    </label>
                    <input
                        type="password"
                        name="x_access_token_secret"
                        id="x_access_token_secret"
                        value={formData.x_access_token_secret}
                        onChange={handleChange}
                        placeholder="X Access Token Secretを入力"
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                        autoComplete="off"
                    />
                </div>
            </div>
        </fieldset>
        
        {profile && (
            <div className="text-xs text-gray-500 mt-8 pt-6 border-t border-gray-200">
                <p>ユーザーID: {profile.id}</p>
                {profile.updated_at && <p>最終更新: {new Date(profile.updated_at).toLocaleString('ja-JP', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>}
            </div>
        )}

        <div className="pt-6">
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full flex justify-center py-3 px-6 border border-transparent rounded-lg shadow-md text-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition duration-150 ease-in-out"
          >
            {isSubmitting ? '更新中...' : 'プロフィールを更新'}
          </button>
        </div>
      </form>
    </div>
  )
}