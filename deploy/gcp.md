# Deploy to Google Cloud (Cloud Run)

Cloud Run runs a container and gives it an HTTPS URL. It scales to zero when nobody uses it,
so for a demo it usually stays inside the free tier.

> New Google Cloud accounts get free trial credit. Still: set a budget alert first
> (console → Billing → Budgets & alerts → $5), and delete the service when you're done.

## 0. One-time setup

```bash
brew install --cask google-cloud-sdk
gcloud init                                   # log in, create/select a project
export PROJECT=$(gcloud config get-value project)
export REGION=europe-west4                    # Netherlands

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 1. Deploy straight from the source folder

```bash
gcloud run deploy forecast-service \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --memory 512Mi \
  --max-instances 2
```

What happens: Cloud Build builds the `Dockerfile` in Google's cloud (on x86, so your Mac's
ARM chip doesn't matter), stores the image in Artifact Registry, and starts it on Cloud Run.
Cloud Run sets the `PORT` variable; the Dockerfile already listens on it.

The command prints the URL:

```bash
curl https://forecast-service-xxxx.a.run.app/forecast?horizon=7
```

## 2. Optional: build locally and push yourself

This is the "registry" workflow you'd use in CI:

```bash
gcloud artifacts repositories create images --repository-format=docker --location=$REGION
gcloud auth configure-docker $REGION-docker.pkg.dev

# Cloud Run needs x86 (amd64) images, so cross-build on your Mac:
docker buildx build --platform linux/amd64 \
  -t $REGION-docker.pkg.dev/$PROJECT/images/forecast-service:v1 --push .

gcloud run deploy forecast-service --region $REGION --allow-unauthenticated \
  --image $REGION-docker.pkg.dev/$PROJECT/images/forecast-service:v1
```

## 3. Clean up

```bash
gcloud run services delete forecast-service --region $REGION
gcloud artifacts repositories delete images --location $REGION         # if you made it
gcloud artifacts repositories delete cloud-run-source-deploy --location $REGION  # made by --source
```

## What to say in an interview

- **Cloud Run vs GKE**: Cloud Run is serverless containers: scale to zero, pay per request.
  GKE is Kubernetes: more control (CronJobs, sidecars, volumes), more to run. This repo's
  `k8s/` folder works on GKE Autopilot unchanged except for the image name.
- **Retraining in the cloud**: on Cloud Run there is no shared disk, so you'd run training as a
  Cloud Run *job* on a Cloud Scheduler trigger and store `model.json` in a GCS bucket.
