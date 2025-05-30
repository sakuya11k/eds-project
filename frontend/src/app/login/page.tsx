'use client'



import { useState } from 'react'
import { supabase } from '@/lib/supabaseClient'
import { useRouter } from 'next/navigation'
import { Toaster, toast } from 'react-hot-toast'
import Link from 'next/link' // サインアップへのリンク用

export default function LogIn() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    const { error } = await supabase.auth.signInWithPassword({
      email: email,
      password: password,
    })

    setLoading(false)

    if (error) {
      toast.error(error.message)
    } else {
      toast.success('ログインしました！')
      // ログイン成功後、ダッシュボードやマイページにリダイレクト
      router.push('/dashboard') // (例: /dashboard へ移動)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <Toaster />
      <div className="max-w-md w-full space-y-8 p-10 bg-white shadow-lg rounded-xl">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            ログイン
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleLogin}>
          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <input
                id="email-address"
                name="email"
                type="email"
                autoComplete="email"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="メールアドレス"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
              />
            </div>
            <div>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="パスワード"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
              />
            </div>
          </div>

          {/* パスワード忘れや新規登録へのリンク (オプション) */}
          <div className="flex items-center justify-between text-sm">
              <Link href="/forgot-password" className="font-medium text-indigo-600 hover:text-indigo-500">
                  パスワードをお忘れですか？
              </Link>
              <Link href="/signup" className="font-medium text-indigo-600 hover:text-indigo-500">
                  アカウントをお持ちでないですか？
              </Link>
          </div>

          <div>
            <button
              type="submit"
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              disabled={loading}
            >
              {loading ? 'ログイン中...' : 'ログイン'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}