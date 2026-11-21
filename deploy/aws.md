# Deploy to AWS (ECR + ECS Express Mode)

ECS Express Mode takes one container image and creates everything else for you: a Fargate
service, an HTTPS load balancer, auto scaling and logs. (AWS App Runner, the older option,
stopped accepting new customers on 30 April 2026; AWS recommends Express Mode instead.)

> **Cost warning.** Express Mode itself is free, but the load balancer and Fargate are not.
> The load balancer is billed every hour it exists, even with no traffic. Deploy, test,
> take a screenshot for your README, then **delete it the same day** (step 6).
> Set a billing alarm first: AWS console → Billing → Budgets → create a $5 budget.

## 0. One-time setup

```bash
brew install awscli
aws configure          # paste an access key for an IAM user (not the root account), region eu-central-1
aws sts get-caller-identity   # check it works

export REGION=eu-central-1
export ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export REPO=forecast-service
```

## 1. Create an image registry (ECR)

```bash
aws ecr create-repository --repository-name $REPO --region $REGION
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com
```

## 2. Build and push the image

Your Mac (Apple Silicon) builds ARM64 images. We tell AWS to run ARM64 in step 4, so no
cross-compiling is needed.

```bash
docker build --platform linux/arm64 -t $REPO .
docker tag $REPO:latest $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest
```

## 3. Create the two IAM roles (once per account)

- **Task execution role**: lets ECS pull your image and write logs.
- **Infrastructure role**: lets ECS create the load balancer, security groups and scaling for you.

```bash
aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document '{
  "Version": "2012-10-17",
  "Statement": [{"Effect": "Allow", "Principal": {"Service": "ecs-tasks.amazonaws.com"}, "Action": "sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

aws iam create-role --role-name ecsInfrastructureRoleForExpressServices --assume-role-policy-document '{
  "Version": "2012-10-17",
  "Statement": [{"Effect": "Allow", "Principal": {"Service": "ecs.amazonaws.com"}, "Action": "sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name ecsInfrastructureRoleForExpressServices \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices
```

If the next step fails with "Unable to assume the service linked role", wait a minute and retry
(new IAM roles take a moment to become active).

## 4. Create the service

```bash
aws ecs create-express-gateway-service \
  --region $REGION \
  --service-name forecast-service \
  --execution-role-arn arn:aws:iam::$ACCOUNT:role/ecsTaskExecutionRole \
  --infrastructure-role-arn arn:aws:iam::$ACCOUNT:role/ecsInfrastructureRoleForExpressServices \
  --primary-container "{\"image\":\"$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest\",\"containerPort\":8080}" \
  --cpu-architecture ARM64 \
  --health-check-path /ready \
  --monitor-resources
```

The output includes the service ARN. Save it:

```bash
export SERVICE_ARN=<paste the serviceArn>
aws ecs describe-express-gateway-service --service-arn $SERVICE_ARN --region $REGION
```

## 5. Try it

The URL looks like `https://forecast-service-xxxx.ecs.eu-central-1.on.aws/`:

```bash
curl https://<your-url>/forecast?horizon=7
```

Logs: AWS console → CloudWatch → Log groups.

## 6. Clean up (do this!)

```bash
aws ecs delete-express-gateway-service --service-arn $SERVICE_ARN --region $REGION
aws ecr delete-repository --repository-name $REPO --force --region $REGION
```

Then check the console under EC2 → Load Balancers and EC2 → Target Groups that nothing is
left. (AWS does not delete target groups automatically.)

## What to say in an interview

- **Why Fargate**: no servers to patch; you pay per task-second.
- **Why two roles**: least privilege. The execution role is for ECS itself; the infrastructure
  role is for creating networking. Your app code would get a third, *task* role.
- **The bigger option**: EKS (managed Kubernetes) runs the same `k8s/` manifests from this repo.
  It costs more (about $0.10/hour for the control plane), so use it when you already run many services.
