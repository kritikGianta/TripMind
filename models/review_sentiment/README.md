# review_sentiment

Scores hotel reviews positive, neutral or negative; TripMind uses it for the review summary and
per-aspect highlights on a stay (`GET /hotels/{id}/reviews`, `scored_by`).

- **Model:** TF-IDF (1-2 word n-grams) + logistic regression, exported as JSON (no pickle).
- **Data:** Trip Advisor Hotel Reviews (Kaggle `andrewmvd/trip-advisor-hotel-reviews`, about
  20,000 reviews). A Hugging Face mirror lists CC BY-NC 4.0; check the dataset page.
- **Labels:** 1-2 stars negative, 3 neutral, 4-5 positive.
- **Baseline:** the word-list rules in `backend/app/modules/ml/sentiment.py` (used until the model
  is present). The notebook refuses to export a model that does not beat them on macro F1.
- **Not trained on** the demo dataset's generated reviews.
- **Run:** Kaggle, then copy `model.json` + `model_card.json` into `artifacts/`.
