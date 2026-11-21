# forecast-service

Forecasts daily alarm counts for a (synthetic) telecom network and serves them over an HTTP
API. The interesting part is the life around the model: backtesting to pick a model,
drift checks, scheduled retraining, and running the same container locally, on Kubernetes,
on AWS and on Google Cloud.

```
data ─▶ train (backtest, pick best) ─▶ model.json ─▶ API (/forecast)
              ▲                                         │
              └──────── nightly CronJob ◀── drift check ┘
```

## Results

Rolling-origin backtest (6 folds × 14 days, synthetic data with noise of σ = 6):

| Model | Mean absolute error |
|---|---|
| Seasonal naive (same weekday last week) | 6.56 |
| Holt-Winters (level + trend + weekly season) | **5.11** |

Training picks the model with the lowest backtest error automatically.

## Design decisions

- **Always compare with a naive baseline.** A model that can't beat "same as last week" isn't worth deploying.
- **Backtest like production.** Train up to day T, forecast the next 14 days, slide T forward. A random train/test split leaks the future into training.
- **Drift = recent error vs backtest error.** If the error on recent actuals is more than 1.5x the backtest error, retrain (`forecast/drift.py`). A test simulates a level shift and checks that it's detected.
- **Swap models with no downtime.** Training writes to a temp file and renames it (atomic). The API reloads the file when it changes, so the nightly job never restarts the API.
- **Liveness vs readiness.** `/health` says the process is alive; `/ready` says a model is loaded. Kubernetes only routes traffic to ready pods.
- **Model in NumPy.** Holt-Winters is ~40 lines, so every step can be explained. In production I'd compare it with statsmodels or Prophet.

## Run it

### Python
```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
python -m forecast.train data/alarms.csv models/model.json
uvicorn forecast.api:app --reload --port 8080
open http://localhost:8080/docs          # interactive API docs
```

### Docker
```bash
docker build -t forecast-service:local .
docker run --rm -p 8080:8080 forecast-service:local
curl "localhost:8080/forecast?horizon=7"

docker compose up --build                # API + one-off training job sharing a volume
```

### Kubernetes (local, with kind)
```bash
brew install kind kubectl
kind create cluster --name demo
docker build -t forecast-service:local .
kind load docker-image forecast-service:local --name demo   # copy the image into the cluster
kubectl apply -f k8s/
kubectl get pods -w                                          # wait for 2/2 Running
kubectl port-forward svc/forecast-service 8080:80
curl "localhost:8080/forecast?horizon=7"

kubectl create job --from=cronjob/forecast-retrain retrain-now   # run the nightly job now
kubectl logs job/retrain-now
kind delete cluster --name demo                              # clean up
```
The autoscaler (`k8s/hpa.yaml`) needs metrics-server; on kind install it with
`kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml`
and add `--kubelet-insecure-tls` to its args.

### Cloud
- AWS (ECR + ECS Express Mode): [deploy/aws.md](deploy/aws.md)
- Google Cloud (Cloud Run): [deploy/gcp.md](deploy/gcp.md)

## API

| Endpoint | What it returns |
|---|---|
| `GET /health` | `{"status": "ok"}` while the process runs |
| `GET /ready` | 200 once a model is loaded, 503 before |
| `GET /model` | model name, backtest errors, training time |
| `GET /forecast?horizon=14` | one point per day, 1–90 days ahead |
