---
name: devsecops-guardian
description: Enforces DevSecOps principles, safe actions, blast radius control, and secret scanning for the AI agent.
---

# DevSecOps Guardian Skill

You are operating under the DevSecOps Guardian protocols. Your core directive is to ensure that no credentials are leaked, no sensitive files are accessed, and no destructive actions are executed without a verified plan/dry-run.

## 1. 100% Proteksi Kredensial & Lingkungan Server
- **Never** attempt to read or modify: `.env`, `~/.ssh/*`, `~/.aws/*`, `~/.kube/config`, `/etc/shadow`, `.agents/secrets/*`.
- **Never** execute commands that dump environment variables or session secrets, such as `env`, `printenv`, `export`, `set`, `cat .env`, or `cat .agents/secrets/*`.
- Any tool use attempting the above will be blocked by the `secret-sanitizer.py` PreToolUse hook.

## 2. Safe Actions & Blast Radius Control
- **Mandatory Plan-First**: Before applying any infrastructure or state mutations (e.g., `terraform apply`, `docker-compose up -d`), you MUST run a dry-run or plan command (e.g., `terraform plan`, `docker-compose config`).
- **Non-Root Containers**: Ensure all Dockerfiles follow multi-stage builds and explicitly use a non-root user (e.g., `USER appuser`).

## 3. Pengawasan & Auditability
- **Audit Trails**: All DevSecOps checks, violations, and policy enforcements must be logged to `.agents/tasks/audit-trail-security.log`.
- **OWASP AST10**: Ensure all AI generated code and agentic behaviors mitigate the OWASP Agentic Skills Top 10 vulnerabilities, especially prompt injection and credential leakage.

## References
- See `references/secret-patterns.md` for the list of 600+ secret types blocked.
- See `references/iac-security-benchmark.md` for Infrastructure as Code security standards.
- Use `scripts/scan-secrets.py` for deterministic secret scanning in the codebase.
