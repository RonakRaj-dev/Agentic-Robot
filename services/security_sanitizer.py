import re
import html
from typing import Tuple
from loguru import logger
from fastapi import HTTPException, status

class SecuritySanitizer:
    """
    Prompt Injection Defense & Input Sanitization Shield:
    - Neutralizes prompt injection attack vectors (system prompt overrides, jailbreaks).
    - Enforces HTML/XSS entity encoding.
    - Validates payload length bounds.
    """
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)",
        r"disregard\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)",
        r"forget\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)",
        r"override\s+(system|prompt|safety|guardrails)",
        r"you\s+are\s+now\s+in\s+(developer|god|dan|jailbreak)\s+mode",
        r"system\s*:\s*assume\s+the\s+role",
        r"bypass\s+(safety|content)\s+filters",
        r"drop\s+table",
        r"delete\s+from",
        r"<script.*?>",
    ]

    def __init__(self, max_query_length: int = 1000) -> None:
        self.max_query_length = max_query_length
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]

    def is_prompt_injection(self, text: str) -> Tuple[bool, str]:
        """Detects if query contains adversarial prompt injection keywords."""
        if not text:
            return False, ""
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                match = pattern.pattern
                logger.warning(f"Detected potential prompt injection attack pattern: '{match}' in input.")
                return True, match
        return False, ""

    def sanitize_input(self, text: str, max_length: int = 1000) -> str:
        """
        Sanitizes user input string:
        - Truncates to max length payload bound.
        - Encodes HTML/XSS special characters.
        - Neutralizes prompt injection phrases.
        """
        if not text:
            return ""

        # 1. Enforce payload character bound
        limit = max_length or self.max_query_length
        if len(text) > limit:
            logger.warning(f"Payload length ({len(text)}) exceeded limit ({limit}). Truncating.")
            text = text[:limit]

        # 2. XSS HTML entity encoding
        text = html.escape(text)

        # 3. Prompt injection neutralization
        is_injection, _ = self.is_prompt_injection(text)
        if is_injection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security Violation: Input query contains prohibited prompt override or system jailbreak directives."
            )

        return text.strip()

security_sanitizer = SecuritySanitizer()
