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
  year?: number;
  one_line_summary?: string;
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
  impact_scores?: ImpactScores;
  video_url?: string;
  image_url?: string;
  product_category?: string;
  product_subcategory?: string;
  country?: string;
  language?: string;
  one_line_summary?: string;
  story_summary?: string;
  format_type?: string;
  primary_setting?: string;
  music_style?: string;
  editing_pace?: string;
  colour_mood?: string;
  has_voiceover?: boolean;
  has_dialogue?: boolean;
  has_celeb?: boolean;
}

export interface ImpactScores {
  overall_impact?: MetricScore;
  pulse_score?: MetricScore;
  echo_score?: MetricScore;
  hook_power?: MetricScore;
  brand_integration?: MetricScore;
  emotional_resonance?: MetricScore;
  clarity_score?: MetricScore;
  distinctiveness?: MetricScore;
}

export interface MetricScore {
  score: number;
  confidence?: number;
  rationale?: string;
}

export interface Brand {
  name: string;
  ad_count?: number;
}

export interface Stats {
  total_ads: number;
  total_brands: number;
}
