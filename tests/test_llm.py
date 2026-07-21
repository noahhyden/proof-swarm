"""Offline tests for the model wrapper, with a fake Ollama client injected.

Covers both the streaming and buffered branches of Agent.ask, memory, and the
available_models success/failure paths - without a running Ollama server.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proofswarm import llm


class FakeClient:
    def __init__(self, full="hello", chunks=("hel", "lo"), models=(), list_raises=False):
        self.full = full
        self.chunks = chunks
        self.models = models
        self.list_raises = list_raises
        self.last_options = None

    def chat(self, model, messages, options, stream=False):
        self.last_options = options
        if stream:
            return iter([{"message": {"content": c}} for c in self.chunks])
        return {"message": {"content": self.full}}

    def list(self):
        if self.list_raises:
            raise RuntimeError("no server")
        return {"models": [{"model": m} for m in self.models]}


def _agent(**kw):
    return llm.Agent("T", "fake-model", "system prompt", **kw)


def test_buffered_ask_returns_reply_and_passes_seed(monkeypatch):
    fake = FakeClient(full="the answer")
    monkeypatch.setattr(llm, "_client", fake)
    agent = _agent(stream=False, seed=7, temperature=0.5)
    assert agent.ask("q") == "the answer"
    assert fake.last_options == {"temperature": 0.5, "seed": 7}
    assert agent.transcript == []  # remember defaults to False


def test_ask_remembers_when_requested(monkeypatch):
    monkeypatch.setattr(llm, "_client", FakeClient(full="r1"))
    agent = _agent(stream=False)
    agent.ask("first", remember=True)
    assert len(agent.transcript) == 2  # user + assistant
    agent.reset()
    assert agent.transcript == []


def test_streaming_ask_joins_chunks_and_prints(monkeypatch, capsys):
    monkeypatch.setattr(llm, "_client", FakeClient(chunks=("Hel", "lo!")))
    agent = _agent(stream=True)
    assert agent.ask("q") == "Hello!"
    assert "Hello!" in capsys.readouterr().out


def test_available_models_returns_ids(monkeypatch):
    monkeypatch.setattr(llm, "_client", FakeClient(models=("qwen2.5:3b", "gemma2:2b")))
    assert llm.available_models() == ["qwen2.5:3b", "gemma2:2b"]


def test_available_models_swallows_errors(monkeypatch):
    monkeypatch.setattr(llm, "_client", FakeClient(list_raises=True))
    assert llm.available_models() == []
