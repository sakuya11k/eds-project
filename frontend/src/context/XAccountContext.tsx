'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { useAuth } from './AuthContext';

// --- 型定義 ---
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
  addXAccount: (accountData: NewXAccountData) => Promise<void>;
  deleteXAccount: (accountId: string) => Promise<void>;
  setActiveXAccount: (accountId: string) => Promise<void>;
  fetchXAccounts: () => Promise<void>;
}

// --- Contextの作成 ---
const XAccountContext = createContext<XAccountContextType | undefined>(undefined);

// --- Providerコンポーネント ---
export const XAccountProvider = ({ children }: { children: ReactNode }) => {
  const { user, session } = useAuth();
  const [xAccounts, setXAccounts] = useState<XAccount[]>([]);
  const [activeXAccount, setActiveXAccountState] = useState<XAccount | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const apiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    if (!session?.access_token) {
      throw new Error("認証トークンが見つかりません。");
    }
    
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
      ...options.headers,
    };

    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}${url}`, { ...options, headers });
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'サーバーから不明なエラー応答です。' }));
        throw new Error(errorData.error || `APIリクエストに失敗しました: ${response.statusText}`);
    }
    
    if (response.status === 204) { // No Contentの場合
        return null;
    }
    return response.json();
  }, [session]);

  const fetchXAccounts = useCallback(async () => {
    if (!user) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const accounts = await apiFetch('/api/v1/x-accounts');
      
      if (!Array.isArray(accounts)) {
        console.error("API did not return an array for x-accounts:", accounts);
        throw new Error("サーバーから予期しない形式の応答がありました。");
      }
      
      setXAccounts(accounts);
      const active = accounts.find((acc) => acc.is_active) ?? accounts[0] ?? null;
      setActiveXAccountState(active);

    } catch (error: unknown) {
      let errorMessage = 'Xアカウントの取得に失敗しました。';
      if (error instanceof Error) {
        errorMessage = error.message;
      }
      console.error(errorMessage, error);
      setXAccounts([]);
      setActiveXAccountState(null);
    } finally {
      setIsLoading(false);
    }
  }, [user, apiFetch]);

  useEffect(() => {
    if (user && session) {
      fetchXAccounts();
    } else if (!user) {
      setIsLoading(false);
      setXAccounts([]);
      setActiveXAccountState(null);
    }
  }, [user, session, fetchXAccounts]);

  const addXAccount = async (accountData: NewXAccountData) => {
    await apiFetch('/api/v1/x-accounts', {
      method: 'POST',
      body: JSON.stringify(accountData),
    });
    await fetchXAccounts();
  };

  const deleteXAccount = async (accountId: string) => {
    if (!window.confirm("このXアカウントを本当に削除してもよろしいですか？")) {
      return;
    }
    await apiFetch(`/api/v1/x-accounts/${accountId}`, { method: 'DELETE' });
    await fetchXAccounts();
  };
  
  const setActiveXAccount = async (accountId: string) => {
    await apiFetch(`/api/v1/x-accounts/${accountId}/activate`, { method: 'PUT' });
    await fetchXAccounts();
  };

  const value = {
    xAccounts,
    activeXAccount,
    isLoading,
    addXAccount,
    deleteXAccount,
    setActiveXAccount,
    fetchXAccounts,
  };

  return <XAccountContext.Provider value={value}>{children}</XAccountContext.Provider>;
};

// --- Custom Hook ---
export const useXAccount = (): XAccountContextType => {
  const context = useContext(XAccountContext);
  if (context === undefined) {
    throw new Error('useXAccount must be used within a XAccountProvider');
  }
  return context;
};