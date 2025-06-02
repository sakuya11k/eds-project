'use client'

import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction' // イベントクリックなどのために必要
import { EventClickArg } from '@fullcalendar/core'

// フロントエンドのTweet型をインポート (必要に応じてパスを調整)
import { type Tweet } from '@/app/tweets/page' // 仮のパス

interface PostCalendarProps {
  scheduledTweets: Tweet[];
  onEventClick: (tweetId: string) => void;
}

const PostCalendar = ({ scheduledTweets, onEventClick }: PostCalendarProps) => {

  // FullCalendarが要求するイベント形式にツイートデータを変換
  const events = scheduledTweets.map(tweet => ({
    id: tweet.id,
    title: tweet.content, // カレンダーに表示するテキスト
    start: tweet.scheduled_at, // 予約日時
    allDay: false, // 時間も考慮する場合はfalse
    extendedProps: { // カスタムデータを格納
      tweetData: tweet,
    },
    // イベントの色をステータスに応じて変えることも可能
    // backgroundColor: '#yourColor',
    // borderColor: '#yourColor',
  }));

  // カレンダー上のイベントがクリックされたときの処理
  const handleEventClick = (clickInfo: EventClickArg) => {
    // extendedPropsからツイートIDを取得して親コンポーネントの関数を呼び出す
    const tweetId = clickInfo.event.id;
    if (tweetId) {
      onEventClick(tweetId);
    }
  };

  return (
    <div className="p-4 bg-white rounded-lg shadow-md">
       <FullCalendar
        plugins={[dayGridPlugin, interactionPlugin]}
        initialView="dayGridMonth"
        weekends={true}
        events={events
          .filter(event => event.start != null) // startがnullまたはundefinedのイベントを除外
          .map(event => ({ ...event, start: event.start! })) //残ったイベントのstartをstringとして扱う (non-null assertion)
        }
        eventClick={handleEventClick}
        locale="ja" // 日本語化
        headerToolbar={{
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,dayGridWeek' // 週表示も追加する例
        }}
        buttonText={{
          today: '今日',
          month: '月',
          week: '週',
          day: '日',
        }}
        eventTimeFormat={{ // 時間のフォーマット
            hour: '2-digit',
            minute: '2-digit',
            meridiem: false
        }}
        height="auto" // コンテンツの高さに合わせる
      />
    </div>
  )
}

export { PostCalendar }