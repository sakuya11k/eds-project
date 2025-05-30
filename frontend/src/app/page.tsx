'use client'

import { useAuth } from '@/context/AuthContext'
import Link from 'next/link'
import { motion } from 'framer-motion' // アニメーション用

export default function Home() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-150px)] bg-black text-gray-700">
        {/* ローディングインジケーター */}
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400"></div>
        <span className="ml-4 text-lg tracking-widest">LOADING_</span>
      </div>
    )
  }

  return (
    // 背景と中央配置コンテナ
    <div className="min-h-[calc(100vh-150px)] flex items-center justify-center bg-black text-white p-6 relative overflow-hidden">
        {/* 背景の装飾 (オプション) */}
        <div className="absolute inset-0 opacity-10 bg-[url('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2228%22%20height%3D%2228%22%20viewBox%3D%220%200%2028%2028%22%3E%3Cpath%20fill%3D%22%23007bff%22%20d%3D%22M14%200h1v28h-1zM0%2014h28v1h-28z%22%2F%3E%3C%2Fsvg%3E')]"></div>
        <div className="absolute top-0 left-0 w-64 h-64 bg-blue-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
        <div className="absolute bottom-0 right-0 w-64 h-64 bg-purple-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute top-1/2 left-1/3 w-64 h-64 bg-cyan-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>

        {/* メインコンテンツ */}
      <motion.div
        className="text-center bg-gray-950/60 backdrop-blur-md p-8 md:p-14 rounded-2xl border border-gray-800/70 shadow-2xl shadow-blue-500/10 max-w-4xl w-full z-10"
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
      >
        {/* ロゴ/タイトル */}
        <motion.h1
          className="text-4xl md:text-5xl lg:text-6xl font-black mb-5 tracking-tight"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.6 }}
        >
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-300 to-purple-400">
            EDS:
          </span>
          <span className="ml-3">Education Drive System</span>
        </motion.h1>

        {/* キャッチコピー */}
        <motion.p
          className="text-lg md:text-xl text-gray-300 mb-10 leading-relaxed font-light"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.6 }}
        >
          あなたの X 運用と高額商品販売を、
          <span className="text-blue-300 font-medium">「売れる仕組み (教育)」</span> と{' '}
          <span className="text-cyan-300 font-medium">AI</span>{' '}
          で自動化・最大化します。
        </motion.p>

        {/* ボタンエリア */}
        {user ? (
          // ログイン時
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.6, duration: 0.5 }}
          >
            <Link
              href="/dashboard"
              className="inline-block px-12 py-3 bg-gradient-to-r from-blue-500 to-cyan-500 text-white text-lg font-bold rounded-full shadow-lg shadow-cyan-500/30 hover:shadow-xl hover:shadow-cyan-500/40 transition-all duration-300 transform hover:scale-105"
            >
              ダッシュボードへアクセス
            </Link>
          </motion.div>
        ) : (
          // 未ログイン時
          <motion.div
            className="flex flex-col sm:flex-row justify-center items-center gap-6"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.5 }}
          >
            <Link
              href="/signup"
              className="w-full sm:w-auto inline-block px-8 py-3 bg-gradient-to-r from-blue-500 to-cyan-500 text-white text-base font-medium rounded-full shadow-md shadow-blue-500/20 transform hover:scale-105 transition duration-300"
            >
              システムを起動する (無料)
            </Link>
            <Link
              href="/login"
              className="w-full sm:w-auto inline-block px-8 py-3 border border-gray-700 text-base font-medium rounded-full text-gray-300 bg-transparent hover:bg-gray-800/50 shadow-md transform hover:scale-105 transition duration-300"
            >
              ログイン
            </Link>
          </motion.div>
        )}
      </motion.div>
    </div>
  )
}