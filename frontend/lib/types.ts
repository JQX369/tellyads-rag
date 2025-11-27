export interface SearchResult {
  id: string;
  external_id: string;
  brand_name?: string;
  product_name?: string;
  text?: string;
  score?: number;
  meta?: any;
  item_type: string;
  image_url?: string;
  description?: string;
}

export interface AdDetail {
    id: string;
    external_id: string;
    brand_name?: string;
    product_name?: string;
    description?: string;
    duration_seconds?: number;
    year?: number;
    analysis?: any;
    impact_scores?: any;
    video_url?: string;
    image_url?: string;
}
