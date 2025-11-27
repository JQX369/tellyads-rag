import { MetadataRoute } from 'next';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'https://tellyads.com';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // In a real app, fetch these from API
  // const ads = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/recent?limit=1000`).then(res => res.json());
  
  const routes = [
    '',
    '/about',
    '/how-it-works',
    '/search',
  ].map((route) => ({
    url: `${BASE_URL}${route}`,
    lastModified: new Date(),
    changeFrequency: 'daily' as const,
    priority: route === '' ? 1 : 0.8,
  }));

  return [...routes];
}
