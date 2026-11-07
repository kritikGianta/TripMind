# Hotel ranker

Learning-to-rank (LightGBM LambdaRank) trained on Expedia's *Personalize Hotel Search* data, using
only randomly ordered result lists so it learns what travellers choose rather than position bias.

- **Run:** `hotel_ranker.ipynb` on Kaggle with the competition data
  [expedia-personalized-sort](https://www.kaggle.com/c/expedia-personalized-sort/data) (join the competition first).
- **Features:** star rating, review score, log price (USD), price and star rank within the search,
  stay length, adults, rooms, booking window. All are available from TripMind's own catalog.
- **Ships only if** NDCG@5 beats TripMind's rule-based score on held-out searches.
- **Used for:** the default "Recommended" sort on stays (`ranked_by: model:<version>`).
- **Limit:** Expedia's `price_usd` mixes per-night and per-stay prices in some markets; the notebook
  corrects obvious cases only.
