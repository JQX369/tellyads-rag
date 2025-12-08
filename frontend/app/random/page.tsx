import { redirect } from "next/navigation";

// Server component that fetches a random ad and redirects
export default async function RandomPage() {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    // Fetch a single random ad
    const response = await fetch(`${apiUrl}/api/recent?limit=100`, {
      cache: "no-store", // Always fetch fresh
    });

    if (!response.ok) {
      throw new Error("Failed to fetch ads");
    }

    const data = await response.json();
    const ads = data.ads || data || [];

    if (ads.length === 0) {
      redirect("/browse");
    }

    // Pick a random ad
    const randomIndex = Math.floor(Math.random() * ads.length);
    const randomAd = ads[randomIndex];

    redirect(`/ads/${randomAd.external_id}`);
  } catch (error) {
    console.error("Random redirect failed:", error);
    redirect("/browse");
  }
}

// Generate metadata - noindex since this is a redirect-only page
export const metadata = {
  title: "Random Ad | TellyAds",
  description: "Discover a random commercial from the TellyAds archive",
  robots: {
    index: false,
    follow: true,
  },
};
