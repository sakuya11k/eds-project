'use client';

import { useAuth } from '@/context/AuthContext';
import { useXAccount } from '@/context/XAccountContext';
import Link from 'next/link';

const Header = () => {
  const { user, signOut } = useAuth();
  const { activeXAccount, isLoading } = useXAccount();

  return (
    <header className="bg-gray-800 text-white p-4 sticky top-0 z-50 shadow-md">
      <nav className="container mx-auto flex justify-between items-center">
        <Link href="/" className="text-xl font-bold hover:text-blue-400 transition-colors">
          EDS
        </Link>
        <div className="flex items-center space-x-4">
          {user ? (
            <>
              {/* アカウント選択状態の表示 */}
              <div className="text-sm">
                {isLoading ? (
                  <span className="text-gray-400">...</span>
                ) : activeXAccount ? (
                  <Link href="/dashboard" className="bg-blue-600 px-3 py-1 rounded-md text-white font-semibold hover:bg-blue-500 transition-colors">
                    <span>@{activeXAccount.x_username}</span>
                  </Link>
                ) : (
                  <Link href="/dashboard" className="bg-yellow-500 text-black px-3 py-1 rounded-md font-semibold hover:bg-yellow-400 transition-colors">
                    <span>アカウント設定</span>
                  </Link>
                )}
              </div>

              {/* ===== メニュー構成 ===== */}
              <Link href="/dashboard" className="hover:text-gray-300">アカウント管理</Link>
              <Link href="/tweets" className="hover:text-gray-300">ツイート管理</Link>
              
              {/* ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★ */}
              {/* ★ ここに新しい「悩み生成」ページへのリンクを追加 ★ */}
              {/* ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★ */}
              <Link href="/problems/generate" className="text-yellow-300 font-semibold hover:text-yellow-200">悩みリスト生成</Link>
              
              <Link href="/initial-post-generator" className="hover:text-gray-300">初期投稿生成</Link>
              <Link href="/educational-tweets" className="hover:text-gray-300">教育ツイート</Link>
              <Link href="/launches" className="hover:text-gray-300">ローンチ管理</Link>
              <Link href="/mypage" className="hover:text-gray-300">マイページ</Link>
              
              <button
                onClick={signOut}
                className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded"
              >
                Sign Out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="hover:text-gray-300">Login</Link>
              <Link href="/signup" className="hover:text-gray-300">Sign Up</Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
};

export default Header;