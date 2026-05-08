# src/core/prompt_builder.py

from langchain_core.prompts import ChatPromptTemplate


class PromptBuilder:
    def build_analysis_prompt(self, format_instructions: str):
        prompt_template = """
Sen kıdemli bir Yazılım Gereksinim Mühendisisin. Aşağıdaki SRS (Yazılım Gereksinim Spesifikasyonu) metin parçalarını analiz et.

**Kritik Talimatlar:**
1. **Sadece Mevcut Metne Odaklan:** ...
2. **Başlıkları ve Şekil Yazılarını Atla:** ...
3. **Somut Hataları Bul:** ...
4. **Kesin Kanıt:** ...
5. **Semantic ilişkiyi çelişki sanma:** İki gereksinim aynı konu alanında olabilir ancak bu otomatik olarak çelişki olduğu anlamına gelmez.
6. **Sadece doğrudan mantıksal çelişki raporla:** Aynı davranış için zıt koşullar, uyumsuz güvenlik/politika kuralları veya mutually exclusive ifadeler varsa çelişki üret.
7. **Destekleyici veya uyumlu gereksinimleri çelişki olarak işaretleme.**

**Giriş Metni:**
{chunk_text}

**Metadata:** {metadata}

Yanıtını SADECE AnalysisReport şemasına uygun JSON formatında ver.
{format_instructions}
"""
        return ChatPromptTemplate.from_template(prompt_template).partial(
            format_instructions=format_instructions
        )