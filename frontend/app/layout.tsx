import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { defaultMetadata } from "@/lib/seo";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = defaultMetadata;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased min-h-screen bg-background text-foreground selection:bg-primary selection:text-white`}>
        {children}
      </body>
    </html>
  );
}
