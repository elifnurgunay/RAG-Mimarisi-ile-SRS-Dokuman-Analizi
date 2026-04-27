import json
import os
from pathlib import Path


def test_cleaned_requirements(json_file_path: str = "cleaned_requirements.json"):
    """
    'cleaned_requirements.json' dosyasının doğruluğunu test eder.
    
    Kontroller:
    1. Dosya başarıyla okunabiliyor mu?
    2. Dosya içindeki veriler boş değil mi?
    3. Her bir veri bloğu "id" ve "text" anahtarlarını içeriyor mu?
    4. JSON parse edilirken encoding hatası var mı?
    
    Args:
        json_file_path (str): Test edilecek JSON dosyasının yolu
    """
    print(f"🔍 '{json_file_path}' dosyasını test ediyorum...")
    
    # 1. Dosya var mı kontrolü
    if not os.path.exists(json_file_path):
        print(f"❌ HATA: '{json_file_path}' dosyası bulunamadı!")
        return False
    
    try:
        # 2. JSON parse etme (UTF-8 ile)
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("✅ JSON dosyası başarıyla okundu ve parse edildi (UTF-8).")
        
    except json.JSONDecodeError as e:
        print(f"❌ HATA: JSON parse hatası - {e}")
        return False
    except UnicodeDecodeError as e:
        print(f"❌ HATA: UTF-8 encoding hatası - {e}")
        return False
    except Exception as e:
        print(f"❌ HATA: Dosya okuma hatası - {e}")
        return False
    
    # 3. Veri boş mu kontrolü
    if not data:
        print("❌ HATA: JSON dosyası boş! Hiç veri bulunamadı.")
        return False
    
    if not isinstance(data, list):
        print("❌ HATA: JSON verisi liste formatında değil!")
        return False
    
    print(f"✅ Veri listesi bulundu, toplam {len(data)} öğe var.")
    
    # 4. Her öğe kontrolü
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            print(f"❌ HATA: {i}. öğe dict değil, {type(item)}!")
            return False
        
        if "id" not in item:
            print(f"❌ HATA: {i}. öğede 'id' anahtarı eksik!")
            return False
        
        if "text" not in item:
            print(f"❌ HATA: {i}. öğede 'text' anahtarı eksik!")
            return False
        
        # Opsiyonel: id format kontrolü
        if not isinstance(item["id"], str) or not item["id"].startswith("REQ-"):
            print(f"⚠️  UYARI: {i}. öğenin 'id'si beklenen formatta değil (REQ-XXX): {item['id']}")
        
        # Opsiyonel: text boş mu kontrolü
        if not item["text"] or not item["text"].strip():
            print(f"⚠️  UYARI: {i}. öğenin 'text'i boş!")
    
    print("✅ Tüm veri blokları 'id' ve 'text' anahtarlarını içeriyor.")
    print("🎉 Test başarılı! Veri sağlama kısmı sisteme hazır.")
    return True


if __name__ == "__main__":
    # Varsayılan dosya ile test et
    test_cleaned_requirements()