"""
src/utils/logging_utils.py

Proje genelinde tutarlı bir loglama altyapısı sağlar.
Her modül `get_logger(__name__)` ile kendi logger'ını alır.
"""
import logging
import sys
from typing import Optional


_ROOT_LOGGER_NAME = "srs_analyzer"
_CONFIGURED = False


def _configure_root_logger(level: int = logging.INFO) -> None:
    """
    Proje root logger'ını bir kez yapılandırır.
    stdout'a renkli-zaman damgalı format yazar.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    İstenen isme sahip bir logger döndürür.
    İlk çağrıda root logger'ı da yapılandırır.

    Kullanım:
        logger = get_logger(__name__)
        logger.info("Mesaj")

    Args:
        name:  Logger adı (genellikle __name__).
        level: Log seviyesi (varsayılan: INFO).

    Returns:
        Yapılandırılmış logging.Logger nesnesi.
    """
    _configure_root_logger(level)

    # Modül adını proje namespace'i altında hiyerarşik oluştur
    if name and not name.startswith(_ROOT_LOGGER_NAME):
        full_name = f"{_ROOT_LOGGER_NAME}.{name}"
    else:
        full_name = name or _ROOT_LOGGER_NAME

    return logging.getLogger(full_name)
