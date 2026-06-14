# Model Card - cta-traffic-speed-forecasting

## Overview

- Project: `cognitive-traffic-analytics`
- Run ID: `v1_20260613T162016Z`
- Created at UTC: `2026-06-13T16:25:33.993499+00:00`
- Task: multi-horizon traffic speed forecasting
- Horizons: `['15m', '60m', '240m']`
- Grain: one row per `segment_id + timestamp`

## Dataset

- Input pack: `/kaggle/input/datasets/vv1ntek/vietnamese-kaggle-dataset`
- Training file: `/kaggle/input/datasets/vv1ntek/vietnamese-kaggle-dataset/data/gold_training_dataset.parquet`
- Rows: `57,600`
- Columns: `67`
- Time range: `2026-05-10 00:00:00` -> `2026-06-08 23:45:00`

## Selected Models

```json
{
  "15m": "lightgbm",
  "60m": "lightgbm",
  "240m": "lightgbm"
}
```

## Test Metrics

| horizon   | model                  | model_type   | split   |     MAE |    RMSE |       R2 |    MAPE |    n |   train_seconds |
|:----------|:-----------------------|:-------------|:--------|--------:|--------:|---------:|--------:|-----:|----------------:|
| 15m       | catboost               | ml           | test    | 1.20694 | 1.61991 | 0.953609 | 4.00801 | 8640 |       11.1035   |
| 15m       | hist_gradient_boosting | ml           | test    | 1.21514 | 1.63014 | 0.953022 | 4.04147 | 8640 |        4.11944  |
| 15m       | xgboost                | ml           | test    | 1.21698 | 1.63339 | 0.952834 | 4.03748 | 8640 |        9.12945  |
| 15m       | lightgbm               | ml           | test    | 1.22409 | 1.64087 | 0.952401 | 4.06355 | 8640 |       10.4672   |
| 15m       | extra_trees            | ml           | test    | 1.24446 | 1.66883 | 0.950765 | 4.13983 | 8640 |       37.1706   |
| 15m       | ridge                  | ml           | test    | 1.27591 | 1.70811 | 0.94842  | 4.253   | 8640 |        0.267187 |
| 240m      | catboost               | ml           | test    | 1.28572 | 1.73358 | 0.947389 | 4.26727 | 8640 |       11.0143   |
| 240m      | hist_gradient_boosting | ml           | test    | 1.29497 | 1.74362 | 0.946778 | 4.30209 | 8640 |        3.55373  |
| 240m      | xgboost                | ml           | test    | 1.30125 | 1.74688 | 0.946578 | 4.30923 | 8640 |        8.68062  |
| 240m      | lightgbm               | ml           | test    | 1.30164 | 1.74774 | 0.946526 | 4.31595 | 8640 |        8.91901  |
| 240m      | extra_trees            | ml           | test    | 1.33615 | 1.79643 | 0.943505 | 4.43334 | 8640 |       36.5056   |
| 240m      | ridge                  | ml           | test    | 1.86733 | 2.44598 | 0.895264 | 6.33556 | 8640 |        0.238865 |
| 60m       | catboost               | ml           | test    | 1.26055 | 1.70538 | 0.948668 | 4.20336 | 8640 |       11.1452   |
| 60m       | xgboost                | ml           | test    | 1.27029 | 1.72073 | 0.94774  | 4.23138 | 8640 |        8.99395  |
| 60m       | lightgbm               | ml           | test    | 1.27174 | 1.72309 | 0.947596 | 4.23711 | 8640 |        8.24495  |
| 60m       | hist_gradient_boosting | ml           | test    | 1.27648 | 1.72385 | 0.94755  | 4.26255 | 8640 |        3.51661  |
| 60m       | extra_trees            | ml           | test    | 1.30674 | 1.76067 | 0.945286 | 4.36685 | 8640 |       36.083    |
| 60m       | ridge                  | ml           | test    | 1.56086 | 2.06976 | 0.924389 | 5.25796 | 8640 |        0.246302 |

## Features

- Numeric features: `54`
- Categorical features: `8`
- Leakage check: PASS

## Explainability

- Feature importance saved at `tables/feature_importance.csv`
- SHAP summary saved at `shap/shap_top_features.csv` if SHAP was available

## Intended Use

This model pack is intended for demo and research use in the Cognitive Traffic Analytics platform.
It can be loaded by FastAPI serving layer using `metadata/model_manifest.json`.

## Limitations

- Dataset is a 30-day training pack.
- If graph/event/weather features are default-filled, real-world performance may be lower.
- For production, validate on longer unseen periods and enable MLflow/S3 model governance.
