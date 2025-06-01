'use client'

import React, { useEffect, useState, FormEvent } from 'react'
import { useAuth } from '@/context/AuthContext' //
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient' //
import { toast } from 'react-hot-toast'

// 教育要素の定義 (strategy/page.tsx のものを参考に調整)
const educationElementsOptions = [
  { key: '', label: '教育要素を選択してください', disabled: true },
  { key: 'product_analysis_summary', label: '商品分析の要点' },
  { key: 'target_customer_summary', label: 'ターゲット顧客分析の要点' },
  { type: 'separator', label: 'A. 6つの必須教育' },
  { key: 'edu_s1_purpose', label: '1. 目的の教育' },
  { key: 'edu_s2_trust', label: '2. 信用の教育' },
  { key: 'edu_s3_problem', label: '3. 問題点の教育' },
  { key: 'edu_s4_solution', label: '4. 手段の教育' },
  { key: 'edu_s5_investment', label: '5. 投資の教育' },
  { key: 'edu_s6_action', label: '6. 行動の教育' },
  { type: 'separator', label: 'B. 6つの強化教育' },
  { key: 'edu_r1_engagement_hook', label: '7. 読む・見る教育' },
  { key: 'edu_r2_repetition', label: '8. 何度も聞く教育' },
  { key: 'edu_r3_change_mindset', label: '9. 変化の教育' },
  { key: 'edu_r4_receptiveness', label: '10. 素直の教育' },
  { key: 'edu_r5_output_encouragement', label: '11. アウトプットの教育' },
  { key: 'edu_r6_baseline_shift', label: '12. 基準値の教育／覚悟の教育' },
]

export default function EducationalTweetsPage() {
  const { user, loading: authLoading, signOut } = useAuth() //
  const router = useRouter()

  const [selectedEducationElementKey, setSelectedEducationElementKey] = useState<string>('')
  const [tweetTheme, setTweetTheme] = useState<string>('')
  const [generatedTweet, setGeneratedTweet] = useState<string | null>(null)
  const [isLoadingAI, setIsLoadingAI] = useState<boolean>(false)
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  const handleGenerateEducationalTweet = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) {
      toast.error('ログインが必要です。')
      return
    }
    if (!selectedEducationElementKey) {
      toast.error('教育要素を選択してください。')
      return
    }
    if (!tweetTheme.trim()) {
      toast.error('ツイートのテーマやキーワードを入力してください。')
      return
    }

    setIsLoadingAI(true)
    setGeneratedTweet(null)
    setError(null)

    try {
      const { data: { session } } = await supabase.auth.getSession() //
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。")
      }

      const payload = {
        education_element_key: selectedEducationElementKey,
        theme: tweetTheme,
      }

      const response = await axios.post(
        'http://localhost:5001/api/v1/educational-tweets/generate',
        payload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      )

      if (response.data?.generated_tweet) {
        setGeneratedTweet(response.data.generated_tweet)
        toast.success('AIによるツイート案が生成されました！')
      } else {
        throw new Error(response.data?.message || 'AIからの応答が不正です。')
      }
    } catch (err: any) {
      console.error('教育ツイート生成エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || '教育ツイートの生成に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsLoadingAI(false)
    }
  }

  const handleSaveTweetDraft = async () => {
    if (!generatedTweet) {
      toast.error('保存するツイートがありません。')
      return
    }
    if (!user) {
      toast.error('ログインが必要です。')
      return
    }

    setIsSavingDraft(true)
    setError(null)

    try {
      const { data: { session } } = await supabase.auth.getSession() //
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。")
      }
      // education_element_key はツイートに紐づける情報として含める
      const payload = {
        content: generatedTweet,
        status: 'draft',
        education_element_key: selectedEducationElementKey,
        // launch_id はこのページでは不要なので null (または含めない)
      }
      await axios.post(
        'http://localhost:5001/api/v1/tweets', //
        payload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      )
      toast.success('ツイートを下書きとして保存しました！')
      setGeneratedTweet(null) // 保存後はクリアする
    } catch (err: any) {
      console.error('ツイート下書き保存エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || 'ツイートの下書き保存に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsSavingDraft(false)
    }
  }


  if (authLoading) {
    return (
      <div className="flex justify-center items-center min-h-[calc(100vh-200px)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="ml-4 text-lg text-gray-600">認証情報を確認中...</p>
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
    <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="mb-8">
        <Link href="/dashboard" className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center group">
          <svg className="w-5 h-5 mr-2 text-indigo-500 group-hover:text-indigo-700" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd"></path></svg>
          ダッシュボードへ戻る
        </Link>
      </div>
      <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-8 tracking-tight">
        教育ツイート作成 (日常用)
      </h1>

      <form onSubmit={handleGenerateEducationalTweet} className="space-y-8 bg-white p-8 sm:p-10 shadow-2xl rounded-2xl border border-gray-200 mb-12">
        <div>
          <label htmlFor="educationElement" className="block text-sm font-semibold text-gray-700 mb-2">
            1. 教育要素を選択
          </label>
          <select
            id="educationElement"
            name="educationElement"
            value={selectedEducationElementKey}
            onChange={(e) => setSelectedEducationElementKey(e.target.value)}
            required
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-white"
          >
            {educationElementsOptions.map((option) => {
              if (option.type === 'separator') {
                return <optgroup key={option.label} label={option.label} className="font-semibold bg-gray-50"></optgroup>
              }
              return (
                <option key={option.key} value={option.key} disabled={option.disabled} className={option.disabled ? "text-gray-400" : ""}>
                  {option.label}
                </option>
              )
            })}
          </select>
        </div>

        <div>
          <label htmlFor="tweetTheme" className="block text-sm font-semibold text-gray-700 mb-2">
            2. ツイートのテーマやキーワードを入力
          </label>
          <textarea
            id="tweetTheme"
            name="tweetTheme"
            rows={4}
            value={tweetTheme}
            onChange={(e) => setTweetTheme(e.target.value)}
            placeholder="例: 「目的の教育」なら「時間的自由を手に入れることの重要性について、具体的な事例を交えて」、などAIへの指示を入力"
            required
            className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm leading-relaxed"
          />
           <p className="mt-2 text-xs text-gray-500">
            選択した教育要素と、ここに入力したテーマに基づいてAIがツイート案を作成します。
          </p>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={isLoadingAI || isSavingDraft}
            className="w-full flex justify-center py-3 px-6 border border-transparent rounded-lg shadow-md text-lg font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition duration-150 ease-in-out"
          >
            {isLoadingAI ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                AIがツイート生成中...
              </>
            ) : (
              'AIでツイート案を生成する'
            )}
          </button>
        </div>
      </form>

      {error && (
        <div className="mb-6 bg-red-50 p-4 rounded-lg border border-red-200">
          <p className="text-sm font-medium text-red-700">エラー: {error}</p>
        </div>
      )}

      {generatedTweet && !isLoadingAI && (
        <div className="mt-10 p-6 border rounded-lg bg-gray-50 shadow-lg">
          <h3 className="text-xl font-semibold text-gray-800 mb-4">AIが生成したツイート案:</h3>
          <textarea
            readOnly
            value={generatedTweet}
            rows={7}
            className="w-full p-4 border border-gray-300 rounded-md bg-white text-gray-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            onClick={(e) => (e.target as HTMLTextAreaElement).select()}
            aria-label="AIが生成したツイート案"
          />
          <div className="mt-6 flex justify-end">
            <button
              onClick={handleSaveTweetDraft}
              disabled={isSavingDraft || isLoadingAI}
              className="px-6 py-2 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 transition duration-300 disabled:opacity-50"
            >
              {isSavingDraft ? (
                <>
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  保存中...
                </>
              ) : (
                '下書きとして保存'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}