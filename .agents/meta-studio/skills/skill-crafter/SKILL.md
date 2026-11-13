---
name: skill-crafter
description: Panduan dan generator terstandarisasi untuk merancang, menyusun, dan menguji Antigravity Skills mandiri.
---

# Skill: Skill Crafter (Antigravity Agent Standard)

## Deskripsi
Skill ini memandu **Meta-Architect** dan **Agent Builder** dalam merancang dan memvalidasi Skill baru agar kompatibel 100% dengan standar Antigravity dan arsitektur agentic ekosistem.

## Struktur Standar Antigravity Skill
Setiap skill yang dibuat wajib memiliki struktur berikut:
```text
<nama-skill>/
├── SKILL.md              (Wajib: Berisi frontmatter YAML dan SOP eksekusi instruksi)
├── scripts/              (Opsional: Skrip pembantu/automasi yang dieksekusi agen)
├── references/           (Opsional: Dokumentasi detail, schema API, atau cheatsheet)
└── examples/             (Opsional: Contoh kasus input-output konkret)
```

## Format Wajib SKILL.md
```markdown
---
name: <kebab-case-name>
description: <Deskripsi ringkas dalam 1-2 kalimat mengenai apa yang dilakukan skill ini dan kapan harus digunakan>
---

# Skill: <Judul Representatif>

## 1. Ikhtisar & Tujuan
...

## 2. Instruksi Operasional Terinci
...

## 3. Checklist Kualitas & DevSecOps
...
```

## Checklist Validasi (Sebelum Approval)
- [ ] Frontmatter YAML valid (`name` dan `description`).
- [ ] Deskripsi menjelaskan pemicu (*trigger*) yang jelas kapan skill harus diaktifkan.
- [ ] Instruksi terstruktur langkah-demi-langkah, menghindari kebingungan agen.
- [ ] Tidak memuat kredensial, token rahasia, atau instruksi mutasi git.
