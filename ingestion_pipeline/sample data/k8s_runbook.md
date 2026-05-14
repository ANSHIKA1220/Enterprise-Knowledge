# Kubernetes OOM Troubleshooting

When a pod is OOMKilled, inspect memory usage and check for memory leaks.

| Parameter | Value |
|-----------|-------|
| limit     | 1Gi   |
| request   | 512Mi |

```bash
kubectl describe pod api-gateway
kubectl top pod api-gateway
```

This file tests:
- Markdown parsing
- Table detection
- Code block detection
