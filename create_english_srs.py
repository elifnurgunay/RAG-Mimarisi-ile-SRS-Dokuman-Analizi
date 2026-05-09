import fitz

text = """
Software Requirements Specification

REQ-001: The system shall allow users to create tasks.

REQ-002: The system shall allow users to delete tasks.

REQ-003: The system shall respond fast to user actions.

REQ-004: The system shall store user data securely.

REQ-005: The system shall encrypt all stored user data using AES-256.

REQ-006: The system shall be available on mobile devices.

REQ-007: The system shall provide a modern user interface.

REQ-008: The system shall allow users to delete tasks.

REQ-009: The system shall work offline.

REQ-010: The system shall require internet access for all operations.
"""

doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), text, fontsize=11)
doc.save("data/english_srs.pdf")
doc.close()

print("Created data/english_srs.pdf")
