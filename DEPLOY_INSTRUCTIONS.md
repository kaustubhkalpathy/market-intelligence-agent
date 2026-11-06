# Deployment Instructions — Market Intelligence Agent

## Option 1: Local (Development)

```bash
cd Use_Case_2_Market_Intelligence_Agent
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Open: http://localhost:8501

---

## Option 2: Docker (Local Container)

```bash
# Build
docker build -t market-intelligence-agent .

# Run (pass AWS credentials)
docker run -p 8501:8501 \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_DEFAULT_REGION=us-east-1 \
  market-intelligence-agent
```

Open: http://localhost:8501

---

## Option 3: AWS ECS Fargate (Production)

### Prerequisites
- AWS CLI configured
- Docker installed
- ECR repository created

### Steps

```bash
# 1. Create ECR repository
aws ecr create-repository --repository-name market-intelligence-agent --region us-east-1

# 2. Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <YOUR_AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# 3. Build and tag
docker build -t market-intelligence-agent .
docker tag market-intelligence-agent:latest \
  <YOUR_AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/market-intelligence-agent:latest

# 4. Push to ECR
docker push <YOUR_AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/market-intelligence-agent:latest

# 5. Create ECS task definition (see task-definition.json below)
aws ecs register-task-definition --cli-input-json file://task-definition.json

# 6. Create/update ECS service
aws ecs create-service \
  --cluster default \
  --service-name market-intelligence-agent \
  --task-definition market-intelligence-agent \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### ECS Task Definition (task-definition.json)

```json
{
  "family": "market-intelligence-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:role/MarketIntelligenceAgentRole",
  "containerDefinitions": [
    {
      "name": "market-intelligence-agent",
      "image": "<YOUR_AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/market-intelligence-agent:latest",
      "portMappings": [
        {
          "containerPort": 8501,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "AWS_DEFAULT_REGION", "value": "us-east-1"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/market-intelligence-agent",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8501/_stcore/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3
      }
    }
  ]
}
```

### IAM Role: MarketIntelligenceAgentRole

Required permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:Converse"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/*"
    }
  ]
}
```

---

## Option 4: AWS AgentCore (Future — Production-Grade)

For full production deployment with managed infrastructure:

```bash
# Install AgentCore CLI
npm install -g @aws/agentcore

# Initialize agent project
agentcore init --name market-intelligence-agent --framework custom

# Deploy to AgentCore Runtime
agentcore deploy

# Add memory (replaces local JSON)
agentcore add memory --strategy USER_PREFERENCE
agentcore add memory --strategy SEMANTIC

# Add gateway (auth + rate limiting)
agentcore add gateway

# Add evaluators
agentcore add evaluator --type code-based --name schema-validator
```

See: https://github.com/awslabs/agentcore-samples/tree/main/02-use-cases/01-conversational-agents/market-trends-agent

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| AWS_ACCESS_KEY_ID | Yes (in container) | — | AWS credentials |
| AWS_SECRET_ACCESS_KEY | Yes (in container) | — | AWS credentials |
| AWS_DEFAULT_REGION | No | us-east-1 | Bedrock region |

---

## Cost Estimate

| Resource | Cost |
|----------|------|
| Bedrock Nova Lite | ~$0.001 per query |
| ECS Fargate (512 CPU, 1GB) | ~$0.03/hour ($22/month) |
| ECR Storage | ~$0.10/month |
| **Total (low usage)** | **~$5-10/month** |
| **Total (production)** | **~$25-50/month** |
