"""
Optional AI advisor using Anthropic Claude.

Only imported / activated when:
  1. User has enabled AI mode in settings
  2. A valid API key is stored
  3. The `anthropic` package is installed

Falls back gracefully with a user-visible message if any of the above is missing.
All AI calls are on-demand (triggered by user clicking "Ask AI"), never automatic.
"""

from __future__ import annotations
from typing import Optional

from analysis.symptom_detector import Symptom
from analysis.suggestion_table import SuggestionEntry
from data_layer.data_models import TelemetrySnapshot
from config import AI_MODEL, AI_MAX_TOKENS


def is_available() -> bool:
    """True if the anthropic package is installed."""
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def build_prompt(
    symptom: Symptom,
    rule_suggestions: list[SuggestionEntry],
    snapshot: TelemetrySnapshot,
) -> str:
    """Construct the structured prompt sent to Claude."""
    car  = snapshot.vehicle_info.mCarName or "Unknown car"
    cls  = snapshot.vehicle_info.mCarClassName or ""
    track = snapshot.event_info.mTrackLocation or "Unknown track"
    variant = snapshot.event_info.mTrackVariation or ""

    rule_text = "\n".join(
        f"  {i+1}. [{e.category.upper()}] {e.title}: {e.detail}"
        for i, e in enumerate(rule_suggestions)
    )

    ctx_text = "  " + "\n  ".join(
        f"{k}: {v}" for k, v in symptom.context.items()
    )

    prompt = f"""You are an expert motorsport engineer advising an Automobilista 2 driver in real time.

Car: {car} ({cls})
Track: {track} {variant}
Speed: {snapshot.speed_kph:.0f} kph

Detected symptom: {symptom.label} (severity: {symptom.severity.value})
Telemetry context:
{ctx_text}

The rule-based advisor has already suggested:
{rule_text}

Please provide 1–2 additional or refined setup recommendations that go beyond the above.
Be specific (click counts, degree values, bar increments where possible).
Consider whether tyre temperatures, track conditions, or car class affect your advice.
Keep your response under 200 words. Do not restate the rule-based suggestions above."""

    return prompt


def ask_claude(
    symptom: Symptom,
    rule_suggestions: list[SuggestionEntry],
    snapshot: TelemetrySnapshot,
    api_key: str,
    streaming_callback=None,
) -> str:
    """
    Call Claude synchronously and return the response text.

    If streaming_callback is provided, it is called with each text chunk
    as it arrives (for streaming display in the UI).

    Raises RuntimeError with a user-friendly message on failure.
    """
    if not is_available():
        raise RuntimeError(
            "The 'anthropic' package is not installed.\n"
            "Run:  pip install anthropic"
        )

    if not api_key:
        raise RuntimeError(
            "No Anthropic API key configured.\n"
            "Add your key in Settings → AI Mode."
        )

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(symptom, rule_suggestions, snapshot)

    try:
        if streaming_callback is not None:
            full_text = ""
            with client.messages.stream(
                model=AI_MODEL,
                max_tokens=AI_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    streaming_callback(text)
            return full_text
        else:
            message = client.messages.create(
                model=AI_MODEL,
                max_tokens=AI_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

    except Exception as exc:
        raise RuntimeError(f"Claude API error: {exc}") from exc
