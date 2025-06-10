'use client'

import React, { useEffect, useState, FormEvent, ChangeEvent, useCallback } from 'react'
import { useAuth } from '@/context/AuthContext'
import { useXAccount } from '@/context/XAccountContext'
import XAccountGuard from '@/components/XAccountGuard'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { supabase } from '@/lib/supabaseClient'
import { toast } from 'react-hot-toast'
import { PostCalendar } from '@/components/PostCalendar'

// --- 型定義 ---
export type Tweet = {
  id: string;
  user_id: string;
  x_account_id?: string | null;
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
  image_urls?: string[] | null;
}
type TweetFormData = {
  content: string;
  scheduled_at: string;
  image_urls: string[];
}
type ActiveTab = 'draft' | 'scheduled' | 'posted' | 'error';
type ViewMode = 'list' | 'calendar';

export default function TweetsPage() {
  const { user, session, loading: authLoading, signOut } = useAuth();
  const { activeXAccount, isLoading: isXAccountLoading } = useXAccount();
  const router = useRouter();

  const [tweets, setTweets] = useState<Tweet[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingTweet, setEditingTweet] = useState<Tweet | null>(null);
  const [formData, setFormData] = useState<TweetFormData>({ content: '', scheduled_at: '', image_urls: [] });
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>('draft');
  const [isCancellingSchedule, setIsCancellingSchedule] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('list');

  const apiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    if (!session?.access_token) throw new Error("認証セッションが無効です。");
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.access_token}`, ...options.headers };
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${url}`, { ...options, headers });
    if (!response.ok) {
        let errorBody;
        try { errorBody = await response.json(); } catch (e) { throw new Error(`サーバーエラー (Status: ${response.status})`); }
        throw new Error(errorBody?.message || errorBody?.error || `APIエラー (Status: ${response.status})`);
    }
    return response.status === 204 ? null : await response.json();
  }, [session]);

  const fetchTweets = useCallback(async () => {
    if (!user || !activeXAccount) {
      if (!isXAccountLoading) { setTweets([]); setIsLoading(false); }
      return;
    }
    setIsLoading(true); setError(null);
    try {
      const data = await apiFetch(`/api/v1/tweets?x_account_id=${activeXAccount.id}`);
      setTweets(data || []);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ツイート一覧の取得に失敗しました。';
      if (err instanceof Error && err.message.includes('401')) {
        signOut();
        router.push('/login');
      }
      setError(errorMessage); toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [user, activeXAccount, isXAccountLoading, apiFetch, signOut, router]);

  useEffect(() => {
    if (!authLoading && user) {
      fetchTweets();
    }
  }, [authLoading, user, fetchTweets]);

  const openTweetModal = (tweet: Tweet | null) => {
    if (tweet) {
      setEditingTweet(tweet);
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
          } catch (e) { console.warn("Error formatting scheduled_at for input: ", e); }
      }
      setFormData({ content: tweet.content, scheduled_at: scheduledDateString, image_urls: tweet.image_urls || [] });
    } else {
      setEditingTweet(null);
      setFormData({ content: '', scheduled_at: '', image_urls: [] });
    }
    setIsEditModalOpen(true);
  };

  const handleFormChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name in formData) {
      setFormData(prev => ({ ...prev, [name as keyof TweetFormData]: value }));
    }
  };

  const handleImageUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0 || !user) return;
    if ((formData.image_urls.length + e.target.files.length) > 4) { toast.error('画像は4枚までしかアップロードできません。'); return; }
    setIsUploading(true);
    const files = Array.from(e.target.files);
    const uploadedUrls: string[] = [];
    for (const file of files) {
      const fileExtension = file.name.split('.').pop() || 'png';
      const sanitizedFileName = file.name.replace(/\.[^/.]+$/, "").replace(/[^a-zA-Z0-9_.-]/g, '_');
      const finalFileName = `${Date.now()}-${sanitizedFileName}.${fileExtension}`;
      const filePath = `${user.id}/${finalFileName}`;
      try {
        const { data, error } = await supabase.storage.from('tweet-images').upload(filePath, file);
        if (error) throw error;
        const { data: publicUrlData } = supabase.storage.from('tweet-images').getPublicUrl(data.path);
        uploadedUrls.push(publicUrlData.publicUrl);
      } catch (error: any) {
        toast.error(`画像「${file.name}」のアップロードに失敗しました。詳細: ${error.message}`);
        setIsUploading(false); return;
      }
    }
    setFormData(prev => ({ ...prev, image_urls: [...prev.image_urls, ...uploadedUrls] }));
    setIsUploading(false); toast.success(`${files.length}枚の画像をアップロードしました。`);
  };

  const removeImage = (index: number) => {
    const newImageUrls = [...formData.image_urls];
    newImageUrls.splice(index, 1);
    setFormData(prev => ({ ...prev, image_urls: newImageUrls }));
  };

  const handleSaveTweet = async (e: FormEvent) => {
    e.preventDefault();
    if (!user || !activeXAccount) { toast.error('アカウントが選択されていません。'); return; }
    setIsSubmitting(true); setError(null);
    try {
      let scheduledAtISO: string | null = null;
      if (formData.scheduled_at) {
          const localDate = new Date(formData.scheduled_at);
          if (isNaN(localDate.getTime())) throw new Error("不正な日付です。");
          scheduledAtISO = localDate.toISOString();
      }

      const payload: Partial<Tweet> = {
        x_account_id: activeXAccount.id,
        content: formData.content,
        scheduled_at: scheduledAtISO,
        image_urls: formData.image_urls,
      };

      if (editingTweet) {
        const originalStatus = editingTweet.status;
        if (scheduledAtISO) {
          if (originalStatus === 'draft' || originalStatus === 'error') payload.status = 'scheduled';
        } else {
          if (originalStatus === 'scheduled') payload.status = 'draft';
        }
        await apiFetch(`/api/v1/tweets/${editingTweet.id}`, { method: 'PUT', body: JSON.stringify(payload) });
        toast.success('ツイートを更新しました。');
      } else {
        payload.status = scheduledAtISO ? 'scheduled' : 'draft';
        await apiFetch('/api/v1/tweets', { method: 'POST', body: JSON.stringify(payload) });
        toast.success('ツイートを作成しました。');
      }
      setIsEditModalOpen(false);
      fetchTweets();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ツイートの処理に失敗しました。';
      setError(errorMessage); toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteTweet = async (tweetId: string) => {
    if (!window.confirm('本当にこのツイートを削除しますか？')) return;
    setError(null);
    try {
      await apiFetch(`/api/v1/tweets/${tweetId}`, { method: 'DELETE' });
      toast.success('ツイートを削除しました。'); fetchTweets();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ツイートの削除に失敗しました。';
      setError(errorMessage); toast.error(errorMessage);
    }
  };

  const handlePostTweetNow = async (tweetId: string) => {
    if (!window.confirm('このツイートを今すぐXに投稿しますか？')) return;
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/tweets/${tweetId}/post-now`, { method: 'POST' });
      if (response && response.x_tweet_id) toast.success(`ツイートを投稿しました！ X ID: ${response.x_tweet_id}`);
      else toast.success('ツイートの投稿処理が完了しました。');
      fetchTweets();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'ツイートの投稿に失敗しました。';
      setError(errorMessage); toast.error(errorMessage);
    }
  };

  const handleCancelSchedule = async (tweetId: string) => {
    if (!window.confirm('このツイートの予約を解除し、下書きに戻しますか？')) return;
    setIsCancellingSchedule(tweetId); setError(null);
    try {
      await apiFetch(`/api/v1/tweets/${tweetId}`, { method: 'PUT', body: JSON.stringify({ status: 'draft', scheduled_at: null }) });
      toast.success('予約を解除し、下書きに戻しました。'); fetchTweets();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '予約の解除に失敗しました。';
      setError(errorMessage); toast.error(errorMessage);
    } finally { setIsCancellingSchedule(null); }
  };

  const filteredTweetsForList = tweets.filter(tweet => tweet.status === activeTab);
  const scheduledTweetsForCalendar = tweets.filter(tweet => tweet.status === 'scheduled' && tweet.scheduled_at);
  const tabs: { key: ActiveTab; label: string }[] = [{ key: 'draft', label: '未投稿' },{ key: 'scheduled', label: '予約' },{ key: 'posted', label: '投稿済み' },{ key: 'error', label: 'エラー' }];
  const handleCalendarEventClick = (tweetId: string) => { const tweet = tweets.find(t => t.id === tweetId); if (tweet) { openTweetModal(tweet); } };
  
  if (authLoading) { return <div className="text-center py-10">認証情報を確認中...</div>; }

  return (
    <XAccountGuard>
      <div className="max-w-5xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">ツイート管理</h1>
            {activeXAccount && <p className="text-indigo-600 font-semibold">対象アカウント: @{activeXAccount.x_username}</p>}
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex rounded-md shadow-sm">
              <button onClick={() => setViewMode('list')} type="button" className={`relative inline-flex items-center px-4 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium hover:bg-gray-50 focus:z-10 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 ${viewMode === 'list' ? 'text-indigo-600 bg-indigo-50' : 'text-gray-700'}`}>リスト</button>
              <button onClick={() => setViewMode('calendar')} type="button" className={`relative -ml-px inline-flex items-center px-4 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium hover:bg-gray-50 focus:z-10 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 ${viewMode === 'calendar' ? 'text-indigo-600 bg-indigo-50' : 'text-gray-700'}`}>カレンダー</button>
            </div>
            <button onClick={() => openTweetModal(null)} className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-lg shadow-md hover:bg-blue-700 transition duration-300 whitespace-nowrap">新規ツイート作成</button>
            <Link href="/educational-tweets" className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700 transition duration-300">AIで教育ツイート作成</Link>
          </div>
        </div>

        {error && <div className="mb-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert"><strong className="font-bold">エラー: </strong><span className="block sm:inline whitespace-pre-wrap">{error}</span></div>}

        {viewMode === 'list' && (
          <>
            <div className="mb-6 border-b border-gray-200"><nav className="-mb-px flex space-x-4 sm:space-x-8" aria-label="Tabs">{tabs.map(tab => (<button key={tab.key} onClick={() => setActiveTab(tab.key)} className={`${activeTab === tab.key ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'} whitespace-nowrap py-3 px-2 sm:py-4 sm:px-3 border-b-2 font-medium text-xs sm:text-sm transition-colors duration-150 ease-in-out focus:outline-none`} aria-current={activeTab === tab.key ? 'page' : undefined}>{tab.label}</button>))}</nav></div>
            {(isLoading || isXAccountLoading) && <div className="text-center py-10"><div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-indigo-500 mx-auto mb-3"></div><p className="text-gray-500">ツイート情報を読み込み中...</p></div>}
            {!isLoading && !isXAccountLoading && filteredTweetsForList.length === 0 && !error && (<div className="text-center py-10 bg-white shadow-md rounded-lg"><h3 className="mt-2 text-sm font-medium text-gray-900">このアカウントの「{tabs.find(t => t.key === activeTab)?.label}」ツイートはありません</h3><p className="mt-1 text-sm text-gray-500">新しいツイートを作成するか、他のタブを確認してください。</p></div>)}
            {filteredTweetsForList.length > 0 && (
              <div className="shadow overflow-x-auto border-b border-gray-200 sm:rounded-lg"><table className="min-w-full divide-y divide-gray-200"><thead className="bg-gray-50"><tr><th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">内容</th><th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ステータス</th><th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">予約/投稿日時</th><th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">X ID</th><th scope="col" className="relative px-6 py-3"><span className="sr-only">操作</span></th></tr></thead><tbody className="bg-white divide-y divide-gray-200">{filteredTweetsForList.map(tweet => (<tr key={tweet.id}><td className="px-6 py-4 max-w-xs"><div className="text-sm text-gray-900 whitespace-pre-wrap break-words">{tweet.content.length > 80 ? tweet.content.substring(0, 80) + "..." : tweet.content}</div>{tweet.image_urls && tweet.image_urls.length > 0 && (<div className="mt-2 flex space-x-2">{tweet.image_urls.map((url, idx) => (<a key={idx} href={url} target="_blank" rel="noopener noreferrer"><img src={url} alt={`attachment ${idx+1}`} className="h-10 w-10 object-cover rounded-md" /></a>))}</div>)}</td><td className="px-6 py-4 whitespace-nowrap"><span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${tweet.status === 'posted' ? 'bg-green-100 text-green-800' : tweet.status === 'scheduled' ? 'bg-yellow-100 text-yellow-800' : tweet.status === 'draft' ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800'}`}>{tweet.status}</span></td><td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{tweet.status === 'scheduled' && tweet.scheduled_at ? new Date(tweet.scheduled_at).toLocaleString('ja-JP') : tweet.status === 'posted' && tweet.posted_at ? new Date(tweet.posted_at).toLocaleString('ja-JP') : 'N/A'}</td><td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{tweet.x_tweet_id ? (<a href={`https://x.com/anyuser/status/${tweet.x_tweet_id}`} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">{tweet.x_tweet_id.substring(0,10)}...</a>) : 'N/A'}</td><td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-y-1 sm:space-y-0 sm:space-x-2 flex flex-col sm:flex-row items-end sm:items-center"><button onClick={() => openTweetModal(tweet)} className="text-indigo-600 hover:text-indigo-900 disabled:opacity-50" disabled={tweet.status === 'posted'}>編集</button><button onClick={() => handlePostTweetNow(tweet.id)} className="text-green-600 hover:text-green-900 disabled:opacity-50" disabled={tweet.status === 'posted' || tweet.status === 'error'}>今すぐ投稿</button>{tweet.status === 'scheduled' && (<button onClick={() => handleCancelSchedule(tweet.id)} className="text-yellow-600 hover:text-yellow-900 disabled:opacity-50" disabled={isCancellingSchedule === tweet.id}>{isCancellingSchedule === tweet.id ? '解除中...' : '予約解除'}</button>)}<button onClick={() => handleDeleteTweet(tweet.id)} className="text-red-600 hover:text-red-900">削除</button></td></tr>))}</tbody></table></div>
            )}
          </>
        )}

        {viewMode === 'calendar' && (
          <div>
            {isLoading && <p className="text-center py-10">カレンダーデータを読み込み中...</p>}
            {!isLoading && scheduledTweetsForCalendar.length === 0 && !error && (<div className="text-center py-10"><h3 className="mt-2 text-sm font-medium text-gray-900">予約投稿はありません</h3></div>)}
            {!isLoading && scheduledTweetsForCalendar.length > 0 && (<PostCalendar scheduledTweets={scheduledTweetsForCalendar} onEventClick={handleCalendarEventClick} />)}
          </div>
        )}

        {isEditModalOpen && (
          <div className="fixed inset-0 bg-gray-600 bg-opacity-75 overflow-y-auto h-full w-full flex items-center justify-center z-50 p-4">
            <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
              <h2 className="text-2xl font-bold mb-6 text-gray-800">{editingTweet ? 'ツイートを編集' : '新規ツイートを作成'}</h2>
              <form onSubmit={handleSaveTweet} className="space-y-6">
                <div><label htmlFor="content" className="block text-sm font-medium text-gray-700 mb-1">内容 *</label><textarea id="content" name="content" rows={7} value={formData.content} onChange={handleFormChange} required className="mt-1 block w-full px-3 py-2 border rounded-md"/></div>
                <div><label className="block text-sm font-medium text-gray-700 mb-1">画像 (4枚まで)</label><div className="mt-2"><input id="image-upload-input" type="file" multiple accept="image/*" onChange={handleImageUpload} className="hidden" disabled={isUploading || formData.image_urls.length >= 4}/><label htmlFor="image-upload-input" className={`px-4 py-2 text-sm font-medium text-white rounded-md cursor-pointer ${isUploading || formData.image_urls.length >= 4 ? 'bg-gray-400' : 'bg-indigo-600 hover:bg-indigo-700'}`}>{isUploading ? 'アップロード中...' : '画像を選択'}</label></div>{formData.image_urls.length > 0 && (<div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4">{formData.image_urls.map((url, index) => (<div key={index} className="relative group"><img src={url} alt={`Preview ${index + 1}`} className="w-full h-24 object-cover rounded-md"/><button type="button" onClick={() => removeImage(index)} className="absolute -top-2 -right-2 bg-red-600 text-white rounded-full p-1 leading-none w-6 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100">✕</button></div>))}</div>)}</div>
                <div><label htmlFor="scheduled_at" className="block text-sm font-medium text-gray-700 mb-1">予約日時 (任意)</label><input type="datetime-local" id="scheduled_at" name="scheduled_at" value={formData.scheduled_at} onChange={handleFormChange} className="mt-1 block w-full px-3 py-2 border rounded-md"/><p className="mt-1 text-xs text-gray-500">日時を設定するとステータスが「予約」になります。</p></div>
              
                <div className="flex justify-end space-x-3 pt-4"><button type="button" onClick={() => setIsEditModalOpen(false)} className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200">キャンセル</button><button type="submit" disabled={isSubmitting || isUploading} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50">{isSubmitting ? '保存中...' : (editingTweet ? '更新する' : '作成する')}</button></div>
              </form>
            </div>
          </div>
        )}
      </div>
    </XAccountGuard>
  )
}