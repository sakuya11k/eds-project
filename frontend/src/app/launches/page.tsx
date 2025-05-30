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

type Launch = {
  id: string;
  user_id: string;
  product_id: string;
  product_name?: string; // 表示用に商品名も保持できるようにする (APIでJOINするか別途取得)
  name: string;
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  goal?: string | null;
  status: string; // 'planning', 'active', 'completed', 'archived'
  created_at: string;
  updated_at: string;
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
  const [userProducts, setUserProducts] = useState<Product[]>([]) // ローンチ作成時の商品選択用
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingLaunch, setEditingLaunch] = useState<Launch | null>(null) // 今回は新規作成のみ
  const [formData, setFormData] = useState<LaunchFormData>(initialLaunchFormData)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // 認証チェック
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  // ローンチ一覧とユーザーの商品一覧の取得
  const fetchData = async () => {
    if (!user || authLoading) return;
    setIsLoading(true)
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) throw new Error("セッションが見つかりません。")

      const token = session.access_token;

      // ローンチ一覧取得
      const launchesResponse = await axios.get(
        'http://localhost:5001/api/v1/launches',
        { headers: { Authorization: `Bearer ${token}` } }
      )
      const launchesData = launchesResponse.data || []

      // 各ローンチの商品名を取得 (N+1問題の可能性あり、バックエンドでJOIN推奨)
      // ここでは簡略化のため、商品名なしで表示するか、別途取得
      const populatedLaunches = await Promise.all(launchesData.map(async (launch: Launch) => {
        try {
          const productResponse = await axios.get(
            // 注意: 本来は /api/v1/products/<product_id> があると良いが、今回は商品一覧から探す
            // もしくは、バックエンドの /api/v1/launches で商品名をJOINして返すのが最善
            `http://localhost:5001/api/v1/products`, // 商品一覧を取得して該当IDを探す (非効率)
             { headers: { Authorization: `Bearer ${token}` } }
          );
          const product = productResponse.data.find((p: Product) => p.id === launch.product_id);
          return { ...launch, product_name: product ? product.name : '不明な商品' };
        } catch (prodError) {
          console.error(`商品情報取得エラー (ID: ${launch.product_id}):`, prodError);
          return { ...launch, product_name: '商品情報取得エラー' };
        }
      }));
      setLaunches(populatedLaunches);


      // ユーザーの商品一覧取得 (モーダルでの選択用)
      const productsResponse = await axios.get(
        'http://localhost:5001/api/v1/products',
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setUserProducts(productsResponse.data || [])

    } catch (err: any) {
      console.error('データ取得エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || 'データの取得に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (user && !authLoading) {
        fetchData()
    }
  }, [user, authLoading])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const openModalForCreate = () => {
    setEditingLaunch(null) // 新規作成モード
    setFormData(initialLaunchFormData)
    setIsModalOpen(true)
  }

  // TODO: ローンチ編集機能は別途実装
  // const openModalForEdit = (launch: Launch) => { ... }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingLaunch(null)
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
        // start_date と end_date が空文字ならnullにする (DBがtimestamptzの場合)
        start_date: formData.start_date || null,
        end_date: formData.end_date || null,
      }

      // TODO: editingLaunch があれば更新、なければ新規作成
      // 今回は新規作成のみを実装
      await axios.post(
        'http://localhost:5001/api/v1/launches',
        payload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      )
      toast.success('ローンチ計画を登録しました！')

      fetchData() // ローンチ一覧を再取得
      closeModal()
    } catch (err: any) {
      console.error('ローンチ登録エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || 'ローンチ計画の登録に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  // TODO: ローンチ削除機能は別途実装
  // const handleDeleteLaunch = async (launchId: string) => { ... }


  if (authLoading) {
    return <div className="text-center py-10">認証情報を確認中...</div>
  }
  if (!user) {
    return <div className="text-center py-10">ログインページへリダイレクトします...</div>
  }
  if (isLoading && launches.length === 0) {
    return <div className="text-center py-10">ローンチ計画を読み込み中...</div>
  }

  return (
    <div className="max-w-5xl mx-auto">
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
      {isLoading && launches.length > 0 && <p className="text-center py-4">情報を更新中...</p>}

      {launches.length === 0 && !isLoading && (
        <p className="text-center text-gray-500 py-10">まだローンチ計画が登録されていません。</p>
      )}

      <div className="space-y-6">
        {launches.map(launch => (
          <div key={launch.id} className="bg-white p-6 shadow-lg rounded-xl border border-gray-200">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-xl font-semibold text-indigo-700 mb-1">{launch.name}</h2>
                <p className="text-sm text-gray-600 mb-1">商品: {launch.product_name || '未選択'}</p>
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
              <div className="flex-shrink-0 ml-4 space-x-2 mt-1">
                <Link href={`/launches/${launch.id}/strategy`} className="px-4 py-1 text-sm bg-green-500 text-white rounded-md hover:bg-green-600 transition">
                  戦略編集
                </Link>
                {/* TODO: ローンチ編集・削除ボタン */}
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
              新規ローンチ計画を作成
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
                </select>
              </div>
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700">概要</label>
                <textarea name="description" id="description" rows={3} value={formData.description} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></textarea>
              </div>
              <div className="grid grid-cols-2 gap-4">
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
                  {isSubmitting ? '登録中...' : '登録する'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}