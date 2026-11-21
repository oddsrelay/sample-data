# Changelog

## Unreleased

- Kaggle description and Hugging Face card: the repo copies now hold the texts live on both pages since 20 Nov
  (what the feed serves today beside this snapshot), and `snapshot.py` writes the same Kaggle description.
- README and dataset card: the sample is pre-match prices from the UK & Ireland; they now say the API itself also
  serves in-play prices, historical odds and 20 more regions, none of which is in this file. The data is unchanged.
- The first sample: one snapshot of the raw board and the standard matched board, bookmakers only, as CSV and JSON
  with a data dictionary, `datapackage.json`, a summary, loading examples and tests.
