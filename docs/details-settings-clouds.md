That is the professional workflow.

## Development / Local Testing

Your laptop  
-> Docker Desktop  
-> docker build / docker run  
-> aws configure  
-> boto3 uses local AWS credentials  
-> test Bedrock, S3, RDS, etc.

Then when everything works:

## Production Deployment

Git push  
-> GitHub Actions  
-> build Docker image  
-> push image to Amazon ECR  
-> update Amazon ECS Fargate service  
-> ECS runs your container  
-> IAM Task Role gives permissions to Bedrock, S3, RDS, OpenSearch, etc.
------------------------

## Way 1 — Recommended: Local test -> GitHub -> GitHub Actions -> ECR -> ECS

This is the professional CI/CD way.

1. Build your FastAPI app locally
2. Create Dockerfile
3. Test Docker locally
4. Push code to GitHub
5. GitHub Actions builds Docker image
6. GitHub Actions pushes image to Amazon ECR
7. GitHub Actions updates Amazon ECS
8. ECS runs your FastAPI container

### Step-by-step

#### Step 1: Test your app locally

```bash
uvicorn app.backend.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/health
```

Make sure it works.

#### Step 2: Create Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Step 3: Build Docker image locally

```bash
docker build -t healthcare-rag .
```

Run it:

```bash
docker run -p 8000:8000 healthcare-rag
```

Test again:

```text
http://localhost:8000/health
```

#### Step 4: Push code to GitHub

```bash
git add .
git commit -m "Add FastAPI Docker deployment"
git push origin main
```

#### Step 5: Create ECR repository

In AWS:

Amazon ECR
-> Create repository
-> healthcare-rag

You will get an image URI like:

```text
381492099851.dkr.ecr.us-east-1.amazonaws.com/healthcare-rag
```

#### Step 6: Create ECS cluster and service

In AWS:

Amazon ECS
-> Create cluster
-> Fargate

Then create:

- Task Definition
- Service
- Load Balancer

The ECS task uses the Docker image from ECR.

#### Step 7: Add GitHub Actions

Create:

```text
.github/workflows/deploy.yml
```

This workflow will:

- build Docker image
- login to ECR
- push image to ECR
- update ECS service

This is best for real projects because every GitHub push can update your AWS deployment automatically.

## Way 2 — Manual Deployment: Local Docker -> ECR -> ECS

This is simpler for learning.

1. Build Docker image locally
2. Push image manually to ECR
3. Create ECS Task Definition manually
4. Create ECS Service manually
5. ECS runs your app

### Step-by-step

#### Step 1: Build locally

```bash
docker build -t healthcare-rag .
```

#### Step 2: Login to ECR

AWS gives you a command like:

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 381492099851.dkr.ecr.us-east-1.amazonaws.com
```

#### Step 3: Tag your image

```bash
docker tag healthcare-rag:latest 381492099851.dkr.ecr.us-east-1.amazonaws.com/healthcare-rag:latest
```

#### Step 4: Push to ECR

```bash
docker push 381492099851.dkr.ecr.us-east-1.amazonaws.com/healthcare-rag:latest
```

#### Step 5: Create ECS Task Definition

In ECS, add:

- Container name: healthcare-rag-api
- Image URI: 381492099851.dkr.ecr.us-east-1.amazonaws.com/healthcare-rag:latest
- Port: 8000

#### Step 6: Create ECS Service

Choose:

- Launch type: Fargate
- Task definition: healthcare-rag
- Desired tasks: 1
- Load balancer: yes

Then AWS runs your app.

------------------------

Attaching an IAM Role to an ECS Task is what allows your Docker container to securely access AWS services like Bedrock, S3, RDS, and OpenSearch without using access keys.

## Step 1. Create an IAM Role

Go to:

AWS Console
↓
IAM
↓
Roles
↓
Create Role

Choose:

Trusted Entity:
AWS Service

Use Case:
Elastic Container Service

↓

Elastic Container Service Task

Click Next.

## Step 2. Attach Permissions

Attach the AWS policies your application needs.

Example:

- AmazonBedrockFullAccess
- AmazonS3FullAccess
- AmazonRDSFullAccess
- CloudWatchLogsFullAccess

Or create a custom least-privilege policy for production.

Example:

Healthcare-RAG-TaskRole

## Step 3. Create an ECS Task Definition

Go to:

AWS Console
↓
Amazon ECS
↓
Task Definitions
↓
Create new Task Definition

Choose:

Launch Type:
Fargate

## Step 4. Configure the Task

You'll see a section similar to:

Task Definition

Task Name:
healthcare-rag

Task Role
▼

Task Execution Role
▼

These are two different roles.

### Task Role

Choose:

Healthcare-RAG-TaskRole

This role is used inside your application.

Your Python code:

```python
boto3.client("bedrock-runtime")
boto3.client("s3")
boto3.client("glue")
```

uses the permissions from this role.

### Task Execution Role

Usually choose:

ecsTaskExecutionRole

This is not used by your application.

AWS uses it to:

- Pull Docker images from Amazon ECR
- Send logs to CloudWatch
- Start the container
---------------

boto3 is the official AWS SDK (Software Development Kit) for Python. It allows Python applications to interact with AWS services programmatically.

Think of it as the Python library that lets your code talk to AWS instead of using the AWS Management Console.

For example, with boto3 you can:

- Upload files to Amazon S3
- Invoke models in Amazon Bedrock
- Launch or stop EC2 instances
- Read and write data in DynamoDB
- Send messages to SQS
- Read secrets from Secrets Manager
- Invoke AWS Lambda functions
- Monitor CloudWatch logs

## Why do we use boto3?

Without boto3, you would need to manually send HTTPS requests to AWS APIs and handle:

- Authentication
- Request signing
- JSON formatting
- Error handling
- Pagination

boto3 handles all of this for you.

For example:

```python
import boto3

s3 = boto3.client("s3")

response = s3.list_buckets()

print(response)
```

Instead of writing HTTP requests yourself.

## How boto3 works

A typical workflow is:

Python code
	|
	v
boto3
	|
	v
AWS API
	|
	v
AWS Service

For example:

Python
   |
boto3
   |
Bedrock Runtime API
   |
Claude 4 Sonnet

------------

Yes. The workflow is almost identical, but you replace AWS services with Azure services. The biggest difference is that Azure doesn't have a single SDK like boto3. Instead, Azure provides multiple SDKs under the Azure SDK for Python (azure-* packages).

## Development / Local Testing (Azure)

Your laptop
↓
Docker Desktop
↓
docker build / docker run
↓
Authenticate with Azure (az login or Service Principal credentials)
↓
Azure SDK for Python uses your local Azure credentials
↓
Test Azure OpenAI, Azure AI Search, Azure SQL, Blob Storage, Cosmos DB, etc.

## What replaces aws configure?

Instead of:

```bash
aws configure
```

you typically use:

```bash
az login
```

This opens your browser for authentication.

Or, for automation and CI/CD, you authenticate using a Service Principal:

- AZURE_CLIENT_ID
- AZURE_TENANT_ID
- AZURE_CLIENT_SECRET

## What replaces boto3?

There is no single equivalent.

Instead, Azure has separate SDKs for each service.

| AWS | Azure | Python SDK |
| --- | --- | --- |
| boto3 | Azure SDK | azure-* packages |

Examples:

| AWS Service | boto3 | Azure Equivalent | Python SDK |
| --- | --- | --- | --- |
| Bedrock | boto3.client("bedrock-runtime") | Azure OpenAI | openai (Azure endpoint) |
| S3 | boto3.client("s3") | Azure Blob Storage | azure-storage-blob |
| RDS | boto3.client("rds") | Azure SQL Database | pyodbc, sqlalchemy, pymssql |
| Secrets Manager | boto3.client("secretsmanager") | Azure Key Vault | azure-keyvault-secrets |
| CloudWatch | boto3.client("cloudwatch") | Azure Monitor / Application Insights | azure-monitor-opentelemetry |
| OpenSearch | OpenSearch client | Azure AI Search | azure-search-documents |
| IAM | IAM Roles | Managed Identity | azure-identity |

## Authentication Example

Instead of boto3 automatically finding AWS credentials:

```python
import boto3

client = boto3.client("bedrock-runtime")
```

Azure typically uses:

```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
```

Every Azure SDK can reuse this credential.

For example:

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()

client = SecretClient(
	vault_url="https://myvault.vault.azure.net/",
	credential=credential
)
```

## Azure OpenAI Example

Instead of:

```python
import boto3

bedrock = boto3.client("bedrock-runtime")
```

you might use:

```python
from openai import AzureOpenAI

client = AzureOpenAI(
	api_key=AZURE_OPENAI_KEY,
	api_version="2024-02-15-preview",
	azure_endpoint="https://YOUR-RESOURCE.openai.azure.com"
)
```

## Azure Blob Storage Example

Instead of

```python
boto3.client("s3")
```

you would use

```python
from azure.storage.blob import BlobServiceClient

client = BlobServiceClient(
	account_url="https://myaccount.blob.core.windows.net",
	credential=credential
)
```

## Production Deployment (Azure)

Git push
↓
GitHub Actions
↓
Build Docker image
↓
Push image to Azure Container Registry (ACR)
↓
Deploy/update Azure Container Apps (or Azure Kubernetes Service (AKS), or Azure App Service)
↓
Azure runs your container
↓
Managed Identity grants secure access to Azure OpenAI, Blob Storage, Azure SQL, Azure AI Search, Key Vault, etc.

## AWS vs Azure Architecture

| Development | AWS | Azure |
| --- | --- | --- |
| Local authentication | aws configure | az login |
| Credentials | Access Key + Secret | Azure CLI or Service Principal |
| SDK | boto3 | Azure SDK (azure-*) |
| AI service | Amazon Bedrock | Azure OpenAI |
| Object storage | Amazon S3 | Azure Blob Storage |
| Database | Amazon RDS | Azure SQL Database |
| Vector Search | Amazon OpenSearch | Azure AI Search |
| Secrets | AWS Secrets Manager | Azure Key Vault |
| Logging | CloudWatch | Azure Monitor |

## Production Deployment Comparison

| AWS | Azure |
| --- | --- |
| GitHub Actions | GitHub Actions |
| Amazon ECR | Azure Container Registry (ACR) |
| Amazon ECS Fargate | Azure Container Apps (or AKS/App Service) |
| IAM Task Role | Managed Identity |
| Bedrock | Azure OpenAI |
| S3 | Azure Blob Storage |
| RDS | Azure SQL Database |
| OpenSearch | Azure AI Search |
| CloudWatch | Azure Monitor |

## Professional Workflow (Azure)

### Development

Your Laptop
	↓
Docker Desktop
	↓
docker build
docker run
	↓
az login
(or Service Principal)
	↓
Azure SDK authenticates
(DefaultAzureCredential)
	↓
Test:
- Azure OpenAI
- Azure Blob Storage
- Azure SQL
- Azure AI Search
- Azure Key Vault

-------------------------------------------------------

### Production

Git Push
	↓
GitHub Actions
	↓
Build Docker Image
	↓
Push to Azure Container Registry (ACR)
	↓
Deploy Azure Container Apps
(or AKS/App Service)
	↓
Container Starts
	↓
Managed Identity
	↓
Access:
- Azure OpenAI
- Blob Storage
- Azure SQL
- Azure AI Search
- Key Vault
- Azure Monitor

