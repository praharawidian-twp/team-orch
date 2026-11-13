#!/usr/bin/env python3
"""
verify-spec.py - Deterministic Validator for Tech Lead Technical Spec & Task List.

Validates that `02-technical-spec.md` and `03-task-list.md` adhere strictly to
Senior Lead Engineer / Tech Lead standards before handover to Coder.

Usage:
    python3 verify-spec.py <project_task_dir_or_project_id>

Exit codes:
    0: Valid (All Senior Tech Lead criteria met)
    1: Invalid (One or more critical sections missing)
"""

import sys
import os
import re
from pathlib import Path

def print_status(check_name: str, passed: bool, detail: str = ""):
    icon = "✅" if passed else "❌"
    print(f"  {icon} {check_name}: {detail}")

def validate_tech_spec(content: str) -> tuple[bool, list[str]]:
    errors = []
    
    # 1. Boilerplate Audit Check
    has_boilerplate = bool(re.search(r'(?i)(boilerplate|shared\s+util|reusable\s+module|audit\s+codebase)', content))
    if not has_boilerplate:
        errors.append("Missing section on 'Boilerplate Audit / Reusable Utilities'")
        
    # 2. C4 Architecture / Mermaid Diagram Check
    has_mermaid = bool(re.search(r'```mermaid\s+(flowchart|graph|sequenceDiagram|classDiagram)', content))
    if not has_mermaid:
        errors.append("Missing C4 Architectural Diagram (Mermaid code block)")
        
    # 3. Architectural Decision Record (ADR) Check
    has_adr = bool(re.search(r'(?i)(ADR-\d+|Architectural\s+Decision\s+Record|Keputusan\s+Arsitektur)', content))
    if not has_adr:
        errors.append("Missing Architectural Decision Record (ADR) section")
        
    # 4. Data Contracts / Interface Definitions Check
    has_contracts = bool(re.search(r'(?i)(contract|interface|struct|dto|skema|schema)', content))
    if not has_contracts:
        errors.append("Missing explicit Data Contracts / Interface Definitions")
        
    # 5. Security & Resilience Check
    has_security = bool(re.search(r'(?i)(keamanan|security|sanitasi|timeout|context|error\s+handling)', content))
    if not has_security:
        errors.append("Missing Security & Resilience / Error Handling section")
        
    return (len(errors) == 0, errors)

def validate_task_list(content: str) -> tuple[bool, list[str]]:
    errors = []
    
    # 1. Atomic Tasks presence
    tasks = re.findall(r'\[\s*[ xX]?\s*\]\s*(TASK-\d+)', content)
    if not tasks:
        tasks = re.findall(r'###\s*(TASK-\d+)', content)
        
    if not tasks:
        errors.append("No atomic tasks formatted as 'TASK-01', 'TASK-02', etc. found")
    else:
        # Check task details for each task
        for task_id in tasks:
            task_section_match = re.search(rf'{task_id}[:\s\-\w]+', content)
            if not task_section_match:
                continue
                
    # 2. Test criteria / Acceptance criteria check
    has_test_criteria = bool(re.search(r'(?i)(test\s+criteria|kriteria\s+pengujian|boundary|skenario)', content))
    if not has_test_criteria:
        errors.append("Missing explicit Test Criteria / Boundary testing in task breakdown")
        
    # 3. Target files check
    has_target_files = bool(re.search(r'(?i)(target\s+file|berkas\s+target|file:)', content))
    if not has_target_files:
        errors.append("Missing target file declarations in task breakdown")
        
    return (len(errors) == 0, errors)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 verify-spec.py <project_task_dir_or_project_id>")
        sys.exit(1)
        
    raw_path = sys.argv[1]
    task_dir = Path(raw_path)
    
    if not task_dir.exists():
        # Try checking in .agents/tasks/active/<project_id>
        candidate = Path(".agents/tasks/active") / raw_path
        if candidate.exists():
            task_dir = candidate
        else:
            print(f"❌ Error: Task directory '{raw_path}' not found.")
            sys.exit(1)
            
    print(f"\n🔍 [Tech Lead Spec Validator] Auditing: {task_dir}")
    print("=" * 60)
    
    spec_file = task_dir / "02-technical-spec.md"
    task_file = task_dir / "03-task-list.md"
    
    all_passed = True
    
    # Check 02-technical-spec.md
    print("\n📄 Verifying 02-technical-spec.md:")
    if not spec_file.exists():
        print("  ❌ 02-technical-spec.md does not exist!")
        all_passed = False
    else:
        spec_content = spec_file.read_text(encoding="utf-8")
        passed, errors = validate_tech_spec(spec_content)
        if passed:
            print("  ✅ All architectural sections, C4 diagrams, and ADRs are present.")
        else:
            all_passed = False
            for err in errors:
                print(f"  ❌ {err}")
                
    # Check 03-task-list.md
    print("\n📋 Verifying 03-task-list.md:")
    if not task_file.exists():
        print("  ❌ 03-task-list.md does not exist!")
        all_passed = False
    else:
        task_content = task_file.read_text(encoding="utf-8")
        passed, errors = validate_task_list(task_content)
        if passed:
            print("  ✅ Vertical slice breakdown, target files, and test criteria validated.")
        else:
            all_passed = False
            for err in errors:
                print(f"  ❌ {err}")
                
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 STATUS: PASSED (Specification conforms to Senior Tech Lead Standards)")
        sys.exit(0)
    else:
        print("⚠️ STATUS: FAILED (Specification requires refinement before handoff)")
        sys.exit(1)

if __name__ == "__main__":
    main()
