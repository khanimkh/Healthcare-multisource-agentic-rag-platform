# AWS Healthcare Multi-Source Agentic RAG Platform

## 1. Project Definition

### Problem Statement

Healthcare organizations often store important information across many disconnected sources, including PDF documents, Excel files, CSV datasets, SQL databases, BigQuery tables, and external APIs. Business users, researchers, or analysts may need to answer questions using all of these sources, but they often do not know where the answer is located, how to write SQL, or how to search long documents efficiently.

The goal of this project is to build an AI-powered assistant that allows users to upload or connect multiple data sources and then ask questions in natural language. The system should automatically decide whether the question should be answered using document retrieval, SQL analysis, BigQuery analysis, summarization, GraphRAG, or another tool.

### Customer Request

A healthcare organization wants an assistant that can help non-technical users analyze structured and unstructured data. The customer wants to upload healthcare reports, CSV files, Excel sheets, and connect to SQL or BigQuery data. After that, users should be able to ask questions such as:

```text
What are the main risk factors for patient readmission?

Show the average patient age by diagnosis.

Summarize this clinical policy document.

How are diabetes, obesity, and hypertension related?

Which patients have the highest risk score based on the uploaded dataset?
```

### Use Case

The main use case is a healthcare analytics assistant for clinical researchers, healthcare analysts, or managers. The assistant helps them search documents, summarize reports, analyze tables, and retrieve source-grounded answers without manually writing SQL or reading long files.

---

## 2. Business, Data, Security, AI, Evaluation, Production, and Maintenance Questions

### Business Questions

**Who will use this system?**
The assumed users are healthcare analysts, clinical researchers, managers, and non-technical business users who need answers from healthcare documents and datasets.

**What business problem does the system solve?**
The system reduces manual work required to search documents, analyze spreadsheets, write SQL queries, and combine results from different sources.

**What is the business value?**
The main value is faster decision-making, improved access to information, reduced dependency on technical teams, and better use of existing healthcare data.

**What happens if the system gives an incorrect answer?**
Incorrect answers could lead to wrong interpretation of healthcare data. Therefore, the system must provide source references, confidence indicators, limitations, and should not provide direct medical advice.

### Data Questions

**What types of data are available?**
The system supports structured data such as CSV, Excel, SQL tables, and BigQuery tables, as well as unstructured data such as PDFs, DOCX files, TXT files, and reports.

**Is the data sensitive?**
Healthcare data may contain personally identifiable information or protected health information. For this project, synthetic or public healthcare datasets should be used.

**How often is the data updated?**
For the GitHub version, uploaded files are updated manually. In a production version, database and BigQuery connections could be refreshed on a schedule.

### Security Questions

**How should PII be handled?**
The system should detect and redact sensitive information before sending text to the LLM.

**Should users be authenticated?**
For the MVP, authentication can be optional. For production, authentication and role-based access control should be added.

**How should SQL be secured?**
Only read-only `SELECT` queries should be allowed. Dangerous commands such as `DROP`, `DELETE`, `UPDATE`, `INSERT`, and `ALTER` must be blocked.

### AI Design Questions

**Should this system use RAG or fine-tuning?**
The first version should use RAG because the goal is to answer questions from uploaded documents and data sources. Fine-tuning is not necessary for the MVP.

**Why use agents?**
Agents are useful because the system must decide which tool to use: RAG, SQL, Amazon Athena or Amazon Redshift, GraphRAG, summarization, or document classification.

**Why use LangGraph?**
LangGraph is useful for building controlled multi-step workflows where each step has a clear state, tool, and decision path.

### Evaluation Questions

**How do we know if the system works well?**
The system should be evaluated using retrieval accuracy, SQL execution success rate, answer factuality, hallucination rate, route accuracy, latency, and cost.

**What does a correct answer mean?**
A correct answer should be relevant, grounded in the right source, factually consistent, and generated using the correct tool or route.

### Production Questions

**Where should the system be deployed?**
The recommended cloud platform for this project is AWS. The solution uses Amazon Bedrock for foundation models, Amazon S3 for document storage, Amazon RDS PostgreSQL for structured healthcare data, Amazon OpenSearch Service for vector search, Amazon Neptune for graph-based relationship analysis, and AWS Glue Data Catalog for metadata management. The backend services can be deployed on Amazon ECS Fargate or Amazon EKS, providing a scalable and production-ready environment for healthcare AI applications.

**What should be containerized?**
The FastAPI backend, Streamlit frontend, LangGraph orchestration layer, document processing services, and optional Redis cache should be containerized using Docker. Containers can be deployed on Amazon ECS Fargate or Amazon EKS to simplify scaling, monitoring, and maintenance.

### Maintenance Questions

**Who updates documents and datasets?**
In the MVP version, users manually upload healthcare documents and datasets through the application interface. In production, automated ingestion pipelines can be created using Amazon EventBridge, AWS Lambda, AWS Glue, and Amazon S3 to continuously ingest and update data from databases, APIs, cloud storage locations, and healthcare systems.

**How are prompts maintained?**
Prompt templates should be stored in a centralized prompt registry and version-controlled using Git repositories. Prompt versions can be tracked alongside application releases and evaluated regularly to ensure answer quality, consistency, and compliance with healthcare requirements.

**How are failures monitored?**
Failures should be monitored through Amazon CloudWatch Logs, CloudWatch Metrics, AWS X-Ray distributed tracing, and custom evaluation dashboards. Monitoring should capture application errors, LLM failures, retrieval failures, SQL execution errors, latency spikes, token consumption, and infrastructure health metrics.

### Final Success Criteria

The project is considered successful if healthcare users can securely upload documents and datasets stored in Amazon S3, query structured and unstructured data using natural language, and receive accurate, source-grounded answers generated through Amazon Bedrock models. The system should correctly route requests to RAG, SQL, Athena, GraphRAG, or summarization workflows, retrieve relevant document chunks from Amazon OpenSearch Service, generate safe SQL queries for Amazon RDS PostgreSQL or Amazon Athena, provide citations and reasoning traces, monitor performance through CloudWatch, and support scalable deployment using AWS-native services.

---

## 3. Data Sources, Data Types, Fields, Loading, Preparation, and Storage

### Supported Data Sources

The system supports multiple input types.

Structured data includes CSV files, Excel files, SQL databases, and BigQuery tables. Unstructured data includes PDFs, DOCX files, TXT files, clinical guidelines, healthcare policies, and reports. API data can also be supported through JSON responses.

### Example Structured Data

A sample `patients.csv` file may include:

```text
patient_id
age
gender
diagnosis
risk_score
province
```

A sample `visits.xlsx` file may include:

```text
visit_id
patient_id
visit_date
provider
department
cost
length_of_stay
```

A sample SQL or Amazon RDS PostgreSQL may include:

```text
patients
visits
diagnoses
medications
lab_results
claims
```

### Example Unstructured Data

Documents may include:

```text
clinical_guideline.pdf
readmission_policy.pdf
insurance_claim_policy.docx
healthcare_report.txt
```

### Data Loading

The platform supports multiple healthcare data sources stored within the AWS ecosystem. CSV and Excel files uploaded by users are first stored in Amazon S3 and then processed using Pandas running on AWS compute services such as AWS Lambda, Amazon ECS, or AWS Glue. Structured healthcare data can be loaded from Amazon RDS PostgreSQL, Amazon Redshift, or queried directly from Amazon Athena using the AWS SDK (Boto3). PDF documents are processed using PyPDF or pdfplumber, while DOCX files are parsed using python-docx. All uploaded files are stored securely in Amazon S3 and registered in the AWS Glue Data Catalog for discovery and governance.


### Data Preparation

Structured healthcare data is prepared using AWS Glue ETL jobs or custom Python pipelines running on Amazon ECS. Data preparation includes handling missing values, standardizing column names, validating schemas, removing duplicate records, converting date and timestamp fields, and enforcing data quality rules. Unstructured documents are processed by extracting text, generating metadata, splitting content into chunks, identifying entities and relationships, and creating vector embeddings using Amazon Bedrock embedding models or Amazon Titan Embeddings. Metadata generated during processing is stored in the AWS Glue Data Catalog.

### Data Storage

The platform follows a cloud-native AWS architecture for storing structured, unstructured, vector, and graph data.

- Raw uploaded files, including CSV, Excel, PDF, DOCX, TXT, and JSON files, are stored in Amazon S3.
- Structured healthcare datasets are stored in Amazon RDS PostgreSQL for transactional workloads and optionally in Amazon Redshift for large-scale analytics.
- Data stored in Amazon S3 can be queried directly using Amazon Athena without requiring data movement.
- Document embeddings are stored in Amazon OpenSearch Service with Vector Engine capabilities to support semantic search and Retrieval-Augmented Generation (RAG).
- Entity relationships extracted from healthcare documents are stored in Amazon Neptune to support GraphRAG and relationship-based reasoning.
- Metadata describing datasets, documents, schemas, and data lineage is maintained in the AWS Glue Data Catalog.
- Frequently accessed data and session information can be cached using Amazon ElastiCache for Redis to improve performance and reduce latency.

---

## 4. Complete Platform Architecture and Flows

### Data Ingestion Flow

The first workflow occurs when users upload healthcare documents, datasets, or connect enterprise data sources. AWS services are used to store, catalog, process, and secure the data before it becomes available for AI-powered analysis.

```text
User uploads CSV / Excel / PDF / DOCX / TXT
or connects Amazon RDS / Athena / External APIs
	↓
Amazon API Gateway
    ↓
FastAPI Application (Amazon ECS Fargate)
	↓
Data Type Detector
	↓
Data Loader
	↓
Data Cleaner and Validator
	↓
AWS Storage Decision Layer
	↓
Structured Data
    → Amazon RDS PostgreSQL
    → Amazon S3 Data Lake
    → Amazon Athena Query Layer

Documents
    → Amazon S3 Document Storage
    → Amazon Bedrock Embeddings
    → Amazon OpenSearch Vector Engine

Relationships & Knowledge Graph
    → Amazon Neptune

Metadata & Schema Information
    → AWS Glue Data Catalog

Caching
    → Amazon ElastiCache Redis

Secrets & Credentials
    → AWS Secrets Manager
```

### Question Answering Flow

The second workflow occurs when users ask questions in natural language. A LangGraph-based Router Agent determines the most appropriate reasoning path and invokes the required AWS services.

```text
User asks question
	↓
Amazon API Gateway
    ↓
FastAPI /ask Endpoint (Amazon ECS Fargate)
	↓
LangGraph Router Agent
	↓
Router checks:
    • User Question
    • AWS Glue Data Catalog
    • Available Tables
    • Available Documents
    • Available Graph Data
    • Previous Conversation Context
	↓
Router selects route:
    • SQL Agent (Amazon RDS)
    • Athena Agent (Amazon Athena)
    • RAG Agent (OpenSearch + Bedrock)
    • GraphRAG Agent (Neptune + OpenSearch)
    • Summarization Agent (Bedrock)
    • Classification Agent (Bedrock)
	↓
Selected Agent Executes Tools
    ↓
Amazon Bedrock Foundation Models
    ↓
Final Answer Agent
    ↓
Response Generation
	↓
User receives:
    • Final Answer
    • Sources & Citations
    • Route Used
    • SQL Query (if applicable)
    • Confidence Information
    • Latency Metrics
    • Cost Information
    • Limitations & Warnings
```

### Important Clarification

The user's question is not permanently stored in the vector database.

For RAG-based workflows, the question is temporarily converted into embeddings using Amazon Bedrock Embedding Models and used to search Amazon OpenSearch Vector Engine for relevant document chunks.

For structured analytics workflows, the question is converted into SQL by an LLM hosted on Amazon Bedrock. The generated SQL is validated against security policies, executed against Amazon RDS PostgreSQL or Amazon Athena, and then summarized before being returned to the user.

For GraphRAG workflows, entities and relationships are retrieved from Amazon Neptune and combined with supporting document evidence retrieved from Amazon OpenSearch before generating the final response.

All interactions, tool calls, latency metrics, token usage, and errors are captured through Amazon CloudWatch and AWS X-Ray for monitoring, observability, auditing, and troubleshooting.

---

## 5. AWS Architecture Flowchart

The platform is organized around three paths: data ingestion, agent routing, and answer generation. AWS services provide scalable storage, retrieval, security, monitoring, and AI capabilities.

```mermaid
flowchart TD

    U[User] --> UI[Streamlit Frontend]
    UI --> APIGW[Amazon API Gateway]
    APIGW --> API[FastAPI on Amazon ECS Fargate]

    subgraph Ingestion[Data Ingestion Path]
        API --> Upload[Upload or Connect Data]
        Upload --> Detector[Data Type Detector]

        Detector -->|CSV / Excel| TabularLoader[Tabular Loader]
        Detector -->|PDF / DOCX / TXT| DocLoader[Document Loader]
        Detector -->|Amazon RDS / Athena| ConnLoader[Connection Loader]
        Detector -->|API JSON| APILoader[API Loader]

        TabularLoader --> Clean[Cleaning and Validation]
        ConnLoader --> GlueCatalog[AWS Glue Data Catalog]
        APILoader --> Clean

        Clean --> RDS[(Amazon RDS PostgreSQL)]
        Clean --> S3Lake[(Amazon S3 Data Lake)]
        Clean --> Athena[(Amazon Athena)]
        Clean --> GlueCatalog

        DocLoader --> TextExtract[Text Extraction]
        TextExtract --> Chunk[Chunking]
        Chunk --> Embed[Amazon Bedrock Embeddings]
        Embed --> VectorDB[(Amazon OpenSearch Vector Engine)]
        Chunk --> EntityExtract[Entity and Relation Extraction]
        EntityExtract --> GraphDB[(Amazon Neptune)]
        DocLoader --> GlueCatalog

        API --> Redis[(Amazon ElastiCache Redis)]
        API --> Secrets[(AWS Secrets Manager)]
    end

    subgraph Query[Question Answering Path]
        API --> Ask[Ask Question]
        Ask --> Router[LangGraph Router Agent]
        Router --> GlueCatalog

        Router --> SQLAgent[SQL Agent (Amazon RDS)]
        Router --> AthenaAgent[Athena Agent (Amazon Athena)]
        Router --> RAGAgent[RAG Agent (OpenSearch + Bedrock)]
        Router --> GraphAgent[GraphRAG Agent (Neptune + OpenSearch)]
        Router --> SumAgent[Summarization Agent (Bedrock)]
        Router --> ClassAgent[Classification Agent (Bedrock)]

        SQLAgent --> RDS
        AthenaAgent --> Athena
        RAGAgent --> VectorDB
        GraphAgent --> GraphDB
        SumAgent --> VectorDB
        ClassAgent --> VectorDB

        SQLAgent --> BedrockFM[Amazon Bedrock Foundation Models]
        AthenaAgent --> BedrockFM
        RAGAgent --> BedrockFM
        GraphAgent --> BedrockFM
        SumAgent --> BedrockFM
        ClassAgent --> BedrockFM

        SQLAgent --> Final[Final Answer Agent]
        AthenaAgent --> Final
        RAGAgent --> Final
        GraphAgent --> Final
        SumAgent --> Final
        ClassAgent --> Final
    end

    subgraph Output[Output, Monitoring, and Response]
        Final --> Response[Response Generation]
        Response --> UI
        Final --> Obs[Amazon CloudWatch]
        Final --> Trace[AWS X-Ray]
        Final --> Eval[Evaluation Reports]
        Final --> UI
    end
```

---

## 6. AWS Folder and File Structure

```text
healthcare-multisource-agentic-rag-platform/
│
├── app/
│   ├── main.py
│   ├── routes.py
│   ├── schemas.py
│   ├── config.py
│   ├── dependencies.py
│   └── auth.py
│
├── aws/
│   ├── bedrock_client.py
│   ├── s3_manager.py
│   ├── athena_client.py
│   ├── rds_client.py
│   ├── opensearch_client.py
│   ├── neptune_client.py
│   ├── glue_catalog.py
│   ├── cognito_auth.py
│   ├── secrets_manager.py
│   ├── cloudwatch_logger.py
│   └── xray_tracing.py
│
├── data_sources/
│   ├── csv_loader.py
│   ├── excel_loader.py
│   ├── rds_loader.py
│   ├── athena_loader.py
│   ├── api_loader.py
│   └── document_loader.py
│
├── data_pipeline/
│   ├── clean_data.py
│   ├── validate_data.py
│   ├── transform_data.py
│   ├── feature_engineering.py
│   ├── pii_detection.py
│   └── schema_validation.py
│
├── storage/
│   ├── s3_store.py
│   ├── rds_store.py
│   ├── athena_store.py
│   ├── opensearch_store.py
│   ├── neptune_store.py
│   └── metadata_store.py
│
├── rag/
│   ├── chunking.py
│   ├── embeddings.py
│   ├── retriever.py
│   ├── reranker.py
│   ├── graph_rag.py
│   └── citation_builder.py
│
├── agents/
│   ├── graph.py
│   ├── state.py
│   ├── router.py
│   ├── nodes.py
│   ├── tools.py
│   │
│   ├── sql_agent.py
│   ├── athena_agent.py
│   ├── rag_agent.py
│   ├── graph_rag_agent.py
│   ├── summarization_agent.py
│   ├── classification_agent.py
│   │
│   └── prompts/
│       ├── system_prompt_v1.md
│       ├── router_prompt.md
│       ├── sql_prompt.md
│       ├── athena_prompt.md
│       ├── rag_prompt.md
│       ├── graph_rag_prompt.md
│       ├── summarization_prompt.md
│       └── safety_prompt.md
│
├── services/
│   ├── bedrock_service.py
│   ├── prompt_registry.py
│   ├── pii_service.py
│   ├── cache_service.py
│   ├── safety_service.py
│   ├── cost_service.py
│   └── response_formatter.py
│
├── evaluation/
│   ├── eval_questions.json
│   ├── evaluate_rag.py
│   ├── evaluate_sql_agent.py
│   ├── evaluate_athena_agent.py
│   ├── evaluate_router.py
│   ├── hallucination_check.py
│   └── evaluation_report.md
│
├── observability/
│   ├── logging_config.py
│   ├── cloudwatch_metrics.py
│   ├── xray_tracing.py
│   ├── alarms.py
│   └── dashboard_notes.md
│
├── frontend/
│   ├── streamlit_app.py
│   ├── pages/
│   └── components/
│
├── infrastructure/
│   ├── terraform/
│   │   ├── s3.tf
│   │   ├── rds.tf
│   │   ├── athena.tf
│   │   ├── opensearch.tf
│   │   ├── neptune.tf
│   │   ├── bedrock.tf
│   │   ├── ecs.tf
│   │   ├── cognito.tf
│   │   └── iam.tf
│   │
│   └── cloudformation/
│
├── deployment/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── ecs-task-definition.json
│   ├── ecs-service.yaml
│   ├── github_actions.yml
│   └── buildspec.yml

├── tests/
│   ├── test_api.py
│   ├── test_loaders.py
│   ├── test_rag.py
│   ├── test_router.py
│   ├── test_sql_agent.py
│   ├── test_athena_agent.py
│   └── test_graph_rag.py
│
├── docs/
│   ├── architecture.md
│   ├── aws_services.md
│   ├── data_sources.md
│   ├── prompt_versioning.md
│   ├── safety_and_pii.md
│   ├── observability.md
│   ├── security.md
│   ├── cost_optimization.md
│   └── deployment.md
│
├── sample_data/
│   ├── patients.csv
│   ├── visits.xlsx
│   ├── sample_policy.pdf
│   └── clinical_guidelines.pdf
│
├── notebooks/
│   ├── data_exploration.ipynb
│   ├── rag_experiments.ipynb
│   └── evaluation_analysis.ipynb
│
├── README.md
├── requirements.txt
├── .env.example
├── pyproject.toml
└── LICENSE
```

---

## 7. Agents, Services, and Model Selection

### Router Agent

The Router Agent is the orchestration layer of the platform and is implemented using LangGraph. It analyzes the user's question, available datasets, document metadata, AWS Glue Data Catalog information, and conversation history to determine the most appropriate workflow.

If the question involves aggregations, filters, statistics, or structured data analysis, the Router Agent routes the request to the SQL Agent or Athena Agent. If the question involves document understanding, policies, clinical guidelines, or knowledge retrieval, it routes the request to the RAG Agent. Questions involving entity relationships, clinical concepts, or connected healthcare knowledge are routed to the GraphRAG Agent.

Amazon Bedrock foundation models are used to assist routing decisions and reasoning throughout the workflow.

### SQL Agent

The SQL Agent answers questions using structured healthcare data stored in Amazon RDS PostgreSQL.

CSV and Excel files uploaded by users are validated, transformed, and loaded into PostgreSQL tables. The SQL Agent reads database schemas, generates SQL queries using Amazon Bedrock foundation models, validates query safety, executes approved queries against Amazon RDS, and summarizes the results for users.

To improve security, only read-only SQL operations are permitted.

### Athena Agent

The Athena Agent answers questions from large-scale healthcare datasets stored in Amazon S3 and queried through Amazon Athena.

The agent accesses metadata from AWS Glue Data Catalog, generates Athena-compatible SQL, estimates query costs, validates query safety, executes the query, and summarizes the results.

This agent enables serverless analytics over large healthcare datasets without requiring dedicated database infrastructure.

### RAG Agent

The Retrieval-Augmented Generation (RAG) Agent answers questions from unstructured healthcare documents.

Documents are stored in Amazon S3 and indexed into Amazon OpenSearch Serverless Vector Engine using embeddings generated through Amazon Bedrock Titan Embeddings.

When a user submits a question, the RAG Agent:

- Generates an embedding for the question.
- Searches the vector index.
- Retrieves the most relevant document chunks.
- Optionally reranks retrieved passages.
- Generates a source-grounded response using Amazon Bedrock.

The final response includes citations and supporting evidence from retrieved healthcare documents.

### GraphRAG Agent

The GraphRAG Agent answers relationship-based healthcare questions.

Entities such as diseases, medications, procedures, providers, risk factors, and clinical concepts are extracted from documents and stored in Amazon Neptune.

When a question requires understanding relationships between concepts, the GraphRAG Agent:

- Extracts relevant entities.
- Searches Amazon Neptune for related nodes and relationships.
- Retrieves supporting document evidence.
- Combines graph knowledge with document retrieval.
- Generates a relationship-aware answer using Amazon Bedrock.

This enables complex healthcare knowledge discovery beyond traditional vector search.

### Summarization Agent

The Summarization Agent creates concise summaries of healthcare documents, reports, datasets, and query results.

The agent can summarize:

- Clinical guidelines
- Policy documents
- Research papers
- Healthcare reports
- SQL query outputs
- Athena query results

Amazon Bedrock foundation models are used to generate high-quality summaries tailored to business and clinical users.

### Classification Agent

The Classification Agent automatically categorizes uploaded content and user requests.

Examples include:

- Clinical guideline
- Healthcare policy
- Research publication
- Claims report
- Regulatory document
- Patient report
- Administrative document

Classification results are stored in metadata repositories and improve routing and retrieval accuracy.

### Data Catalog Agent

The Data Catalog Agent manages metadata across all connected healthcare sources.

The agent uses AWS Glue Data Catalog to:

- Discover available datasets
- Track schemas
- Maintain table metadata
- Store document metadata
- Support dataset search and discovery

This enables the Router Agent to understand available information before selecting a workflow.

### Final Answer Agent

The Final Answer Agent combines outputs from all agents and generates the final response.

The response includes:

- Final answer
- Sources and citations
- Selected workflow
- Generated SQL (if applicable)
- Confidence indicators
- Limitations
- Query latency
- Estimated AWS service costs
- Data source information

This provides transparency and explainability for healthcare users.

### Recommended AWS Models

#### Foundation Models (Amazon Bedrock)

For reasoning, orchestration, summarization, and answer generation:

- Anthropic Claude 3.7 Sonnet
- Anthropic Claude 3.5 Sonnet
- Meta Llama 3.3 70B
- Mistral Large
- Amazon Nova Pro
- Amazon Nova Lite

#### Embedding Models

For vector search and retrieval:

- Amazon Titan Text Embeddings V2
- Cohere Embed (via Bedrock)

#### Reranking Models

For improving retrieval quality:

- Cohere Rerank
- Cross-Encoder reranker models (optional custom deployment)

#### Graph Analytics

For GraphRAG:

- Amazon Neptune
- spaCy
- NetworkX (development and prototyping)

---

## 8. Deployment Steps (AWS Version)

### Step 1: Build Backend APIs

Create FastAPI endpoints for data ingestion, retrieval, monitoring, and question answering.

```text
POST /upload/csv
POST /upload/excel
POST /upload/document
POST /connect/database
POST /ask
GET /health
GET /metrics
```

### Step 2: Build Local Development Environment

Use Docker Compose to run:

- FastAPI Backend
- Streamlit Frontend
- PostgreSQL
- Redis
- OpenSearch Local
- Local Embedding Service

This environment allows developers to test the platform before deploying to AWS.

### Step 3: Containerize the Application

Create Docker images for:

- FastAPI Backend
- Streamlit Frontend
- Background Workers

Store images in Amazon Elastic Container Registry (ECR).

Use environment variables and AWS Secrets Manager for credentials and API keys.

### Step 4: Deploy Locally

Run:

```bash
docker-compose up
```

Users can upload healthcare documents and datasets and interact with the assistant locally.

### Step 5: Deploy to AWS Cloud

#### Storage Layer

Amazon S3

- Raw Documents
- Processed Documents
- Data Lake
- Evaluation Results

#### Database Layer

- Amazon RDS PostgreSQL
- Amazon Athena
- AWS Glue Data Catalog
- Amazon Neptune

#### AI Layer

- Amazon Bedrock
- Titan Embeddings
- Claude Models
- Nova Models

#### Retrieval Layer

- Amazon OpenSearch Serverless
- Vector Search
- Semantic Search
- Hybrid Search

#### Compute Layer

- Amazon ECS Fargate
- AWS Lambda
- AWS Step Functions

#### Security Layer

- Amazon Cognito
- AWS IAM
- AWS KMS
- AWS Secrets Manager
- AWS WAF

#### Monitoring Layer

- Amazon CloudWatch
- AWS X-Ray
- CloudWatch Dashboards
- CloudWatch Alarms

### Step 6: CI/CD Pipeline

Deploy automatically using:

- GitHub Actions
- Amazon ECR
- Amazon ECS Fargate
- CloudFormation or Terraform

Pipeline stages:

- Build
- Test
- Security Scan
- Docker Build
- Push to ECR
- Deploy to ECS
- Run Validation Tests

---

## 9. Evaluation Methods

### RAG Evaluation

Evaluate retrieval quality using:

- Recall@K
- Precision@K
- MRR
- Context Relevance
- Answer Relevance
- Faithfulness
- Citation Accuracy

Evaluation datasets and reports are stored in Amazon S3.

### SQL and Athena Evaluation

Measure:

- SQL validity rate
- Athena query validity rate
- Query execution success rate
- Correct table selection
- Correct column selection
- Unsafe query blocking rate
- Answer correctness

### Agent Evaluation

Evaluate:

- Routing accuracy
- Tool selection accuracy
- Workflow completion rate
- Structured output validity
- Recovery from failures
- Average latency
- Cost per request

### Hallucination Evaluation

Compare generated responses against:

- Retrieved document chunks
- Athena query results
- PostgreSQL query results
- GraphRAG evidence

Unsupported claims are flagged and reported.

### Prompt Evaluation

Compare prompt versions using:

- Route accuracy
- Retrieval accuracy
- Hallucination rate
- SQL generation quality
- Cost efficiency
- User satisfaction

---

## 10. Monitoring and Observability

### Logging

Amazon CloudWatch Logs stores:

- Request ID
- User question
- Selected route
- Tool calls
- Generated SQL
- Athena queries
- Retrieved chunks
- Prompt version
- Model name
- Latency
- Errors
- Cost estimates

### Distributed Tracing

AWS X-Ray traces:

```text
User Request
→ FastAPI
→ Router Agent
→ Bedrock
→ OpenSearch
→ Athena/RDS
→ Final Response
```

This enables full end-to-end visibility.

### Metrics

Amazon CloudWatch Metrics tracks:

- Request volume
- Error rate
- Latency
- Token usage
- Bedrock costs
- Athena scanned bytes
- SQL failures
- Retrieval latency
- Cache hit rate

### Dashboards

CloudWatch Dashboards display:

- System health
- Service availability
- Agent route distribution
- Bedrock usage
- Retrieval performance
- Failed requests
- Prompt injection attempts
- PII detections
- Operational costs

---

## 11. Recommended Libraries and AWS SDKs

- FastAPI
- Uvicorn
- Pydantic
- LangChain
- LangGraph
- boto3
- Amazon Bedrock SDK
- Pandas
- NumPy
- OpenPyXL
- SQLAlchemy
- psycopg2
- Amazon Athena
- AWS Glue
- Amazon OpenSearch
- Amazon Neptune
- PyPDF
- pdfplumber
- python-docx
- spaCy
- NetworkX
- Redis
- OpenTelemetry
- Amazon CloudWatch
- AWS X-Ray
- Pytest
- Docker
- GitHub Actions
- Terraform

---

## 12. Final GitHub README Summary

This project implements a production-grade Healthcare Multi-Source Agentic RAG Platform built entirely on AWS. Users can upload CSV, Excel, PDF, DOCX, and TXT files or connect healthcare databases and data lakes. Structured data is stored in Amazon RDS PostgreSQL and Amazon Athena, documents are stored in Amazon S3, embeddings are indexed in Amazon OpenSearch Serverless, entity relationships are stored in Amazon Neptune, and metadata is managed through AWS Glue Data Catalog.

A LangGraph-based multi-agent architecture orchestrates SQL, Athena, RAG, GraphRAG, Summarization, Classification, and Metadata Discovery agents. Amazon Bedrock foundation models provide reasoning, retrieval, summarization, and answer generation capabilities. The platform returns source-grounded answers with citations, generated SQL, workflow traces, latency metrics, and cost estimates.

The project demonstrates enterprise-scale Agentic AI, Retrieval-Augmented Generation (RAG), GraphRAG, healthcare analytics, AWS cloud architecture, MLOps, observability, security, governance, and production deployment best practices.


