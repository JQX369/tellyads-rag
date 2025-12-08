import type { Metadata } from "next";
import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import { defaultMetadata } from "@/lib/seo";
import { SmoothScrollProvider } from "@/components/providers/SmoothScrollProvider";
import { OrganizationJsonLd, WebSiteJsonLd } from "@/components/JsonLd";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  ...defaultMetadata,
  title: {
    default: "TellyAds — Every Ad Ever Aired",
    template: "%s | TellyAds",
  },
  description: "The definitive archive of television advertising. Explore decades of commercials, discover iconic campaigns, and research advertising history.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        {/* Site-wide JSON-LD Structured Data */}
        <OrganizationJsonLd />
        <WebSiteJsonLd />
      </head>
      <body
        className={`${spaceGrotesk.variable} ${ibmPlexMono.variable} font-display antialiased min-h-screen bg-void text-signal`}
      >
        <SmoothScrollProvider>
          <div className="film-grain">
            {children}
          </div>
        </SmoothScrollProvider>
      </body>
    </html>
  );
}
