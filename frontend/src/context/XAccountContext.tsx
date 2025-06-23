'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { toast } from 'react-hot-toast';

// --- 型定義  ---
export interface XAccount {
  id: string;
  x_username: string;
  is_active: boolean;
  created_at: string;
}

interface NewXAccountData {
  x_username: string;
  api_key: string;
  api_key_secret: string;
  access_token: string;
  access_token_secret: string;
}

interface XAccountContextType {
  xAccounts: XAccount[];
  activeXAccount: XAccount | null;
  isLoading: boolean;
  isInitialized: boolean; 
  addXAccount: (accountData: NewXAccountData) => Promise<void>;
  deleteXAccount: (accountId: string) => Promise<void>;
  setActiveXAccount: (accountId: string) => Promise<void>;
  fetchXAccounts: () => Promise<void>;
}

// --- Contextの作成  ---
const XAccountContext = createContext<XAccountContextType | undefined>(undefined);

// --- Providerコンポーネント ---
export const XAccountProvider = ({ children }: { children: ReactNode }) => {
  const { user, session } = useAuth();
  const [xAccounts, setXAccounts] = useState<XAccount[]>([]);
  const [activeXAccount, setActiveXAccountState] = useState<XAccount | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialized, setIsInitialized] = useState(false); // 初期化フラグを追加

  // apiFetch関数
  const apiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    if (!session?.access_token) {
      console.error("Authentication token is missing.");
      throw new Error("認証セッションが無効です。再度ログインしてください。");
    }
    
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
      ...options.headers,
    };

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${url}`, { ...options, headers });
      
      if (!response.ok) {
          let errorBody;
          try {
            errorBody = await response.json();
          } catch (e) {
            throw new Error(`サーバーから予期せぬ応答がありました (Status: ${response.status})`);
          }

          const errorMessage = errorBody?.message || errorBody?.error || `APIリクエストエラー (Status: ${response.status})`;
          throw new Error(errorMessage);
      }
      

      if (response.status === 204) {
          return null;
      }
      

      return response.json();

    } catch (error) {

       console.error(`API Fetch Error: ${url}`, error);

       throw error;
    }
  }, [session]);

  const fetchXAccounts = useCallback(async () => {
    // ユーザーセッションがない場合は何もせず、初期状態を維持
    if (!user || !session) {
      setIsLoading(false);
      setIsInitialized(true);
      return;
    }
    
    setIsLoading(true);
    try {
      const accounts: XAccount[] = await apiFetch('/api/v1/x-accounts');

      const validAccounts = Array.isArray(accounts) ? accounts : [];
      setXAccounts(validAccounts);

      const active = validAccounts.find((acc) => acc.is_active) ?? (validAccounts.length > 0 ? validAccounts[0] : null);
      setActiveXAccountState(active);

    } catch (error: unknown) {
      // fetchXAccountsでのエラーはユーザーに通知する
      const errorMessage = error instanceof Error ? error.message : 'Xアカウントの取得に失敗しました。';
      toast.error(errorMessage);
      console.error("Failed to fetch X accounts:", error);
      
      // エラー発生時は状態をクリア
      setXAccounts([]);
      setActiveXAccountState(null);
    } finally {
      setIsLoading(false);
      setIsInitialized(true); // 処理が完了したので初期化完了
    }
  }, [user, session, apiFetch]);

  useEffect(() => {
    // userとsessionが存在する場合にのみアカウント情報を取得する
    if (user && session) {
      fetchXAccounts();
    } else {
      // ログアウト時や初期表示時（user/sessionがまだない場合）の状態をクリア
      setIsLoading(false);
      setIsInitialized(!user); // userがいなければ初期化済みとみなす
      setXAccounts([]);
      setActiveXAccountState(null);
    }
  }, [user, session, fetchXAccounts]);

  const addXAccount = async (accountData: NewXAccountData) => {
    try {
      setIsLoading(true);
      await apiFetch('/api/v1/x-accounts', {
        method: 'POST',
        body: JSON.stringify(accountData),
      });
      toast.success(`${accountData.x_username} を追加しました。`);
      await fetchXAccounts(); // fetchXAccounts内でisLoadingがfalseになる
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'アカウントの追加に失敗しました。';
      toast.error(errorMessage);
      setIsLoading(false);
    }
  };

  const deleteXAccount = async (accountId: string) => {
    const accountToDelete = xAccounts.find(acc => acc.id === accountId);
    if (!accountToDelete) return;

    // テンプレートリテラルと二重引用符で安全に表示
    if (!window.confirm(`Xアカウント "${accountToDelete.x_username}" を本当に削除してもよろしいですか？`)) {
      return;
    }
    
    try {
      setIsLoading(true);
      await apiFetch(`/api/v1/x-accounts/${accountId}`, { method: 'DELETE' });
      toast.success(`${accountToDelete.x_username} を削除しました。`);
      await fetchXAccounts();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'アカウントの削除に失敗しました。';
      toast.error(errorMessage);
      setIsLoading(false);
    }
  };
  
  const setActiveXAccount = async (accountId: string) => {
    try {
      // アクティブ化はUIに即時反映させたいので、APIリクエスト前に状態を楽観的更新
      const newActiveAccount = xAccounts.find(acc => acc.id === accountId);
      if (newActiveAccount) {
         setXAccounts(prev => prev.map(acc => ({ ...acc, is_active: acc.id === accountId })));
         setActiveXAccountState(newActiveAccount);
      }

      await apiFetch(`/api/v1/x-accounts/${accountId}/activate`, { method: 'PUT' });
      toast.success(`${newActiveAccount?.x_username} に切り替えました。`);
      await fetchXAccounts();

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'アカウントの切り替えに失敗しました。';
      toast.error(errorMessage);
      await fetchXAccounts();
    }
  };

  const value = {
    xAccounts,
    activeXAccount,
    isLoading,
    isInitialized, // isInitializedをvalueに追加
    addXAccount,
    deleteXAccount,
    setActiveXAccount,
    fetchXAccounts,
  };

  return <XAccountContext.Provider value={value}>{children}</XAccountContext.Provider>;
};

// --- Custom Hook  ---
export const useXAccount = (): XAccountContextType => {
  const context = useContext(XAccountContext);
  if (context === undefined) {
    throw new Error('useXAccount must be used within a XAccountProvider');
  }
  return context;
};