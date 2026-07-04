import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Neptune Bitumen Bid Aggregator",
  description: "Aggregate bitumen procurement tenders across Africa, Southeast Asia, and India",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>
          <div className="min-h-screen bg-gray-50">
            <header className="bg-[#1a365d] text-white shadow-md">
              <div className="max-w-screen-xl mx-auto px-4 py-4 flex items-center gap-3">
                <div className="w-8 h-8 bg-amber-400 rounded-full flex items-center justify-center font-bold text-[#1a365d]">
                  N
                </div>
                <div>
                  <h1 className="text-lg font-bold leading-tight">Neptune Petrochemicals</h1>
                  <p className="text-xs text-blue-200">Bitumen Bid Aggregator</p>
                </div>
                <nav className="ml-auto flex gap-6 text-sm">
                  <a href="/" className="hover:text-amber-400 transition-colors">Dashboard</a>
                  <a href="/alerts" className="hover:text-amber-400 transition-colors">Alerts</a>
                </nav>
              </div>
            </header>
            <main className="max-w-screen-xl mx-auto px-4 py-6">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
