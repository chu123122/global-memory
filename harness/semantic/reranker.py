"""Optional local reranker backends for semantic retrieval candidates.

The reranker layer is intentionally best-effort: dependency load failures,
backend exceptions, or timeout breaches produce an explicit fallback diagnostic
and preserve the original retrieval order.  Reranker scores are raw,
backend-specific scores and must not be presented as calibrated confidence.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Protocol, Sequence

DEFAULT_RERANK_MODEL = "Qwen/Qwen3-Reranker-0.6B"
DEFAULT_RERANK_BACKEND = "sentence-transformers"
DEFAULT_RERANK_TOPK = 30
DEFAULT_RERANK_TIMEOUT_MS = 5000
DEFAULT_RERANK_MAX_CHARS = 2000
DEFAULT_INSTRUCTION = "Given a web search query, retrieve relevant passages that answer the query"
_VALID_BACKENDS = {"off", "sentence-transformers", "transformers", "vllm"}


class RerankerError(RuntimeError):
    """Raised when a reranker backend cannot score candidates."""


@dataclass(frozen=True)
class RerankerConfig:
    backend: str = DEFAULT_RERANK_BACKEND
    model: str = DEFAULT_RERANK_MODEL
    top_k: int = DEFAULT_RERANK_TOPK
    timeout_ms: int = DEFAULT_RERANK_TIMEOUT_MS
    max_chars: int = DEFAULT_RERANK_MAX_CHARS

    @property
    def enabled(self) -> bool:
        return self.backend != "off"


class RerankerBackend(Protocol):
    name: str

    def score(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        instruction: str,
        max_chars: int,
    ) -> list[float]:
        """Return one raw relevance score per candidate."""


class MockRerankerBackend:
    """Deterministic backend for tests."""

    name = "mock"

    def __init__(self, scores_by_path: Mapping[str, float] | None = None, scores: Sequence[float] | None = None) -> None:
        self._scores_by_path = dict(scores_by_path or {})
        self._scores = list(scores or [])

    def score(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        instruction: str,
        max_chars: int,
    ) -> list[float]:
        if self._scores:
            if len(self._scores) != len(candidates):
                raise RerankerError("mock score count does not match candidates")
            return list(self._scores)
        return [float(self._scores_by_path.get(str(candidate.get("path") or ""), 0.0)) for candidate in candidates]


class SentenceTransformersBackend:
    name = "sentence-transformers"

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - depends on optional local install
            raise RerankerError(f"sentence-transformers unavailable: {exc}") from exc
        self._model = CrossEncoder(model_name)

    def score(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        instruction: str,
        max_chars: int,
    ) -> list[float]:
        query_text = query if instruction == DEFAULT_INSTRUCTION else f"{instruction}\n{query}"
        pairs = [(query_text, candidate_document(candidate, max_chars=max_chars)) for candidate in candidates]
        raw_scores = self._model.predict(pairs)
        try:
            return [float(score) for score in raw_scores.tolist()]  # numpy / torch tensors
        except AttributeError:
            return [float(score) for score in raw_scores]


class TransformersBackend:
    """Qwen official yes/no log-prob scoring path using transformers."""

    name = "transformers"

    def __init__(self, model_name: str) -> None:
        try:
            import torch  # type: ignore[import-not-found]
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - depends on optional local install
            raise RerankerError(f"transformers backend unavailable: {exc}") from exc
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
        self._model = AutoModelForCausalLM.from_pretrained(model_name).eval()
        if torch.cuda.is_available():  # pragma: no cover - machine dependent
            try:
                self._model = self._model.cuda()
            except Exception:
                # Explicit CPU fallback; diagnostics expose only backend/model, not a calibrated confidence.
                self._model = self._model.cpu()
        self._token_false_id = self._tokenizer.convert_tokens_to_ids("no")
        self._token_true_id = self._tokenizer.convert_tokens_to_ids("yes")
        self._max_length = 8192
        prefix = (
            '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. '
            'Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
        )
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        self._prefix_tokens = self._tokenizer.encode(prefix, add_special_tokens=False)
        self._suffix_tokens = self._tokenizer.encode(suffix, add_special_tokens=False)

    def _format_instruction(self, instruction: str, query: str, doc: str) -> str:
        return f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}"

    def _process_inputs(self, pairs: Sequence[str]):
        tokenizer = self._tokenizer
        inputs = tokenizer(
            list(pairs),
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=self._max_length - len(self._prefix_tokens) - len(self._suffix_tokens),
        )
        for i, token_ids in enumerate(inputs["input_ids"]):
            inputs["input_ids"][i] = self._prefix_tokens + token_ids + self._suffix_tokens
        inputs = tokenizer.pad(inputs, padding=True, return_tensors="pt", max_length=self._max_length)
        for key in inputs:
            inputs[key] = inputs[key].to(self._model.device)
        return inputs

    def score(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        instruction: str,
        max_chars: int,
    ) -> list[float]:
        pairs = [
            self._format_instruction(instruction, query, candidate_document(candidate, max_chars=max_chars))
            for candidate in candidates
        ]
        inputs = self._process_inputs(pairs)
        with self._torch.no_grad():
            batch_scores = self._model(**inputs).logits[:, -1, :]
            true_vector = batch_scores[:, self._token_true_id]
            false_vector = batch_scores[:, self._token_false_id]
            batch_scores = self._torch.stack([false_vector, true_vector], dim=1)
            batch_scores = self._torch.nn.functional.log_softmax(batch_scores, dim=1)
            scores = batch_scores[:, 1].exp().tolist()
        return [float(score) for score in scores]


class VllmBackend:
    """Experimental offline vLLM backend for benchmark-only evaluation."""

    name = "vllm"

    def __init__(self, model_name: str) -> None:
        try:
            import math as _math
            import torch  # type: ignore[import-not-found]
            from transformers import AutoTokenizer  # type: ignore[import-not-found]
            from vllm import LLM, SamplingParams  # type: ignore[import-not-found]
            from vllm.inputs.data import TokensPrompt  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - depends on optional local install
            raise RerankerError(f"vllm backend unavailable: {exc}") from exc
        self._math = _math
        self._TokensPrompt = TokensPrompt
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._tokenizer.padding_side = "left"
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        gpu_count = torch.cuda.device_count()
        self._model = LLM(
            model=model_name,
            tensor_parallel_size=max(1, gpu_count),
            max_model_len=10000,
            enable_prefix_caching=True,
            gpu_memory_utilization=0.8,
        )
        self._suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        self._suffix_tokens = self._tokenizer.encode(self._suffix, add_special_tokens=False)
        self._max_length = 8192
        self._true_token = self._tokenizer("yes", add_special_tokens=False).input_ids[0]
        self._false_token = self._tokenizer("no", add_special_tokens=False).input_ids[0]
        self._sampling_params = SamplingParams(
            temperature=0,
            max_tokens=1,
            logprobs=20,
            allowed_token_ids=[self._true_token, self._false_token],
        )

    def _format_instruction(self, instruction: str, query: str, doc: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": 'Judge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".',
            },
            {"role": "user", "content": f"<Instruct>: {instruction}\n\n<Query>: {query}\n\n<Document>: {doc}"},
        ]

    def score(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        instruction: str,
        max_chars: int,
    ) -> list[float]:
        messages = [
            self._format_instruction(instruction, query, candidate_document(candidate, max_chars=max_chars))
            for candidate in candidates
        ]
        tokenized = self._tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False, enable_thinking=False)
        prompts = [self._TokensPrompt(prompt_token_ids=tokens[: self._max_length - len(self._suffix_tokens)] + self._suffix_tokens) for tokens in tokenized]
        outputs = self._model.generate(prompts, self._sampling_params, use_tqdm=False)
        scores: list[float] = []
        for output in outputs:
            final_logits = output.outputs[0].logprobs[-1]
            true_logit = final_logits.get(self._true_token).logprob if self._true_token in final_logits else -10
            false_logit = final_logits.get(self._false_token).logprob if self._false_token in final_logits else -10
            true_score = self._math.exp(true_logit)
            false_score = self._math.exp(false_logit)
            scores.append(float(true_score / (true_score + false_score)))
        return scores


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def config_from_env() -> RerankerConfig:
    backend = os.environ.get("GM_SEARCH_RERANKER", DEFAULT_RERANK_BACKEND).strip().lower() or DEFAULT_RERANK_BACKEND
    if backend not in _VALID_BACKENDS:
        backend = "off"
    return RerankerConfig(
        backend=backend,
        model=os.environ.get("GM_SEARCH_RERANK_MODEL", DEFAULT_RERANK_MODEL).strip() or DEFAULT_RERANK_MODEL,
        top_k=_env_int("GM_SEARCH_RERANK_TOPK", DEFAULT_RERANK_TOPK, minimum=1),
        timeout_ms=_env_int("GM_SEARCH_RERANK_TIMEOUT_MS", DEFAULT_RERANK_TIMEOUT_MS, minimum=1),
        max_chars=_env_int("GM_SEARCH_RERANK_MAX_CHARS", DEFAULT_RERANK_MAX_CHARS, minimum=200),
    )


def candidate_document(candidate: Mapping[str, Any], *, max_chars: int = DEFAULT_RERANK_MAX_CHARS) -> str:
    parts: list[str] = []
    for label, key in (
        ("Path", "path"),
        ("Heading", "heading_path"),
        ("Summary", "summary"),
        ("Why", "why"),
        ("Text", "chunk_text"),
        ("Text", "text"),
    ):
        value = str(candidate.get(key) or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    text = "\n".join(parts).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 20)].rstrip() + "\n...[truncated]"


@lru_cache(maxsize=4)
def _backend_from_config(backend: str, model: str) -> RerankerBackend:
    if backend == "sentence-transformers":
        return SentenceTransformersBackend(model)
    if backend == "transformers":
        return TransformersBackend(model)
    if backend == "vllm":
        return VllmBackend(model)
    raise RerankerError(f"unsupported reranker backend: {backend}")


def _retrieval_score(candidate: Mapping[str, Any]) -> float:
    for key in ("retrieval_score", "score", "rank_score"):
        value = candidate.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return 0.0


def _fallback_rows(
    candidates: Sequence[Mapping[str, Any]],
    *,
    top_n: int,
    config: RerankerConfig,
    fallback_reason: str | None,
    latency_ms: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, candidate in enumerate(candidates[:top_n], start=1):
        row = dict(candidate)
        row.setdefault("retrieval_score", _retrieval_score(candidate))
        row.update({
            "reranker_enabled": False,
            "reranker_backend": config.backend,
            "reranker_model": config.model,
            "reranker_score": None,
            "reranker_rank": None,
            "reranker_latency_ms": round(latency_ms, 3),
            "confidence_calibrated": False,
            "fallback_reason": fallback_reason,
            "retrieval_rank": rank,
        })
        rows.append(row)
    diagnostics = {
        "requested_backend": config.backend,
        "backend": "off" if config.backend == "off" else config.backend,
        "model": config.model,
        "enabled": False,
        "confidence_calibrated": False,
        "candidate_count": len(candidates),
        "returned_count": len(rows),
        "latency_ms": round(latency_ms, 3),
        "fallback_reason": fallback_reason,
    }
    return rows, diagnostics


def rerank_candidates(
    query: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    top_n: int,
    instruction: str | None = None,
    config: RerankerConfig | None = None,
    backend_impl: RerankerBackend | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rerank candidates or preserve retrieval order with explicit fallback diagnostics."""
    config = config or config_from_env()
    top_n = max(1, int(top_n))
    selected = list(candidates[: max(top_n, config.top_k)])
    start = time.perf_counter()
    if not selected:
        return _fallback_rows([], top_n=top_n, config=config, fallback_reason=None if config.enabled else "backend_off", latency_ms=0.0)
    if not config.enabled:
        return _fallback_rows(selected, top_n=top_n, config=config, fallback_reason="backend_off", latency_ms=0.0)

    try:
        backend = backend_impl or _backend_from_config(config.backend, config.model)
        scores = backend.score(query, selected, instruction=instruction or DEFAULT_INSTRUCTION, max_chars=config.max_chars)
        latency_ms = (time.perf_counter() - start) * 1000.0
        if len(scores) != len(selected):
            raise RerankerError(f"score count {len(scores)} != candidate count {len(selected)}")
        if latency_ms > config.timeout_ms:
            raise RerankerError(f"timeout_ms_exceeded:{round(latency_ms, 3)}>{config.timeout_ms}")
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return _fallback_rows(selected, top_n=top_n, config=config, fallback_reason=str(exc), latency_ms=latency_ms)

    ranked: list[tuple[float, int, Mapping[str, Any]]] = []
    for idx, (score, candidate) in enumerate(zip(scores, selected)):
        score_value = float(score)
        if not math.isfinite(score_value):
            score_value = float("-inf")
        ranked.append((score_value, idx, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    rows: list[dict[str, Any]] = []
    for rank, (score, original_idx, candidate) in enumerate(ranked[:top_n], start=1):
        row = dict(candidate)
        row.setdefault("retrieval_score", _retrieval_score(candidate))
        row.update({
            "reranker_enabled": True,
            "reranker_backend": backend.name,
            "reranker_model": config.model,
            "reranker_score": round(float(score), 6),
            "reranker_rank": rank,
            "reranker_latency_ms": round(latency_ms, 3),
            "confidence_calibrated": False,
            "fallback_reason": None,
            "retrieval_rank": original_idx + 1,
        })
        rows.append(row)
    diagnostics = {
        "requested_backend": config.backend,
        "backend": backend.name,
        "model": config.model,
        "enabled": True,
        "confidence_calibrated": False,
        "candidate_count": len(selected),
        "returned_count": len(rows),
        "latency_ms": round(latency_ms, 3),
        "fallback_reason": None,
    }
    return rows, diagnostics
