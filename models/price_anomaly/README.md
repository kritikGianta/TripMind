# Fare anomaly detector

Isolation Forest (scikit-learn) over route-relative fare and duration, fitted on every import
(`backend/app/modules/ingestion/anomalies.py`). Suspicious fares appear as `PRICE_ANOMALY`
warnings with examples in the import report; nothing is rejected.

`price_anomaly.ipynb` measures it against fares the demo generator deliberately inflates 8x, using a
clean run of the same seed as ground truth. Latest results are in `artifacts/model_card.json`.
