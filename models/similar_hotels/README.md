# Similar stays

TF-IDF over each hotel's amenities, star class, rating band and price band within its city, compared
by cosine similarity (`backend/app/modules/ml/similar.py`). Computed on demand from the live
catalog, so it works on any imported dataset with no training step.

`similar_hotels.ipynb` checks that suggestions share star class and price band and share more
amenities than random pairs. Latest results are in `artifacts/model_card.json`. With click data, the
next step is to learn the weights instead of fixing them.
