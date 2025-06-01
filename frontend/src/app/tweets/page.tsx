'use client'

import React, { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext' //
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient' //
import { toast } from 'react-hot-toast'

// ツイートの型定義 (tweetsテーブルのカラムに合わせる)
type Tweet = {
  id: string;
  user_id: string;
  content: string;
  status: 'draft' | 'scheduled' | 'posted' | 'error';
  scheduled_at?: string | null;
  posted_at?: string | null;
  x_tweet_id?: string | null;
  education_element_key?: string | null;
  launch_id?: string | null;
  notes_internal?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export default function TweetsPage() {
  const { user, loading: authLoading, signOut } = useAuth() //
  const router = useRouter()

  const [tweets, setTweets] = useState<Tweet[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 認証チェック
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  // ツイート一覧の取得
  const fetchTweets = async () => {
    if (!user || authLoading) return;
    setIsLoading(true)
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession(); //
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。")
      }

      const response = await axios.get(
        `http://localhost:5001/api/v1/tweets`, //
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      )
      setTweets(response.data || [])
    } catch (err: any) {
      console.error('ツイート一覧取得エラー:', err)
      const errorMessage = err.response?.data?.message || err.message || 'ツイート一覧の取得に失敗しました。'
      setError(errorMessage)
      toast.error(errorMessage)
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
      fetchTweets()
    }
  }, [user, authLoading])


  const handleEditTweet = (tweetId: string) => {
    // TODO: ツイート編集モーダルを開くなどの処理
    toast(`ツイート編集機能は未実装です (ID: ${tweetId})`)
  }

  const handleDeleteTweet = async (tweetId: string) => {
    if (!user) {
      toast.error('ログインが必要です。');
      return;
    }
    if (!window.confirm('本当にこのツイートを削除しますか？この操作は元に戻せません。')) {
      return;
    }

    // setIsLoading(true); // fetchTweets が呼ばれるので、そちらで制御
    setError(null);

    try {
      const { data: { session } } = await supabase.auth.getSession(); //
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。");
      }

      await axios.delete(
        `http://localhost:5001/api/v1/tweets/${tweetId}`, //
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      toast.success('ツイートを削除しました。');
      fetchTweets(); 
    } catch (err: any) {
      console.error('ツイート削除エラー:', err);
      const errorMessage = err.response?.data?.message || err.message || 'ツイートの削除に失敗しました。';
      setError(errorMessage);
      toast.error(errorMessage);
    } 
    // finally { setIsLoading(false); } // fetchTweetsが最後にisLoadingをfalseにする
  };

  const handlePostTweetNow = async (tweetId: string) => {
    if (!user) {
      toast.error('ログインが必要です。');
      return;
    }
    if (!window.confirm('このツイートを今すぐXに投稿しますか？')) {
        return;
    }
    
    // setIsLoading(true); // fetchTweets が呼ばれるので、そちらで制御
    setError(null);

    try {
      const { data: { session } } = await supabase.auth.getSession(); //
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。");
      }

      const response = await axios.post(
        `http://localhost:5001/api/v1/tweets/${tweetId}/post-now`, //
        {}, 
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );

      if (response.data && response.data.x_tweet_id) {
        toast.success(`ツイートを投稿しました！ X Tweet ID: ${response.data.x_tweet_id}`);
      } else {
        toast.success('ツイートの投稿処理が完了しました。一覧を更新します。');
      }
      fetchTweets(); 
    } catch (err: any) {
      console.error('ツイート即時投稿エラー:', err);
      const errorMessage = err.response?.data?.message || err.message || 'ツイートの投稿に失敗しました。';
      let detailedError = err.response?.data?.error || err.response?.data?.error_detail_from_x || err.response?.data?.error_detail || '';
      if (detailedError && typeof detailedError === 'object') { 
        detailedError = JSON.stringify(detailedError);
      }
      const fullErrorMessage = `${errorMessage}${detailedError ? ` (詳細: ${detailedError})` : ''}`;
      setError(fullErrorMessage);
      toast.error(errorMessage); // トーストには簡潔なメッセージ、詳細はsetErrorで
    } 
    // finally { setIsLoading(false); } // fetchTweetsが最後にisLoadingをfalseにする
  };


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
    <div className="max-w-5xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="mb-8 flex justify-between items-center">
        <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">
          ツイート管理
        </h1>
        <Link href="/educational-tweets" className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700 transition duration-300">
          新規教育ツイート作成
        </Link>
      </div>

      {error && (
        <div className="mb-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
          <strong className="font-bold">エラー: </strong>
          <span className="block sm:inline whitespace-pre-wrap">{error}</span>
        </div>
      )}

      {isLoading && tweets.length === 0 && (
        <div className="text-center py-10">
          <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-indigo-500 mx-auto mb-3"></div>
          <p className="text-gray-500">ツイート情報を読み込み中...</p>
        </div>
      )}

      {!isLoading && tweets.length === 0 && !error && (
        <div className="text-center py-10 bg-white shadow-md rounded-lg">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2zm14-1V7a2 2 0 00-2-2H7a2 2 0 00-2 2v8a2 2 0 002 2h10a2 2 0 002-2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">ツイートがありません</h3>
          <p className="mt-1 text-sm text-gray-500">まだツイートが作成または保存されていません。</p>
          <div className="mt-6">
            <Link
              href="/educational-tweets"
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <svg className="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
              最初の教育ツイートを作成する
            </Link>
          </div>
        </div>
      )}

      {tweets.length > 0 && (
        <div className="shadow overflow-x-auto border-b border-gray-200 sm:rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  内容
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ステータス
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  予約/投稿日時
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  X ID
                </th>
                <th scope="col" className="relative px-6 py-3">
                  <span className="sr-only">操作</span>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {tweets.map((tweet) => (
                <tr key={tweet.id}>
                  <td className="px-6 py-4 max-w-xs"> {/* 幅調整 */}
                    <div className="text-sm text-gray-900 whitespace-pre-wrap break-words" title={tweet.content}>
                        {tweet.content.length > 80 ? tweet.content.substring(0, 80) + "..." : tweet.content}
                    </div>
                    {tweet.education_element_key && (
                        <div className="text-xs text-gray-400 mt-1">教育要素: {tweet.education_element_key}</div>
                    )}
                    {tweet.launch_id && (
                        <div className="text-xs text-gray-400 mt-1">ローンチID: <Link href={`/launches/${tweet.launch_id}/strategy`} className="hover:underline">{tweet.launch_id.substring(0,8)}...</Link></div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        tweet.status === 'posted' ? 'bg-green-100 text-green-800' :
                        tweet.status === 'scheduled' ? 'bg-yellow-100 text-yellow-800' :
                        tweet.status === 'draft' ? 'bg-blue-100 text-blue-800' :
                        'bg-red-100 text-red-800' 
                    }`}>
                      {tweet.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {tweet.status === 'scheduled' && tweet.scheduled_at ? new Date(tweet.scheduled_at).toLocaleString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : 
                     tweet.status === 'posted' && tweet.posted_at ? new Date(tweet.posted_at).toLocaleString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : 
                     'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {tweet.x_tweet_id ? (
                        <a 
                            href={`https://x.com/anyuser/status/${tweet.x_tweet_id}`} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-indigo-600 hover:text-indigo-900 hover:underline"
                            title="Xでツイートを見る"
                        >
                           {tweet.x_tweet_id.substring(0,10)}...
                        </a>
                    ) : 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-y-1 sm:space-y-0 sm:space-x-2 flex flex-col sm:flex-row items-end sm:items-center">
                    <button
                      onClick={() => handleEditTweet(tweet.id)}
                      className="text-indigo-600 hover:text-indigo-900 disabled:opacity-50 px-2 py-1 rounded-md hover:bg-gray-100 text-xs sm:text-sm"
                      title="編集 (未実装)"
                    >
                      編集
                    </button>
                    <button
                      onClick={() => handlePostTweetNow(tweet.id)}
                      className="text-green-600 hover:text-green-900 disabled:opacity-50 px-2 py-1 rounded-md hover:bg-gray-100 text-xs sm:text-sm"
                      disabled={tweet.status === 'posted'} 
                      title={tweet.status === 'posted' ? "投稿済み" : "今すぐ投稿"}
                    >
                      今すぐ投稿
                    </button>
                    <button
                      onClick={() => handleDeleteTweet(tweet.id)}
                      className="text-red-600 hover:text-red-900 disabled:opacity-50 px-2 py-1 rounded-md hover:bg-gray-100 text-xs sm:text-sm"
                      title="削除"
                    >
                      削除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}