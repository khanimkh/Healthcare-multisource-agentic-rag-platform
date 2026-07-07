# Final architecture

I would organize it like this:

```text
Agents
	|
	v
BedrockService
	|
	v
ModelService
	|
	v
Amazon Bedrock Runtime
```

### Responsibilities

| Class | Responsibility |
|---|---|
| **ModelService** | Low-level model inference (text generation and embeddings). It knows how to call Bedrock but knows nothing about healthcare or prompts. |
| **BedrockService** | High-level AI tasks (classification, summarization, entity extraction, SQL generation, etc.). It builds prompts and delegates inference to `ModelService`. |

This separation follows the **Single Responsibility Principle** much better than having both classes independently invoke Bedrock. It also makes it much easier to switch to another model provider later, because only `ModelService` needs to change.
