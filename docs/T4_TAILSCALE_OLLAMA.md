# Tesla T4 + Tailscale + Ollama deployment guide

This guide describes the intended private-model setup for `cagent`.

```text
Workstation
  cagent CLI
  http://127.0.0.1:18080/v1
      |
      v
  local SSH/Tailscale forward
      |
      v
T4 worker
  Ollama on 127.0.0.1:11434
  qwen2.5-coder:14b-instruct-q4_K_M
```

## Model choices

Recommended for a single 16 GB Tesla T4:

```text
default  qwen2.5-coder:14b-instruct-q4_K_M
fast     qwen2.5-coder:7b-instruct-q4_K_M
reviewer qwen3-coder:30b-a3b-q4_K_M
```

The 14B quantized coder model is the best default balance. The 7B model is useful for fast inspection. The 30B-A3B reviewer profile is optional and may be slower or partially offloaded depending on backend and quantization.

## Worker setup

Install Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
```

Pull models:

```bash
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull qwen3-coder:30b-a3b-q4_K_M || true
```

Check the local API on the worker:

```bash
curl -s http://127.0.0.1:11434/v1/models
```

Check GPU usage while the model is running:

```bash
nvidia-smi
ollama ps
```

## Tailscale setup

Install and start Tailscale on the worker:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
```

Give the worker a stable tailnet name, for example:

```text
colab-ollama
```

Confirm the workstation can reach it:

```bash
tailscale status
ssh root@colab-ollama tailscale status
```

## Local forward on the workstation

Keep Ollama bound to the worker loopback address and forward it locally:

```bash
ssh -N \
  -L 127.0.0.1:18080:127.0.0.1:11434 \
  root@colab-ollama
```

Now the workstation should see the worker through:

```bash
curl -s http://127.0.0.1:18080/v1/models
```

## Optional systemd user service for the forward

Create a user service:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/cagent-ollama-forward.service <<'EOF'
[Unit]
Description=cagent Ollama Tailscale forward
After=network-online.target

[Service]
ExecStart=/usr/bin/ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 127.0.0.1:18080:127.0.0.1:11434 root@colab-ollama
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now cagent-ollama-forward.service
```

Check status:

```bash
systemctl --user status cagent-ollama-forward.service
curl -s http://127.0.0.1:18080/v1/models
```

## cagent configuration

```bash
export CAGENT_BASE_URL=http://127.0.0.1:18080/v1
export CAGENT_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
export CAGENT_FAST_MODEL=qwen2.5-coder:7b-instruct-q4_K_M
export CAGENT_REVIEWER_MODEL=qwen3-coder:30b-a3b-q4_K_M
export CAGENT_MODEL_ROLE=default
export CAGENT_COMMAND_PROFILE=inspect
```

Run the doctor check:

```bash
cagent doctor \
  --base-url http://127.0.0.1:18080/v1 \
  --model-role default \
  --command-profile inspect
```

## Smoke tests

Fast inspect:

```bash
cagent run \
  --workspace . \
  --model-role fast \
  --command-profile inspect \
  --goal "Inspect this repo and list the main files."
```

Normal edit workflow:

```bash
cagent run \
  --workspace . \
  --model-role default \
  --write \
  --shell \
  --command-profile test \
  --log-run \
  --goal "Make a small documentation improvement, review the diff, and run tests."
```

Reviewer workflow:

```bash
cagent run \
  --workspace . \
  --model-role reviewer \
  --command-profile inspect \
  --goal "Review the current git diff and identify risky changes."
```

## Operational notes

- Keep the model API private to the tailnet or localhost.
- Prefer one local endpoint, `127.0.0.1:18080`, for all clients.
- Keep `CAGENT_COMMAND_PROFILE=inspect` as the default.
- Enable `--auto-approve-shell` only for a single reviewed run.
- Use `.cagent-runs/` logs for debugging agent behavior.

## Common failures

Forward is down:

```bash
systemctl --user restart cagent-ollama-forward.service
curl -s http://127.0.0.1:18080/v1/models
```

Worker is online but model missing:

```bash
ssh root@colab-ollama 'ollama list'
ssh root@colab-ollama 'ollama pull qwen2.5-coder:14b-instruct-q4_K_M'
```

Model too slow:

```bash
cagent run --model-role fast --workspace . --goal "Inspect only."
```

GPU not active:

```bash
ssh root@colab-ollama 'nvidia-smi && ollama ps'
```
