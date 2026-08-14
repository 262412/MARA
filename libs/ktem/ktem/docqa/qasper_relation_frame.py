from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_NUMBER_RE = re.compile(
    r"(?<![a-z0-9])(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|"
    r"eight|nine|ten)(?![a-z0-9])",
    re.IGNORECASE,
)
_PREDICATE_PATTERNS = {
    "leverage": r"\bleverag(?:e|es|ed|ing)\b",
    "rely_on": r"\brel(?:y|ies|ied|ying)\s+on\b",
    "use": r"\b(?:use|uses|used|using)\b",
    "provide": r"\bprovid(?:e|es|ed|ing)\b",
    "contain": r"\bcontain(?:s|ed|ing)?\b",
    "include": r"\binclud(?:e|es|ed|ing)\b",
    "report": r"\breport(?:s|ed|ing)?\b",
    "describe": r"\bdescrib(?:e|es|ed|ing)\b",
    "identify": r"\bidentif(?:y|ies|ied|ying)\b",
    "recruit": r"\brecruit(?:s|ed|ing)?\b",
    "evaluate": r"\b(?:evaluat(?:e|es|ed|ing)|assess(?:es|ed|ing)?)\b",
    "train": r"\btrain(?:s|ed|ing)?\b",
    "improve": r"\bimprov(?:e|es|ed|ing)\b",
    "calculate": r"\bcalculat(?:e|es|ed|ing)\b",
    "compute": r"\bcomput(?:e|es|ed|ing)\b",
    "derive": r"\bderiv(?:e|es|ed|ing)\b",
    "apply": r"\bappl(?:y|ies|ied|ying)\b",
    "perform": r"\bperform(?:s|ed|ing)?\b",
    "create": r"\bcreat(?:e|es|ed|ing)\b",
    "collect": r"\bcollect(?:s|ed|ing)?\b",
    "release": r"\breleas(?:e|es|ed|ing)\b",
    "compare": r"\bcompar(?:e|es|ed|ing)\b",
    "analyze": r"\banaly(?:ze|zes|zed|zing|se|ses|sed|sing)\b",
    "explore": r"\bexplor(?:e|es|ed|ing)\b",
    "address": r"\baddress(?:es|ed|ing)?\b",
    "achieve": r"\bachiev(?:e|es|ed|ing)\b",
    "find": r"\b(?:find|finds|found|finding)\b",
}


@dataclass(frozen=True, slots=True)
class QuestionRelationFrame:
    actor: str
    predicate: str
    expected_object_role: str
    expected_object_type: str
    scope: str
    qualifier: str
    quantifier: str
    relation_kind: str


def question_relation_frame(question: str) -> QuestionRelationFrame:
    lowered = str(question or "").lower()
    actor = "current_paper" if _requires_current_paper_actor(question) else "unknown"
    qualifier = _qualifier(question)
    quantifiers = _numbers(question)
    quantifier = sorted(quantifiers)[0] if quantifiers else "none"
    object_type = _expected_object_type(question)
    scope = _question_scope(question)
    qualification = _qualification_frame(
        lowered,
        actor=actor,
        scope=scope,
        qualifier=qualifier,
        quantifier=quantifier,
    )
    if qualification is not None:
        return qualification
    account_for = _account_for_frame(
        lowered,
        actor=actor,
        object_type=object_type,
        scope=scope,
        qualifier=qualifier,
        quantifier=quantifier,
    )
    if account_for is not None:
        return account_for
    if re.search(r"\bhow\s+(?:many|much)\b|\b(?:number|count)\s+of\b", lowered):
        return _frame(
            actor,
            _lexical_predicate(question) or "quantify",
            "quantity",
            object_type,
            scope,
            qualifier,
            quantifier,
            "quantity",
        )
    definition = _definition_frame(
        lowered,
        actor=actor,
        object_type=object_type,
        scope=scope,
        qualifier=qualifier,
        quantifier=quantifier,
    )
    if definition is not None:
        return definition
    if re.search(r"\bwhy\b|\b(?:cause|reason|drive|lead\s+to|result\s+in)\b", lowered):
        return _frame(
            actor,
            _lexical_predicate(question) or "cause",
            "cause",
            object_type,
            scope,
            qualifier,
            quantifier,
            "cause",
        )
    if re.search(r"^\s*how\b", lowered):
        return _frame(
            actor,
            _lexical_predicate(question) or "method",
            "manner",
            object_type,
            scope,
            qualifier,
            quantifier,
            "method",
        )
    return _frame(
        actor,
        _lexical_predicate(question),
        "object",
        object_type,
        scope,
        qualifier,
        quantifier,
    )


def relation_is_explicit(
    frame: QuestionRelationFrame,
    quote: str,
    *,
    answer_numbers: set[str],
    quote_numbers: set[str],
) -> bool:
    lowered = quote.lower()
    if frame.predicate == "account_for":
        return _account_for_is_explicit(lowered)
    if frame.predicate == "qualify":
        return bool(
            re.search(
                r"\b(?:improv(?:e|es|ed|ing|ement)|significant|only|"
                r"qualif(?:y|ies|ied|ying|ication))\b",
                lowered,
            )
        )
    predicate_explicit = _predicate_is_explicit(frame.predicate, lowered)
    if frame.relation_kind == "quantity":
        return bool(
            answer_numbers and answer_numbers <= quote_numbers and predicate_explicit
        )
    if frame.relation_kind == "definition":
        return bool(
            re.search(
                r"\b(?:mean|represent|refer|denote|define|stand|is|are)\w*\b",
                lowered,
            )
        )
    if frame.relation_kind == "cause":
        return bool(
            predicate_explicit
            and re.search(
                r"\b(?:because|cause|due\s+to|reason|drive|lead|result)\w*\b",
                lowered,
            )
        )
    if frame.relation_kind == "method":
        return bool(
            predicate_explicit
            and re.search(r"\b(?:by|using|through|via|with)\b", lowered)
        )
    return predicate_explicit


def question_scope_is_explicit(frame: QuestionRelationFrame, quote: str) -> bool:
    if frame.scope == "document":
        return True
    scope_tokens = set(_TOKEN_RE.findall(frame.scope.lower()))
    quote_tokens = set(_TOKEN_RE.findall(quote.lower()))
    return bool(scope_tokens and scope_tokens <= quote_tokens)


def _frame(
    actor: str,
    predicate: str,
    object_role: str,
    object_type: str,
    scope: str,
    qualifier: str,
    quantifier: str,
    relation_kind: str = "attribute",
) -> QuestionRelationFrame:
    return QuestionRelationFrame(
        actor,
        predicate,
        object_role,
        object_type,
        scope,
        qualifier,
        quantifier,
        relation_kind,
    )


def _qualification_frame(
    question: str,
    *,
    actor: str,
    scope: str,
    qualifier: str,
    quantifier: str,
) -> QuestionRelationFrame | None:
    match = re.search(
        r"\bwhat\s+qualification\s+appl(?:y|ies|ied)\s+to\s+(.+?)(?:\?|$)",
        question,
    )
    if match is None:
        return None
    return _frame(
        actor,
        "qualify",
        "qualifier",
        " ".join(match.group(1).split()),
        scope,
        qualifier,
        quantifier,
        "qualification",
    )


def _account_for_frame(
    question: str,
    *,
    actor: str,
    object_type: str,
    scope: str,
    qualifier: str,
    quantifier: str,
) -> QuestionRelationFrame | None:
    if not re.search(r"\baccount(?:s|ed|ing)?\s+for\b", question):
        return None
    return _frame(
        actor,
        "account_for",
        "patient",
        object_type,
        scope,
        qualifier,
        quantifier,
    )


def _definition_frame(
    question: str,
    *,
    actor: str,
    object_type: str,
    scope: str,
    qualifier: str,
    quantifier: str,
) -> QuestionRelationFrame | None:
    if not re.search(
        r"\b(?:mean|means|repr?esents?|refer\s+to|denote|define|stand\s+for)\b",
        question,
    ):
        return None
    return _frame(
        actor,
        "define",
        "definition",
        object_type,
        scope,
        qualifier,
        quantifier,
        "definition",
    )


def _account_for_is_explicit(quote: str) -> bool:
    return bool(
        re.search(r"\baccount(?:s|ed|ing)?\s+for\b", quote)
        and (
            re.search(r"\bby\s+(?:this\s+work|this\s+paper|us|the\s+authors?)\b", quote)
            or re.search(
                r"\b(?:this\s+work|this\s+paper|we|the\s+authors?)\b[^.!?]*"
                r"\baccount(?:s|ed|ing)?\s+for\b",
                quote,
            )
        )
    )


def _lexical_predicate(question: str) -> str:
    lowered = str(question or "").lower()
    return next(
        (
            predicate
            for predicate, pattern in _PREDICATE_PATTERNS.items()
            if re.search(pattern, lowered, re.IGNORECASE)
        ),
        "",
    )


def _predicate_is_explicit(predicate: str, quote: str) -> bool:
    semantic_patterns = {
        "leverage": (
            _PREDICATE_PATTERNS["leverage"],
            _PREDICATE_PATTERNS["rely_on"],
            _PREDICATE_PATTERNS["use"],
        ),
        "rely_on": (
            _PREDICATE_PATTERNS["rely_on"],
            _PREDICATE_PATTERNS["leverage"],
            _PREDICATE_PATTERNS["use"],
        ),
    }
    if predicate in semantic_patterns:
        return any(
            re.search(pattern, quote, re.IGNORECASE)
            for pattern in semantic_patterns[predicate]
        )
    if predicate in {"cause", "method", "quantify"}:
        patterns = {
            "cause": r"\b(?:because|cause|due\s+to|reason|drive|lead|result)\w*\b",
            "method": r"\b(?:use|apply|perform|compute|derive)\w*\b",
            "quantify": r"\b(?:number|count|total|amount)\w*\b",
        }
        return bool(re.search(patterns[predicate], quote, re.IGNORECASE))
    pattern = _PREDICATE_PATTERNS.get(predicate)
    return bool(pattern and re.search(pattern, quote, re.IGNORECASE))


def _expected_object_type(question: str) -> str:
    text = " ".join(str(question or "").strip().split())
    quantity = re.search(
        r"\bhow\s+(?:many|much)\s+(.+?)(?=\s+(?:do|does|did|is|are|was|were|"
        r"has|have|had|can|could|will|would)\b)",
        text,
        re.IGNORECASE,
    )
    match = quantity or re.search(
        r"\b(?:what|which)\s+(.+?)(?=\s+(?:do|does|did|is|are|was|were|has|"
        r"have|had|can|could|will|would)\b)",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return "answer object"
    value = match.group(1).strip(" ,? ")
    value = re.split(
        r"\b(?:encountered|observed|found|that|which|who|in|during|for|by)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    return value or "answer object"


def _question_scope(question: str) -> str:
    text = " ".join(str(question or "").strip().lower().split())
    for pattern in (
        r"\bin\s+(actual\s+data)\b",
        r"\bduring\s+([a-z0-9][a-z0-9 -]{0,48}?)(?=\?|$)",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            return " ".join(match.group(1).split())
    return "document"


def _requires_current_paper_actor(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:authors?|paper|study|work|approach|model|method|proposed|we|our|"
            r"they|their)\b",
            question,
            re.IGNORECASE,
        )
    )


def _numbers(value: str) -> set[str]:
    return {match.group(0).lower() for match in _NUMBER_RE.finditer(str(value or ""))}


def _qualifier(value: str) -> str:
    match = re.search(
        r"\b(?:at\s+least|at\s+most|more\s+than|less\s+than|only|approximately|"
        r"about|now)\b",
        str(value or "").lower(),
    )
    return match.group(0) if match else "none"
