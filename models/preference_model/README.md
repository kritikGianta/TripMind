# preference_model

Learns which stays a signed-in traveller tends to choose and blends that into the "Recommended"
order (`personalized`, `ranked_by: ...+preferences`, `personal_reasons` on each stay).

- **Model:** one logistic regression per traveller over readable features (stars, rating, value
  for the city, distance from the centre, 12 amenities), centred on each city's average.
- **Signal:** stays the traveller opened (1), saved (3) and booked (5); negatives sampled across
  the catalog (their cities plus 20 others) with a seed from the user ID.
- **Training:** in production by the worker (`train_preferences`, hourly by default) once a
  traveller has touched 3 different stays. No artifact to hand back.
- **Control:** `GET /me/preferences` shows what was learned; `DELETE /me/preferences` forgets the
  activity and the model.
- **Evaluation:** `preference_model.ipynb` on simulated travellers (no real activity exists yet).
  Among stays the traveller had not opened, the booked stay's mean reciprocal rank goes from
  0.38 (rules) to 0.41 at the served blend of 0.3, and 0.66 with the preference alone. Simulated
  travellers care only about their hidden taste, so this flatters personalisation; the blend is
  kept conservative and is configurable (`preferences.blend` in `config/rules.yaml`).
