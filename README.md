1- Project Architecture

project/
│
├── app/
│   ├── backend/
│   │   ├── main.py
│   │   │   # Starts FastAPI application.
│   │   │   # Registers API routers.
│   │   │   # Configures CORS, middleware, startup events.
│   │
│   │   ├── api/
│   │   │   └── routes.py
│   │   │       # Defines endpoints such as /upload and /ask.
│   │   │       # Handles HTTP requests and responses.
│   │   │       # Calls services, tools, agents, or LangGraph workflow.
│   │
│   │   ├── config/
│   │   │   ├── settings.py
│   │   │   │   # Loads environment variables, API keys, AWS settings.
│   │   │   ├── agents.yaml
│   │   │   │   # Optional CrewAI agent configuration.
│   │   │   └── tasks.yaml
│   │   │       # Optional CrewAI task configuration.
│   │
│   │   ├── data/
│   │   │   ├── raw/
│   │   │   │   # Original uploaded files: CSV, Excel, PDF, images.
│   │   │   ├── processed/
│   │   │   │   # Cleaned and transformed datasets.
│   │   │   ├── embeddings/
│   │   │   │   # Local saved embeddings for development.
│   │   │   └── outputs/
│   │   │       # Reports, summaries, predictions, evaluation results.
│   │
│   │   ├── agents/
│   │   │   ├── router_agent.py
│   │   │   │   # Decides which agent/workflow should answer the question.
│   │   │   ├── sql_agent.py
│   │   │   │   # Answers questions from structured database tables.
│   │   │   ├── rag_agent.py
│   │   │   │   # Answers questions from documents using retrieval.
│   │   │   ├── graph_rag_agent.py
│   │   │   │   # Answers relationship-based questions using graph data.
│   │   │   ├── s3_agent.py
│   │   │   │   # Finds or reads raw files stored in S3.
│   │   │   ├── summarization_agent.py
│   │   │   │   # Summarizes documents, reports, or query results.
│   │   │   ├── classification_agent.py
│   │   │   │   # Classifies documents or user questions.
│   │   │   └── final_answer_agent.py
│   │   │       # Formats final response with sources and explanation.
│   │
│   │   ├── state/
│   │   │   └── state.py
│   │   │       # LangGraph shared state.
│   │   │       # Stores question, route, retrieved documents,
│   │   │       # SQL results, chat history, and final answer.
│   │
│   │   ├── prompts/
│   │   │   ├── router_prompt.py
│   │   │   ├── sql_prompt.py
│   │   │   ├── rag_prompt.py
│   │   │   ├── summary_prompt.py
│   │   │   ├── classification_prompt.py
│   │   │   └── final_answer_prompt.py
│   │   │       # Prompt templates and LLM instructions.
│   │
│   │   ├── tools/
│   │   │   ├── data_loader.py
│   │   │   │   # load_csv, load_excel, load_pdf, load_docx,
│   │   │   │   # load_image, detect_file_type.
│   │   │   ├── rag_utils.py
│   │   │   │   # chunk_documents, create_embeddings,
│   │   │   │   # retrieve_documents, rerank_results.
│   │   │   ├── database.py
│   │   │   │   # Connect to PostgreSQL/RDS and execute safe SQL.
│   │   │   ├── aws_storage.py
│   │   │   │   # Save/read files from S3, RDS, OpenSearch, Neptune.
│   │   │   ├── glue_catalog.py
│   │   │   │   # Register and read metadata, schemas, table names,
│   │   │   │   # document metadata, and data lineage.
│   │   │   └── web_search.py
│   │   │       # Optional external search tool.
│   │
│   │   ├── graphs/
│   │   │   └── langgraph_workflow.py
│   │   │       # Defines LangGraph nodes, edges,
│   │   │       # conditional routing, and graph compilation.
│   │
│   │   ├── services/
│   │   │   ├── llm_service.py
│   │   │   │   # Wrapper for LLM calls.
│   │   │   ├── bedrock_service.py
│   │   │   │   # Calls AWS Bedrock foundation models.
│   │   │   ├── embedding_service.py
│   │   │   │   # Creates embeddings using Bedrock/Titan embeddings.
│   │   │   ├── model_service.py
│   │   │   │   # ML/DL model serving wrapper.
│   │   │   ├── memory_service.py
│   │   │   │   # Stores conversation history and session context.
│   │   │   └── cache_service.py
│   │   │       # Uses Redis/ElastiCache for caching repeated results.
│   │
│   │   └── utils/
│   │       ├── helpers.py
│   │       │   # format_date, clean_text, generate_id,
│   │       │   # validate_file_extension.
│   │       ├── logger.py
│   │       └── validators.py
│   │
│   └── frontend/
│       ├── public/
│       ├── src/
│       ├── components/
│       ├── pages/
│       └── assets/
│
├── tests/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
├── .gitignore
└── README.md

-------------------------
2- Project Flows and Steps

2-1- Data Flow

User uploads data or connects to data source:
    - Structured data: CSV, Excel, SQL, AWS RDS
    - Unstructured data: PDF, DOCX, TXT, images, OCR
↓
AWS API Gateway
↓
FastAPI /upload endpoint
↓
Data type detector
↓
Data loader
↓
Data cleaning and validation
↓
Classification Agent:
    - Detects document type or dataset type
    - Example: clinical guideline, patient report, claims dataset, policy document
↓
AWS storage decision layer
↓
Save based on data type:
    - Raw files → Amazon S3
    - Structured data → PostgreSQL / AWS RDS
    - Large S3 datasets → Amazon Athena
    - Document chunks → OpenSearch Vector Store
    - Embeddings → Bedrock embeddings + OpenSearch
    - Relationships/entities → Amazon Neptune
    - Metadata/schema/lineage → AWS Glue Data Catalog
    - Sessions/cache → Redis / Amazon ElastiCache
↓
Return upload status to user

2-2- Question Flow

User asks question
↓
AWS API Gateway
↓
FastAPI /ask endpoint
↓
LangGraph workflow starts
↓
Load memory/session context from memory_service or Redis
↓
Router Agent analyzes:
    - User question
    - Available datasets
    - AWS Glue metadata
    - Previous conversation
    - Data type
↓
Router selects the best path:
    - SQL Agent → PostgreSQL/RDS questions
    - Athena Agent → large S3 data lake questions
    - RAG Agent → document-based questions
    - GraphRAG Agent → relationship/entity questions
    - S3 Agent → raw file lookup
    - Summarization Agent → summary/report questions
    - Classification Agent → classify question or document type
↓
Selected agent executes tools:
    - SQL query
    - Vector retrieval
    - S3 file access
    - Graph query
    - Metadata lookup
↓
AWS Bedrock model generates response
↓
Final Answer Agent formats:
    - Final answer
    - Sources/citations
    - Route used
    - SQL query if used
    - Confidence/limitations
↓
Save useful session memory/cache
↓
Generate response to user
---------------------

3- start to coding

app/backend/
├── config/settings.py 
├── requirements.txt
├── main.py
├── api/routes.py
├── schemas/upload_schema.py
├── tools/data_loader.py
├── tools/rag_utils.py
├── tools/aws_storage.py
├── tools/database.py
├── tools/glue_catalog.py
├── agents/classification_agent.py
├── services/bedrock_service.py
├── services/cache_service.py
└── utils/helpers.py

