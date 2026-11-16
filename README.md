# DailyUpdate
Daily pipeline that aggregates, scores, and publishes Veterans Affairs research publications from PubMed, OpenAlex and Crossref, with funding attribution and a static dashboard.

Dimensions is used only as a benchmark, not as a data source (`dimensions.ingest: false` in `config/settings.yaml`). To compare the tool against a Dimensions export (VA scope, capped at 500 rows):

```
python -m compare.report "Dimensions comparison\<export folder>" <label>
```

This writes `reports/dimensions-gaps-<label>.csv` and `reports/dimensions-comparison-<label>.md`.
