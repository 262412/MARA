from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .finance_verification import (
    finance_numeric_claim_supported,
    finance_verification_claims,
)


class DomainVerifier(Protocol):
    def verification_claims(self, claims: list[str], *, prompt: str) -> list[str]:
        ...

    def claim_supported(
        self,
        claim: str,
        evidence_items: list[dict[str, Any]],
        *,
        prompt: str,
    ) -> bool | None:
        ...


@dataclass(frozen=True)
class GenericDomainVerifier:
    name: str = "generic"

    def verification_claims(self, claims: list[str], *, prompt: str) -> list[str]:
        del prompt
        return claims

    def claim_supported(
        self,
        claim: str,
        evidence_items: list[dict[str, Any]],
        *,
        prompt: str,
    ) -> bool | None:
        del claim, evidence_items, prompt
        return None


@dataclass(frozen=True)
class FinanceDomainVerifier:
    name: str = "finance"

    def verification_claims(self, claims: list[str], *, prompt: str) -> list[str]:
        return finance_verification_claims(claims, prompt=prompt)

    def claim_supported(
        self,
        claim: str,
        evidence_items: list[dict[str, Any]],
        *,
        prompt: str,
    ) -> bool | None:
        return finance_numeric_claim_supported(
            claim,
            evidence_items,
            prompt=prompt,
        )


class DomainVerifierRegistry:
    def __init__(self) -> None:
        self.generic = GenericDomainVerifier()
        self.finance = FinanceDomainVerifier()

    def select(self, *, profile_flags: dict[str, Any]) -> DomainVerifier:
        domain = normalize_verification_domain(
            profile_flags.get("domain_verifier")
            or profile_flags.get("verification_domain")
        )
        if domain == "finance":
            return self.finance
        return self.generic


_REGISTRY = DomainVerifierRegistry()


def normalize_verification_domain(value: Any) -> str:
    domain = str(value or "").strip().lower()
    aliases = {"financebench": "finance", "financial": "finance"}
    return aliases.get(domain, domain)


def domain_verification_claims(
    domain: str,
    claims: list[str],
    *,
    prompt: str,
) -> list[str]:
    verifier = _REGISTRY.select(profile_flags={"domain_verifier": domain})
    return verifier.verification_claims(claims, prompt=prompt)


def domain_claim_supported(
    domain: str,
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
) -> bool | None:
    verifier = _REGISTRY.select(profile_flags={"domain_verifier": domain})
    return verifier.claim_supported(claim, evidence_items, prompt=prompt)
