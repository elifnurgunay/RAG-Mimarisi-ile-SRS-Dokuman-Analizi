# src/core/prompt_builder.py

from langchain_core.prompts import ChatPromptTemplate


class PromptBuilder:
    def build_analysis_prompt(self, format_instructions: str):
        prompt_template = """
Sen kıdemli bir Yazılım Gereksinim Mühendisisin. Aşağıdaki SRS (Yazılım Gereksinim Spesifikasyonu) metin parçalarını analiz et.

**Kritik Talimatlar:**
1. **Sadece Mevcut Metne Odaklan:** Metinde açıkça yazmayan bölümler için (örn: "Giriş bölümü eksik", "Proje önerisi yok") gibi halüsinasyonlar üretme. Sadece elindeki metin parçasındaki hataları raporla.
2. **Başlıkları ve Şekil Yazılarını Atla:** Eğer bir satır sadece bir başlık (örn: "4. Kısıtlar") veya şekil adı (örn: "Şekil 5: Diyagram") ise, bunu bir gereksinim maddesi olarak görme ve hata raporlama.
3. **Somut Hataları Bul:** Belirsizlik (Ambiguity), Çelişki (Inconsistency), Eksiklik (Maddenin kendi içindeki eksiklik) ve Test Edilebilirlik (Testability) kriterlerine odaklan.
4. **Kesin Kanıt:** Her hata için "Problem" kısmında metindeki hangi ifadenin neden hatalı olduğunu açıklat.

**Giriş Metni:**
{chunk_text}

**Metadata:** {metadata}

Yanıtını SADECE AnalysisReport şemasına uygun JSON formatında ver.
{format_instructions}
"""
        return ChatPromptTemplate.from_template(prompt_template).partial(
            format_instructions=format_instructions
        )