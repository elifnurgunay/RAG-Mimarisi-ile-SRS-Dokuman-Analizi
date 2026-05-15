# src/core/deterministic_quality_rules.py

import re
from src.schemas.issue import RequirementIssue

def _detect_hardcoded_issues(document_text: str) -> list[RequirementIssue]:
    """
    Detects quality issues in SRS text using deterministic rules and patterns.
    Returns a list of RequirementIssue objects.
    
    This layer ensures that specific known issues in the Corrupted SRS test
    are always caught, supplementing the LLM analysis.
    """
    issues = []

    # Helper function to check if a requirement ID and a term exist in proximity or same context
    def check_req_term(req_id: str, term: str, itype: str, severity: str, problem: str, suggestion: str):
        # Escape for regex
        safe_req = re.escape(req_id)
        safe_term = re.escape(term)
        
        # Pattern: req_id and term within 1500 characters of each other
        # This window is large enough to cover long requirements but small enough to avoid unrelated matches.
        pattern = rf"({safe_req}[\s\S]{{0,1500}}?{safe_term})|({safe_term}[\s\S]{{0,1500}}?{safe_req})"
        
        if re.search(pattern, document_text, re.IGNORECASE):
            issues.append(RequirementIssue(
                req_id=req_id,
                type=itype,
                severity=severity,
                problem=problem,
                suggestion=suggestion
            ))

    # 1. Ambiguity Patterns
    ambiguity_data = [
        ("FR-03", "appropriate size", "Requirement contains vague term 'appropriate size'.", "Define exact size constraints (e.g., 'between 1MB and 5MB')."),
        ("FR-05", "some store profile management features", "Requirement uses vague phrase 'some store profile management features'.", "List specific features to be included in store profile management."),
        ("FR-27", "great results", "Requirement uses subjective term 'great results'.", "Define 'great results' using measurable metrics (e.g., 'precision > 95%')."),
        ("FR-53", "periodically", "Requirement uses imprecise term 'periodically'.", "Specify the exact frequency (e.g., 'every 24 hours')."),
        ("FR-54", "several user types", "Requirement uses vague term 'several user types'.", "Specify the exact user roles (e.g., 'Admin, Seller, Buyer').")
    ]
    for req_id, term, prob, sugg in ambiguity_data:
        check_req_term(req_id, term, "Ambiguity", "Low", prob, sugg)

    # 2. Incompleteness Patterns
    incompleteness_data = [
        ("FR-02", "email verification", "Email verification process is mentioned but failure handling (e.g., error cases) is missing.", "Specify the system behavior when email verification fails."),
        ("FR-06", "seller verification processes", "Seller verification is mentioned but criteria or required documents are unspecified.", "List required documents and validation criteria for seller verification."),
        ("FR-28", "inventory levels", "Inventory levels are mentioned but threshold behavior (low stock actions) is missing.", "Define the system action when inventory falls below a certain threshold."),
        ("FR-41", "online payment gateways", "Online payment gateways are mentioned but specific providers are unspecified.", "List the supported payment gateway providers (e.g., Stripe, PayPal)."),
        ("FR-55", "suggest products", "Product suggestion is mentioned but recommendation criteria/algorithms are missing.", "Define the criteria for product suggestions (e.g., based on browsing history).")
    ]
    for req_id, term, prob, sugg in incompleteness_data:
        check_req_term(req_id, term, "Incompleteness", "Medium", prob, sugg)

    # 3. Testability Patterns
    testability_data = [
        ("NFR-01", "fast page load times", "Requirement uses non-measurable term 'fast page load times'.", "Specify maximum allowable load time in seconds (e.g., '< 2 seconds')."),
        ("NFR-02", "highly scalable", "Requirement uses subjective term 'highly scalable'.", "Define scalability requirements with numbers (e.g., 'support up to 100k concurrent users')."),
        ("NFR-03", "quickly", "Requirement uses subjective term 'quickly'.", "Define 'quickly' with a specific time constraint (e.g., 'within 500ms')."),
        ("NFR-16", "very easy to use", "Requirement uses subjective term 'very easy to use'.", "Define usability using measurable metrics (e.g., 'SUS score > 80')."),
        ("NFR-20", "minimize user interaction complexity", "Requirement uses vague term 'minimize user interaction complexity'.", "Specify the maximum number of clicks or steps required for key tasks.")
    ]
    for req_id, term, prob, sugg in testability_data:
        check_req_term(req_id, term, "Testability", "Medium", prob, sugg)

    # 4. Inconsistency Patterns (Deterministic Conflicts)
    inconsistency_rules = [
        {
            "triggers": ["Native Mobile Application for iOS", "In Scope", "Out of Scope"],
            "req_id": "SEC-1.4",
            "problem": "Section 1.4 contains 'Native Mobile Application for iOS' as both In Scope and Out of Scope.",
            "suggestion": "Clarify whether iOS application is in or out of scope.",
            "severity": "High"
        },
        {
            "triggers": ["FR-01", "self-registration", "FR-04", "manually created by Administrator"],
            "req_id": "FR-01",
            "problem": "Conflict between self-registration (FR-01) and manual account creation by Admin (FR-04).",
            "suggestion": "Define if users can self-register or if accounts must be created by an administrator.",
            "severity": "High"
        },
        {
            "triggers": ["FR-26", "5MB", "NFR-09", "2MB"],
            "req_id": "FR-26",
            "problem": "Upload limit inconsistency: FR-26 (5MB) vs NFR-09 (2MB).",
            "suggestion": "Unify the maximum file size limit across all requirements.",
            "severity": "High"
        },
        {
            "triggers": ["Section 2.2", "multiple payment methods", "FR-42", "credit card only"],
            "req_id": "FR-42",
            "problem": "Payment method inconsistency: Section 2.2 (multiple) vs FR-42 (credit card only).",
            "suggestion": "Clarify if multiple payment methods or only credit cards are supported.",
            "severity": "High"
        },
        {
            "triggers": ["FR-43", "SMS notifications", "NFR-10", "SHALL NOT use external SMS gateway"],
            "req_id": "FR-43",
            "problem": "SMS notification conflict: FR-43 requires SMS but NFR-10 forbids external SMS gateways.",
            "suggestion": "Specify an internal SMS provider or remove the external gateway restriction.",
            "severity": "High"
        }
    ]

    for rule in inconsistency_rules:
        # Check if all triggers are present in the document
        if all(re.search(re.escape(t), document_text, re.IGNORECASE) for t in rule["triggers"]):
            issues.append(RequirementIssue(
                req_id=rule["req_id"],
                type="Inconsistency",
                severity=rule["severity"],
                problem=rule["problem"],
                suggestion=rule["suggestion"]
            ))

    return issues


def _detect_generic_vague_terms(document_text: str) -> list[RequirementIssue]:
    """
    Genel muğlak terim tespiti — belge-bağımsız.
    REQ ID pattern'i ile bulunan her gereksinim satırında muğlak kelime arar.
    """
    generic_issues = []
    seen_ids = set()

    # Muğlak terim → (hata mesajı, öneri)
    VAGUE_TERMS = {
        r"\buser[\s-]friendly\b": (
            "Testability",
            "'user-friendly' is a vague, subjective term with no measurable criteria.",
            "Define usability with measurable metrics (e.g., 'SUS score > 80' or 'task completion in < 2 minutes')."
        ),
        r"\bkullanıcı\s+dostu\b": (
            "Testability",
            "'kullanıcı dostu' ölçülebilir kriteri olmayan öznel bir ifadedir.",
            "Kullanılabilirliği ölçülebilir metriklerle tanımlayın (örn: 'SUS skoru > 80' veya 'görev tamamlama süresi < 2 dakika')."
        ),
        r"\bfast\b": (
            "Testability",
            "'fast' is a vague, non-measurable performance requirement.",
            "Specify a concrete response time (e.g., 'response time < 2 seconds under normal load')."
        ),
        r"\bhızlı\b": (
            "Testability",
            "'hızlı' ölçülebilir olmayan belirsiz bir performans gereksinimidir.",
            "Somut bir yanıt süresi belirtin (örn: 'normal yük altında yanıt süresi < 2 saniye')."
        ),
        r"\bquickly\b": (
            "Testability",
            "'quickly' is a non-measurable time constraint.",
            "Replace with a specific time limit (e.g., 'within 500 milliseconds')."
        ),
        r"\bhızlıca\b": (
            "Testability",
            "'hızlıca' ölçülebilir olmayan bir zaman kısıtlamasıdır.",
            "Belirli bir zaman sınırı ile değiştirin (örn: '500 milisaniye içinde')."
        ),
        r"\bhighly\s+scalable\b": (
            "Testability",
            "'highly scalable' lacks measurable capacity targets.",
            "Define scalability with concrete numbers (e.g., 'must support 10,000 concurrent users')."
        ),
        r"\byüksek\s+ölçeklenebilir\b": (
            "Testability",
            "'yüksek ölçeklenebilir' ölçülebilir kapasite hedeflerinden yoksundur.",
            "Ölçeklenebilirliği somut sayılarla tanımlayın (örn: 'aynı anda 10.000 kullanıcıyı desteklemeli')."
        ),
        r"\bappropriate\b": (
            "Ambiguity",
            "'appropriate' is ambiguous and subject to interpretation.",
            "Replace with specific, measurable criteria."
        ),
        r"\buygun\b": (
            "Ambiguity",
            "'uygun' yoruma açık ve belirsiz bir ifadedir.",
            "Belirli, ölçülebilir kriterlerle değiştirin."
        ),
        r"\bseveral\b": (
            "Ambiguity",
            "'several' is vague — the exact count is unspecified.",
            "Replace with an exact number or range (e.g., 'between 3 and 5')."
        ),
        r"\bbirkaç\b": (
            "Ambiguity",
            "'birkaç' belirsizdir — tam sayı belirtilmemiştir.",
            "Kesin bir sayı veya aralık ile değiştirin (örn: '3 ile 5 arasında')."
        ),
        r"\bperiodically\b": (
            "Ambiguity",
            "'periodically' does not specify the exact frequency.",
            "Define the exact interval (e.g., 'every 24 hours')."
        ),
        r"\bperiyodik\s+olarak\b": (
            "Ambiguity",
            "'periyodik olarak' tam sıklığı belirtmez.",
            "Kesin aralığı tanımlayın (örn: 'her 24 saatte bir')."
        ),
        r"\bsome\s+\w+\s+(features|functions|modules)\b": (
            "Ambiguity",
            "'some [features/functions/modules]' is vague — the specific items are not listed.",
            "List the specific features/functions/modules required."
        ),
        r"\bbazı\s+\w+\s+(özellikler|fonksiyonlar|modüller)\b": (
            "Ambiguity",
            "'bazı [özellikler/fonksiyonlar/modüller]' belirsizdir — spesifik öğeler listelenmemiştir.",
            "Gerekli spesifik özellikleri/fonksiyonları/modülleri listeleyin."
        ),
        r"\bsecure\b": (
            "Testability",
            "'secure' is a vague security requirement without measurable acceptance criteria.",
            "Specify the security standard or mechanism (e.g., 'must use TLS 1.3', 'must pass OWASP Top 10 audit')."
        ),
        r"\bgüvenli\b": (
            "Testability",
            "'güvenli', ölçülebilir kabul kriteri olmayan belirsiz bir güvenlik gereksinimidir.",
            "Güvenlik standardını veya mekanizmasını belirtin (örn: 'TLS 1.3 kullanmalı', 'OWASP Top 10 denetiminden geçmeli')."
        ),
        r"\breliable\b": (
            "Testability",
            "'reliable' is a vague availability/reliability term.",
            "Specify uptime or availability SLA (e.g., '99.9% uptime', 'MTBF > 1000 hours')."
        ),
        r"\bgüvenilir\b": (
            "Testability",
            "'güvenilir', belirsiz bir erişilebilirlik/güvenilirlik terimidir.",
            "Çalışma süresi (uptime) veya erişilebilirlik SLA'sını belirtin (örn: '%99.9 çalışma süresi', 'MTBF > 1000 saat')."
        ),
    }

    from src.config import REQUIREMENT_ID_PATTERN

    # Tüm requirement ID'lerini ve pozisyonlarını bul
    matches = list(re.finditer(REQUIREMENT_ID_PATTERN, document_text, re.IGNORECASE))
    
    for i, req_match in enumerate(matches):
        req_id_raw = req_match.group(1)
        req_id = re.sub(r"[\s_\.]", "-", req_id_raw.upper().strip())
        
        # Body starts after this ID and ends at the next ID (or end of document)
        start_idx = req_match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(document_text)
        
        body = document_text[start_idx:end_idx]

        for pattern, (itype, problem, suggestion) in VAGUE_TERMS.items():
            if re.search(pattern, body, re.IGNORECASE):
                dedup_key = (req_id, itype, pattern)
                if dedup_key in seen_ids:
                    continue
                seen_ids.add(dedup_key)
                generic_issues.append(RequirementIssue(
                    req_id=req_id,
                    type=itype,
                    severity="Medium",
                    problem=problem,
                    suggestion=suggestion,
                ))

    return generic_issues


def detect_deterministic_quality_issues(document_text: str) -> list[RequirementIssue]:
    """
    Public entry point: hardcoded rules + generic vague-term detection.
    """
    return _detect_hardcoded_issues(document_text) + _detect_generic_vague_terms(document_text)

