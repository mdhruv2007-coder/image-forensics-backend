"""AI-generated image detection layer (``umm-maybe/AI-image-detector``).

This layer answers the question "does this image look AI-generated?", which is
a different question from "was this specific photo edited?". A genuine photo
that was retouched, spliced or copy-moved can score as fully "human" here, and
a clean synthetic image can score high without any tampering of a real
photograph. The score is therefore one signal among several in the fusion
step and must not be treated as authoritative on its own.

Model handling: the Swin Transformer classifier is read strictly from a local
cache directory (``MODEL_CACHE_DIR``) with ``local_files_only=True``; it is
never downloaded at runtime. The model is loaded lazily once and shared as a
process-wide singleton. If it cannot be loaded (empty cache, corrupted files,
unrecognised labels, missing dependencies) ``run()`` returns a clean
"skipped" ``LayerResult`` instead of raising, so the rest of the pipeline keeps
working.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

from forensics.layers.base import Layer, make_skipped_result
from forensics.schemas import LayerResult

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps heavy imports lazy
    import torch
    from transformers import AutoImageProcessor, AutoModelForImageClassification

__all__ = [
    "AIDetectorLayer",
    "ModelUnavailableError",
    "LayerLabelError",
    "layer",
    "load_model",
    "LAYER_NAME",
    "MODEL_ID",
]

logger = logging.getLogger(__name__)

LAYER_NAME = "ai_generated_classifier"
MODEL_ID = "umm-maybe/AI-image-detector"
CACHE_ENV_VAR = "MODEL_CACHE_DIR"

# Reliability thresholds on the probability's distance from 0.5, rescaled to
# 0-1 (0 = coin flip, 1 = fully certain). 0.8 -> p >= 0.9 or p <= 0.1;
# 0.4 -> p >= 0.7 or p <= 0.3.
_HIGH_CONFIDENCE = 0.8
_MEDIUM_CONFIDENCE = 0.4

# Label vocabulary used to decide which of the model's real labels means
# "AI-generated". Matching is done on lower-cased alphanumeric tokens.
_AI_TOKENS = frozenset(
    {"artificial", "ai", "fake", "generated", "synthetic", "gan", "diffusion"}
)
_HUMAN_TOKENS = frozenset(
    {"human", "real", "authentic", "natural", "genuine", "photo", "photograph"}
)
_NEGATION_TOKENS = frozenset({"not", "non", "no"})


class ModelUnavailableError(RuntimeError):
    """Raised when the classifier cannot be loaded from the local cache."""


class LayerLabelError(RuntimeError):
    """Raised when the model's labels cannot be mapped to AI / human."""


@dataclass(frozen=True)
class _LoadedModel:
    """Everything needed to run inference, loaded once and shared."""

    processor: AutoImageProcessor
    model: AutoModelForImageClassification
    device: str
    ai_index: int
    id2label: dict[int, str]


# --------------------------------------------------------------------------- #
# Model loading (singleton)
# --------------------------------------------------------------------------- #

_model_lock = threading.Lock()
_loaded: _LoadedModel | None = None
_load_error: ModelUnavailableError | LayerLabelError | None = None


def _resolve_cache_dir() -> Path:
    """Return the configured model cache directory or fail with a clear error."""
    raw = os.environ.get(CACHE_ENV_VAR, "").strip()
    if not raw:
        raise ModelUnavailableError(
            f"Environment variable {CACHE_ENV_VAR} is not set. Point it at the "
            f"local Hugging Face cache containing '{MODEL_ID}' (this layer "
            "never downloads models at runtime)."
        )
    path = Path(raw).expanduser()
    if not path.is_dir():
        raise ModelUnavailableError(
            f"{CACHE_ENV_VAR}='{path}' does not exist or is not a directory."
        )
    if not any(path.iterdir()):
        raise ModelUnavailableError(
            f"Model cache directory '{path}' is empty. Pre-download "
            f"'{MODEL_ID}' into it before starting the service."
        )
    return path


def _tokens(label: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", label.lower()) if t}


def _classify_label(label: str) -> str | None:
    """Return ``"ai"``, ``"human"`` or ``None`` for an unrecognised label."""
    toks = _tokens(label)
    has_ai = bool(toks & _AI_TOKENS)
    has_human = bool(toks & _HUMAN_TOKENS)
    negated = bool(toks & _NEGATION_TOKENS)
    if has_ai and not negated and not has_human:
        return "ai"
    if has_human or (has_ai and negated):
        return "human"
    return None


def _find_ai_index(id2label: dict[int, str]) -> int:
    """Work out which output index means "AI-generated" from the real labels."""
    kinds = {idx: _classify_label(name) for idx, name in id2label.items()}
    ai_indices = [i for i, k in kinds.items() if k == "ai"]
    if len(ai_indices) == 1:
        return ai_indices[0]

    # Binary classifier where only the human side was recognised: AI is the other.
    human_indices = [i for i, k in kinds.items() if k == "human"]
    if len(id2label) == 2 and len(human_indices) == 1:
        return next(i for i in id2label if i != human_indices[0])

    raise LayerLabelError(
        f"Cannot map model labels {dict(id2label)} onto AI/human; expected "
        "exactly one label that denotes AI-generated content."
    )


def _load_model_unlocked() -> _LoadedModel:
    cache_dir = _resolve_cache_dir()
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification
    except ImportError as exc:
        raise ModelUnavailableError(
            f"Required ML dependency is missing: {exc}. Install 'torch' and "
            "'transformers'."
        ) from exc

    try:
        processor = AutoImageProcessor.from_pretrained(
            MODEL_ID, cache_dir=str(cache_dir), local_files_only=True
        )
        model = AutoModelForImageClassification.from_pretrained(
            MODEL_ID, cache_dir=str(cache_dir), local_files_only=True
        )
    except Exception as exc:  # noqa: BLE001 - any load failure means "unavailable"
        raise ModelUnavailableError(
            f"Could not load '{MODEL_ID}' from local cache '{cache_dir}': "
            f"{type(exc).__name__}: {exc}. The cache may be empty or corrupted; "
            "this layer does not fall back to downloading."
        ) from exc

    id2label = {int(i): str(name) for i, name in model.config.id2label.items()}
    ai_index = _find_ai_index(id2label)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    logger.info(
        "Loaded %s on %s (labels=%s, ai_index=%d)", MODEL_ID, device, id2label, ai_index
    )
    return _LoadedModel(
        processor=processor,
        model=model,
        device=device,
        ai_index=ai_index,
        id2label=id2label,
    )


def load_model() -> _LoadedModel:
    """Return the shared model, loading it on first use.

    Raises:
        ModelUnavailableError: if the local cache is missing/empty/corrupted
            or dependencies are not installed.
        LayerLabelError: if the model's labels cannot be mapped to AI/human.

    A failure is remembered so a broken cache is not re-read on every request.
    Restart the process after fixing the cache.
    """
    global _loaded, _load_error
    if _loaded is not None:
        return _loaded
    if _load_error is not None:
        raise _load_error
    with _model_lock:
        if _loaded is not None:
            return _loaded
        if _load_error is not None:
            raise _load_error
        try:
            _loaded = _load_model_unlocked()
        except (ModelUnavailableError, LayerLabelError) as exc:
            _load_error = exc
            logger.error("AI detector unavailable: %s", exc)
            raise
        return _loaded


# --------------------------------------------------------------------------- #
# Scoring helpers
# --------------------------------------------------------------------------- #


def _reliability_from_probability(p_ai: float) -> str:
    """Map distance from 0.5 onto the schema's low/medium/high reliability."""
    certainty = abs(p_ai - 0.5) * 2.0
    if certainty >= _HIGH_CONFIDENCE:
        return "high"
    if certainty >= _MEDIUM_CONFIDENCE:
        return "medium"
    return "low"


def _to_rgb(image: Image.Image) -> Image.Image:
    """Flatten any PIL mode (RGBA, P, L, CMYK...) to RGB for the model."""
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


# --------------------------------------------------------------------------- #
# Layer
# --------------------------------------------------------------------------- #


class AIDetectorLayer:
    """Detection layer wrapping the ``umm-maybe/AI-image-detector`` classifier."""

    layer_name: str = LAYER_NAME

    def run(self, image: Image.Image) -> LayerResult:
        """Estimate how likely ``image`` is to be AI-generated.

        Returns:
            ``LayerResult`` with ``score`` = P(AI-generated), reliability based
            on distance from 0.5, and the raw labels/probabilities in
            ``detail``. If the model cannot be loaded, a "skipped" result; if
            inference itself errors, a "failed" result.
        """
        try:
            loaded = load_model()
        except (ModelUnavailableError, LayerLabelError) as exc:
            return make_skipped_result(self.layer_name, f"model unavailable: {exc}")

        try:
            import torch

            rgb = _to_rgb(image)
            inputs = loaded.processor(images=rgb, return_tensors="pt")
            inputs = {k: v.to(loaded.device) for k, v in inputs.items()}
            with torch.inference_mode():
                logits = loaded.model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0].detach().cpu().tolist()
        except Exception as exc:  # noqa: BLE001 - never crash the pipeline
            logger.exception("AI detector inference failed")
            return LayerResult(
                layer_name=self.layer_name,
                score=0.0,
                reliability="low",
                status="failed",
                detail={
                    "reason": f"inference error: {type(exc).__name__}: {exc}",
                    "model_id": MODEL_ID,
                },
                heatmap_png_b64=None,
            )

        p_ai = min(1.0, max(0.0, float(probs[loaded.ai_index])))
        raw: dict[str, float] = {
            loaded.id2label[i]: float(p) for i, p in enumerate(probs)
        }
        detail: dict[str, Any] = {
            "model_id": MODEL_ID,
            "device": loaded.device,
            "ai_label": loaded.id2label[loaded.ai_index],
            "ai_probability": p_ai,
            "labels": list(loaded.id2label.values()),
            "probabilities": raw,
            "note": (
                "Measures whether the image looks AI-generated, not whether a "
                "real photo was edited; not authoritative on its own."
            ),
        }
        return LayerResult(
            layer_name=self.layer_name,
            score=p_ai,
            reliability=_reliability_from_probability(p_ai),
            status="ok",
            detail=detail,
            heatmap_png_b64=None,
        )


# Shared instance for the pipeline; satisfies the ``Layer`` protocol.
layer: Layer = AIDetectorLayer()