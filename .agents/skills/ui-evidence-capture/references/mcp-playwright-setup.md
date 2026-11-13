# Playwright MCP Server Configuration & Operational Protocol

Dokumen ini memuat panduan integrasi Model Context Protocol (MCP) untuk browser automation berbasis Playwright.

---

## 1. Konfigurasi MCP Server

Jika pengguna memilih opsi **Playwright MCP** (Opsi 3) pada Provisioning Consent Gate, berikan snippet konfigurasi berikut agar pengguna dapat menambahkannya ke konfigurasi client MCP mereka:

### Untuk Antigravity / Claude Code (`antigravity.json` atau `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-playwright"
      ]
    }
  }
}
```

---

## 2. Aturan Baku Penggunaan MCP oleh Agen (Operational Protocol)

Jika agen mendeteksi tersedianya tool MCP browser (misal `browser_navigate`, `browser_screenshot`, dll.), agen **WAJIB** menerapkan standar keamanan dan proteksi yang identik dengan CLI `ui-capture`:

1. **Origin Allowlist**:
   - Agen hanya boleh menavigasi ke domain yang tercantum pada `allowed_origins` di `.agents/config/qa-ui.config.json`.
2. **Read-Only Invariant**:
   - Agen dilarang mengeklik tombol submit, simpan, ubah, atau hapus (`click`, `submit`, `type` ke field mutasi).
   - MCP hanya digunakan untuk membaca (`navigate`, `get_content`, `screenshot`).
3. **Penyimpanan Bukti Konsisten**:
   - Gambar screenshot wajib disimpan ke path yang sama:
     `docs/qa/evidence/TC-<N>/<name>.png`
   - Buat/perbarui entri di `docs/qa/evidence/TC-<N>/capture-log.json` dengan `backend: "mcp"`.
4. **Challenge Detector**:
   - Bila halaman memunculkan CAPTCHA, Cloudflare Turnstile, atau prompt "verify you are human":
   - **STOP SEGERA**. Dilarang mencoba menyelesaikan atau melewati tantangan tersebut. Laporkan temuan ke pengguna.
5. **Masking**:
   - Pastikan field kata sandi atau data sensitif disamarkan sebelum screenshot diambil atau disimpan.
