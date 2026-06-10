# HOW TO EXECUTE PHASE 3-5 — Step by Step

**Status:** Everything is ready. Follow these steps in order.

---

## 📋 PHASE 3 FIRST: Feature Engineering (20-30 minutes)

### STEP 1: Build Training Dataset with 8 Feature Groups (15 minutes)

**What:** Engineer 50+ features from Silver tables → create gold_training_dataset

**How:**

**Via Command Line (RECOMMENDED):**
```bash
cd /home/longha/Desktop/leue

spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 \
  processing/gold/build_training_dataset.py \
  s3a://lakehouse

# Expected output (takes ~15 minutes):
# ✅ Engineered temporal features
# ✅ Engineered traffic features
# ✅ Engineered weather features
# ✅ Engineered spatial features
# ✅ Engineered stats baseline features
# ✅ Engineered lag features
# ✅ Engineered event features
# ✅ Engineered graph features
# ✅ Created target labels
# ✅ gold_training_dataset written successfully!
```

**✅ When done, you should have:**
- `gold_traffic_features`: ~500K records with 50 features
- `gold_training_dataset`: ~500K records with targets (future_speed_15/60/240m)

**Verification:**
```bash
# Count records in gold tables
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) FROM iceberg.lakehouse.gold_training_dataset"

# Should show ~500000
```

---

### STEP 2: Train LightGBM Models (10-15 minutes)

**What:** Train 3 separate LightGBM models (15m, 60m, 240m horizons)

**How:**

**Via Command Line:**
```bash
cd /home/longha/Desktop/leue

python ml/training/train_lightgbm.py s3a://lakehouse

# Expected output (takes ~10-15 minutes):
# 🏃 Training 3 LightGBM models...
#
#   Training model for 15m horizon...
#     MAE train: 4.8 km/h
#     MAE test: 5.2 km/h
#     RMSE test: 7.1 km/h
#     R² test: 0.8834
#     Top features: [currentSpeed, congestion_ratio, hour_of_day, ...]
#
#   Training model for 60m horizon...
#     MAE test: 7.8 km/h
#     ...
#
#   Training model for 240m horizon...
#     MAE test: 12.4 km/h
#     ...
#
# ✅ LightGBM Training Complete!
# ✅ 3 models registered in MLflow Registry (status: Staging)
# ✅ gold_prediction_results written!
```

**✅ When done, you should have:**
- 3 LightGBM models trained and registered in MLflow Registry
- Predictions in `gold_prediction_results` table (~100K initial predictions)
- Baseline accuracy: MAE < 6 km/h for 15m horizon

**Verification:**
```bash
# Check MLflow models
# Open MLflow UI: http://localhost:5000
# Should see 3 experiments with traffic_forecast_15m, 60m, 240m

# Check predictions table
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*), AVG(predicted_speed_15m) FROM iceberg.lakehouse.gold_prediction_results"
```

---

## ⏸️ PAUSE: Verify Phase 3 Worked

**Check 1: Gold Tables in MinIO**
```
1. Open http://localhost:9001
2. Login: minioadmin / minioadmin
3. Browse: lakehouse/
4. Should see folders:
   - gold/ (NEW!)
   - Should contain: traffic_features/, training_dataset/, prediction_results/
```

**Check 2: Feature Completeness**
```bash
# Check number of features in gold_traffic_features
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) as feature_count FROM iceberg.lakehouse.gold_traffic_features LIMIT 1"

# Should have ~50 columns (temporal + traffic + weather + spatial + stats + lag + event + graph)
```

✅ **If you see data in gold/ folders → Phase 3 is DONE!**

---

## 🤖 PHASE 4: AI Analytics (15-20 minutes)

### STEP 3: Detect Congestion Hotspots with DBSCAN (5 minutes)

**What:** Run DBSCAN clustering to find congestion hotspots

**How:**

**Terminal 1: Hanoi Hotspots**
```bash
cd /home/longha/Desktop/leue

python ml/clustering/dbscan_hotspot.py hanoi s3a://lakehouse

# Expected output:
# 📖 Loading current traffic for hanoi...
# ✓ Loaded 2500 recent records
# 🔎 Detecting hotspots with DBSCAN...
# ✓ Detected 5 hotspot clusters
#   High severity: 2
#   Medium severity: 2
#   Low severity: 1
# ✅ gold_congestion_hotspots written!
```

**Terminal 2: HCMC Hotspots**
```bash
cd /home/longha/Desktop/leue

python ml/clustering/dbscan_hotspot.py hcmc s3a://lakehouse

# Same output for HCMC
```

---

### STEP 4: Generate Alerts Based on Rules (5 minutes)

**What:** Evaluate alert rules on predictions → generate traffic warnings

**How:**

```bash
cd /home/longha/Desktop/leue

python alerts/alert_engine.py s3a://lakehouse

# Expected output:
# 📖 Loading recent predictions...
# ✓ Loaded 50000 recent predictions
# ⚖️ Evaluating alert rules...
# ✓ Generated 125 alerts
#   CRITICAL: 8
#   HIGH: 25
#   MEDIUM: 52
#   LOW: 40
# ✅ Alerts written to gold_alerts!
```

---

### STEP 5: Compute SHAP Explanations (5-10 minutes)

**What:** Calculate SHAP values to explain predictions

**How:**

```bash
cd /home/longha/Desktop/leue

# For 15m horizon
python ml/explainability/shap_explainer.py 15 s3a://lakehouse

# For 60m horizon
python ml/explainability/shap_explainer.py 60 s3a://lakehouse

# For 240m horizon
python ml/explainability/shap_explainer.py 240 s3a://lakehouse

# Expected output:
# 📊 Computing SHAP values...
# ✓ SHAP value computation complete
# ✅ SHAP explanations written!
```

---

## 🚀 PHASE 5: Serving Layer (Immediate)

### STEP 6: Start FastAPI Backend (1 minute)

**What:** Run REST API server to serve predictions and alerts

**How:**

```bash
cd /home/longha/Desktop/leue

# Install dependencies (if not already installed)
pip install fastapi uvicorn pydantic pydantic-settings

# Start FastAPI server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Expected output:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

---

## 📊 STEP 7: Verify API is Working

**Open API Documentation:**
```
http://localhost:8000/docs
```

You should see all 14+ endpoints with descriptions:

✅ **Traffic Endpoints:**
- GET /traffic/current/{city} — Real-time status
- GET /traffic/predict/{segment_id} — Speed forecast
- GET /traffic/segments — List segments

✅ **Alert Endpoints:**
- GET /alerts/active — Active alerts
- GET /alerts/{id} — Alert details
- PATCH /alerts/{id}/ack — Acknowledge alert
- PATCH /alerts/bulk-ack — Bulk acknowledge

✅ **Analysis Endpoints:**
- GET /predictions/{id}/explain — SHAP explanation
- GET /hotspots — Congestion clusters
- GET /segments/geojson — Map data
- GET /monitoring/pipeline — Health status
- GET /monitoring/model — Model metrics
- GET /settings — App settings
- GET /routing/alternatives — Route suggestions

---

## 🔍 STEP 8: Test API Endpoints (5 minutes)

**Test Traffic Endpoint:**
```bash
curl http://localhost:8000/traffic/current/hanoi
```

Expected response:
```json
{
  "city": "hanoi",
  "total_segments": 450,
  "avg_speed": 35.5,
  "congestion_ratio": 0.42,
  "max_jam_factor": 7.8,
  "critical_segment_count": 12,
  "timestamp": "2026-06-01T10:30:00"
}
```

**Test Prediction Endpoint:**
```bash
curl "http://localhost:8000/traffic/predict/seg_001?horizon=15"
```

**Test Alert Endpoint:**
```bash
curl "http://localhost:8000/alerts/active?city=hanoi"
```

---

## 📈 STEP 9: Monitor Data (Automatic)

**Airflow will automatically run (when configured):**

```
Every Hour:
  ├─ dag_gold_features: Engineer new features
  └─ dag_batch_predict: Run predictions

Every 15 Minutes:
  └─ dag_dbscan_hotspot: Detect hotspots

Every 5 Minutes:
  └─ dag_alert_engine: Generate alerts
```

For now, manually run these jobs as shown above.

---

## 🔍 Check Status While Running

### Check 1: Gold Tables Size

```bash
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) as feature_records FROM iceberg.lakehouse.gold_traffic_features"
```

### Check 2: Predictions Count

```bash
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) as predictions FROM iceberg.lakehouse.gold_prediction_results WHERE predicted_speed_15m IS NOT NULL"
```

### Check 3: Active Alerts

```bash
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) as alert_count FROM iceberg.lakehouse.gold_alerts WHERE acknowledged = false"
```

### Check 4: API Logs

```bash
# See requests in FastAPI terminal
# Look for: GET /traffic/current/hanoi — 200 OK
```

### Check 5: MLflow UI

```
Open: http://localhost:5000
Look for experiments: traffic_forecast_15m, traffic_forecast_60m, traffic_forecast_240m
```

---

## 📈 Expected Timeline

```
Time      What Happens                      Your Action
────────────────────────────────────────────────────────
0:00      Phase 3: Feature Engineering      STEP 1 (15 min)
0:15      Phase 3: LightGBM Training        STEP 2 (15 min)
0:30      ✅ Gold tables ready!
          Phase 4: DBSCAN Hotspots         STEP 3 (5 min)
0:35      Phase 4: Alert Engine             STEP 4 (5 min)
0:40      Phase 4: SHAP Explanations        STEP 5 (10 min)
0:50      ✅ Analytics complete!
          Phase 5: FastAPI Server           STEP 6 (1 min)
0:51      ✅ API Running!                   Test endpoints (STEP 8)
1:00+     Data auto-updates                 Monitor (STEP 9)
```

---

## 💾 Data Volume Growth

```
After Phase 3 (30 minutes):
├── gold_traffic_features: ~500K records (50 features each)
├── gold_training_dataset: ~500K records (with targets)
├── gold_prediction_results: ~100K records (initial batch)

After Phase 4 (20 minutes):
├── gold_congestion_hotspots: ~10-20 clusters
├── gold_alerts: ~100-200 alerts
└── gold_prediction_results: +SHAP explanations

After 1 hour (with Airflow):
├── gold_traffic_features: +50K new records/hour
├── gold_prediction_results: +50K predictions/hour
├── gold_alerts: Growing continuously
└── Model metrics recorded in MLflow
```

---

## ✅ Success Checklist

### After Phase 3 (Feature Engineering)
- [ ] gold_traffic_features has data (500K+)
- [ ] gold_training_dataset has data with targets
- [ ] LightGBM models show MAE < 6 km/h (15m)

### After Phase 4 (AI Analytics)
- [ ] gold_congestion_hotspots has clusters
- [ ] gold_alerts has entries
- [ ] SHAP explanations computed
- [ ] MLflow shows 3 models trained

### After Phase 5 (Serving Layer)
- [ ] FastAPI running at http://localhost:8000
- [ ] API docs accessible at http://localhost:8000/docs
- [ ] All 14+ endpoints working
- [ ] Endpoints return real data from gold tables

✅ **When all checks pass → You have a working Phase 3-5!**

---

## 🚨 Troubleshooting

### Problem: "gold_training_dataset" is empty

**Solution:**
- Phase 2 (Silver layer) wasn't completed
- See HOW_TO_EXECUTE_PHASE1_PHASE2.md
- Run Phase 2 first, wait 30 minutes for silver tables

### Problem: LightGBM training fails

**Solution:**
```bash
# Check if training data exists
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) FROM iceberg.lakehouse.gold_training_dataset WHERE future_speed_15m IS NOT NULL"

# If < 1000, wait for more data or sample a smaller dataset
```

### Problem: FastAPI fails to start

**Solution:**
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill process if needed
kill -9 <PID>

# Or use different port
uvicorn api.main:app --port 8001
```

### Problem: API endpoints return 404

**Solution:**
- Ensure all routers are in `api/routers/`
- Check `api/main.py` includes all routers
- Restart FastAPI: Ctrl+C then run again

---

## 📚 Next Steps (Phase 6)

Once API is running and data is flowing:

```bash
# Phase 6: Frontend Connection
# See Phase 6 documentation to:
# 1. Connect Next.js frontend
# 2. Wire up dashboard pages
# 3. Enable real-time polling (SWR)
# 4. Test end-to-end user flows
```

---

## 🎯 Summary

**What you're doing:**
1. ✅ Engineer 50+ features (Phase 3) — 30 min
2. ✅ Train LightGBM models (Phase 3) — 15 min
3. ✅ Detect hotspots with DBSCAN (Phase 4) — 5 min
4. ✅ Generate alerts (Phase 4) — 5 min
5. ✅ Explain predictions with SHAP (Phase 4) — 10 min
6. ✅ Serve via FastAPI (Phase 5) — 1 min

**Result:**
- Complete ML pipeline: Features → Training → Prediction → Alerts → API
- 14+ endpoints serving real traffic data
- DBSCAN hotspot detection
- Model explainability
- Ready for dashboard connection (Phase 6)

**Time to ready:** ~65 minutes for Phases 3-5 (fully automated once started)

---

## 🚀 GO! You're Ready

Everything is implemented. Just follow the steps above in order.

**Good luck! 🎉**
