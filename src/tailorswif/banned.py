"""The negative concept bank.

Two jobs. First, LLMs converge hard on the same twenty surreal images, so
concepts get checked before any money is spent on them. Second, every published
surrealism LoRA and preset is in the *dreamlike* register - melting, cosmic,
ethereal, glowing - and those words in a prompt drag a video model straight
back into it. The cheapest rejection is the earliest one.
"""

from __future__ import annotations

import re

# Concepts an LLM reaches for when asked to be surreal. Rejected at the plan
# stage, before a single image is rendered.
BANNED_CONCEPTS: frozenset[str] = frozenset(
    {
        "floating clock",
        "melting clock",
        "giant eyeball",
        "eye in the sky",
        "portal",
        "wormhole",
        "floating island",
        "floating castle",
        "whale in the sky",
        "jellyfish in the sky",
        "koi fish in the air",
        "butterfly swarm",
        "neon particles",
        "glowing orb",
        "energy wisp",
        "dragon",
        "unicorn",
        "crystal formation",
        "infinite staircase",
        "escher staircase",
        "mirror maze",
        "shattering mirror",
        "clockwork gears",
        "hourglass",
        "chess board",
        "third eye",
        "astronaut",
        "cosmic void",
        "galaxy in a jar",
        "tree of life",
        "faceless figure",
        "shadow person",
        "doll parts",
        "mannequin",
    }
)

# Style words that pull generation toward the dreamlike register. These are
# stripped or flagged in prompts rather than rejecting the whole concept.
DREAMLIKE_WORDS: frozenset[str] = frozenset(
    {
        "surreal",
        "surrealism",
        "surrealist",
        "dreamlike",
        "dreamy",
        "oneiric",
        "ethereal",
        "otherworldly",
        "cosmic",
        "celestial",
        "mystical",
        "magical",
        "enchanted",
        "whimsical",
        "fantastical",
        "psychedelic",
        "trippy",
        "melting",
        "dissolving",
        "glowing",
        "luminous",
        "iridescent",
        "shimmering",
        "swirling",
        "surrealistic",
        "hyperreal",
        "vibrant",
        "surrealism-inspired",
        "painterly",
        "fantasy",
        "epic",
        "cinematic masterpiece",
    }
)

# Naming a living director or a specific copyrighted work is both a provenance
# problem and, on most providers, a filtered request.
ATTRIBUTION_WORDS: frozenset[str] = frozenset(
    {
        "heymann",
        "muggia",
        "tailor swif",
        "up&up",
        "up and up",
        "a$ap",
        "asap rocky",
        "coldplay",
        "in the style of",
        "directed by",
        "music video by",
    }
)


class ConceptRejected(ValueError):
    """Raised when a concept hits the bank. Carries the reason for the ledger."""

    def __init__(self, kind: str, hits: list[str]) -> None:
        self.kind = kind
        self.hits = hits
        super().__init__(f"{kind}: {', '.join(sorted(hits))}")


def _hits(text: str, vocabulary: frozenset[str]) -> list[str]:
    lowered = text.lower()
    found = []
    for term in vocabulary:
        # Word-boundary match so "portal" does not fire on "portALL" and
        # multi-word terms still match as phrases.
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered):
            found.append(term)
    return found


def check_concept(text: str) -> None:
    """Reject a concept outright, or return. Costs nothing; run it first."""
    if banned := _hits(text, BANNED_CONCEPTS):
        raise ConceptRejected("generic surreal cliche", banned)
    if attributed := _hits(text, ATTRIBUTION_WORDS):
        raise ConceptRejected("named artist or work", attributed)


def check_prompt(text: str) -> list[str]:
    """Return dreamlike style words present in a prompt, worst offenders first.

    Not an exception: a prompt is repairable, a concept usually is not.
    """
    return sorted(_hits(text, DREAMLIKE_WORDS))


def scrub_prompt(text: str) -> str:
    """Remove dreamlike style words from a prompt, tidying the whitespace.

    Used as a guard on generated prompts. The register is meant to come from
    staging and specificity, never from a style adjective.
    """
    out = text
    for term in sorted(DREAMLIKE_WORDS, key=len, reverse=True):
        out = re.sub(rf"(?<!\w){re.escape(term)}(?!\w)", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+([,.])", r"\1", out)
    out = re.sub(r"([,.])\1+", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip(" ,.").strip() + "." if out.strip(" ,.") else ""
