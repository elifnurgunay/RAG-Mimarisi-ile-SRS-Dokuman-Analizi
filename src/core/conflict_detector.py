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
from typing import List, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.core.llm_client import get_llm
from src.schemas.issue import ConflictIssue
from src.utils.json_utils import safe_parse_json
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt şablonları
# ---------------------------------------------------------------------------

_PAIR_PROMPT = """\
Sen uzman bir Yazılım Gereksinim Analistisin. Aşağıdaki iki gereksinim maddesini \
karşılaştır ve aralarında bir ÇELİŞKİ veya tutarsızlık olup olmadığını belirle.

**Gereksinim 1:** {req1}
**Gereksinim 2:** {req2}

**Analiz Rehberi:**
- Nicel Çelişkiler: Farklı limitler, süreler veya kapasite değerleri.
- Mantıksal Çelişkiler: Bir madde aksiyona izin verirken diğerinin yasaklaması.
- Kapsam Çelişkileri: Aynı süreci farklı aktör/koşullara atayan maddeler.
- Terminoloji Farkları: Aynı kavram için farklı terimler (hafif tutarsızlık).

Yanıtı SADECE şu JSON formatında ver:
{{
    "conflict": boolean,
    "reason": "string",
    "severity": "Low|Medium|High",
    "conflict_type": "Quantitative|Logical|Scope|Terminology|None"
}}
"""

_BATCH_PROMPT = """\
Sen uzman bir Yazılım Gereksinim Analistisin.

"ANA GEREKSİNİM" ile "ADAY LİSTESİ"ndeki maddeler arasında SADECE doğrudan mantıksal çelişkileri tespit et.

**ANA GEREKSİNİM:**
{source_req}

**ADAY LİSTESİ:**
{candidates_text}

**Kritik Kurallar:**
1. Semantic similarity conflict değildir.
2. Aynı konu alanında olmak conflict değildir.
3. Birbirini destekleyen maddeler conflict değildir.
4. Teknolojik uyumluluk conflict değildir.
5. Varsayımlar conflict değildir.
6. Genel ilişkiler conflict değildir.
7. Eğer emin değilsen conflict üretme.
8. Sadece güçlü mantıksal çelişkileri raporla.
9. Eğer açıklaman içinde "çelişki yok", "conflict değildir", "uyumludur", "destekler" gibi ifadeler geçiyorsa BU MADDEYİ SONUÇ LİSTESİNE EKLEME.
10. Olası ilişki veya tradeoff conflict değildir.
11. Performance vs security gibi engineering tradeoff durumlarını conflict olarak işaretleme.
12. Sadece kesin contradiction varsa sonuç üret.

**SADECE şu durumlarda conflict üret:**
- Aynı davranış için zıt koşullar varsa
- Bir requirement izin verip diğeri yasaklıyorsa
- Çelişen güvenlik politikaları varsa
- Çelişen veri saklama kuralları varsa
- Çelişen performans limitleri varsa
- Mutually exclusive gereksinimler varsa

**Önemli:**
Aşağıdakiler conflict DEĞİLDİR:
- semantic benzerlik
- destekleyici requirement
- aynı teknoloji stack'i
- aynı domain
- refinement ilişkisi
- broad/narrow relation

Her çelişki için kısa ve somut teknik gerekçe ver.

Yanıtı SADECE şu JSON listesi formatında ver (çelişki yoksa boş liste):
[
    {{
        "conflict_with_text": "çelişen aday metninin ilk 80 karakteri",
        "reason": "çelişki nedeni",
        "severity": "Low|Medium|High",
        "conflict_type": "Quantitative|Logical|Scope|Terminology"
    }}
]
**Çok Önemli:**
Aşağıdaki durumlarda BOŞ LİSTE dön:
- requirementlar birbirini destekliyorsa
- aynı sistemi farklı açıdan tanımlıyorsa
- biri diğerini genişletiyorsa
- sadece engineering tradeoff varsa
- conflict olabilir diyorsan
- kesin contradiction yoksa
"""

class ConflictDetector:
    def __init__(self):
        self.llm = get_llm()
        self.parser = JsonOutputParser()

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
        chain = prompt | self.llm | self.parser

        try:
            result = chain.invoke({"req1": req1, "req2": req2})
            logger.debug("Çift analizi tamamlandı: conflict=%s", result.get("conflict"))
            return result
        except Exception as exc:
            logger.warning("analyze_pair_conflict hatası: %s — fallback döndürülüyor.", exc)
            return {
                "conflict": False,
                "reason": f"Analiz hatası: {exc}",
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
            f"--- ADAY {i + 1} ---\n{c}" for i, c in enumerate(candidates)
        )

        prompt = ChatPromptTemplate.from_template(_BATCH_PROMPT)
        chain = prompt | self.llm | self.parser

        for attempt in range(max_retries):
            try:
                results = chain.invoke(
                    {"source_req": source_req, "candidates_text": candidates_text}
                )
                if isinstance(results, list):
                    logger.debug(
                        "Batch analizi tamamlandı: %d çelişki bulundu.", len(results)
                    )
                    return results
                return []
            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "rate_limit" in err_str:
                    wait = (2 ** attempt) * 5 + random.random()
                    logger.warning(
                        "Rate limit (429). %d/%d deneme. %.1f sn bekleniyor...",
                        attempt + 1,
                        max_retries,
                        wait,
                    )
                    time.sleep(wait)
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

        for i, source in enumerate(requirements):
            req_id = (
                source_req_ids[i]
                if source_req_ids and i < len(source_req_ids)
                else f"REQ-{i + 1:03d}"
            )

            # Adaylar: kendisi hariç tüm liste (veya sınırlı sayıda)
            candidates = [
                r for j, r in enumerate(requirements)
                if j != i
            ][:top_k_candidates]

            if not candidates:
                continue

            raw_conflicts = self.analyze_batch_conflicts(source, candidates)

            for raw in raw_conflicts:
                try:
                    all_conflicts.append(
                        ConflictIssue(
                            source_req_id=req_id,
                            conflict_with_text=raw.get("conflict_with_text", "")[:80],
                            reason=raw.get("reason", "Çelişki tespit edildi."),
                            severity=raw.get("severity", "Medium"),
                            conflict_type=raw.get("conflict_type"),
                        )
                    )
                except Exception as exc:
                    logger.warning("ConflictIssue oluşturulamadı: %s | raw=%s", exc, raw)

            time.sleep(inter_batch_sleep)

        logger.info(
            "Global çelişki analizi tamamlandı: %d gereksinim, %d çelişki bulundu.",
            len(requirements),
            len(all_conflicts),
        )
        return all_conflicts


# ---------------------------------------------------------------------------
# Geriye dönük uyumluluk: workflow.py hâlâ `from  from src.core.conflict_detector import ConflictDetector import` diyebilir
# ---------------------------------------------------------------------------
# NOT: logic.py'yi bu dosyaya yönlendirmek için logic.py güncellenmeli.
