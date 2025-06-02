'use client'

import { useEffect, useState, FormEvent } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient'
import { toast } from 'react-hot-toast'

// 型定義
type Product = { // 商品選択用
  id: string;
  name: string;
}

// Launch 型に product_name をオプショナルで追加 (バックエンドからのJOIN結果を反映)
type Launch = {
  id: string;
  user_id: string;
  product_id: string;
  product_name?: string; // ★ 表示用に商品名を保持 (フロントエンドで整形して格納)
  name: string;
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  goal?: string | null;
  status: string; // 'planning', 'active', 'completed', 'archived'
  created_at: string;
  updated_at: string;
  products?: { // ★ バックエンドからのJOIN結果がネストされている場合の型 (Supabaseの標準的な挙動)
    id: string;
    name: string;
  } | null; // 単一の関連商品の場合
}

type LaunchFormData = {
  name: string;
  product_id: string;
  description: string;
  start_date: string;
  end_date: string;
  goal: string;
  status: string;
}

const initialLaunchFormData: LaunchFormData = {
  name: '',
  product_id: '',
  description: '',
  start_date: '',
  end_date: '',
  goal: '',
  status: 'planning',
}

export default function LaunchesPage() {
  const { user, loading: authLoading, signOut } = useAuth()
  const router = useRouter()

  const [launches, setLaunches] = useState<Launch[]>([])
  const [userProducts, setUserProducts] = useState<Product[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingLaunch, setEditingLaunch] = useState<Launch | null>(null)
  const [formData, setFormData] = useState<LaunchFormData>(initialLaunchFormData)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  // ★ ローンチ一覧とユーザーの商品一覧の取得 (fetchData関数を修正)
  const fetchData = async () => {
    if (!user || authLoading) return;
    setIsLoading(true)
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) throw new Error("セッションが見つかりません。")

      const token = session.access_token;

      // ローンチ一覧取得 (バックエンドで商品情報もJOINされるように変更した前提)
      const launchesResponse = await axios.get(
        'http://localhost:5001/api/v1/launches', // バックエンドのエンドポイント
        { headers: { Authorization: `Bearer ${token}` } }
      )
      const launchesData: Launch[] = launchesResponse.data || [] // 型アサーション

      // バックエンドからJOINされた商品情報を product_name に整形する
      const populatedLaunches = launchesData.map(launch => {
        let productName = '不明な商品';
        if (launch.products && typeof launch.products === 'object' && launch.products.name) {
          productName = launch.products.name;
        }
        return { ...launch, product_name: productName };
      });
      setLaunches(populatedLaunches);

      // ユーザーの商品一覧取得 (モーダルでの選択用 - これは変更なし)
      const productsResponse = await axios.get(
        'http://localhost:5001/api/v1/products',
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setUserProducts(productsResponse.data || [])

    } catch (err: any) { // axiosエラーなどを考慮してany型で受け取る
      console.error('データ取得エラー (LaunchesPage):', err);
      const errorMessage = err.response?.data?.message || err.message || 'データの取得に失敗しました。';
      setError(errorMessage); // UIに表示するエラーメッセージ
      toast.error(errorMessage); // トーストでも通知
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        await signOut();
        router.push('/login');
      }
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (user && !authLoading) {
        fetchData()
    }
  }, [user, authLoading]) // 依存配列に user と authLoading

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const openModalForCreate = () => {
    setEditingLaunch(null)
    setFormData(initialLaunchFormData)
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingLaunch(null) // editingLaunchもクリア
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) {
      toast.error('認証されていません。')
      return
    }
    if (!formData.product_id) {
      toast.error('商品を選択してください。')
      return
    }
    setIsSubmitting(true)
    setError(null)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) throw new Error("セッションが見つかりません。")

      const payload = {
        ...formData,
        start_date: formData.start_date || null,
        end_date: formData.end_date || null,
      }

      // editingLaunch があれば更新API、なければ作成APIを呼び出す (今回は作成のみ)
      if (editingLaunch) {
        // 更新処理 (未実装のためコメントアウト)
        // await axios.put(
        //   `http://localhost:5001/api/v1/launches/${editingLaunch.id}`,
        //   payload,
        //   { headers: { Authorization: `Bearer ${session.access_token}` } }
        // );
        // toast.success('ローンチ計画を更新しました！');
      } else {
        await axios.post(
          'http://localhost:5001/api/v1/launches',
          payload,
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        )
        toast.success('ローンチ計画を登録しました！')
      }

      fetchData()
      closeModal()
    } catch (err: any) {
      console.error('ローンチ登録/更新エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || 'ローンチ計画の処理に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  // ローンチ削除機能 (今回は未実装のためコメントアウト)
  // const handleDeleteLaunch = async (launchId: string) => { ... }


  if (authLoading) {
    return <div className="text-center py-10">認証情報を確認中...</div>
  }
  if (!user) {
    return <div className="text-center py-10">ログインページへリダイレクトします...</div>
  }
  // isLoading 中でも launches があればそれを表示しつつ、更新中メッセージを出す
  if (isLoading && launches.length === 0) {
    return <div className="text-center py-10">ローンチ計画を読み込み中...</div>
  }

  return (
    <div className="max-w-5xl mx-auto py-10 px-4 sm:px-6 lg:px-8"> {/* Tailwind CSSのクラスを微調整 */}
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800">ローンチ計画管理</h1>
        <button
          onClick={openModalForCreate}
          className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700 transition duration-300"
        >
          新規ローンチ計画作成
        </button>
      </div>

      {error && <p className="text-red-500 bg-red-100 p-3 rounded-md mb-4">エラー: {error}</p>}
      {isLoading && launches.length > 0 && <p className="text-center text-gray-500 py-4">情報を更新中...</p>}

      {launches.length === 0 && !isLoading && (
        <div className="text-center py-10 bg-white shadow-lg rounded-lg p-6"> {/* スタイル追加 */}
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.242M2.25 12.162A2.25 2.25 0 004.5 14.412A2.25 2.25 0 006.75 12.162V10.5a2.25 2.25 0 00-4.5 0v1.662zM18.75 12.162a2.25 2.25 0 012.25 2.25 2.25 2.25 0 002.25-2.25V10.5a2.25 2.25 0 00-4.5 0v1.662zM21.75 16.122a3 3 0 01-5.78 1.128 2.25 2.25 0 00-2.4 2.242M12 10.5a2.25 2.25 0 01-4.5 0v-1.662a2.25 2.25 0 014.5 0v1.662z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">ローンチ計画がありません</h3>
            <p className="mt-1 text-sm text-gray-500">最初のローンチ計画を作成しましょう。</p>
        </div>
      )}

      <div className="space-y-6">
        {launches.map(launch => (
          <div key={launch.id} className="bg-white p-6 shadow-lg rounded-xl border border-gray-200">
            <div className="flex flex-col sm:flex-row justify-between items-start"> {/* レスポンシブ対応 */}
              <div className="flex-grow"> {/* コンテンツが幅を取るように */}
                <h2 className="text-xl font-semibold text-indigo-700 mb-1">{launch.name}</h2>
                {/* product_name を表示するように修正 */}
                <p className="text-sm text-gray-600 mb-1">商品: {launch.product_name || '未選択または取得エラー'}</p>
                <p className="text-sm text-gray-600 mb-1">
                  期間: {launch.start_date ? new Date(launch.start_date).toLocaleDateString('ja-JP') : '未定'} - {launch.end_date ? new Date(launch.end_date).toLocaleDateString('ja-JP') : '未定'}
                </p>
                <p className="text-sm text-gray-600 mb-1">ステータス: {launch.status}</p>
                <p className="text-gray-700 text-sm mt-2 whitespace-pre-wrap">
                  <strong className="font-medium">概要:</strong> {launch.description || '未設定'}
                </p>
                 <p className="text-gray-700 text-sm mt-1 whitespace-pre-wrap">
                  <strong className="font-medium">目標:</strong> {launch.goal || '未設定'}
                </p>
              </div>
              <div className="flex-shrink-0 ml-0 sm:ml-4 mt-4 sm:mt-1 space-x-2"> {/* レスポンシブ対応 */}
                <Link href={`/launches/${launch.id}/strategy`} className="inline-block px-4 py-2 text-sm bg-green-500 text-white rounded-md hover:bg-green-600 transition duration-150 ease-in-out">
                  戦略編集
                </Link>
                {/* TODO: ローンチ編集・削除ボタン (今回は対象外) */}
                {/* <button className="px-4 py-1 text-sm bg-yellow-500 text-white rounded-md hover:bg-yellow-600 transition">編集</button> */}
                {/* <button className="px-4 py-1 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 transition">削除</button> */}
              </div>
            </div>
             <p className="text-xs text-gray-400 mt-3 text-right">
              作成日: {new Date(launch.created_at).toLocaleString('ja-JP')}
            </p>
          </div>
        ))}
      </div>

      {/* 新規ローンチ作成モーダル */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75 overflow-y-auto h-full w-full flex items-center justify-center z-50 p-4">
          <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">
              {editingLaunch ? 'ローンチ計画を編集' : '新規ローンチ計画を作成'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">ローンチ名 *</label>
                <input type="text" name="name" id="name" value={formData.name} onChange={handleInputChange} required className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" />
              </div>
              <div>
                <label htmlFor="product_id" className="block text-sm font-medium text-gray-700">対象商品 *</label>
                <select name="product_id" id="product_id" value={formData.product_id} onChange={handleInputChange} required className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 bg-white">
                  <option value="" disabled>商品を選択してください</option>
                  {userProducts.map(product => (
                    <option key={product.id} value={product.id}>{product.name}</option>
                  ))}
                  {userProducts.length === 0 && <option disabled>先に商品を登録してください</option>}
                </select>
              </div>
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700">概要</label>
                <textarea name="description" id="description" rows={3} value={formData.description} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></textarea>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4"> {/* レスポンシブ対応 */}
                <div>
                  <label htmlFor="start_date" className="block text-sm font-medium text-gray-700">開始日</label>
                  <input type="date" name="start_date" id="start_date" value={formData.start_date} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" />
                </div>
                <div>
                  <label htmlFor="end_date" className="block text-sm font-medium text-gray-700">終了日</label>
                  <input type="date" name="end_date" id="end_date" value={formData.end_date} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" />
                </div>
              </div>
              <div>
                <label htmlFor="goal" className="block text-sm font-medium text-gray-700">目標</label>
                <input type="text" name="goal" id="goal" value={formData.goal} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" />
              </div>
              <div>
                <label htmlFor="status" className="block text-sm font-medium text-gray-700">ステータス</label>
                <select name="status" id="status" value={formData.status} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 bg-white">
                  <option value="planning">計画中</option>
                  <option value="active">実行中</option>
                  <option value="completed">完了</option>
                  <option value="archived">アーカイブ済</option>
                </select>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button type="button" onClick={closeModal} className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500">
                  キャンセル
                </button>
                <button type="submit" disabled={isSubmitting} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50">
                  {isSubmitting ? (editingLaunch ? '更新中...' : '登録中...') : (editingLaunch ? '更新する' : '登録する')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}