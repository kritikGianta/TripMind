"""Suspicious-price detection at import (Isolation Forest, scikit-learn).

Each fare is compared with fares on the SAME route and cabin, which removes the legitimate
differences between short and long routes or economy and business. Two features per fare:

    relative fare      log(fare) - median log(fare) for its route and cabin
    relative duration  log(duration) - median log(duration) for its route and cabin

Isolation Forest then isolates fares that do not fit their route. Flagged rows are WARNINGS in
the import report, never rejections: a fare can be unusual and still correct, so an operator
decides. The model is fitted per import, so it adapts to whatever dataset arrives.
models/price_anomaly/ measures it against deliberately injected price errors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.modules.ingestion.rejects import RejectLog

MIN_FARES = 50  # below this there is not enough data to learn what is normal
# Only deviations of at least e^1.0 = 2.7x the route median are reported. On the demo data,
# genuine peak fares reach 0.81 (2.2x) and injected price errors start at 1.9 (6.7x); see
# models/price_anomaly/ for the evaluation.
MIN_RELATIVE_JUMP = 1.0
SEED = 7


def score_fares(flights: pd.DataFrame) -> pd.Series:
    """True for fares that look wrong for their route. Index matches `flights`."""
    flagged = pd.Series(False, index=flights.index)
    priced = flights[flights["fare_minor"].notna() & (flights["fare_minor"] > 0)].copy()
    if len(priced) < MIN_FARES:
        return flagged
    priced["route"] = (
        priced["origin_airport_id"].astype(str)
        + ">"
        + priced["destination_airport_id"].astype(str)
        + ":"
        + priced["cabin_class"].astype(str)
        + ":"
        + priced["currency"].astype(str)
    )
    log_fare = pd.Series(np.log(priced["fare_minor"].astype(float)), index=priced.index)
    log_duration = pd.Series(
        np.log(priced["duration_minutes"].astype(float).clip(lower=1)), index=priced.index
    )
    relative_fare = log_fare - log_fare.groupby(priced["route"]).transform("median")
    relative_duration = log_duration - log_duration.groupby(priced["route"]).transform("median")
    features = np.column_stack([relative_fare, relative_duration])
    model = IsolationForest(n_estimators=200, contamination="auto", random_state=SEED)
    outlier = model.fit_predict(features) == -1
    # Isolation Forest also isolates harmless small deviations; report only material ones.
    material = np.abs(relative_fare.to_numpy()) >= MIN_RELATIVE_JUMP
    flagged.loc[priced.index] = outlier & material
    return flagged


def flag_fare_anomalies(flights: pd.DataFrame, log: RejectLog) -> int:
    """Record suspicious fares in the import report. Returns how many were flagged."""
    if flights.empty or "fare_minor" not in flights:
        return 0
    flagged = flights[score_fares(flights)]
    for _, row in flagged.head(10).iterrows():
        log.adjust(
            "PRICE_ANOMALY",
            example=(
                f"{row['flight_number']} {row['origin_ref'].code}-"
                f"{row['destination_ref'].code} {row['departure_local']:%d %b} "
                f"{row['cabin_class']}: {row['fare_minor'] / 100:,.0f} {row['currency']}"
            ),
        )
    log.adjust("PRICE_ANOMALY", max(len(flagged) - 10, 0))
    return len(flagged)
