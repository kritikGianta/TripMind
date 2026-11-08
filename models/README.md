# TripMind models

Small models that improve TripMind without being required by it. Each model has its own folder
with a README, a notebook and an `artifacts/` folder.

| Model | What it does in the product | Trained where | Status |
|---|---|---|---|
| [hotel_ranker](hotel_ranker/) | Orders "Recommended" stays from real click and booking behaviour (LightGBM LambdaRank) | Kaggle (Expedia data) | Notebook ready; artifact awaited |
| [fare_estimator](fare_estimator/) | Labels a fare below typical, typical or above typical (LightGBM regression) | Kaggle (Indian domestic fares) | Notebook ready; artifact awaited |
| [price_anomaly](price_anomaly/) | Flags suspicious fares in the import report (Isolation Forest) | Fitted per import; evaluated locally | Live |
| [similar_hotels](similar_hotels/) | "Similar stays" on the hotel page (TF-IDF + cosine similarity) | Computed on demand; evaluated locally | Live |
| [review_sentiment](review_sentiment/) | Review sentiment and per-aspect highlights on a stay (TF-IDF + logistic regression, JSON) | Kaggle (TripAdvisor reviews) | Notebook ready; word-list rules until trained |
| [request_classifier](request_classifier/) | Routes support tickets by category (TF-IDF + logistic regression, JSON) | Local or Kaggle (Bitext travel intents) | Notebook ready; keyword rules until trained |

## Contract every model follows

1. **Artifact + model card.** `artifacts/model.txt` (LightGBM text format) or `artifacts/model.json`
   (text models: TF-IDF vocabulary and logistic-regression weights), never a pickle, so loading cannot run code, and `artifacts/model_card.json` (dataset, features, metrics, library
   versions, date).
2. **Same features at training and serving.** Feature names come from
   `backend/app/modules/ml/features.py`; the API refuses a model whose card lists different
   features (`app/modules/ml/registry.py`).
3. **Beats a baseline or does not ship.** Each notebook compares the model with TripMind's
   rule-based behaviour and stops with an error if the model is not better.
4. **Optional at runtime.** No artifact, a mismatched card or a disabled flag
   (`ml_hotel_ranker`, `ml_fare_insight` in `config/features.yaml`) means TripMind uses its rules.
   The API reports which was used (`ranked_by`, `fare_insight`).
5. **Honest about scope.** The fare estimator only scores routes inside the distance range of its
   training data; the price detector only warns, it never rejects a row.

## Running the Kaggle notebooks

Open the notebook on Kaggle, add the dataset named at its top, *Run all*, then download
`model.txt` and `model_card.json` from `/kaggle/working` into the model's `artifacts/` folder.
The API picks the files up on the next request (Docker mounts `./models` read-only).

To regenerate the notebooks after editing them as code: `python models/build_notebooks.py`.
