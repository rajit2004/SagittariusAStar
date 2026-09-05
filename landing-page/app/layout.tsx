import { Analytics } from '@vercel/analytics/next'
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import { ThemeProvider } from '@/components/ThemeProvider'
import './globals.css'

const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] })
const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  metadataBase: new URL('https://rhythma-navy.vercel.app'),
  title: 'Rhythma - AI for Every Phase of Her Health',
  description:
    'Track your menstrual cycle, get personalized health insights, and access AI-powered guidance in your language.',
  generator: 'v0.app',
  keywords: [
    'menstrual cycle tracker',
    'period tracker',
    'women health AI',
    'health insights',
    'cycle tracking',
    'fertility tracking',
    'hormone health',
    'wellness app',
  ],
  themeColor: '#C46A8A',
  openGraph: {
    title: 'Rhythma - AI for Every Phase of Her Health',
    description:
      'Track your menstrual cycle, get personalized health insights, and access AI-powered guidance in your language.',
    url: 'https://rhythma-navy.vercel.app',
    siteName: 'Rhythma',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Rhythma - AI for Every Phase of Her Health',
    description:
      'Track your menstrual cycle, get personalized health insights, and access AI-powered guidance in your language.',
  },
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body className="font-sans antialiased">
        <ThemeProvider>
          {children}
        </ThemeProvider>
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
