# Secret scanning

`cagent` includes a lightweight local secret scanner. It is designed to reduce accidental leakage into model context, run logs and reports. It is not a replacement for a dedicated enterprise scanner.

## What it detects

Current pattern families:

- private key headers
- OpenAI-style keys
- Anthropic-style keys
- GitHub tokens
- AWS access key IDs
- JWT-like tokens
- environment-style assignments such as `TOKEN=...`, `PASSWORD=...`, `CLIENT_SECRET=...`

Findings include:

```text
path
line
kind
severity
entropy
redacted preview
```

Severity levels:

```text
critical
high
medium
low
```

## Run

```bash
cagent secret-scan --workspace .
cagent secret-scan --workspace . --fail-on-findings
```

## Allowlist

Add one regex per line to either file:

```text
.cagent-secret-allowlist
.cagent/secret-allowlist
```

Empty lines and `# comments` are ignored.

Example:

```text
# Ignore a documented dummy token line in tests
example_dummy_token
```

Allowlist patterns are matched against both the line and a combined `path:kind:line` target.

## Entropy filter

Some patterns use Shannon entropy thresholds to reduce low-quality placeholder matches. For example, `TOKEN=aaaaaaaaaaaaaaaa` is ignored because it has too little randomness to be useful as a real secret signal.

## JSON helpers

The internal scanner exposes `findings_json(findings)` for integrations that need machine-readable output. A later CLI phase can expose this directly as `cagent secret-scan --json`.

## Redaction

Tool output is redacted by default before it is returned to the model. Disable only for a reviewed one-off run:

```bash
cagent run --workspace . --no-redact-secrets --goal "Inspect this exact file."
```
