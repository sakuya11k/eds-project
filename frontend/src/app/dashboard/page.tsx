'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext' // AuthContext のパスを確認してください
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient' // Supabaseクライアントのパスを確認してください
import { toast } from 'react-hot-toast'     // toast をインポート

// バックエンドのダミーレスポンスに合わせた型定義
type ProfileData = {
  id: string;
  username: string | null;
  message: string;
}

export default function Dashboard() {
  const { user, loading: authLoading, signOut } = useAuth() // loading を authLoading に変更
  const router = useRouter()
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [apiLoading, setApiLoading] = useState(true) // 初期値をtrueにして最初から読み込む
  const [apiError, setApiError] = useState<string | null>(null)

  // 認証状態を監視し、未ログインならリダイレクト
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  // プロファイル情報を取得する API 呼び出し
  useEffect(() => {
    const fetchProfile = async () => {
      // ユーザーが確定していて、まだAPIをロード中でない場合のみ実行
      if (user && !authLoading) {
        setApiLoading(true) // API呼び出し開始
        setApiError(null)
        try {
          const { data: { session } } = await supabase.auth.getSession()

          if (!session) {
            // toast.error("セッションが見つかりません。再度ログインしてください。");
            // await signOut(); // signOut を呼び出すと無限ループの可能性があるので注意
            // router.push('/login');
            throw new Error("セッションが見つかりません。再度ログインしてください。")
          }

          const response = await axios.get(
            'http://localhost:5001/api/v1/profile', // ポート番号 5001 を確認
            {
              headers: {
                Authorization: `Bearer ${session.access_token}`,
              },
            }
          )
          setProfile(response.data)
        } catch (error: any) {
          console.error('プロファイル取得エラー:', error)
          let errorMessage = 'プロファイルの取得に失敗しました。'
          if (axios.isAxiosError(error)) {
            if (error.response) {
              // サーバーがエラーレスポンスを返した場合
              errorMessage = error.response.data?.message || error.message
            } else if (error.request) {
              // リクエストは送られたが、応答がなかった場合 (Network Errorなど)
              errorMessage = 'サーバーからの応答がありません。バックエンドが起動しているか確認してください。'
            } else {
              // リクエスト設定時のエラー
              errorMessage = error.message
            }
          } else {
            errorMessage = error.message || '不明なエラーが発生しました。';
          }
          setApiError(errorMessage)
          toast.error(errorMessage) // エラーを通知

          // 401エラー（認証エラー）の場合はログインページに強制送還も検討
          if (axios.isAxiosError(error) && error.response?.status === 401) {
             toast.error("認証の有効期限が切れたか、無効です。再度ログインしてください。");
             // await signOut(); // 無限ループを避けるため、ここでは signOut しない方が良いかも
             router.push('/login');
          }

        } finally {
          setApiLoading(false) // API呼び出し完了
        }
      } else if (!authLoading && !user) {
        // ユーザーがいない場合はAPIローディングも終了
        setApiLoading(false);
      }
    }

    fetchProfile()
  }, [user, authLoading, router, signOut]) // signOut を依存配列に追加 (使う場合)

  // 認証情報のローディング中
  if (authLoading) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <p>認証情報を確認中...</p>
      </div>
    )
  }

  // 未ログイン（useEffect でリダイレクトされるはずだが、念のため）
  if (!user) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <p>ログインページへリダイレクトします...</p>
      </div>
    )
  }

  // ログイン済みユーザー向けの表示
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">ようこそ、ダッシュボードへ！</h1>
      <div className="bg-white p-6 shadow rounded-lg">
        <p className="text-lg mb-4">
          こんにちは、<span className="font-semibold">{user.email}</span> さん！
        </p>

        <div className="mt-6 p-4 border rounded-md bg-gray-50">
          <h2 className="text-xl font-semibold mb-3">APIからの情報 (テスト)</h2>
          {apiLoading && <p>読み込み中...</p>}
          {apiError && <p className="text-red-500">エラー: {apiError}</p>}
          {profile && !apiLoading && !apiError && (
            <div>
              <p><strong>メッセージ:</strong> {profile.message}</p>
              <p><strong>ID:</strong> {profile.id}</p>
              <p><strong>ユーザー名:</strong> {profile.username}</p>
            </div>
          )}
        </div>

        <Link
          href="/mypage" // 例: マイページへのリンク
          className="mt-6 inline-block text-indigo-600 hover:text-indigo-800 font-medium"
        >
          マイページで編集する (未作成)
        </Link>
      </div>
    </div>
  )
}