import { Metadata } from "next";
import { constructMetadata } from "@/lib/seo";

export const metadata: Metadata = constructMetadata({
  title: "Browse TV Adverts",
  description:
    "Browse the TellyAds archive of thousands of TV commercials. Filter by decade, category, or brand to discover classic and modern advertising.",
  path: "/browse",
});

export default function BrowseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
