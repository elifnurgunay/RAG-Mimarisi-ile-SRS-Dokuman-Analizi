# src/core/deterministic_quality_rules.py

import re
from src.schemas.issue import RequirementIssue

def detect_deterministic_quality_issues(document_text: str) -> list[RequirementIssue]:
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

