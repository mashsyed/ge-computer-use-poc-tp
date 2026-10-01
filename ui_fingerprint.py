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

"""UI Fingerprint module for detecting layout and structural DOM changes on any URL.
"""

import hashlib
import re
from typing import Dict, Any, Tuple


def compute_dom_structure_hash(html_content: str) -> str:
    """Extracts tag structure (divs, inputs, buttons, forms, ids) to create a DOM layout fingerprint."""
    if not html_content:
        return ""
    
    # Strip inline text, keeping structural tags, element names, and key identifiers (id, name, class)
    tags = re.findall(r'<(button|input|select|form|textarea|a|h[1-6]|table|div|p)\b[^>]*>', html_content, re.IGNORECASE)
    cleaned_structure = "".join(tags)
    return hashlib.sha256(cleaned_structure.encode("utf-8")).hexdigest()


def compute_visual_hash(image_bytes: bytes) -> str:
    """Computes SHA-256 hash of screenshot image bytes."""
    if not image_bytes:
        return ""
    return hashlib.sha256(image_bytes).hexdigest()


def evaluate_ui_change(
    stored_fingerprint: Dict[str, Any],
    current_html: str,
    current_screenshot_bytes: bytes
) -> Tuple[bool, str]:
    """Compares current DOM and screenshot against stored fingerprint.
    
    Returns (has_changed: bool, reason: str).
    """
    if not stored_fingerprint:
        return True, "No prior UI fingerprint stored for this URL (Brand New URL)."

    current_dom_hash = compute_dom_structure_hash(current_html)
    current_visual_hash = compute_visual_hash(current_screenshot_bytes)

    stored_dom_hash = stored_fingerprint.get("dom_hash", "")
    stored_visual_hash = stored_fingerprint.get("visual_hash", "")

    if stored_dom_hash and current_dom_hash != stored_dom_hash:
        return True, "DOM structural layout changed (Form fields, buttons, or HTML hierarchy updated)."

    if stored_visual_hash and current_visual_hash != stored_visual_hash:
        return True, "Visual UI layout changed (Styles, popups, or positions shifted)."

    return False, "UI layout is unchanged (100% Match)."
