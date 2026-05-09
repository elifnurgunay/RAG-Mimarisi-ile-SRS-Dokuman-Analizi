"""
src/core/conflict_detector.py

Gereksinimler arası çelişki analizini yürüten modül.
logic.py'daki ConflictDetector sınıfının yeniden adlandırılmış,
temizlenmiş ve genişletilmiş halidir.

Sağlanan işlevler:
  - analyze_pair_conflict   : İki gereksinim arasındaki çelişkiyi analiz eder.
  - analyze_batch_conflicts : Bir kaynak gereksinimi N aday ile tek API çağrısında karşılaştırır.
  - analyze_global_conflicts: Tüm gereksinim listesini toplu olarak tarar.
"""
import time
import random
import re
import json
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from src.core.llm_client import get_llm
from src.schemas.issue import ConflictIssue
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)
_TR_MAP = str.maketrans({
    "ı": "i",
    "ğ": "g",
    "ü": "u",
    "ş": "s",
    "ö": "o",
    "ç": "c",
    "İ": "i",
    "Ğ": "g",
    "Ü": "u",
    "Ş": "s",
    "Ö": "o",
    "Ç": "c",
})

OFFLINE_TERMS = [
    "offline", "work offline", "operate offline", "without internet",
    "cevrimdisi", "çevrimdışı"
]

INTERNET_REQUIRED_TERMS = [
    "requires internet", "internet required", "internet access required",
    "internet connection required", "require internet access",
    "internet access for all operations", "internet zorunlu", "internet gerektirir"
]

LOCAL_TERMS = [
    "local only", "local-only", "local database", "stored locally only",
    "lokal veritabani", "yerel veritabani"
]

CLOUD_TERMS = [
    "cloud only", "cloud-only", "stored in cloud only", "sadece bulut"
]

MOBILE_ONLY_TERMS = [
    "mobile only", "mobile-only", "only mobile", "sadece mobil"
]

DESKTOP_REQUIRED_TERMS = [
    "desktop required", "desktop mandatory", "desktop support is mandatory",
    "masaustu zorunlu"
]

POSITIVE_MARKERS = [
    "shall", "must", "required", "mandatory", "zorunlu", "olmalidir"
]

NEGATIVE_MARKERS = [
    "shall not", "must not", "not allowed", "forbidden", "yasak",
    "olmamalidir", "izin verilmez"
]

def _extract_json_list(raw_text: str) -> List[dict]:
    """
    LLM bazen JSON'dan önce açıklama yazıyor:
    'Boş liste dönecektir...\\n[]'

    Bu fonksiyon cevabın içinden ilk JSON array'i çıkarır.
    Geçerli liste yoksa güvenli şekilde [] döner.
    """
    if not raw_text:
        return []

    text = raw_text.strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        pass

    start = text.find("[")
    end = text.rfind("]")

    if start == -1 or end == -1 or end <= start:
        return []

    json_part = text[start:end + 1]

    try:
        parsed = json.loads(json_part)
    except json.JSONDecodeError:
        return []

    return parsed if isinstance(parsed, list) else []

def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    """
    LLM bazen JSON object'ten önce/sonra açıklama yazabilir.
    Bu fonksiyon cevabın içinden ilk JSON object'i güvenli şekilde çıkarır.
    Geçerli object yoksa boş dict döner.
    """
    if not raw_text:
        return {}

    text = raw_text.strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return {}

    json_part = text[start:end + 1]

    try:
        parsed = json.loads(json_part)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}

def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""

    text = text.lower().translate(_TR_MAP)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


_REJECT_REASON_PHRASES = [
    "celiski yok",
    "dogrudan celiski yok",
    "dogrudan bir celiski yok",
    "celiski bulunmuyor",
    "celiski tespit edilmedi",
    "conflict yok",
    "conflict degildir",
    "bu bir celiski degil",
    "bu bir celiski degildir",
    "celiski degildir",
    "uyumlu",
    "uyumludur",
    "birlikte calisabilir",
    "birbirini destekler",
    "destekler",
    "ayni gereksinimin tekrari",
    "duplicate",
    "tekrar",
    "yinelenen",
    "benzer",
    "semantic similarity",
]


def _contains_reject_phrase(reason: str) -> bool:
    normalized = _normalize_text(reason)
    return any(phrase in normalized for phrase in _REJECT_REASON_PHRASES)


def _is_duplicate_or_same_requirement(source_req: str, candidate_req: str, reason: str) -> bool:
    source_norm = _normalize_text(source_req)
    candidate_norm = _normalize_text(candidate_req)
    reason_norm = _normalize_text(reason)

    if not source_norm or not candidate_norm:
        return True

    if source_norm == candidate_norm:
        return True

    duplicate_markers = [
        "duplicate",
        "tekrar",
        "yinelenen",
        "ayni gereksinim",
        "same requirement",
    ]

    return any(marker in reason_norm for marker in duplicate_markers)


def _extract_seconds_constraint(text: str) -> Dict[str, Optional[int]]:
    """
    Basit performans çelişkileri için:
    - maksimum 2 saniye
    - minimum 10 saniye
    gibi ifadeleri yakalar.
    """
    normalized = _normalize_text(text)

    result = {
        "max": None,
        "min": None,
    }

    max_match = re.search(
        r"(maksimum|max|en fazla|within|icinde)\s*(\d+)\s*(saniye|sn|second|seconds)",
        normalized,
    )
    min_match = re.search(
        r"(minimum|min|en az|at least)\s*(\d+)\s*(saniye|sn|second|seconds)",
        normalized,
    )

    if max_match:
        result["max"] = int(max_match.group(2))

    if min_match:
        result["min"] = int(min_match.group(2))

    return result


def _has_quantitative_time_conflict(source_req: str, candidate_req: str) -> bool:
    source_time = _extract_seconds_constraint(source_req)
    candidate_time = _extract_seconds_constraint(candidate_req)

    if source_time["max"] is not None and candidate_time["min"] is not None:
        return source_time["max"] < candidate_time["min"]

    if candidate_time["max"] is not None and source_time["min"] is not None:
        return candidate_time["max"] < source_time["min"]

    return False


def _contains_any(text: str, terms: list) -> bool:
    """Verilen terimlerden herhangi biri metin içinde geçiyor mu?"""
    return any(term in text for term in terms)


def _has_cross_requirement_pair(
    source: str, candidate: str, left_terms: list, right_terms: list
) -> bool:
    """
    Bir çift terim kümesinin hem source hem de candidate içinde
    karşılıklı olarak bulunup bulunmadığını kontrol eder.
    Reason alanına bakmaz — sadece gereksinim metinlerine bakar.
    """
    source_has_left = _contains_any(source, left_terms)
    source_has_right = _contains_any(source, right_terms)
    candidate_has_left = _contains_any(candidate, left_terms)
    candidate_has_right = _contains_any(candidate, right_terms)

    return (source_has_left and candidate_has_right) or (
        source_has_right and candidate_has_left
    )


def _has_strong_conflict_signal(source_req: str, candidate_req: str, reason: str) -> bool:
    """
    Güçlü çelişki sinyali tespiti.

    Semantik çift (offline/internet, local/cloud, mobile/desktop) kontrollerinde
    yalnızca gereksinim metinleri kullanılır; LLM reason alanı bu kararlarda
    esas alınmaz. Böylece LLM'nin reason içine uydurduğu ifadeler (hallucination)
    false positive oluşturamaz.

    LLM reason yalnızca şu durumda devreye girer:
      - Gereksinimlerden biri 'shall not / must not / …' gibi açık yasaklama içeriyor
        VE diğeri açık bir yükümlülük içeriyorsa — ve LLM bu çelişkiyi kendi sözleriyle
        onaylıyorsa.
    """
    source = _normalize_text(source_req)
    candidate = _normalize_text(candidate_req)
    reason_norm = _normalize_text(reason)

    # 1. Sayısal zaman kısıtı çelişkisi — sadece requirement metinlerinden
    if _has_quantitative_time_conflict(source_req, candidate_req):
        return True

    # 2. Offline ↔ Internet-required — sadece requirement metinlerinden
    if _has_cross_requirement_pair(source, candidate, OFFLINE_TERMS, INTERNET_REQUIRED_TERMS):
        return True

    # 3. Local-only ↔ Cloud-only — sadece requirement metinlerinden
    if _has_cross_requirement_pair(source, candidate, LOCAL_TERMS, CLOUD_TERMS):
        return True

    # 4. Mobile-only ↔ Desktop-required — sadece requirement metinlerinden
    if _has_cross_requirement_pair(source, candidate, MOBILE_ONLY_TERMS, DESKTOP_REQUIRED_TERMS):
        return True

    # 5. Genel pozitif ↔ negatif çelişki — requirement metinleri + LLM reason onayı
    contradiction_reason_markers = [
        "cannot both be true",
        "mutually exclusive",
        "contradiction",
        "contradicts",
        "ayni anda saglanamaz",
        "birbirini dislar",
        "celisir",
        "tutarsiz",
    ]

    has_positive_in_requirements = _contains_any(source, POSITIVE_MARKERS) or _contains_any(
        candidate, POSITIVE_MARKERS
    )
    has_negative_in_requirements = _contains_any(source, NEGATIVE_MARKERS) or _contains_any(
        candidate, NEGATIVE_MARKERS
    )
    has_reason_signal = _contains_any(reason_norm, contradiction_reason_markers)

    return has_positive_in_requirements and has_negative_in_requirements and has_reason_signal


def _has_canonical_conflict_pair(source_req: str, candidate_req: str) -> bool:
    source = _normalize_text(source_req)
    candidate = _normalize_text(candidate_req)

    if _has_quantitative_time_conflict(source_req, candidate_req):
        return True

    if _has_cross_requirement_pair(source, candidate, OFFLINE_TERMS, INTERNET_REQUIRED_TERMS):
        return True

    if _has_cross_requirement_pair(source, candidate, LOCAL_TERMS, CLOUD_TERMS):
        return True

    if _has_cross_requirement_pair(source, candidate, MOBILE_ONLY_TERMS, DESKTOP_REQUIRED_TERMS):
        return True

    return False


def _is_obvious_non_conflict(source_req: str, candidate_req: str, reason: str) -> bool:
    combined = _normalize_text(f"{source_req} {candidate_req} {reason}")

    # Eğer güçlü çatışma sinyali varsa non-conflict filtresi devreye girmesin.
    if _has_strong_conflict_signal(source_req, candidate_req, reason):
        return False

    compatible_pairs = [
        ("guvenlik", "sifreleme"),
        ("guvenli", "sifreleme"),
        ("security", "encryption"),
        ("cloud", "internet"),
        ("bulut", "internet"),
        ("modern arayuz", "mobil"),
        ("modern ui", "mobile"),
        ("performans", "saniye"),
        ("hizli", "saniye"),
    ]

    for left, right in compatible_pairs:
        if left in combined and right in combined:
            return True

    return False


def _calculate_conflict_severity(source_req: str, candidate_req: str, reason: str) -> str:
    combined = _normalize_text(f"{source_req} {candidate_req} {reason}")

    high_terms = [
        "guvenlik",
        "security",
        "authentication",
        "authorization",
        "kvkk",
        "gdpr",
        "data loss",
        "veri kaybi",
        "odeme",
        "payment",
        "yasak",
        "zorunlu",
        "must not",
        "shall not",
        "mutually exclusive",
        "ayni anda saglanamaz",
    ]

    if _has_canonical_conflict_pair(source_req, candidate_req):
        return "High"

    if any(term in combined for term in high_terms):
        return "High"

    if _has_strong_conflict_signal(source_req, candidate_req, reason):
        return "Medium"

    return "Low"


def _is_valid_conflict(source_req: str, candidate_req: str, raw: Dict[str, Any]) -> bool:
    """
    LLM çıktısı ConflictIssue değildir.
    LLM çıktısı sadece conflict adayıdır.
    Bu kapıdan geçemeyen hiçbir şey UI'ye conflict olarak gitmemeli.
    """
    if not isinstance(raw, dict):
        return False

    reason = raw.get("reason", "")
    conflict_type = _normalize_text(raw.get("conflict_type", ""))

    if not source_req or not candidate_req or not reason:
        return False

    if _contains_reject_phrase(reason):
        return False

    if _is_duplicate_or_same_requirement(source_req, candidate_req, reason):
        return False

    if conflict_type in {"none", "terminology"}:
        return False

    if _is_obvious_non_conflict(source_req, candidate_req, reason):
        return False

    if not _has_strong_conflict_signal(source_req, candidate_req, reason):
        return False

    return True


def _safe_candidate_index(raw: Dict[str, Any], candidates: List[str]) -> Optional[int]:
    value = raw.get("candidate_index")

    try:
        index = int(value)
    except (TypeError, ValueError):
        return None

    index -= 1

    if 0 <= index < len(candidates):
        return index

    return None


def _match_candidate_by_text(raw: Dict[str, Any], candidates: List[str]) -> Optional[int]:
    conflict_with_text = _normalize_text(raw.get("conflict_with_text", ""))

    if not conflict_with_text:
        return None

    for index, candidate in enumerate(candidates):
        candidate_norm = _normalize_text(candidate)

        if conflict_with_text in candidate_norm or candidate_norm.startswith(conflict_with_text):
            return index

    return None


def _detect_requirement_language(text_a: str, text_b: str) -> str:
    combined = f"{text_a} {text_b}".lower()
    turkish_chars = set("çğıöşüÇĞİÖŞÜ")
    if any(ch in combined for ch in turkish_chars):
        return "tr"
    turkish_terms = [" olmalıdır", " olmamalıdır", " gerektirir", " kullanıcı", " sistem "]
    english_terms = [" shall ", " must ", " requires ", " requirement ", " system "]
    tr_score = sum(1 for t in turkish_terms if t in combined)
    en_score = sum(1 for t in english_terms if t in combined)
    return "tr" if tr_score > en_score else "en"


def _build_deterministic_conflict_reason(source_req: str, candidate_req: str) -> str:
    lang = _detect_requirement_language(source_req, candidate_req)

    source = _normalize_text(source_req)
    candidate = _normalize_text(candidate_req)

    if _has_cross_requirement_pair(source, candidate, OFFLINE_TERMS, INTERNET_REQUIRED_TERMS):
        if lang == "tr":
            return "Bir gereksinim çevrimdışı çalışmayı zorunlu kılarken diğer gereksinim tüm işlemler için internet erişimi gerektiriyor. Bu iki gereksinim aynı anda sağlanamaz."
        return "The requirements cannot both be satisfied because one requires offline operation while the other requires internet access for all operations."

    if _has_cross_requirement_pair(source, candidate, LOCAL_TERMS, CLOUD_TERMS):
        if lang == "tr":
            return "Bir gereksinim verinin yerel olarak saklanmasını zorunlu kılarken diğer gereksinim yalnızca bulut depolamayı zorunlu kılıyor. Bu iki gereksinim aynı anda sağlanamaz."
        return "The requirements cannot both be satisfied because one requires local-only storage while the other requires cloud-only storage."

    if _has_cross_requirement_pair(source, candidate, MOBILE_ONLY_TERMS, DESKTOP_REQUIRED_TERMS):
        if lang == "tr":
            return "Bir gereksinim yalnızca mobil platformu zorunlu kılarken diğer gereksinim masaüstü desteğini zorunlu kılıyor. Bu iki gereksinim aynı anda sağlanamaz."
        return "The requirements cannot both be satisfied because one limits the system to mobile only while the other requires desktop support."

    if lang == "tr":
        return "Bu iki gereksinim aynı anda sağlanamaz."
    return "These two requirements cannot both be satisfied."


def _score_candidate_pair(source_req: str, candidate_req: str) -> int:
    source = _normalize_text(source_req)
    candidate = _normalize_text(candidate_req)
    score = 0

    if source == candidate:
        return -1000

    if _has_cross_requirement_pair(source, candidate, OFFLINE_TERMS, INTERNET_REQUIRED_TERMS):
        score += 100

    if _has_cross_requirement_pair(source, candidate, LOCAL_TERMS, CLOUD_TERMS):
        score += 100

    if _has_cross_requirement_pair(source, candidate, MOBILE_ONLY_TERMS, DESKTOP_REQUIRED_TERMS):
        score += 100

    if _has_quantitative_time_conflict(source_req, candidate_req):
        score += 100

    if _has_cross_requirement_pair(source, candidate, POSITIVE_MARKERS, NEGATIVE_MARKERS):
        score += 80

    source_words = set(source.split())
    candidate_words = set(candidate.split())
    common = source_words & candidate_words
    score += min(len(common), 10)

    return score


def _select_conflict_candidates(
    source_index: int,
    requirements: List[str],
    top_k_candidates: int,
    seen_pairs: set
) -> List[str]:
    scored_candidates = []
    source_req = requirements[source_index]

    for j, candidate_req in enumerate(requirements):
        if j == source_index:
            continue

        pair_key = tuple(sorted([source_index, j]))
        if pair_key in seen_pairs:
            continue

        score = _score_candidate_pair(source_req, candidate_req)
        scored_candidates.append((score, j, candidate_req))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    selected = []
    for score, j, candidate_req in scored_candidates:
        if score >= 100:
            selected.append(candidate_req)
            seen_pairs.add(tuple(sorted([source_index, j])))
        elif len(selected) < top_k_candidates:
            selected.append(candidate_req)
            seen_pairs.add(tuple(sorted([source_index, j])))

    return selected


# ---------------------------------------------------------------------------
# Prompt şablonları
# ---------------------------------------------------------------------------

_PAIR_PROMPT = """\
You are a strict Software Requirements Conflict Analyst.

Compare the following two requirements and decide whether there is a direct contradiction.

**OUTPUT LANGUAGE RULE:**
- Detect the dominant language of the two requirements.
- Write the `reason` field in the same language as the requirements.
- If the requirements are in English, write the reason in English.
- If the requirements are in Turkish, write the reason in Turkish.
- Keep JSON keys unchanged.
- Keep enum values unchanged.
- Do not mix Turkish and English unless the original requirement uses technical terms.

**Requirement 1:**
{req1}

**Requirement 2:**
{req2}

**Conflict Definition:**
A conflict exists ONLY IF both requirements cannot be true at the same time.

**Report as conflict ONLY when:**
- One requirement requires something while another forbids it.
- Two requirements define incompatible numeric limits.
- Two requirements assign mutually exclusive behavior.
- Two requirements define incompatible storage, security, platform, or availability constraints.
- One requirement says offline operation is required while another requires internet for all operations.
- One requirement says local-only storage while another says cloud-only storage.
- Platform constraints are mutually exclusive, such as mobile-only vs desktop mandatory.

**Do NOT report as conflict:**
- Similar requirements
- Duplicate requirements
- Supportive requirements
- Refinement/detail relationship
- Same domain or same technology stack
- Engineering tradeoff without explicit contradiction
- Terminology difference alone
- Security + encryption
- Cloud + internet access
- Fast system + concrete response time
- Modern UI + mobile app

Return ONLY this JSON object:
{{
    "conflict": boolean,
    "reason": "short technical explanation in the same language as the requirements",
    "severity": "Low|Medium|High",
    "conflict_type": "Quantitative|Logical|Scope|None"
}}

OUTPUT RULE:
- The first character of your response must be {{
- The last character of your response must be }}
- Do not write markdown.
- Do not write explanations outside JSON.
"""

_BATCH_PROMPT = """\
You are a strict Software Requirements Conflict Analyst.

Compare the "SOURCE REQUIREMENT" with each item in the "CANDIDATE LIST".
Report ONLY direct logical contradictions.

**OUTPUT LANGUAGE RULE:**
- Detect the dominant language of the source requirement and candidates.
- Write the `reason` field in the same language as the requirements.
- If the requirements are in English, write the reason in English.
- If the requirements are in Turkish, write the reason in Turkish.
- Keep JSON keys unchanged.
- Keep enum values unchanged.
- Do not mix Turkish and English unless the original requirement uses technical terms.

**SOURCE REQUIREMENT:**
{source_req}

**CANDIDATE LIST:**
{candidates_text}

**Critical Rules:**
1. Semantic similarity is not a conflict.
2. Same domain is not a conflict.
3. Supportive requirements are not conflicts.
4. Technological compatibility is not a conflict.
5. Assumptions are not conflicts.
6. General relationship is not a conflict.
7. If you are uncertain, return no conflict.
8. Report only strong logical contradictions.
9. Duplicate requirements are not conflicts.
10. Engineering tradeoffs are not conflicts unless there is an explicit contradiction.
11. A conflict exists only when two requirements cannot both be true at the same time.

**Report conflict ONLY when:**
- One requirement requires something while another forbids it.
- One requirement says offline operation is required while another requires internet for all operations.
- One requirement says local-only storage while another says cloud-only storage.
- Numeric constraints are incompatible, such as maximum 2 seconds vs minimum 10 seconds.
- Platform constraints are mutually exclusive, such as mobile-only vs desktop mandatory.

**Do NOT report conflict for:**
- Security + encryption
- Cloud + internet access
- Fast system + concrete response time
- Modern UI + mobile app
- Similar wording
- Repeated requirement
- Refinement relationship
- Broad/narrow relationship

Return ONLY a valid JSON list.
If there is no direct contradiction, return [].

[
    {{
        "candidate_index": 1,
        "conflict_with_text": "first 80 characters of the conflicting candidate",
        "reason": "short technical explanation in the same language as the SRS",
        "severity": "Low|Medium|High",
        "conflict_type": "Quantitative|Logical|Scope"
    }}
]

OUTPUT RULE:
- The first character of your response must be [
- The last character of your response must be ]
- Do not write markdown.
- Do not write explanations outside JSON.
- If there is no conflict, write only []
"""

class ConflictDetector:
    def __init__(self, model_name: str = None):
        self.llm = get_llm(model=model_name) if model_name else get_llm()
        self.rate_limited = False

    # ------------------------------------------------------------------
    # 1. Çift analizi
    # ------------------------------------------------------------------
    def analyze_pair_conflict(self, req1: str, req2: str) -> dict:
        """
        İki gereksinim metni arasındaki çelişkiyi analiz eder.

        Returns:
            {conflict: bool, reason: str, severity: str, conflict_type: str}
        """
        prompt = ChatPromptTemplate.from_template(_PAIR_PROMPT)
        chain = prompt | self.llm

        try:
            response = chain.invoke({"req1": req1, "req2": req2})
            raw_text = response.content if hasattr(response, "content") else str(response)
            result = _extract_json_object(raw_text)

            if not result:
                return {
                    "conflict": False,
                    "reason": "No valid JSON object could be parsed from the model response.",
                    "severity": "None",
                    "conflict_type": "None",
                }

            if not bool(result.get("conflict", False)):
                return {
                    "conflict": False,
                    "reason": result.get("reason", "No direct contradiction was detected."),
                    "severity": "None",
                    "conflict_type": "None",
                }

            if not _is_valid_conflict(req1, req2, result):
                return {
                    "conflict": False,
                    "reason": result.get("reason", "Rejected by deterministic conflict validation."),
                    "severity": "None",
                    "conflict_type": "None",
                }

            return {
                "conflict": True,
                "reason": result.get("reason", "Direct contradiction detected."),
                "severity": _calculate_conflict_severity(
                    req1,
                    req2,
                    result.get("reason", ""),
                ),
                "conflict_type": result.get("conflict_type", "Logical"),
            }

        except Exception as exc:
            logger.warning("analyze_pair_conflict hatası: %s — fallback döndürülüyor.", exc)
            return {
                "conflict": False,
                "reason": f"Analysis error: {exc}",
                "severity": "None",
                "conflict_type": "None",
            }
    # ------------------------------------------------------------------
    # 2. Toplu (batch) analizi
    # ------------------------------------------------------------------
    def analyze_batch_conflicts(
        self,
        source_req: str,
        candidates: List[str],
        max_retries: int = 3,
    ) -> List[dict]:
        """
        Kaynak gereksinimi N aday ile TEK API çağrısında karşılaştırır.
        Rate-limit durumunda exponential back-off ile yeniden dener.

        Args:
            source_req:  Kaynak gereksinim metni.
            candidates:  Karşılaştırılacak aday metinleri listesi.
            max_retries: Maksimum yeniden deneme sayısı.

        Returns:
            Çelişki bulguları listesi (dict listesi).
        """
        if not candidates:
            return []

        candidates_text = "\n".join(
            f"--- CANDIDATE {i + 1} | candidate_index={i + 1} ---\n{c}"
            for i, c in enumerate(candidates)
        )

        prompt = ChatPromptTemplate.from_template(_BATCH_PROMPT)
        chain = prompt | self.llm

        for attempt in range(max_retries):
            try:
                response = chain.invoke(
                    {"source_req": source_req, "candidates_text": candidates_text}
                )

                raw_text = response.content if hasattr(response, "content") else str(response)
                results = _extract_json_list(raw_text)

                logger.debug(
                    "Batch analizi tamamlandı: %d çelişki adayı döndü.",
                    len(results),
                )
                return results

            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "rate_limit" in err_str or "too many requests" in err_str:
                    self.rate_limited = True
                    logger.warning("Rate limit tespit edildi; conflict analizi erken durdurulacak.")
                    return []
                else:
                    logger.error("analyze_batch_conflicts hatası: %s", exc)
                    break

        return []

    # ------------------------------------------------------------------
    # 3. Global (tüm liste) analizi
    # ------------------------------------------------------------------
    def analyze_global_conflicts(
        self,
        requirements: List[str],
        source_req_ids: Optional[List[str]] = None,
        top_k_candidates: int = 3,
        inter_batch_sleep: float = 1.5,
        max_consecutive_failures: int = 2,
    ) -> List[ConflictIssue]:
        """
        Gereksinim listesindeki her maddeyi diğerleriyle karşılaştırır.
        Basit bir tam-tarama (O(n²)) yerine her madde için en yakın
        `top_k_candidates` aday seçilir (RAG katmanı ile entegre kullanım için).

        Args:
            requirements:     Gereksinim metinleri listesi.
            source_req_ids:   Her gereksinimin ID'si (opsiyonel, indekse göre üretilir).
            top_k_candidates: Her madde için kaç aday seçileceği.
            inter_batch_sleep: API sağlığı için batch'ler arası bekleme (sn).

        Returns:
            ConflictIssue nesneleri listesi.
        """
        all_conflicts: List[ConflictIssue] = []
        consecutive_failures = 0
        seen_pairs = set()

        for i, source in enumerate(requirements):
            if getattr(self, "rate_limited", False):
                logger.warning("Rate limit nedeniyle global conflict analizi erken durduruldu.")
                break

            req_id = (
                source_req_ids[i]
                if source_req_ids and i < len(source_req_ids)
                else f"REQ-{i + 1:03d}"
            )

            # Adayları skora ve seen_pairs durumuna göre seç
            candidates = _select_conflict_candidates(
                source_index=i,
                requirements=requirements,
                top_k_candidates=top_k_candidates,
                seen_pairs=seen_pairs
            )

            if not candidates:
                continue

            try:
                raw_conflicts = self.analyze_batch_conflicts(source, candidates)
                if getattr(self, "rate_limited", False):
                    continue
                consecutive_failures = 0
            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "rate_limit" in err_str or "too many requests" in err_str:
                    self.rate_limited = True
                    logger.warning("Rate limit nedeniyle global conflict analizi erken durduruldu.")
                    break
                
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.error("Maksimum ardışık hata ulaşıldı. Global analiz durduruluyor.")
                    break
                
                logger.error("Global analizde beklenmedik hata | req_id=%s | hata=%s", req_id, exc)
                continue

            found_candidates = set()

            for raw in raw_conflicts:
                try:
                    candidate_index = _safe_candidate_index(raw, candidates)

                    if candidate_index is None:
                        candidate_index = _match_candidate_by_text(raw, candidates)

                    if candidate_index is None:
                        logger.debug("Conflict adayı eşleştirilemedi, reddedildi | raw=%s", raw)
                        continue

                    candidate_req = candidates[candidate_index]

                    if not _is_valid_conflict(source, candidate_req, raw):
                        logger.debug("Geçersiz/fake conflict reddedildi | raw=%s", raw)
                        continue

                    found_candidates.add(candidate_req)

                    raw_reason = raw.get("reason", "Çelişki tespit edildi.")
                    final_reason = raw_reason

                    if _has_canonical_conflict_pair(source, candidate_req):
                        final_reason = _build_deterministic_conflict_reason(source, candidate_req)

                    final_severity = _calculate_conflict_severity(
                        source,
                        candidate_req,
                        final_reason,
                    )

                    all_conflicts.append(
                        ConflictIssue(
                            source_req_id=req_id,
                            conflict_with_text=candidate_req[:80],
                            reason=final_reason,
                            severity=final_severity,
                            conflict_type=raw.get("conflict_type", "Logical"),
                        )
                    )

                except Exception as exc:
                    logger.warning("Conflict adayı işlenemedi ve reddedildi: %s | raw=%s", exc, raw)

            # LLM'in kaçırdığı obvious (canonical) çelişkiler için deterministic fallback:
            for candidate_req in candidates:
                if candidate_req not in found_candidates:
                    if _has_strong_conflict_signal(source, candidate_req, reason=""):
                        logger.info("Deterministic fallback tetiklendi | %s <-> %s", req_id, candidate_req[:40])
                        reason_text = _build_deterministic_conflict_reason(source, candidate_req)
                        all_conflicts.append(
                            ConflictIssue(
                                source_req_id=req_id,
                                conflict_with_text=candidate_req[:80],
                                reason=reason_text,
                                severity="High",
                                conflict_type="Logical",
                            )
                        )

            time.sleep(inter_batch_sleep)

        logger.info(
            "Global çelişki analizi tamamlandı: %d gereksinim, %d çelişki bulundu.",
            len(requirements),
            len(all_conflicts),
        )
        return all_conflicts


# ---------------------------------------------------------------------------
# Geriye dönük uyumluluk: workflow.py hâlâ `from src.core.conflict_detector import ConflictDetector` diyebilir
# ---------------------------------------------------------------------------
# NOT: logic.py'yi bu dosyaya yönlendirmek için logic.py güncellenmeli.
