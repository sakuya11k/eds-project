import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/context/AuthContext'
import { Toaster } from 'react-hot-toast'
import Header from '@/components/header' // ← 小文字に統一したパス

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'EDS - AI Assistant',
  description: 'X運用と高額商品販売を自動化',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ja">
      <body className={inter.className}>
        <AuthProvider>
          <Toaster position="top-center" reverseOrder={false} />
          <Header />
          <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {children}
          </main>
        </AuthProvider>
      </body>
    </html>
  )
}