# Data Quality Report

## City Summary

| city | segment_count | total_records | median_correct_5m_interval_ratio | max_gap_minutes |
| --- | --- | --- | --- | --- |
| hanoi | 75 | 2570 | 0.0 | 1805.0 |
| hcmc | 72 | 622 | 0.7720588235294117 | 60.0 |

## Horizon Stats

| horizon_minutes | city | exact_target_rows_all_cities | training_rows_primary_city | has_training_file | note |
| --- | --- | --- | --- | --- | --- |
| 15 | hanoi | 2420 | 1690 | True | enough_rows |
| 60 | hanoi | 2305 | 910 | True | enough_rows |
| 240 | hanoi | 1345 | 560 | False | 240m intentionally not exported for baseline training |

## Worst Segments By Missing Bucket Ratio

| city | segment_id | min_time_bucket | max_time_bucket | record_count | expected_bucket_count | missing_bucket_count | missing_bucket_ratio | median_interval_minutes | max_time_gap_minutes | correct_5m_interval_ratio | is_train_candidate_15m | is_train_candidate_60m | is_train_candidate_240m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hanoi | HN_BD_004 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_BD_002 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_BD_001 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_HK_004 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_HK_003 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_HK_002 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_HK_001 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_DD_005 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_DD_004 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_DD_003 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_DD_002 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_DD_001 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_CG_005 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_BD_003 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_CG_004 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_CG_003 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_CG_002 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_CG_001 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_TX_002 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
| hanoi | HN_TX_001 | 2026-06-11 20:05:00 | 2026-06-12 08:15:00 | 2 | 147 | 145 | 0.9863945578231292 | 730.0 | 730.0 | 0.0 | False | False | False |
