| Column | Type | Role | Description |
|---|---|---|---|
| `segment_id` | `object` | `id` | Unique road segment identifier. |
| `timestamp` | `datetime64[ns]` | `time` | 15-minute timestamp for one segment observation. |
| `city` | `object` | `categorical_feature` | City code, lowercase: hanoi or hcmc. |
| `district` | `object` | `categorical_feature` | District or urban context label. |
| `road_class` | `object` | `categorical_feature` | Road class / road type for the segment. |
| `corridor_id` | `object` | `categorical_feature` | Corridor group identifier. |
| `corridor_name` | `object` | `categorical_feature` | Human-readable corridor label. |
| `weather_main` | `object` | `categorical_feature` | Categorical weather state. |
| `current_speed` | `float64` | `numeric_feature` | Synthetic calibrated current speed at timestamp. |
| `free_flow_speed` | `float64` | `numeric_feature` | Segment free-flow reference speed. |
| `jam_factor` | `float64` | `numeric_feature` | Synthetic calibrated congestion intensity, roughly 0 to 10. |
| `congestion_ratio` | `float64` | `numeric_feature` | Congestion ratio derived from current speed vs free-flow speed. |
| `speed_confidence` | `float64` | `numeric_feature` | Synthetic confidence score; lower under rain/event/noisy conditions. |
| `speed_lag_1` | `float64` | `numeric_feature` | Previous 15-minute speed by segment. |
| `speed_lag_2` | `float64` | `numeric_feature` | Previous 30-minute speed by segment. |
| `speed_lag_3` | `float64` | `numeric_feature` | Previous 45-minute speed by segment. |
| `speed_lag_4` | `float64` | `numeric_feature` | Previous 60-minute speed by segment. |
| `jam_lag_1` | `float64` | `numeric_feature` | Previous 15-minute jam factor by segment. |
| `jam_lag_2` | `float64` | `numeric_feature` | Previous 30-minute jam factor by segment. |
| `jam_lag_3` | `float64` | `numeric_feature` | Previous 45-minute jam factor by segment. |
| `jam_lag_4` | `float64` | `numeric_feature` | Previous 60-minute jam factor by segment. |
| `speed_roll_mean_3` | `float64` | `numeric_feature` | Past 3-bucket speed rolling mean by segment using shifted observations. |
| `speed_roll_mean_6` | `float64` | `numeric_feature` | Past 6-bucket speed rolling mean by segment using shifted observations. |
| `speed_roll_std_6` | `float64` | `numeric_feature` | Past 6-bucket speed rolling standard deviation by segment using shifted observations. |
| `jam_roll_mean_3` | `float64` | `numeric_feature` | Past 3-bucket jam rolling mean by segment using shifted observations. |
| `hour_of_day` | `float64` | `numeric_feature` | Hour extracted from timestamp. |
| `day_of_week` | `float64` | `numeric_feature` | Day of week where Monday=0. |
| `month` | `float64` | `numeric_feature` | Month extracted from timestamp. |
| `is_weekend` | `int64` | `numeric_feature` | Weekend flag. |
| `is_peak_hour` | `int64` | `numeric_feature` | Vietnam urban peak-hour flag. |
| `is_holiday_vn` | `int64` | `numeric_feature` | Vietnam holiday flag. No public holiday in default generated window. |
| `temperature` | `float64` | `numeric_feature` | Synthetic Vietnam May/June temperature pattern. |
| `humidity` | `float64` | `numeric_feature` | Synthetic humidity pattern. |
| `rain_1h` | `float64` | `numeric_feature` | Synthetic rainfall in last hour. |
| `visibility` | `float64` | `numeric_feature` | Synthetic visibility proxy. |
| `wind_speed` | `float64` | `numeric_feature` | Synthetic wind speed. |
| `rain_flag` | `int64` | `numeric_feature` | Rain flag from rain_1h. |
| `p15_speed` | `float64` | `numeric_feature` | Historical 15th percentile speed baseline estimated from generated 30-day panel. |
| `p50_speed` | `float64` | `numeric_feature` | Historical median speed baseline estimated from generated 30-day panel. |
| `p85_speed` | `float64` | `numeric_feature` | Historical 85th percentile speed baseline estimated from generated 30-day panel. |
| `baseline_congestion_ratio` | `float64` | `numeric_feature` | Historical baseline congestion ratio for segment/time slot. |
| `speed_vs_p50` | `float64` | `numeric_feature` | Current speed minus p50 speed baseline. |
| `pct_below_p15` | `int64` | `numeric_feature` | Flag: current speed is below p15 baseline. |
| `pct_above_p85` | `int64` | `numeric_feature` | Flag: current speed is above p85 baseline. |
| `has_accident` | `int64` | `numeric_feature` | Synthetic accident event flag. |
| `has_flood` | `int64` | `numeric_feature` | Synthetic flood/rain disruption flag. |
| `has_roadwork` | `int64` | `numeric_feature` | Synthetic roadwork flag. |
| `has_event` | `int64` | `numeric_feature` | Any synthetic event flag. |
| `event_severity_score` | `float64` | `numeric_feature` | Event severity score from accident/flood/roadwork and peak/rain context. |
| `event_distance_km` | `float64` | `numeric_feature` | Distance to synthetic event center; lower means closer disruption. |
| `poi_density` | `float64` | `numeric_feature` | POI density proxy copied/calibrated from source segment metadata. |
| `school_density` | `float64` | `numeric_feature` | School density proxy copied/calibrated from source segment metadata. |
| `hospital_density` | `float64` | `numeric_feature` | Hospital density proxy copied/calibrated from source segment metadata. |
| `bus_stop_density` | `float64` | `numeric_feature` | Bus stop density proxy copied/calibrated from source segment metadata. |
| `urban_density_score` | `float64` | `numeric_feature` | Urban density pressure proxy copied/calibrated from source segment metadata. |
| `degree_centrality` | `float64` | `numeric_feature` | Graph degree centrality proxy. |
| `betweenness_centrality` | `float64` | `numeric_feature` | Graph betweenness centrality proxy. |
| `upstream_avg_jam_factor` | `float64` | `numeric_feature` | Synthetic upstream congestion proxy derived from city/time average. |
| `downstream_avg_jam_factor` | `float64` | `numeric_feature` | Synthetic downstream congestion proxy derived from city/time average. |
| `neighbor_congestion_count` | `int64` | `numeric_feature` | Synthetic count of congested neighboring segments in same city/time bucket. |
| `propagation_risk_score` | `float64` | `numeric_feature` | Synthetic congestion propagation risk from jam/event/urban/graph features. |
| `future_speed_15m` | `float64` | `target` | Target: speed 15 minutes after timestamp by segment. |
| `future_speed_60m` | `float64` | `target` | Target: speed 60 minutes after timestamp by segment. |
| `future_speed_240m` | `float64` | `target` | Target: speed 240 minutes after timestamp by segment. |
| `is_synthetic` | `int64` | `excluded` | Excluded marker: 1 for generated synthetic row. |
| `data_source` | `object` | `excluded` | Excluded marker describing source category. |
| `synthetic_generation_method` | `object` | `excluded` | Excluded marker describing generation method. |
