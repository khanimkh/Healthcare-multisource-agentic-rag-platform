> **Outdated**: `services/bedrock_service.py` has been removed. This walkthrough describes its original design, where `BedrockService` owned the raw `boto3` `bedrock-runtime` client directly and called `self.client.invoke_model(...)` itself. That responsibility now belongs solely to `services/model_service.py` (see `docs/model-service.md` and the "AI service layering" section of `docs/design-code-general-structure.md`). Classification moved to `agents/classification_agent.py` (via `LLMService` + `prompts/classification_prompt.py`); embeddings moved to `services/embedding_service.py`. Kept here for the general explanation of the Bedrock request/response shape (`invoke_model`, request body, parsing), which is still accurate for `model_service.py`.

1. Use an LLM (Claude on Bedrock) to classify healthcare documents.
2. Use an embedding model (Titan Embeddings) to convert text into vectors for semantic search.

Let's go through it section by section.

---

# Imports

```python
import json
```

Used to convert Python dictionaries into JSON before sending requests to AWS.

Example:

```python
body = {"inputText": "Hello"}
```

becomes:

```json
{"inputText":"Hello"}
```

using:

```python
json.dumps(body)
```

---

```python
import boto3
```

`boto3` is the official AWS SDK for Python.

It allows Python code to communicate with AWS services such as:

- Bedrock
- S3
- DynamoDB
- RDS
- CloudWatch
- Secrets Manager

Here it is only communicating with **Bedrock Runtime**.

---

```python
from typing import List
```

Used only for type hints.

```python
def create_embedding(...) -> List[float]
```

means:

> This function returns a list of floating point numbers.

Example:

```python
[0.17, -0.22, 0.45, ...]
```

---

```python
from app.backend.config.settings import settings
```

Imports your application configuration.

Instead of hardcoding:

```text
us-east-1
```

or:

```text
anthropic.claude...
```

everything comes from:

```python
settings
```

For example:

```python
settings.aws_region
```

might contain:

```text
ca-central-1
```

and:

```python
settings.bedrock_llm_model_id
```

might contain:

```text
anthropic.claude-3-5-sonnet...
```

This makes the code portable.

---

# Class Definition

```python
class BedrockService:
```

This class is responsible for **all interactions with AWS Bedrock**.

Instead of writing:

```python
boto3.client(...)
```

throughout the project,

every component simply uses:

```python
bedrock_service.classify_text(...)
```

or:

```python
bedrock_service.create_embedding(...)
```

This is an example of the **Service Layer** design pattern.

---

# Constructor

```python
def __init__(self):
```

Runs automatically when:

```python
service = BedrockService()
```

is created.

---

## Creating the Bedrock client

```python
self.client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
```

This creates a reusable AWS client.

Think of it as:

```text
Python
	|
	v
Bedrock Client
	|
	v
AWS Bedrock Runtime
```

Every request later uses:

```python
self.client
```

instead of reconnecting every time.

---

# classify_text()

```python
def classify_text(self, text: str) -> str:
```

Input:

```text
Healthcare document
```

Output:

```text
clinical guideline
```

or:

```text
lab result
```

etc.

---

## Prompt

```python
prompt = f"""
```

This is prompt engineering.

The model receives instructions like:

```text
Classify the following healthcare content...Return only the category name.
```

Then your document.

Example:

```text
Patient is diagnosed with diabetes...
```

Claude receives:

```text
Classify...Content:Patient is diagnosed...
```

---

## Why

```python
{text[:4000]}
```

instead of:

```python
{text}
```

Because LLMs have context limits.

This keeps only the first 4000 characters.

Otherwise:

- larger cost
- slower inference
- possible token limit exceeded

---

# Request Body

```python
body = {
```

Everything inside is the request sent to Claude.

---

## anthropic_version

```python
"anthropic_version": "bedrock-2023-05-31"
```

AWS Bedrock requires specifying which Anthropic API format is being used.

---

## max_tokens

```python
"max_tokens": 100
```

Maximum response length.

Since you only expect:

```text
lab result
```

100 tokens is more than enough.

---

## temperature

```python
"temperature": 0
```

Very important.

Temperature controls randomness.

Temperature 1:

```text
Maybe...Perhaps...
```

Temperature 0:

```text
Always deterministic.
```

For classification,

temperature should almost always be:

```text
0
```

because you want consistency.

---

## Messages

```python
"messages": [
```

Claude uses a chat format.

Here there is only one message.

```python
{"role": "user", "content": prompt}
```

Equivalent to a user asking ChatGPT:

```text
Please classify this.
```

---

# Invoke Model

```python
response = self.client.invoke_model(...)
```

This sends the request to AWS.

Parameters:

```python
modelId=settings.bedrock_llm_model_id
```

Example:

```text
Claude 3.5 Sonnet
```

---

```python
body=json.dumps(body)
```

Converts Python dictionary

v

JSON

v

HTTP request

v

AWS

---

```python
contentType="application/json"
```

Tells AWS:

```text
I'm sending JSON.
```

---

```python
accept="application/json"
```

Tells AWS:

```text
Return JSON.
```

---

# Response

AWS returns something like:

```json
{
	"content": [
		{
			"text": "clinical guideline"
		}
	]
}
```

---

```python
result = json.loads(response["body"].read())
```

Steps:

Read bytes

v

Convert to string

v

Convert JSON into Python dictionary

---

Finally:

```python
return result["content"][0]["text"].strip()
```

returns:

```text
clinical guideline
```

The caller never sees the raw AWS response.

---

# create_embedding()

```python
def create_embedding(...)
```

Instead of generating text,

this function generates **embeddings**.

Input:

```text
Patient has diabetes
```

Output:

```python
[0.23, -0.14, ...]
```

Thousands of numbers.

---

# Request

```python
body = {"inputText": text}
```

Unlike Claude,

Titan Embeddings expects:

```text
inputText
```

instead of:

```text
messages
```

Different models have different APIs.

---

# Invoke Model

```python
response = self.client.invoke_model(...)
```

Now:

```python
modelId=settings.bedrock_embedding_model_id
```

points to something like:

```text
amazon.titan-embed-text-v2
```

instead of Claude.

---

# Response

Titan returns:

```json
{
	"embedding": [
		0.12,
		-0.43,
		...
	]
}
```

This code:

```python
return result["embedding"]
```

returns the vector.

---

# Where is this used?

Typically, the flow in your application looks like this:

```text
								User uploads document
												|
												v
								BedrockService
									/           \
								 /             \
								v               v
			classify_text()    create_embedding()
								|               |
								v               v
		 "patient report"     [0.2,-0.1,...]
								|               |
								+-------+-------+
												|
												v
						Store in OpenSearch / Vector DB
												|
												v
						 Future semantic search & RAG
```

The **classification** result is useful for organizing or routing documents, while the **embedding** is stored in a vector database (such as OpenSearch) so that future user queries can retrieve semantically similar documents.

## Why this design is good

This class follows several software engineering best practices:

- **Single Responsibility Principle:** It only handles communication with AWS Bedrock.
- **Encapsulation:** The rest of the application doesn't need to know Bedrock's API details, request formats, or response parsing.
- **Reusability:** Any part of the application can call `classify_text()` or `create_embedding()` without duplicating code.
- **Maintainability:** If you later switch from Claude to another Bedrock model (or even another provider), you only need to update this service instead of changing code throughout the project.
- **Configuration-driven:** Model IDs and the AWS region come from `settings`, making it easy to use different environments (development, staging, production) without changing the code itself.

This service layer is a common pattern in production AI systems because it isolates external service interactions behind a clean, reusable interface.
