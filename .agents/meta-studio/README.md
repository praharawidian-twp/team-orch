# 🛠️ Meta-Studio: Autonomous Agent Capability & Evolution Forge

Selamat datang di **Meta-Studio**, namespace / kategori khusus di dalam ekosistem agen otonom yang didedikasikan untuk **Agentic Meta-Engineering** dan **Self-Improvement Framework**.

Folder ini mengisolasi seluruh peran tingkat tinggi (*High Tier*), alur kerja (*workflows*), keahlian internal (*skills*), server MCP (*Model Context Protocol*), dan perkakas (*tools*) yang bertugas menganalisis, merancang, dan memproduksi kapabilitas baru bagi seluruh agen.

---

## 📂 Struktur Direktori

```text
.agents/meta-studio/
├── README.md                          <-- Dokumentasi Arsitektur & Panduan
├── roles/                             <-- Peran Expert Khusus (Tier HIGH)
│   ├── meta-architect.yaml / .md      (Agent Systems, Protocol & Capability Architect)
│   └── agent-builder.yaml / .md       (MCP, Skill & Tooling Synthesis Engineer)
├── workflows/                         <-- Alur Kerja Otonom Khusus
│   └── meta-agent-evolution.yaml      (Alur Discovery -> Schema Design -> Tooling -> Audit -> Sign-off)
├── skills/                            <-- Keahlian Internal Meta-Studio
│   └── skill-crafter/SKILL.md         (Generator & Validator Antigravity Skills)
├── mcp/                               <-- Koleksi MCP Server Buatan Meta-Studio
│   ├── servers/                       (Tempat source code server MCP mandiri)
│   ├── configs/mcp-catalog.yaml       (Registrasi & skema konfigurasi integrasi)
│   └── README.md
└── tools/                             <-- Common Tools Khusus Ekosistem Ini
    ├── bin/meta-orch                  (CLI Runner & Refleksi Self-Improvement)
    └── README.md
```

---

## 🎭 2 Role Expert Khusus (Keduanya Tier HIGH - `gemini-3.1-pro-high`)

1. **Meta-Architect (`meta-architect`)**
   * **Fokus**: Analisis gap kapabilitas, brainstorming bersama Pengguna, penentuan bentuk artefak (MCP vs Skill vs Tool), desain kontrak protokol/skema JSON-RPC, evaluasi deviasi & mitigasi DevSecOps, serta memimpin siklus refleksi **Self-Improvement**.
2. **Agent Builder (`agent-builder`)**
   * **Fokus**: Konstruksi teknis server MCP (Python FastMCP/TypeScript), penyusunan berkas `SKILL.md` standar, penulisan script automasi dan common CLI tools, serta pengujian runtime mandiri sebelum audit.

---

## 🔄 Alur Pemanggilan Khusus (*Workflow*)

Ekosistem ini menggunakan workflow khusus: **`meta-agent-evolution`**:
1. **Capability Discovery** (*Meta-Architect*): Penggalian kebutuhan kapabilitas baru bersama Pengguna di Control Room.
2. **User Approval Gate**: Pengguna menyetujui cakupan kapabilitas dan batas keamanannya.
3. **Protocol & Schema Architecture** (*Meta-Architect*): Perancangan schema MCP, input/output contract, dan parameter.
4. **Tool Synthesis** (*Agent Builder*): Implementasi kode MCP / Skill / Tool CLI.
5. **Verification & Security Audit** (*Meta-Architect*): Pengujian runtime dan audit blast radius / sanitasi.
6. **Human Sign-off & Registry**: Pengguna meresmikan artefak untuk dipakai oleh ekosistem agen.

---

## 🧠 Mekanisme Self-Improvement Framework

Melalui perintah:
```bash
python3 .agents/meta-studio/tools/bin/meta-orch self-improve
```
Sistem akan:
1. Memindai data historis (`audit-trail.md`, `review-log.md`).
2. Mendiagnosis friksi berulang (misalnya pola penolakan code review atau ketiadaan utilitas bersama).
3. Merekomendasikan apakah perlu dibuatkan aturan pengetahuan baru (`team-orch knowledge draft`) atau diproduksi tool baru oleh tim Meta-Studio.

---

## 🌐 Panduan Kontribusi Komunitas Open-Source & Packaging

Meta-Studio kini terbuka bagi komunitas rekayasa AI open-source untuk mempercepat evolusi kapabilitas agen otonom.

### 1. Rekomendasi Model Tier (High-Reasoning Models)
Peran inti di dalam Meta-Studio (`meta-architect` dan `agent-builder`) dioptimalkan untuk model **Tier HIGH** (*Reasoning Effort: High*). Pekerjaan perancangan protokol, dekomposisi C4, keamanan DevSecOps, serta sintesis server MCP menuntut daya nalar tingkat tinggi:
* **Anthropic**: Claude Opus 4.6 / Claude Sonnet 4.6 (Extended Thinking)
* **Google**: Gemini 2.0 / 3.1 Pro (High Reasoning)
* **OpenAI / DeepSeek**: OpenAI o1 / o3-mini, DeepSeek R1

*Catatan: Model tier lebih rendah (seperti Flash atau Haiku) tetap dapat digunakan untuk subtask scanning atau linter, tetapi penalaran arsitektural utama direkomendasikan menggunakan model High Reasoning.*

### 2. Peluang Kontribusi Komunitas
Komunitas dipersilakan berkontribusi pada area-area berikut:
* **MCP Servers (`mcp/servers/`)**: Mengembangkan adapter Model Context Protocol baru (contoh: PostgreSQL inspector, Redis cache manager, Kafka streaming debugger).
* **Reusable Agent Skills (`skills/`)**: Merancang skill baru sesuai standar Antigravity untuk menambah keahlian domain khusus ke agen pekerja.
* **Meta-Tooling & Refactoring Engine (`tools/` & `tools/bin/meta-orch`)**: Memperluas deteksi pola anti-pattern, menambah algoritma AST analysis, dan mempercanggih diagnosa audit trail.

### 3. Kedaulatan Manusia & Prinsip Zero Self-Approval (Human-in-the-Loop)
Meskipun Meta-Studio ditenagai oleh model AI penalaran tercanggih di dunia:
* **Zero Self-Approval**: Agen dilarang keras mengesahkan (approve) artefak atau mempromosikan draf secara sepihak ke sistem produksi.
* **Control Room Sovereignty**: Seluruh proposal MCP, skill baru, dan perubahan pengetahuan (`.drafts/`) **wajib** melalui peninjauan eksplisit dan persetujuan Pengguna (Human) di Control Room.
* **Workspace Stirring & Git Isolation**: Agen beroperasi dalam batasan folder yang ketat dan dilarang mengeksekusi perintah Git yang memutasi status repository (`git add`, `git commit`, `git push`). Integritas versi sepenuhnya berada di tangan pengembang manusia.
