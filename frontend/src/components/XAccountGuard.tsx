
'use client';

import React, { ReactNode } from 'react';
import { useXAccount } from '@/context/XAccountContext';
import Link from 'next/link';

interface XAccountGuardProps {
  children: ReactNode;
}

const XAccountGuard: React.FC<XAccountGuardProps> = ({ children }) => {
  const { xAccounts, isLoading, isInitialized } = useXAccount();

  // データ取得中、または初期化が完了していない場合はローディング画面を表示
  if (isLoading || !isInitialized) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  // 初期化が完了し、かつ、Xアカウントが1件も登録されていない場合
  if (isInitialized && xAccounts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-80px)] text-center p-4">
        <h2 className="text-2xl font-bold mb-4 text-gray-800">Xアカウントの登録が必要です</h2>
        <p className="text-gray-600 mb-6 max-w-md">
          この機能を利用するには、まず管理対象のXアカウントを登録する必要があります。
          ダッシュボードからアカウントを追加してください。
        </p>
        <Link 
          href="/dashboard" 
          className="bg-blue-600 text-white font-bold py-3 px-6 rounded-lg hover:bg-blue-700 transition-transform transform hover:scale-105 shadow-lg"
        >
          アカウント管理ページへ
        </Link>
      </div>
    );
  }

  // チェックをパスした場合（アカウントが存在する場合）、ページの中身を表示
  return <>{children}</>;
};

export default XAccountGuard;