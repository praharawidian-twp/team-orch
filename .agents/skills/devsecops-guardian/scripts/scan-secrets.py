#!/usr/bin/env python3
import os
import re
import sys

SECRET_PATTERNS = [
    (re.compile(r'\b(AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b'), 'AWS Access Key'),
    (re.compile(r'(?i)(aws_secret_access_key|secret_key)\s*[:=]\s*["\']?[A-Za-z0-9/+=]{40}["\']?'), 'AWS Secret Key'),
    (re.compile(r'\bgh[pousr]_[A-Za-z0-9_]{36,}\b'), 'GitHub Token'),
    (re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'), 'Private Key'),
    (re.compile(r'(?i)(postgres|postgresql|mysql|mongodb|redis)://[^:]+:[^@\s]{4,}@'), 'Database Credentials URI'),
]

def scan_file(filepath):
    findings = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            for i, line in enumerate(f):
                for pattern, name in SECRET_PATTERNS:
                    if pattern.search(line):
                        findings.append((i+1, name))
    except Exception as e:
        print(f"Error scanning {filepath}: {e}", file=sys.stderr)
    return findings

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    found_any = False
    ignored_dirs = {'.git', 'tests', 'sandbox', 'tasks', '.drafts', 'node_modules', 'venv', '.venv', '__pycache__', '.agents/meta-studio'}
    ignored_files = {'secret-patterns.md'}

    for root, dirs, files in os.walk(target_dir):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        for file in files:
            if file in ignored_files or file.endswith('.pyc'):
                continue
            filepath = os.path.join(root, file)
            findings = scan_file(filepath)
            if findings:
                found_any = True
                for line_num, name in findings:
                    print(f"[!] Found {name} in {filepath}:{line_num}")
    if found_any:
        sys.exit(1)
    else:
        print("No secrets found.")
        sys.exit(0)

if __name__ == '__main__':
    main()
