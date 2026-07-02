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

The default client remains dependency-free and keeps existing cagent behavior unchanged, except that temporary endpoint interruptions now get one automatic retry.
