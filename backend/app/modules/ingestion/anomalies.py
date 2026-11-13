"""Suspicious-price detection at import (a plain rule, no model).

A fare is flagged when it is at least 2.7 times above or below the median fare of its route
(same airports, cabin and currency). Flags are warnings in the import report, never rejections:
a fare can be unusual and still correct, so an operator decides.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.modules.ingestion.rejects import RejectLog

MIN_FARES = 50  # below this there is not enough data to learn what is normal
# Only deviations of at least e^1.0 = 2.7x the route median are reported. On the demo data,
# genuine fares (last-minute peaks included) reach 2.6x, while injected price errors are 8x.
MIN_RELATIVE_JUMP = 1.0


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
    relative_fare = log_fare - log_fare.groupby(priced["route"]).transform("median")
    material = np.abs(relative_fare.to_numpy()) >= MIN_RELATIVE_JUMP
    flagged.loc[priced.index] = material
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
