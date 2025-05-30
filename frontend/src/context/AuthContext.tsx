'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { supabase } from '@/lib/supabaseClient'
import { Session, User } from '@supabase/supabase-js'

// Context の型定義
type AuthContextType = {
  session: Session | null
  user: User | null
  loading: boolean
  signOut: () => Promise<void>
}

// Context の作成 (初期値は undefined)
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Context を提供する Provider コンポーネント
export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [session, setSession] = useState<Session | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)

    // 最初に現在のセッションを取得
    const getSession = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        setSession(session);
        setUser(session?.user ?? null);
        setLoading(false);
    };

    getSession();


    // 認証状態の変化を監視
    const { data: authListener } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setUser(session?.user ?? null)
        setLoading(false)
      }
    )

    // クリーンアップ関数: コンポーネントがアンマウントされたときにリスナーを解除
    return () => {
      authListener?.subscription.unsubscribe()
    }
  }, [])

  // ログアウト関数
  const signOut = async () => {
    await supabase.auth.signOut()
  }

  const value = {
    session,
    user,
    loading,
    signOut,
  }

  // loading 中は何も表示しないか、ローディング画面を表示 (ここでは children を表示)
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// Context を簡単に利用するためのカスタムフック
export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}