"""
src/core/logic.py — UYUMLULUK KÖPRÜSÜ (Deprecated)

Bu dosya kaldırılmadı; mevcut import'ların kırılmaması için
conflict_detector.py modülüne yönlendirme yapar.

UYARI: Yeni kodda doğrudan `src.core.conflict_detector` modülünü kullanın.
       Bu dosya bir sonraki sürümde kaldırılacaktır.

Eski kullanım (hâlâ çalışır):
    from src.core.logic import ConflictDetector

Yeni kullanım (önerilen):
    from src.core.conflict_detector import ConflictDetector
"""
import warnings

warnings.warn(
    "src.core.logic modülü kullanımdan kaldırıldı. "
    "Lütfen src.core.conflict_detector kullanın.",
    DeprecationWarning,
    stacklevel=2,
)

# Geriye dönük uyumluluk için yeniden dışa aktar
from src.core.conflict_detector import ConflictDetector  # noqa: F401, E402

__all__ = ["ConflictDetector"]
