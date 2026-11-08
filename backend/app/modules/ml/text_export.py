"""Export a fitted scikit-learn TfidfVectorizer + LogisticRegression as plain JSON.

Self-contained on purpose: the training notebooks embed this file verbatim, and the API's
`TextModel` (ml/text.py) reads the result. JSON instead of pickle, so loading a model can never
run code. A unit test checks that TextModel reproduces scikit-learn's probabilities.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

FORMAT = "tfidf-logreg-v1"


def export_tfidf_logreg(
    vectorizer: Any,
    model: Any,
    out_dir: str | Path,
    *,
    name: str,
    dataset: str,
    metrics: dict[str, float],
    notes: str = "",
    decimals: int = 6,
) -> dict[str, Any]:
    params = vectorizer.get_params()
    unsupported = {
        "analyzer": params["analyzer"] != "word",
        "tokenizer": params["tokenizer"] is not None,
        "preprocessor": params["preprocessor"] is not None,
        "stop_words": params["stop_words"] is not None,
        "strip_accents": params["strip_accents"] is not None,
        "norm": params["norm"] not in ("l2", None),
        "use_idf": not params["use_idf"],
        "binary": params["binary"],
    }
    if any(unsupported.values()):
        raise ValueError(
            f"unsupported vectorizer settings: {[k for k, v in unsupported.items() if v]}"
        )
    vocabulary = {term: int(index) for term, index in vectorizer.vocabulary_.items()}
    payload = {
        "format": FORMAT,
        "lowercase": bool(params["lowercase"]),
        "token_pattern": params["token_pattern"],
        "ngram_range": list(params["ngram_range"]),
        "sublinear_tf": bool(params["sublinear_tf"]),
        "norm": params["norm"],
        "vocabulary": vocabulary,
        "idf": [round(float(v), decimals) for v in vectorizer.idf_],
        "classes": [str(c) for c in model.classes_],
        "coef": [[round(float(v), decimals) for v in row] for row in model.coef_],
        "intercept": [round(float(v), decimals) for v in model.intercept_],
    }
    import sklearn

    card = {
        "name": name,
        "version": datetime.date.today().strftime("%Y.%m.%d"),
        "trained_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "framework": "scikit-learn",
        "framework_version": sklearn.__version__,
        "dataset": dataset,
        "features": [FORMAT],
        "metrics": {k: float(v) for k, v in metrics.items()},
        "notes": notes,
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    (out / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card
