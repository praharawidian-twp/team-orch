# Credential Models & Human-Session Protocol for UI Evidence Capture

Dokumen ini menjelaskan model kredensial yang didukung oleh skill `ui-evidence-capture` beserta batas-batas keamanan dan kedaulatan manusia (*human sovereignty*).

---

## 1. Perbandingan Model Kredensial

| Model | Nama | Deskripsi | Kapan Digunakan | Persetujuan Manusia |
|---|---|---|---|---|
| **Opsi B** *(Default)* | `human_session` | Manusia login sendiri di browser *headed*. Sesi disimpan sebagai `storageState` (cookie & localStorage). Agen **tidak pernah** melihat atau menyimpan password. | Lingkungan dengan SSO, MFA/OTP, CAPTCHA, atau kebijakan keamanan ketat. | Otomatis (manusia berinteraksi langsung di browser). |
| **Opsi A** | `env_service_account` | Kredensial akun uji read-only dibaca dari `.env.qa`. Agen mengisi form login secara otomatis. | Hanya untuk service account *read-only* tanpa MFA pada lingkungan dev terisolasi. | **Wajib persetujuan eksplisit per project** (`approved_by_human: true` di config). |
| **Opsi C** | `secret_manager` | Adapter membaca kredensial dari vault lokal (macOS Keychain via `/usr/bin/security` atau 1Password CLI `op://...`). | Integrasi enterprise dengan secure vault lokal. | Tergantung konfigurasi vault pengguna. |

---

## 2. Opsi B: Human-Session Protocol (Default — Keputusan D1)

Sesuai Keputusan D1, Opsi B adalah protokol default mutlak:
1. Agen menjalankan `ui-capture login --project <project_id>`.
2. Browser Chromium dibuka dalam mode **headed** (antarmuka grafis terlihat oleh pengguna) mengarah ke `login_url`.
3. Pengguna melakukan login secara manual, termasuk menyelesaikan tantangan autentikasi SSO, MFA, push notification, atau CAPTCHA login.
4. Setelah login berhasil (ditandai dengan munculnya `post_login_selector` atau pengguna menekan Enter di terminal), sesi diekstraksi ke file `ui-auth-state.json`.
5. Hak akses file dibatasi secara ketat:
   - File `ui-auth-state.json`: permission `0600` (`-rw-------`).
   - File `ui-auth-meta.json`: permission `0600` (`-rw-------`).
   - Folder `.agents/secrets/<project>/`: permission `0700` (`drwx------`).
6. Masa berlaku sesi ditentukan oleh `session_ttl_hours` (default: 8 jam). Jika sesi kedaluwarsa, `shot` akan mengembalikan kode `20` (`AUTH_REQUIRED`) dan meminta pengguna login ulang.

---

## 3. Opsi A: Service Account Read-Only (.env.qa) (Keputusan D5)

Model ini **hanya boleh digunakan** jika:
1. Akun yang digunakan memiliki hak akses murni *read-only*.
2. Akun tidak memiliki autentikasi dua faktor (MFA/OTP).
3. Pengguna memberikan persetujuan eksplisit di `qa-ui.config.json`:
   ```json
   {
     "credential_model": "env_service_account",
     "approved_by_human": true,
     "approved_at": "2026-11-12T10:00:00+07:00"
   }
   ```
4. Nilai kredensial disimpan di `.env.qa` lokal (yang wajib masuk `.gitignore`) dan tidak pernah dikomit ke repositori.

---

## 4. Opsi C: Secret Manager Adapter (Opsional)

Mendukung integrasi vault eksternal secara terabstraksi:
- macOS Keychain: `keychain:<service_name>` (diakses via `/usr/bin/security find-generic-password`).
- 1Password CLI: `op://<vault>/<item>/<field>`.

---

## 5. Batasan Keamanan & Larangan Mutlak (Absolute Invariants)

1. **Anti-Leakage**: CLI `ui-capture` dilarang mencetak cookie, token, authorization header, atau password ke terminal, log audit, atau berkas JSON.
2. **Read-Protected Secrets**: Agen dilarang membaca atau menampilkan isi `.agents/secrets/*` menggunakan `cat`, `read_file`, atau skrip dump.
3. **Penyimpanan Aman**: Seluruh sesi tersimpan di `.agents/secrets/` yang selalu diabaikan oleh Git (`.gitignore`).
