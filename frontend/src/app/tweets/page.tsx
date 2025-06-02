'use client'

import React, { useEffect, useState, FormEvent } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import axios from 'axios'
import { supabase } from '@/lib/supabaseClient'
import { toast } from 'react-hot-toast'
import { PostCalendar } from '@/components/PostCalendar' // ★ PostCalendarコンポーネントをインポート

// ★ Tweet型定義をエクスポートするように変更
export type Tweet = {
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

// 編集用フォームデータの型
type TweetEditFormData = {
  content: string;
  scheduled_at: string;
}

// アクティブなタブを管理する型
type ActiveTab = 'draft' | 'scheduled' | 'posted' | 'error';

// ★ 表示モードを管理する型 (新規追加)
type ViewMode = 'list' | 'calendar';

export default function TweetsPage() {
  const { user, loading: authLoading, signOut } = useAuth()
  const router = useRouter()

  const [tweets, setTweets] = useState<Tweet[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editingTweet, setEditingTweet] = useState<Tweet | null>(null)
  const [editFormData, setEditFormData] = useState<TweetEditFormData>({
    content: '',
    scheduled_at: '',
  })
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false)
  const [activeTab, setActiveTab] = useState<ActiveTab>('draft');
  const [isCancellingSchedule, setIsCancellingSchedule] = useState<string | null>(null);

  // ★ 表示モードを管理するstate (新規追加)
  const [viewMode, setViewMode] = useState<ViewMode>('list');


  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login')
    }
  }, [user, authLoading, router])

  const fetchTweets = async () => {
    if (!user || authLoading) return;
    setIsLoading(true)
    setError(null)
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。")
      }
      const response = await axios.get(
        `http://localhost:5001/api/v1/tweets`,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      )
      setTweets(response.data || [])
    } catch (err: unknown) {
      console.error('ツイート一覧取得エラー:', err)
      let errorMessage = 'ツイート一覧の取得に失敗しました。'
      if (axios.isAxiosError(err) && err.response) {
           errorMessage = err.response.data?.message || err.message || errorMessage;
           if (err.response.status === 401) {
                await signOut();
                router.push('/login');
           }
      } else if (err instanceof Error) {
           errorMessage = err.message;
      }
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (user && !authLoading) {
      fetchTweets()
    }
  }, [user, authLoading])

  const handleEditTweet = (tweet: Tweet) => {
    setEditingTweet(tweet)
    let scheduledDateString = '';
    if (tweet.scheduled_at) {
        try {
            const dateObj = new Date(tweet.scheduled_at);
            const year = dateObj.getFullYear();
            const month = (`0${dateObj.getMonth() + 1}`).slice(-2);
            const day = (`0${dateObj.getDate()}`).slice(-2);
            const hours = (`0${dateObj.getHours()}`).slice(-2);
            const minutes = (`0${dateObj.getMinutes()}`).slice(-2);
            scheduledDateString = `${year}-${month}-${day}T${hours}:${minutes}`;
        } catch (e) {
            console.warn("Error formatting scheduled_at for input: ", e);
        }
    }
    setEditFormData({
      content: tweet.content,
      scheduled_at: scheduledDateString,
    })
    setIsEditModalOpen(true)
  }

  const handleEditFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setEditFormData(prev => ({ ...prev, [name]: value as string }));
  };

  const handleUpdateTweet = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingTweet || !user) {
      toast.error('更新対象のツイートが見つからないか、認証されていません。');
      return;
    }
    setIsSubmittingEdit(true);
    setError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。");
      }
      let scheduledAtISO: string | null = null;
      if (editFormData.scheduled_at) {
        try {
            const localDate = new Date(editFormData.scheduled_at);
            if (isNaN(localDate.getTime())) {
                throw new Error("Invalid date value from input.");
            }
            scheduledAtISO = localDate.toISOString();
        } catch (parseError) {
            console.error("Invalid date format for scheduled_at:", editFormData.scheduled_at, parseError);
            toast.error("予約日時の形式が正しくありません。");
            setIsSubmittingEdit(false);
            return;
        }
      }
      const payload: Partial<Tweet> = {
        content: editFormData.content,
        scheduled_at: scheduledAtISO,
      };
      if (editingTweet) {
        const originalStatus = editingTweet.status;
        if (scheduledAtISO) {
          if (originalStatus === 'draft' || originalStatus === 'error') {
            payload.status = 'scheduled';
          }
        } else {
          if (originalStatus === 'scheduled') {
            payload.status = 'draft';
          }
        }
      }
      await axios.put(
        `http://localhost:5001/api/v1/tweets/${editingTweet.id}`,
        payload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      toast.success('ツイートを更新しました。');
      setIsEditModalOpen(false);
      setEditingTweet(null);
      fetchTweets();
    } catch (err: unknown) {
      console.error('ツイート更新エラー:', err);
      let errorMessage = 'ツイートの更新に失敗しました。';
       if (axios.isAxiosError(err) && err.response) {
           errorMessage = err.response.data?.message || err.message || errorMessage;
      } else if (err instanceof Error) {
           errorMessage = err.message;
      }
      setError(errorMessage);
      toast.error('ツイートの更新に失敗しました。');
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  const handleDeleteTweet = async (tweetId: string) => {
    if (!user) {
      toast.error('ログインが必要です。');
      return;
    }
    if (!window.confirm('本当にこのツイートを削除しますか？この操作は元に戻せません。')) {
      return;
    }
    setError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。");
      }
      await axios.delete(
        `http://localhost:5001/api/v1/tweets/${tweetId}`,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      toast.success('ツイートを削除しました。');
      fetchTweets();
    } catch (err: unknown) {
      console.error('ツイート削除エラー:', err);
      let errorMessage = 'ツイートの削除に失敗しました。';
      if (axios.isAxiosError(err) && err.response) {
           errorMessage = err.response.data?.message || err.message || errorMessage;
      } else if (err instanceof Error) {
           errorMessage = err.message;
      }
      setError(errorMessage);
      toast.error(errorMessage);
    }
  };

  const handlePostTweetNow = async (tweetId: string) => {
    if (!user) {
      toast.error('ログインが必要です。');
      return;
    }
    if (!window.confirm('このツイートを今すぐXに投稿しますか？')) {
        return;
    }
    setError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。");
      }
      const response = await axios.post(
        `http://localhost:5001/api/v1/tweets/${tweetId}/post-now`,
        {},
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      if (response.data && response.data.x_tweet_id) {
        toast.success(`ツイートを投稿しました！ X Tweet ID: ${response.data.x_tweet_id}`);
      } else {
        toast.success('ツイートの投稿処理が完了しました。一覧を更新します。');
      }
      fetchTweets();
    } catch (err: unknown) {
      console.error('ツイート即時投稿エラー:', err);
      let errorMessage = 'ツイートの投稿に失敗しました。';
      let detailedError = '';
      if (axios.isAxiosError(err) && err.response) {
        errorMessage = err.response.data?.message || err.message || errorMessage;
        detailedError = err.response.data?.error || err.response.data?.error_detail_from_x || err.response.data?.error_detail || '';
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }
      if (detailedError && typeof detailedError === 'object') {
        detailedError = JSON.stringify(detailedError);
      }
      const fullErrorMessage = `${errorMessage}${detailedError ? ` (詳細: ${detailedError})` : ''}`;
      setError(fullErrorMessage);
      toast.error(errorMessage);
    }
  };

  const handleCancelSchedule = async (tweetId: string) => {
    if (!user) {
      toast.error('ログインが必要です。');
      return;
    }
    if (!window.confirm('このツイートの予約を解除し、下書きに戻しますか？')) {
      return;
    }
    setIsCancellingSchedule(tweetId);
    setError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("セッションが見つかりません。再度ログインしてください。");
      }
      const payload: Partial<Tweet> = {
        status: 'draft',
        scheduled_at: null,
      };
      await axios.put(
        `http://localhost:5001/api/v1/tweets/${tweetId}`,
        payload,
        { headers: { Authorization: `Bearer ${session.access_token}` } }
      );
      toast.success('ツイートの予約を解除し、下書きに戻しました。');
      fetchTweets();
    } catch (err: unknown) {
      console.error('予約解除エラー:', err);
      let errorMessage = '予約の解除に失敗しました。';
       if (axios.isAxiosError(err) && err.response) {
           errorMessage = err.response.data?.message || err.message || errorMessage;
      } else if (err instanceof Error) {
           errorMessage = err.message;
      }
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsCancellingSchedule(null);
    }
  };

  // ★ リスト表示用のフィルタリングされたツイート
  const filteredTweetsForList = tweets.filter(tweet => {
    return tweet.status === activeTab;
  });

  // ★ カレンダー表示用の予約投稿ツイート
  const scheduledTweetsForCalendar = tweets.filter(tweet => tweet.status === 'scheduled');

  const tabs: { key: ActiveTab; label: string }[] = [
    { key: 'draft', label: '未投稿' },
    { key: 'scheduled', label: '予約' },
    { key: 'posted', label: '投稿済み' },
    { key: 'error', label: 'エラー' },
  ];

  // ★ カレンダー上のイベントがクリックされたときの処理 (新規追加)
  const handleCalendarEventClick = (tweetId: string) => {
    const tweetToEdit = tweets.find(tweet => tweet.id === tweetId);
    if (tweetToEdit) {
      handleEditTweet(tweetToEdit); // 既存の編集モーダルを開く関数を呼び出す
    } else {
      toast.error('編集対象のツイートが見つかりませんでした。');
    }
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
        <div className="flex items-center space-x-4"> {/* ボタンを横並びにするためのコンテナ */}
          {/* ★ 表示モード切り替えボタン (新規追加) */}
          <div className="flex rounded-md shadow-sm">
            <button
              onClick={() => setViewMode('list')}
              type="button"
              className={`relative inline-flex items-center px-4 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium hover:bg-gray-50 focus:z-10 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 ${
                viewMode === 'list' ? 'text-indigo-600 bg-indigo-50' : 'text-gray-700'
              }`}
            >
              リスト
            </button>
            <button
              onClick={() => setViewMode('calendar')}
              type="button"
              className={`relative -ml-px inline-flex items-center px-4 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium hover:bg-gray-50 focus:z-10 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 ${
                viewMode === 'calendar' ? 'text-indigo-600 bg-indigo-50' : 'text-gray-700'
              }`}
            >
              カレンダー
            </button>
          </div>
          <Link href="/educational-tweets" className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700 transition duration-300">
            新規教育ツイート作成
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
          <strong className="font-bold">エラー: </strong>
          <span className="block sm:inline whitespace-pre-wrap">{error}</span>
        </div>
      )}

      {/* ★ リスト表示の場合のUI */}
      {viewMode === 'list' && (
        <>
          <div className="mb-6 border-b border-gray-200">
            <nav className="-mb-px flex space-x-4 sm:space-x-8" aria-label="Tabs">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`${
                    activeTab === tab.key
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  } whitespace-nowrap py-3 px-2 sm:py-4 sm:px-3 border-b-2 font-medium text-xs sm:text-sm transition-colors duration-150 ease-in-out focus:outline-none`}
                  aria-current={activeTab === tab.key ? 'page' : undefined}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {isLoading && filteredTweetsForList.length === 0 && (
            <div className="text-center py-10">
              <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-indigo-500 mx-auto mb-3"></div>
              <p className="text-gray-500">ツイート情報を読み込み中...</p>
            </div>
          )}

          {!isLoading && filteredTweetsForList.length === 0 && !error && (
            <div className="text-center py-10 bg-white shadow-md rounded-lg">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2zm14-1V7a2 2 0 00-2-2H7a2 2 0 00-2 2v8a2 2 0 002 2h10a2 2 0 002-2z" />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">
                {tabs.find(t => t.key === activeTab)?.label} のツイートはありません
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                新しいツイートを作成するか、他のタブを確認してください。
              </p>
              {(activeTab === 'draft' || activeTab === 'scheduled') && (
                <div className="mt-6">
                  <Link
                    href="/educational-tweets"
                    className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  >
                    <svg className="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                      <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
                    </svg>
                    教育ツイートを作成する
                  </Link>
                </div>
              )}
            </div>
          )}

          {filteredTweetsForList.length > 0 && (
            <div className="shadow overflow-x-auto border-b border-gray-200 sm:rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">内容</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ステータス</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">予約/投稿日時</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">X ID</th>
                    <th scope="col" className="relative px-6 py-3"><span className="sr-only">操作</span></th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredTweetsForList.map((tweet) => (
                    <tr key={tweet.id}>
                      <td className="px-6 py-4 max-w-xs">
                        <div className="text-sm text-gray-900 whitespace-pre-wrap break-words" title={tweet.content}>
                            {tweet.content.length > 80 ? tweet.content.substring(0, 80) + "..." : tweet.content}
                        </div>
                        {tweet.education_element_key && (<div className="text-xs text-gray-400 mt-1">教育要素: {tweet.education_element_key}</div>)}
                        {tweet.launch_id && (<div className="text-xs text-gray-400 mt-1">ローンチID: <Link href={`/launches/${tweet.launch_id}/strategy`} className="hover:underline">{tweet.launch_id.substring(0,8)}...</Link></div>)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            tweet.status === 'posted' ? 'bg-green-100 text-green-800' :
                            tweet.status === 'scheduled' ? 'bg-yellow-100 text-yellow-800' :
                            tweet.status === 'draft' ? 'bg-blue-100 text-blue-800' :
                            'bg-red-100 text-red-800'
                        }`}>{tweet.status}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {tweet.status === 'scheduled' && tweet.scheduled_at ? new Date(tweet.scheduled_at).toLocaleString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) :
                         tweet.status === 'posted' && tweet.posted_at ? new Date(tweet.posted_at).toLocaleString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) :
                         'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {tweet.x_tweet_id ? (<a href={`https://x.com/anyuser/status/${tweet.x_tweet_id}`} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-900 hover:underline" title="Xでツイートを見る">{tweet.x_tweet_id.substring(0,10)}...</a>) : 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-y-1 sm:space-y-0 sm:space-x-2 flex flex-col sm:flex-row items-end sm:items-center">
                        <button onClick={() => handleEditTweet(tweet)} className="text-indigo-600 hover:text-indigo-900 disabled:opacity-50 disabled:cursor-not-allowed px-2 py-1 rounded-md hover:bg-gray-100 text-xs sm:text-sm" title={tweet.status === 'posted' ? "投稿済みツイートは編集できません" : "編集"} disabled={tweet.status === 'posted'}>編集</button>
                        <button onClick={() => handlePostTweetNow(tweet.id)} className="text-green-600 hover:text-green-900 disabled:opacity-50 px-2 py-1 rounded-md hover:bg-gray-100 text-xs sm:text-sm" disabled={tweet.status === 'posted' || tweet.status === 'error'} title={tweet.status === 'posted' ? "投稿済み" : (tweet.status === 'error' ? "エラーのため投稿不可" : "今すぐ投稿")}>今すぐ投稿</button>
                        {tweet.status === 'scheduled' && (<button onClick={() => handleCancelSchedule(tweet.id)} className="text-yellow-600 hover:text-yellow-900 disabled:opacity-50 px-2 py-1 rounded-md hover:bg-gray-100 text-xs sm:text-sm" title="予約を解除" disabled={isCancellingSchedule === tweet.id}>{isCancellingSchedule === tweet.id ? '解除中...' : '予約解除'}</button>)}
                        <button onClick={() => handleDeleteTweet(tweet.id)} className="text-red-600 hover:text-red-900 px-2 py-1 rounded-md hover:bg-gray-100 text-xs sm:text-sm" title="削除">削除</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ★ カレンダー表示の場合のUI */}
      {viewMode === 'calendar' && (
        <div>
          {isLoading && <p className="text-center py-10 text-gray-500">カレンダーデータを読み込み中...</p>}
          {!isLoading && scheduledTweetsForCalendar.length === 0 && !error && (
            <div className="text-center py-10 bg-white shadow-md rounded-lg p-6">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">表示できる予約投稿はありません</h3>
              <p className="mt-1 text-sm text-gray-500">
                ツイートを予約すると、このカレンダーに表示されます。
              </p>
            </div>
          )}
          {!isLoading && scheduledTweetsForCalendar.length > 0 && (
             <PostCalendar
                scheduledTweets={scheduledTweetsForCalendar}
                onEventClick={handleCalendarEventClick}
             />
          )}
           {error && viewMode === 'calendar' && ( // カレンダー表示時にエラーがあれば表示
            <div className="mt-4 text-center text-red-500">
                カレンダーデータの取得中にエラーが発生しました。
            </div>
           )}
        </div>
      )}

      {/* ツイート編集モーダル */}
      {isEditModalOpen && editingTweet && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75 overflow-y-auto h-full w-full flex items-center justify-center z-50 p-4">
          <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">ツイートを編集</h2>
            <form onSubmit={handleUpdateTweet} className="space-y-6">
              <div>
                <label htmlFor="edit-content" className="block text-sm font-medium text-gray-700 mb-1">内容 *</label>
                <textarea
                  id="edit-content"
                  name="content"
                  rows={7}
                  value={editFormData.content}
                  onChange={handleEditFormChange}
                  required
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                />
              </div>
              <div>
                <label htmlFor="edit-scheduled_at" className="block text-sm font-medium text-gray-700 mb-1">予約日時 (任意)</label>
                <input
                  type="datetime-local"
                  id="edit-scheduled_at"
                  name="scheduled_at"
                  value={editFormData.scheduled_at}
                  onChange={handleEditFormChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                />
                <p className="mt-1 text-xs text-gray-500">
                  この日時を設定すると、ツイートのステータスが自動的に「予約」に変更されることがあります。
                </p>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => { setIsEditModalOpen(false); setEditingTweet(null); }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
                >
                  キャンセル
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingEdit}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                >
                  {isSubmittingEdit ? '更新中...' : '更新する'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}