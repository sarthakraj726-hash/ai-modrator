import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Goddess AI | Broadcast Operations Command Center",
  description: "Developer Control Center for Honney AI Co-Host & Live Stream Multi-Channel Management",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#08090f] text-slate-200 min-h-screen antialiased selection:bg-purple-600 selection:text-white">
        {children}
      </body>
    </html>
  );
}
