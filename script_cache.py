# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Script Cache module for storing and retrieving learned Playwright DOM action maps for URLs.
"""

import json
import os
import urllib.parse
from typing import Dict, Any, List, Optional

CACHE_DIR = os.environ.get("CACHE_DIR", "./site_cache")


def ensure_cache_dir():
    """Creates cache directory if it does not exist."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_key_from_url(url: str) -> str:
    """Normalizes URL into a safe filename string."""
    parsed = urllib.parse.urlparse(url)
    clean = f"{parsed.netloc}{parsed.path}".replace("/", "_").replace(":", "_").replace(".", "_")
    return clean or "default_site"


def get_site_cache_path(url: str) -> str:
    ensure_cache_dir()
    key = get_cache_key_from_url(url)
    return os.path.join(CACHE_DIR, f"{key}.json")


def load_site_cache(url: str) -> Optional[Dict[str, Any]]:
    """Loads stored fingerprint and action map for a given URL."""
    cache_path = get_site_cache_path(url)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ScriptCache] Warning loading cache for {url}: {e}")
    return None


def save_site_cache(url: str, dom_hash: str, visual_hash: str, actions: List[Dict[str, Any]]):
    """Saves learned UI fingerprint and Playwright action steps for a URL."""
    ensure_cache_dir()
    cache_path = get_site_cache_path(url)
    payload = {
        "url": url,
        "fingerprint": {
            "dom_hash": dom_hash,
            "visual_hash": visual_hash,
            "updated_at": os.path.getmtime(cache_path) if os.path.exists(cache_path) else None
        },
        "actions": actions
    }
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"✓ Saved Playwright action map to cache: {cache_path}")
    except Exception as e:
        print(f"❗️ Error saving site cache for {url}: {e}")
