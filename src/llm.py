"""Thin wrapper around a local Ollama model.

Every model in proof-swarm is an `Agent`: a name, a model id, and a system
prompt describing its role. Talking to a model is just `agent.ask(messages)`.
Nothing is hidden — read this file and you've read the whole interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import ollama


@dataclass
class Agent:
    """One model instance playing one role (prover, critic, judge, ...)."""

    name: str
    model: str
    system: str
    temperature: float = 0.7
    # Kept so you can inspect exactly what an agent has seen.
    transcript: list[dict] = field(default_factory=list)

    def ask(self, user_message: str, remember: bool = False) -> str:
        """Send a message, return the reply text.

        If `remember` is True the exchange is appended to this agent's
        transcript so follow-up calls keep the conversation going.
        """
        messages = [{"role": "system", "content": self.system}]
        messages.extend(self.transcript)
        messages.append({"role": "user", "content": user_message})

        response = ollama.chat(
            model=self.model,
            messages=messages,
            options={"temperature": self.temperature},
        )
        reply = response["message"]["content"]

        if remember:
            self.transcript.append({"role": "user", "content": user_message})
            self.transcript.append({"role": "assistant", "content": reply})

        return reply

    def reset(self) -> None:
        self.transcript.clear()


def available_models() -> list[str]:
    """Model ids currently pulled into Ollama, for a friendly error message."""
    try:
        return [m["model"] for m in ollama.list().get("models", [])]
    except Exception:
        return []
