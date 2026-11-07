# Fare estimator

Regression (LightGBM) of log fare from distance, duration, stops, days before departure,
departure hour and cabin, trained on about 300,000 Indian domestic fares.

- **Run:** `fare_estimator.ipynb` on Kaggle with
  [Flight Price Prediction](https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction).
- **Ships only if** its error (MAPE) beats the median fare for the same cabin and distance band.
- **Used for:** a "below typical / typical / above typical" note on flight results, with the typical
  fare shown. Prices themselves are never changed.
- **Limits:** domestic INR fares up to 2,000 km only (the training range); airline identity is
  deliberately not a feature; the data is from one season, so it is context, not a forecast.
