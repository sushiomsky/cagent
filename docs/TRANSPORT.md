# LLM transport

`cagent` talks to OpenAI-compatible model endpoints with a small standard-library HTTP client.

The client supports:

- `/v1/models`
- `/v1/chat/completions`
- non-streaming JSON responses
- request timeout
- a small retry budget for temporary endpoint failures
- exponential backoff between retry attempts

Retryable cases include temporary connection failures, timeouts and selected transient HTTP status codes.

## Configuration

The default transport behavior is configured through `AgentConfig` and environment variables:

```text
CAGENT_REQUEST_TIMEOUT_SECONDS=120
CAGENT_REQUEST_RETRIES=1
CAGENT_RETRY_BACKOFF_SECONDS=0.5
```

`CAGENT_REQUEST_RETRIES` is the number of retries after the first attempt. `CAGENT_RETRY_BACKOFF_SECONDS` is the base delay used before retrying.

The default client remains dependency-free and keeps existing cagent behavior unchanged, except that temporary endpoint interruptions now get one automatic retry.
