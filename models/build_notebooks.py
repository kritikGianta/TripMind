"""Generates the training/evaluation notebooks in this folder from readable cell lists.

    python models/build_notebooks.py

Kaggle notebooks (hotel_ranker, fare_estimator) are run by hand on Kaggle. Local notebooks
(price_anomaly, similar_hotels) are executed in the backend environment:

    cd backend
    uv run --with nbconvert --with ipykernel jupyter nbconvert --to notebook --execute \
        --inplace ../models/price_anomaly/price_anomaly.ipynb
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

HERE = Path(__file__).parent


def md(text: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(text).strip()}


def code(text: str) -> dict[str, object]:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": dedent(text).strip()}


def write(path: Path, cells: list[dict[str, object]]) -> None:
    notebook = {
        "nbformat": 4, "nbformat_minor": 5, "cells": cells,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3",
                                    "language": "python"},
                     "language_info": {"name": "python"}},
    }
    path.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {path.relative_to(HERE.parent)}")


CARD_HELPER = '''
import json, datetime, lightgbm
def write_card(name, features, dataset, metrics, notes):
    version = datetime.date.today().strftime("%Y.%m.%d")
    card = {"name": name, "version": version,
            "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "framework": "lightgbm", "framework_version": lightgbm.__version__,
            "dataset": dataset, "features": list(features), "metrics": metrics, "notes": notes}
    with open("/kaggle/working/model_card.json", "w") as f:
        json.dump(card, f, indent=2)
    print(json.dumps(card, indent=2))
'''

# ── Hotel ranker (Kaggle) ────────────────────────────────────────────────────────────────────────
write(HERE / "hotel_ranker" / "hotel_ranker.ipynb", [
    md("""
    # TripMind hotel ranker (LightGBM LambdaRank)

    Learns how real travellers choose hotels from **Expedia's Personalize Hotel Search** data
    (search results with clicks and bookings), then orders TripMind's "Recommended" stays.

    **Run on Kaggle:** create a notebook, *Add data* → competition
    [expedia-personalized-sort](https://www.kaggle.com/c/expedia-personalized-sort/data)
    (join the competition to accept its rules), then *Run all*. CPU is enough; a GPU is not used.

    **Hand back:** download `model.txt` and `model_card.json` from `/kaggle/working` and put both in
    `models/hotel_ranker/artifacts/`. TripMind only uses the model if the card's features match
    and the model beats the rule-based baseline below.

    Features are exactly those in `backend/app/modules/ml/features.py` (`HOTEL_RANKER_FEATURES`),
    limited to what TripMind's own catalog can provide at serving time.
    """),
    code("""
    import glob
    import numpy as np, pandas as pd, lightgbm
    path = glob.glob("/kaggle/input/**/train.csv", recursive=True)[0]
    cols = ["srch_id", "prop_starrating", "prop_review_score", "price_usd", "srch_length_of_stay",
            "srch_adults_count", "srch_room_count", "srch_booking_window", "click_bool",
            "booking_bool", "random_bool"]
    df = pd.read_csv(path, usecols=cols)
    print(path, df.shape)
    """),
    md("""
    Only randomly ordered result lists (`random_bool == 1`) are used, so the model learns what people
    choose, not the position Expedia's own ranker gave a hotel. Prices are clipped to remove obvious
    errors; Expedia notes `price_usd` can be per night or per stay depending on the market, so it is
    also divided by the stay length when it is far above the search's median.
    """),
    code("""
    df = df[df.random_bool == 1].copy()
    searches = df.srch_id.drop_duplicates().sample(n=min(150_000, df.srch_id.nunique()), random_state=7)
    df = df[df.srch_id.isin(searches)]
    df["price_usd"] = df.price_usd.clip(5, 5_000)
    median = df.groupby("srch_id").price_usd.transform("median")
    per_stay = (df.price_usd > 3 * median) & (df.srch_length_of_stay > 1)
    df.loc[per_stay, "price_usd"] = df.price_usd / df.srch_length_of_stay
    df["label"] = np.where(df.booking_bool == 1, 5, np.where(df.click_bool == 1, 1, 0))
    df = df.sort_values("srch_id")
    print(df.shape, df.label.value_counts().to_dict())
    """),
    code("""
    FEATURES = ("star_rating", "review_score", "log_price_usd", "price_rank_pct", "star_rank_pct",
                "length_of_stay", "adults", "rooms", "booking_window_days")
    g = df.groupby("srch_id")
    X = pd.DataFrame({
        "star_rating": df.prop_starrating.astype(float),
        "review_score": df.prop_review_score.fillna(0).astype(float),
        "log_price_usd": np.log1p(df.price_usd),
        "price_rank_pct": g.price_usd.rank(pct=True, method="min").sub(g.price_usd.transform(lambda s: 1 / len(s))).clip(0, 1),
        "star_rank_pct": g.prop_starrating.rank(pct=True, method="min").sub(g.prop_starrating.transform(lambda s: 1 / len(s))).clip(0, 1),
        "length_of_stay": df.srch_length_of_stay.astype(float),
        "adults": df.srch_adults_count.astype(float),
        "rooms": df.srch_room_count.astype(float),
        "booking_window_days": df.srch_booking_window.astype(float),
    })[list(FEATURES)]
    ids = df.srch_id.unique()
    rng = np.random.default_rng(7); rng.shuffle(ids)
    valid_ids = set(ids[: len(ids) // 5])
    is_valid = df.srch_id.isin(valid_ids).to_numpy()
    def groups(mask): return df[mask].groupby("srch_id", sort=False).size().to_numpy()
    train = lightgbm.Dataset(X[~is_valid], df.label[~is_valid], group=groups(~is_valid))
    valid = lightgbm.Dataset(X[is_valid], df.label[is_valid], group=groups(is_valid))
    params = {"objective": "lambdarank", "metric": "ndcg", "ndcg_eval_at": [5], "learning_rate": 0.05,
              "num_leaves": 63, "min_data_in_leaf": 200, "feature_fraction": 0.9, "verbose": -1}
    model = lightgbm.train(params, train, 600, valid_sets=[valid],
                           callbacks=[lightgbm.early_stopping(50), lightgbm.log_evaluation(50)])
    """),
    md("**Baseline:** TripMind's rule-based score (rating 50%, value 30%, stars 20%). The model must beat it."),
    code("""
    from sklearn.metrics import ndcg_score
    v = df[is_valid].assign(model=model.predict(X[is_valid]),
                            rules=0.5 * X[is_valid].review_score / 5 + 0.3 * (1 - X[is_valid].price_rank_pct)
                                  + 0.2 * X[is_valid].star_rating / 5)
    def mean_ndcg(column):
        scores = [ndcg_score([grp.label], [grp[column]], k=5) for _, grp in v.groupby("srch_id") if grp.label.max() > 0]
        return float(np.mean(scores))
    metrics = {"ndcg5_model": mean_ndcg("model"), "ndcg5_rules_baseline": mean_ndcg("rules"),
               "train_searches": float(len(ids) - len(valid_ids)), "valid_searches": float(len(valid_ids))}
    print(metrics)
    assert metrics["ndcg5_model"] > metrics["ndcg5_rules_baseline"], "model does not beat the baseline: do not ship"
    """),
    code(CARD_HELPER + '''
    model.save_model("/kaggle/working/model.txt", num_iteration=model.best_iteration)
    write_card("hotel_ranker", FEATURES,
               "Expedia Personalize Hotel Search (Kaggle), randomly ordered result lists only",
               metrics, "LambdaRank; labels: booking 5, click 1. Prices may mix per-night and per-stay values.")
    '''),
])

# ── Fare estimator (Kaggle) ──────────────────────────────────────────────────────────────────────
write(HERE / "fare_estimator" / "fare_estimator.ipynb", [
    md("""
    # TripMind fare estimator (LightGBM regression)

    Learns typical Indian domestic economy and business fares, so TripMind can tell a traveller
    whether a fare is **below typical, typical or above typical** for that route length, timing and
    stops. It never changes a price; it only adds context.

    **Run on Kaggle:** *Add data* → dataset
    [Flight Price Prediction](https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction)
    (file `Clean_Dataset.csv`, about 300,000 flights between six Indian metros), then *Run all*.
    CPU is enough.

    **Hand back:** `model.txt` and `model_card.json` from `/kaggle/working` into
    `models/fare_estimator/artifacts/`. Features match `FARE_ESTIMATOR_FEATURES` in
    `backend/app/modules/ml/features.py`. TripMind only scores routes up to 2,000 km, the range
    this data covers.
    """),
    code("""
    import glob, math
    import numpy as np, pandas as pd, lightgbm
    path = glob.glob("/kaggle/input/**/Clean_Dataset.csv", recursive=True)[0]
    df = pd.read_csv(path)
    print(df.shape); df.head()
    """),
    md("Distances use the same airport coordinates as TripMind's catalog, so the feature means the same thing at serving time."),
    code("""
    AIRPORTS = {"Delhi": (28.5562, 77.1000), "Mumbai": (19.0896, 72.8656), "Bangalore": (13.1986, 77.7066),
                "Kolkata": (22.6547, 88.4467), "Hyderabad": (17.2403, 78.4294), "Chennai": (12.9941, 80.1709)}
    def km(a, b):
        lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
        h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        return 6371 * 2 * math.asin(math.sqrt(h))
    HOURS = {"Late_Night": 2, "Early_Morning": 6, "Morning": 10, "Afternoon": 14, "Evening": 18, "Night": 22}
    STOPS = {"zero": 0, "one": 1, "two_or_more": 2}
    FEATURES = ("distance_km", "duration_minutes", "stops", "days_left", "departure_hour", "business")
    X = pd.DataFrame({
        "distance_km": [km(AIRPORTS[s], AIRPORTS[d]) for s, d in zip(df.source_city, df.destination_city)],
        "duration_minutes": df.duration * 60,
        "stops": df.stops.map(STOPS),
        "days_left": df.days_left.clip(1, 50),
        "departure_hour": df.departure_time.map(HOURS),
        "business": (df["class"] == "Business").astype(float),
    })[list(FEATURES)]
    y = np.log(df.price)
    print(X.describe().T[["min", "max"]])
    """),
    code("""
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=7)
    model = lightgbm.train({"objective": "regression_l1", "learning_rate": 0.05, "num_leaves": 63,
                            "min_data_in_leaf": 100, "verbose": -1},
                           lightgbm.Dataset(X_train, y_train), 1500,
                           valid_sets=[lightgbm.Dataset(X_test, y_test)],
                           callbacks=[lightgbm.early_stopping(100), lightgbm.log_evaluation(100)])
    pred, actual = np.exp(model.predict(X_test)), np.exp(y_test)
    # Baseline: median fare for the same cabin and distance band.
    band = pd.cut(X_test.distance_km, 8)
    baseline = pd.Series(actual.values, index=X_test.index).groupby([X_test.business, band], observed=True).transform("median")
    metrics = {"mape_model": float(np.mean(np.abs(pred - actual) / actual)),
               "mape_median_baseline": float(np.mean(np.abs(baseline - actual) / actual)),
               "mae_inr_model": float(np.mean(np.abs(pred - actual))), "rows": float(len(df))}
    print(metrics)
    assert metrics["mape_model"] < metrics["mape_median_baseline"], "model does not beat the baseline: do not ship"
    """),
    code(CARD_HELPER + '''
    model.save_model("/kaggle/working/model.txt", num_iteration=model.best_iteration)
    write_card("fare_estimator", FEATURES, "Flight Price Prediction (Kaggle), Indian domestic fares between six metros",
               metrics, "Predicts log(fare in INR) per adult. Airline identity is deliberately not a feature.")
    '''),
])

# ── Price anomaly detector (local evaluation) ────────────────────────────────────────────────────
write(HERE / "price_anomaly" / "price_anomaly.ipynb", [
    md("""
    # Fare anomaly detector: evaluation

    The detector (`backend/app/modules/ingestion/anomalies.py`) is an Isolation Forest fitted on
    every import over route-relative fare and duration. Here it is measured against **known** errors:
    the demo generator injects fares at 8x their real value, and a clean run of the same seed gives
    the true fares, so precision and recall are exact. Runs locally in the backend environment.
    """),
    code("""
    import csv, io, json, sys, tempfile, zipfile, datetime
    from datetime import date
    from pathlib import Path
    from app.core.config import get_settings
    from app.datagen.generator import GeneratorOptions, generate
    from app.modules.ingestion.anomalies import MIN_RELATIVE_JUMP, score_fares
    from app.modules.ingestion.mapping import load_mapping
    from app.modules.ingestion.pipeline import prepare
    from app.modules.ingestion.rules import load_rules, load_vocabulary
    from app.modules.ingestion.sources import open_source
    """),
    code("""
    tmp = Path(tempfile.mkdtemp())
    results = []
    settings = get_settings()
    for seed in (7, 11, 23):
        opts = dict(seed=seed, start=date(2026, 11, 13), days=45)
        generate(tmp / "dirty.zip", GeneratorOptions(**opts)); generate(tmp / "clean.zip", GeneratorOptions(**opts, dirty_rate=0))
        rows = lambda z: list(csv.DictReader(io.StringIO(zipfile.ZipFile(z).read("flights.csv").decode())))
        spiked = {f"{d['flight_no'].replace(' ', '')}|{d['departure']}|{d['cabin']}"
                  for c, d in zip(rows(tmp / "clean.zip"), rows(tmp / "dirty.zip"))
                  if c["fare"] and d["fare"] and float(d["fare"]) > 4 * float(c["fare"])}
        prepared = prepare(open_source(tmp / "dirty.zip", max_members=10, max_uncompressed_mb=900),
                           load_mapping(settings.config_dir, "synthetic-v1"), load_rules(settings.config_dir),
                           load_vocabulary(settings.config_dir), catalog_airports=lambda: [])
        f = prepared.flights
        key = f.flight_number + "|" + f.departure_local.dt.strftime("%Y-%m-%d %H:%M") + "|" + f.cabin_class.str.capitalize()
        flagged, truth = score_fares(f), key.isin(spiked)
        tp, fp, fn = int((flagged & truth).sum()), int((flagged & ~truth).sum()), int((~flagged & truth).sum())
        results.append({"seed": seed, "fares": len(f), "injected": int(truth.sum()), "tp": tp, "fp": fp, "fn": fn})
        print(results[-1])
    """),
    code("""
    tp, fp, fn = (sum(r[k] for r in results) for k in ("tp", "fp", "fn"))
    metrics = {"precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1), "fares_checked": float(sum(r["fares"] for r in results)),
               "min_relative_jump": MIN_RELATIVE_JUMP}
    print(metrics)
    card = {"name": "price_anomaly", "version": datetime.date.today().strftime("%Y.%m.%d"),
            "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "framework": "scikit-learn",
            "framework_version": __import__("sklearn").__version__, "dataset": "TripMind synthetic data, 3 seeds, injected 8x fares",
            "features": ["relative_log_fare", "relative_log_duration"], "metrics": metrics,
            "notes": "Fitted per import; this card records the evaluation, there is no stored artifact."}
    Path("artifacts").mkdir(exist_ok=True); Path("artifacts/model_card.json").write_text(json.dumps(card, indent=2))
    """),
])

# ── Similar stays (local evaluation) ─────────────────────────────────────────────────────────────
write(HERE / "similar_hotels" / "similar_hotels.ipynb", [
    md("""
    # Similar stays: evaluation

    `backend/app/modules/ml/similar.py` ranks stays in the same city by TF-IDF cosine similarity
    over amenities, star class, rating band and price band. With no click data to learn from yet,
    it is checked for the properties a traveller would expect: recommended stays should usually
    share the star class and price band, and share distinctive amenities more than random pairs.
    """),
    code("""
    import json, sys, tempfile, datetime
    from collections import defaultdict
    from datetime import date
    from pathlib import Path
    import numpy as np, pandas as pd
    from app.core.config import get_settings
    from app.datagen.generator import GeneratorOptions, generate
    from app.modules.ingestion.mapping import load_mapping
    from app.modules.ingestion.pipeline import prepare
    from app.modules.ingestion.rules import load_rules, load_vocabulary
    from app.modules.ingestion.sources import open_source
    from app.modules.ml.similar import HotelProfile, similar_hotels
    tmp = Path(tempfile.mkdtemp()) / "demo.zip"
    generate(tmp, GeneratorOptions(seed=7, start=date(2026, 11, 13), days=3, dirty_rate=0))
    s = get_settings()
    p = prepare(open_source(tmp, max_members=10, max_uncompressed_mb=900), load_mapping(s.config_dir, "synthetic-v1"),
                load_rules(s.config_dir), load_vocabulary(s.config_dir), catalog_airports=lambda: [])
    hotels, rooms = p.hotels, p.room_types
    cheapest = rooms.groupby("hotel_id").nightly_rate_minor.min()
    print(len(hotels), "hotels in", hotels.city_key.nunique(), "cities")
    """),
    code("""
    rng = np.random.default_rng(7)
    same_star, same_band, jaccard_similar, jaccard_random = [], [], [], []
    def jac(a, b): return len(a & b) / max(len(a | b), 1)
    for city, group in hotels.groupby("city_key"):
        profiles = [HotelProfile(h.id, tuple(h.amenity_codes), h.star_rating, h.guest_rating, cheapest.get(h.id))
                    for h in group.itertuples()]
        if len(profiles) < 4:
            continue
        prices = np.array([pr.nightly_price or 0 for pr in profiles]); edges = np.quantile(prices, [0.2, 0.4, 0.6, 0.8])
        band = {pr.id: int(np.searchsorted(edges, pr.nightly_price or 0)) for pr in profiles}
        by_id = {pr.id: pr for pr in profiles}
        for pr in profiles:
            for n in similar_hotels(pr.id, profiles, k=3):
                other = by_id[n.id]
                same_star.append(int(pr.star_rating) == int(other.star_rating))
                same_band.append(abs(band[pr.id] - band[n.id]) <= 1)
                jaccard_similar.append(jac(set(pr.amenities), set(other.amenities)))
                rand = profiles[rng.integers(len(profiles))]
                jaccard_random.append(jac(set(pr.amenities), set(rand.amenities)))
    metrics = {"same_star_class": float(np.mean(same_star)), "within_one_price_band": float(np.mean(same_band)),
               "amenity_jaccard_similar": float(np.mean(jaccard_similar)), "amenity_jaccard_random": float(np.mean(jaccard_random))}
    print(metrics)
    assert metrics["amenity_jaccard_similar"] > metrics["amenity_jaccard_random"]
    """),
    code("""
    card = {"name": "similar_hotels", "version": datetime.date.today().strftime("%Y.%m.%d"),
            "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "framework": "scikit-learn",
            "framework_version": __import__("sklearn").__version__, "dataset": "TripMind synthetic catalog",
            "features": ["amenities", "star_class", "rating_band", "price_band"], "metrics": metrics,
            "notes": "Computed on demand from the live catalog; this card records the evaluation."}
    Path("artifacts").mkdir(exist_ok=True); Path("artifacts/model_card.json").write_text(json.dumps(card, indent=2))
    """),
])
