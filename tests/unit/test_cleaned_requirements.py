import json
import os
import pytest


def test_cleaned_requirements(json_file_path: str = "cleaned_requirements.json"):
    """
    'cleaned_requirements.json' dosyasının doğruluğunu test eder.
    """

    print(f"🔍 '{json_file_path}' dosyasını test ediyorum...")

    if not os.path.exists(json_file_path):
        pytest.skip(f"'{json_file_path}' dosyası bulunamadı, test atlandı.")

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print("✅ JSON dosyası başarıyla okundu ve parse edildi (UTF-8).")

    except json.JSONDecodeError as e:
        pytest.fail(f"JSON parse hatası: {e}")
    except UnicodeDecodeError as e:
        pytest.fail(f"UTF-8 encoding hatası: {e}")
    except Exception as e:
        pytest.fail(f"Dosya okuma hatası: {e}")

    assert data, "JSON dosyası boş! Hiç veri bulunamadı."
    assert isinstance(data, list), "JSON verisi liste formatında değil."

    print(f"✅ Veri listesi bulundu, toplam {len(data)} öğe var.")

    for i, item in enumerate(data, start=1):
        assert isinstance(item, dict), f"{i}. öğe dict değil, {type(item)}!"
        assert "id" in item, f"{i}. öğede 'id' anahtarı eksik!"
        assert "text" in item, f"{i}. öğede 'text' anahtarı eksik!"

        if not isinstance(item["id"], str) or not item["id"].startswith("REQ-"):
            print(f"⚠️  UYARI: {i}. öğenin 'id'si beklenen formatta değil (REQ-XXX): {item['id']}")

        if not item["text"] or not item["text"].strip():
            print(f"⚠️  UYARI: {i}. öğenin 'text'i boş!")

    print("✅ Tüm veri blokları 'id' ve 'text' anahtarlarını içeriyor.")
    print("🎉 Test başarılı! Veri sağlama kısmı sisteme hazır.")


if __name__ == "__main__":
    test_cleaned_requirements()