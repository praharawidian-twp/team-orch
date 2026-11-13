---
draft_id: "<route>-<slug>-<YYYYMMDD>"
category: "knowledge_draft | skill_update | role_prompt_patch | meta_studio_mcp"
status: "PENDING_HUMAN_APPROVAL"
generated_at: "<ISO-8601 timestamp>"
generated_by: "meta-architect"
evidence_project: "<project_id>"
signals_ref: ".agents/tasks/active/self-improvement/signals.json"
---

# [Judul Proposal — Deskriptif & Spesifik]

## 1. Masalah yang Dideteksi
<!-- 
Deskripsi pola anomali yang terdeteksi oleh Signal Collector.
WAJIB menyebut bukti dari signals.json (signature_id, category, count).

Contoh:
- Signature: SIG_BOILERPLATE_DEVIATION_01
- Kategori: boilerplate_deviation
- Frekuensi: 3x dalam 2 proyek terakhir
- Pola: Coder menulis ulang utilitas yang sudah tersedia di pkg/crypto
-->

## 2. Analisis Root Cause
<!--
Mengapa pola ini terjadi? Apa yang kurang dari knowledge/skill/role saat ini?

Pertanyaan panduan:
- Apakah rule ini belum pernah didokumentasikan?
- Apakah rule ada tapi tidak cukup jelas/eksplisit?
- Apakah ada ambiguitas dalam instruksi role?
-->

## 3. Solusi yang Diusulkan
<!--
Konten baru / perubahan yang diusulkan secara konkret dan actionable.
Tulis persis teks yang akan ditambahkan ke knowledge/skill/role.
-->

## 4. Diff Terhadap Versi Sebelumnya
<!--
WAJIB: Tampilkan diff eksplisit jika ini adalah revisi (mode AMEND).
Format diff:

```diff
- [Baris lama yang dihapus atau diganti]
+ [Baris baru yang ditambahkan atau menggantikan]
```

Jika ini adalah entitas baru, tulis: "N/A - Entitas Baru"
-->

## 5. Dampak yang Diharapkan
<!--
Metrik kesuksesan yang terukur setelah proposal ini diaktifkan.

Contoh:
- Rejection rate terkait boilerplate_deviation < 1x per project (dari baseline 3x)
- Coder tidak perlu menulis fungsi enkripsi mandiri lagi
- Code review approval pada first attempt meningkat
-->

## 6. Risk Assessment

| Risiko | Probabilitas | Dampak | Mitigasi |
|--------|-------------|--------|----------|
| <!-- Risiko 1 --> | Rendah/Sedang/Tinggi | Rendah/Sedang/Tinggi | <!-- Strategi mitigasi --> |
| <!-- Risiko 2 --> | | | |
