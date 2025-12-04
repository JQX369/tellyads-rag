import csv
from pathlib import Path
from typing import Dict, Optional

class TellyAdsCSVParser:
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        self.ad_map: Dict[str, Dict] = {}
        self._load_csv()

    def _load_csv(self):
        """Loads the CSV and builds a lookup map by external_id"""
        if not self.csv_path.exists():
            return

        try:
            with open(self.csv_path, mode='r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean up keys if necessary (sometimes there are BOMs or weird chars)
                    # Mapping: record_id, movie_filename -> external_id
                    
                    # In TellyAds data:
                    # movie_filename usually looks like "TA12345"
                    # record_id is "12345"
                    
                    external_id = row.get("movie_filename")
                    if external_id:
                        self.ad_map[external_id] = {
                            "video_url": row.get("VID_filename_Link"),
                            "image_url": row.get("still_filename_Link"),
                            "title": row.get("commercial_title"),
                            "advertiser": row.get("advertiser-1"),
                            "date_collected": row.get("Date_Collected")
                        }
        except Exception as e:
            print(f"Error loading CSV: {e}")

    def get_ad_data(self, external_id: str) -> Optional[Dict]:
        """Returns CSV data for a given external_id"""
        return self.ad_map.get(external_id)

# Singleton instance to be used by the API
# In a real app, this path should be from env or config
DEFAULT_CSV_PATH = "TELLY+ADS (2).csv"
parser = TellyAdsCSVParser(DEFAULT_CSV_PATH)

def get_video_url_from_csv(external_id: str) -> Optional[str]:
    data = parser.get_ad_data(external_id)
    return data.get("video_url") if data else None

def get_image_url_from_csv(external_id: str) -> Optional[str]:
    data = parser.get_ad_data(external_id)
    return data.get("image_url") if data else None





