'use client'

import { useEffect, useState, FormEvent } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useRouter } from 'next/navigation'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient'
import { toast } from 'react-hot-toast'
import Link from 'next/link' // Linkコンポーネントをインポート

// 商品の型定義 (バックエンドと合わせる)
type Product = {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  price?: number | null;
  currency?: string | null;
  target_audience?: string | null;
  value_proposition?: string | null;
  created_at: string;
  updated_at: string;
}

// フォームデータの型
type ProductFormData = {
  name: string;
  description: string;
  price: string; // フォームでは文字列として扱い、送信時に数値に変換
  currency: string;
  target_audience: string;
  value_proposition: string;
}

const initialFormData: ProductFormData = {
  name: '',
  description: '',
  price: '',
  currency: 'JPY',
  target_audience: '',
  value_proposition: '',
}

export default function ProductsPage() {
  const { user, loading: authLoading, signOut } = useAuth()
  const router = useRouter()

  const [products, setProducts] = useState<Product[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [formData, setFormData] = useState<ProductFormData>(initialFormData)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // 認証チェック
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  // 商品一覧の取得
  const fetchProducts = async () => {
    if (!user || authLoading) return;
    setIsLoading(true)
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) throw new Error("セッションが見つかりません。")

      const response = await axios.get(
        'http://localhost:5001/api/v1/products',
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      )
      setProducts(response.data || [])
    } catch (err: any) {
      console.error('商品一覧取得エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || '商品一覧の取得に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchProducts()
  }, [user, authLoading]) // user が確定したら実行

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const openModalForCreate = () => {
    setEditingProduct(null)
    setFormData(initialFormData)
    setIsModalOpen(true)
  }

  const openModalForEdit = (product: Product) => {
    setEditingProduct(product)
    setFormData({
      name: product.name || '',
      description: product.description || '',
      price: product.price?.toString() || '',
      currency: product.currency || 'JPY',
      target_audience: product.target_audience || '',
      value_proposition: product.value_proposition || '',
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingProduct(null)
    setFormData(initialFormData)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) {
      toast.error('認証されていません。')
      return
    }
    setIsSubmitting(true)
    setError(null)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) throw new Error("セッションが見つかりません。")

      const payload = {
        ...formData,
        price: formData.price !== '' ? parseFloat(formData.price) : null,
      }

      if (editingProduct) { // 更新の場合
        await axios.put(
          `http://localhost:5001/api/v1/products/${editingProduct.id}`,
          payload,
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        )
        toast.success('商品を更新しました！')
      } else { // 新規作成の場合
        await axios.post(
          'http://localhost:5001/api/v1/products',
          payload,
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        )
        toast.success('商品を登録しました！')
      }
      fetchProducts() // 商品一覧を再取得
      closeModal()
    } catch (err: any) {
      console.error('商品登録/更新エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || '商品の処理に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async (productId: string) => {
    if (!user || !window.confirm('本当にこの商品を削除しますか？')) {
      return
    }
    setIsSubmitting(true) // 削除中もボタンを無効化するため流用
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) throw new Error("セッションが見つかりません。")

      await axios.delete(
        `http://localhost:5001/api/v1/products/${productId}`,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      )
      toast.success('商品を削除しました！')
      fetchProducts() // 商品一覧を再取得
    } catch (err: any) {
      console.error('商品削除エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || '商品の削除に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (authLoading) {
    return <div className="text-center py-10">認証情報を確認中...</div>
  }
  if (!user) { // useEffectでリダイレクトされるが、念のため
    return <div className="text-center py-10">ログインページへリダイレクトします...</div>
  }
  if (isLoading && products.length === 0) { // 初回ロード時
    return <div className="text-center py-10">商品情報を読み込み中...</div>
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800">商品管理</h1>
        <button
          onClick={openModalForCreate}
          className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700 transition duration-300"
        >
          新規商品登録
        </button>
      </div>

      {error && <p className="text-red-500 bg-red-100 p-3 rounded-md mb-4">エラー: {error}</p>}

      {isLoading && products.length > 0 && <p className="text-center py-4">情報を更新中...</p>}

      {products.length === 0 && !isLoading && (
        <p className="text-center text-gray-500 py-10">まだ商品が登録されていません。</p>
      )}

      <div className="space-y-4">
        {products.map(product => (
          <div key={product.id} className="bg-white p-6 shadow-lg rounded-xl border border-gray-200">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-xl font-semibold text-indigo-700 mb-1">{product.name}</h2>
                <p className="text-sm text-gray-500 mb-2">
                  価格: {product.price ? `${product.price.toLocaleString()} ${product.currency}` : '未設定'}
                </p>
                <p className="text-gray-700 whitespace-pre-wrap mb-1">
                  <strong className="font-medium">説明:</strong> {product.description || '未設定'}
                </p>
                <p className="text-gray-700 text-sm mb-1">
                  <strong className="font-medium">ターゲット:</strong> {product.target_audience || '未設定'}
                </p>
                <p className="text-gray-700 text-sm">
                  <strong className="font-medium">提供価値:</strong> {product.value_proposition || '未設定'}
                </p>
              </div>
              <div className="flex-shrink-0 ml-4 space-x-2">
                <button
                  onClick={() => openModalForEdit(product)}
                  className="px-4 py-1 text-sm bg-yellow-500 text-white rounded-md hover:bg-yellow-600 transition"
                >
                  編集
                </button>
                <button
                  onClick={() => handleDelete(product.id)}
                  disabled={isSubmitting}
                  className="px-4 py-1 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 transition disabled:opacity-50"
                >
                  削除
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-3 text-right">
              最終更新: {new Date(product.updated_at).toLocaleString('ja-JP')}
            </p>
          </div>
        ))}
      </div>

      {/* モーダル */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full flex items-center justify-center z-50 p-4">
          <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">
              {editingProduct ? '商品を編集' : '新規商品を登録'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">商品名 *</label>
                <input type="text" name="name" id="name" value={formData.name} onChange={handleInputChange} required className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" />
              </div>
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700">説明</label>
                <textarea name="description" id="description" rows={3} value={formData.description} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></textarea>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="price" className="block text-sm font-medium text-gray-700">価格</label>
                  <input type="number" name="price" id="price" value={formData.price} onChange={handleInputChange} placeholder="例: 10000" className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" />
                </div>
                <div>
                  <label htmlFor="currency" className="block text-sm font-medium text-gray-700">通貨</label>
                  <select name="currency" id="currency" value={formData.currency} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                    <option value="JPY">JPY</option>
                    <option value="USD">USD</option>
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor="target_audience" className="block text-sm font-medium text-gray-700">ターゲット顧客</label>
                <textarea name="target_audience" id="target_audience" rows={2} value={formData.target_audience} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></textarea>
              </div>
              <div>
                <label htmlFor="value_proposition" className="block text-sm font-medium text-gray-700">提供価値</label>
                <textarea name="value_proposition" id="value_proposition" rows={2} value={formData.value_proposition} onChange={handleInputChange} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"></textarea>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button type="button" onClick={closeModal} className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500">
                  キャンセル
                </button>
                <button type="submit" disabled={isSubmitting} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50">
                  {isSubmitting ? '処理中...' : (editingProduct ? '更新する' : '登録する')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}