"""Task prompts: what she asks the AI to do, in plain words.

Each function builds the prompt; the provider runs it. Everything that
comes back is a DRAFT -- she reviews, edits, approves. Nothing here
posts, sends, or publishes anything.
"""

from __future__ import annotations

from forge.ai.providers import AIProvider, AIResponse


SYSTEM = (
    "You are a helpful assistant for an adult content creator managing "
    "her own business. Keep outputs short, punchy, and ready to use. "
    "Never invent prices, links, or personal details."
)


def ask(provider: AIProvider, prompt: str, max_tokens: int = 500) -> AIResponse:
    return provider.complete(prompt, system=SYSTEM, max_tokens=max_tokens)


def captions(provider: AIProvider, topic: str, n: int = 3,
             tone: str = "playful") -> AIResponse:
    return provider.complete(
        f"Write {n} short social-media captions ({tone} tone) for an adult "
        f"content creator posting about: {topic}. One per line, no "
        f"numbering, each under 200 characters. No hashtags.",
        system=SYSTEM, max_tokens=400)


def titles(provider: AIProvider, topic: str, n: int = 5) -> AIResponse:
    return provider.complete(
        f"Write {n} catchy, SEO-friendly video titles (under 80 characters "
        f"each) for an adult content creator's video about: {topic}. "
        f"One per line, no numbering, no clickbait lies.",
        system=SYSTEM, max_tokens=400)


def hashtags(provider: AIProvider, topic: str, n: int = 10) -> AIResponse:
    return provider.complete(
        f"Suggest {n} effective hashtags for an adult creator's post about: "
        f"{topic}. Comma-separated, single line, no explanations.",
        system=SYSTEM, max_tokens=200)


def content_ideas(provider: AIProvider, niche: str, n: int = 10) -> AIResponse:
    return provider.complete(
        f"Brainstorm {n} video content ideas for an adult content creator "
        f"whose niche is: {niche}. Each idea: one bold title line plus one "
        f"sentence on the hook. Numbered list.",
        system=SYSTEM, max_tokens=600)


def scene_ideas(provider: AIProvider, vibe: str, n: int = 5) -> AIResponse:
    return provider.complete(
        f"Describe {n} filmable scene concepts (setting, outfit, camera "
        f"angle, mood) for an AI video shoot with this vibe: {vibe}. "
        f"Keep each to 2-3 sentences. Numbered list.",
        system=SYSTEM, max_tokens=600)


def polish(provider: AIProvider, text: str) -> AIResponse:
    return provider.complete(
        f"Rewrite this creator's draft to be punchier and more engaging, "
        f"keeping her meaning and voice. Return ONLY the rewritten text, "
        f"no commentary:\n\n{text}",
        system=SYSTEM, max_tokens=500)


def reply_assist(provider: AIProvider, incoming: str,
                 context: str = "") -> AIResponse:
    ctx = f"\nConversation context: {context}" if context.strip() else ""
    return provider.complete(
        f"A fan just messaged an adult content creator: \"{incoming}\"{ctx}\n"
        f"Draft 2 short reply options she could send: one playful, one "
        f"flirty-but-classy. Label them A and B. Keep each under 240 "
        f"characters.",
        system=SYSTEM, max_tokens=400)


def promo_text(provider: AIProvider, item: str, price: str) -> AIResponse:
    return provider.complete(
        f"Write 3 short promo lines selling \"{item}\" for {price} from an "
        f"adult content creator to her fans. Playful, confident, no "
        f"pressure tactics. One per line.",
        system=SYSTEM, max_tokens=300)
