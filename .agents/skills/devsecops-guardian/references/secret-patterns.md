# Secret Patterns

This system monitors and blocks over 600+ types of secrets. Some prominent examples include:

1. **AWS Credentials**: `aws_access_key_id`, `aws_secret_access_key`
2. **GCP Service Accounts**: `type": "service_account"` and associated private keys.
3. **GitHub Tokens**: `ghp_...`, `gho_...`, `ghs_...`, `ghr_...`
4. **JWT Tokens**: Strings starting with `eyJ...`
5. **Private Keys**: PEM files, RSA, ED25519, DSA keys (`-----BEGIN PRIVATE KEY-----`)
6. **Connection Strings**: `postgres://`, `mysql://`, `redis://`, `mongodb://`
7. **Bearer Tokens**: `Bearer [A-Za-z0-9\-\._]+`
8. **Stripe Keys**: `sk_live_...`, `sk_test_...`
9. **Slack Tokens**: `xoxb-...`, `xoxp-...`
10. **Twilio**: API keys and Auth Tokens.
