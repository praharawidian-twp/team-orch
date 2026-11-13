# IAC Security Benchmark

1. **Least Privilege**: IAM roles and policies should grant minimum permissions required.
2. **Encryption**: All data at rest must be encrypted (S3, RDS, EBS).
3. **Network Isolation**: Use private subnets, restrict security group ingress (no 0.0.0.0/0 on port 22/3306/5432).
4. **Containers**: Run Docker containers as non-root, use trusted base images, avoid --privileged.
5. **No Hardcoded Secrets**: Secrets must be injected via secure Vaults/Managers, never hardcoded.
