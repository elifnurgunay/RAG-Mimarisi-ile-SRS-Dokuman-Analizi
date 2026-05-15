import re
from typing import Any, Dict, List, Tuple

from src.config import REQUIREMENT_ID_PATTERN

def clean_requirement_text(text: str) -> str:
    """Cleans whitespace and strips the requirement text."""
    text = re.sub(r"\s+", " ", text or "").strip()
    # Metnin başındaki olası nokta veya iki noktaları temizle
    text = re.sub(r"^[\.\-:]\s*", "", text)
    return text

def extract_requirements_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extracts individual requirements from a block of text using the central regex pattern.
    Handles duplicate IDs by appending a suffix.
    """
    results = []
    if not text:
        return results

    seen_ids = {}
    
    matches = list(re.finditer(REQUIREMENT_ID_PATTERN, text, re.IGNORECASE))

    for i, match in enumerate(matches):
        req_id_raw = match.group(1)
        req_id = re.sub(r"[\s_\.]", "-", req_id_raw.upper().strip())

        # Body starts after this ID and ends at the next ID (or end of document)
        start_idx = match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        body_raw = text[start_idx:end_idx]
        body = clean_requirement_text(body_raw)

        # Skip requirements that are too short to be meaningful
        if not body or len(body) < 8:
            continue

        count = seen_ids.get(req_id, 0) + 1
        seen_ids[req_id] = count

        # Create a unique ID if duplicates exist (e.g., REQ-004#2)
        unique_id = req_id if count == 1 else f"{req_id}#{count}"

        results.append({
            "req_id": unique_id,
            "text": f"{req_id}: {body}",
            "original_req_id": req_id,
        })

    return results

def extract_requirements_from_chunks(chunks) -> Tuple[List[str], List[str]]:
    """
    Concatenates chunks and extracts all unique requirements.
    Returns a tuple of (list of requirement texts, list of requirement IDs).
    """
    full_text = "\n".join(
        getattr(chunk, "page_content", "") or ""
        for chunk in chunks
    )

    requirements = extract_requirements_from_text(full_text)

    req_texts = [item["text"] for item in requirements]
    req_ids = [item["req_id"] for item in requirements]

    return req_texts, req_ids


if __name__ == "__main__":
    sample = "REQ-001: This is req A. REQ-002: This is req B. REQ-003: This is req C."
    reqs = extract_requirements_from_text(sample)
    print(f"Test 1 - Beklenen 3, Bulunan {len(reqs)}")
    assert len(reqs) == 3

    sample2 = "FR-01. User login must be secure. NFR-01 Security must be high."
    reqs2 = extract_requirements_from_text(sample2)
    print(f"Test 2 - Beklenen 2, Bulunan {len(reqs2)}")
    assert len(reqs2) == 2
