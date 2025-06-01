'use client'

import { useAuth } from '@/context/AuthContext' //
import Link from 'next/link'
import { useRouter } from 'next/navigation' // ログアウト後のリダイレクト用

export default function Header() {
  const { user, signOut, loading } = useAuth() // loading は認証状態のローディング
  const router = useRouter()

  const handleSignOut = async () => {
    await signOut()
    router.push('/login') // ログアウト後にログインページへリダイレクト
  }

  return (
    <header className="bg-white shadow-sm sticky top-0 z-50"> {/* ヘッダーを上部固定 */}
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex-shrink-0">
            <Link href="/" className="text-2xl font-bold text-indigo-600 hover:text-indigo-700 transition-colors">
              EDS
            </Link>
          </div>
          <div className="ml-4 flex items-center space-x-1 sm:space-x-2 md:space-x-4"> {/* スペース調整 */}
            {loading ? (
              // 認証情報読み込み中のプレースホルダー
              <div className="animate-pulse flex items-center space-x-2 md:space-x-4">
                <div className="h-5 w-16 sm:w-20 bg-gray-200 rounded"></div>
                <div className="h-8 w-20 sm:w-24 bg-gray-200 rounded-md"></div>
              </div>
            ) : user ? (
              // ログイン時の表示
              <>
                <span className="text-xs sm:text-sm text-gray-600 hidden md:block mr-2"> {/* メールアドレス、小さい画面では非表示 */}
                  {user.email}
                </span>
                <Link
                  href="/dashboard"
                  className="px-2 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors"
                >
                  ダッシュボード
                </Link>
                <Link
                  href="/mypage/products"
                  className="px-2 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors"
                >
                  商品管理
                </Link>
                <Link
                  href="/launches"
                  className="px-2 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors"
                >
                  ローンチ計画
                </Link>
                <Link
                  href="/educational-tweets" 
                  className="px-2 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors"
                >
                  教育ツイート作成
                </Link>
                {/* ===== ここから追加 ===== */}
                <Link
                  href="/tweets" // 新しい「ツイート管理」ページへのパス
                  className="px-2 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors"
                >
                  ツイート管理
                </Link>
                {/* ===== ここまで追加 ===== */}
                <button
                  onClick={handleSignOut}
                  className="px-3 sm:px-4 py-2 border border-transparent text-xs sm:text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
                >
                  ログアウト
                </button>
              </>
            ) : (
              // 未ログイン時の表示
              <>
                <Link
                  href="/login"
                  className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors"
                >
                  ログイン
                </Link>
                <Link
                  href="/signup"
                  className="ml-2 inline-flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
                >
                  新規登録
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>
    </header>
  )
}