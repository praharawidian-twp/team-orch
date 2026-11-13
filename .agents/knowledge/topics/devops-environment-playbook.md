# 🐳 DevOps Multi-Environment & Containerization Playbook

> **Topik ID**: `devops-environment-playbook`  
> **Akses**: `*` (Global - Terutama `devops`, `coder`, `analyst`)  
> **Tingkat Kepatuhan**: `STRICT`

---

## 1. Pemetaan & Standarisasi Multi-Environment
Setiap proyek atau microservice wajib dirancang untuk beroperasi secara deterministik di 4 spektrum lingkungan:

| Lingkungan | Karakteristik Utama | Konfigurasi Database | Strategi Eksekusi |
| :--- | :--- | :--- | :--- |
| **Local Dev** | Bind-mount volume, debugging port terbuka, fast-feedback. | Kontainer lokal Podman/Docker (`postgres:16-alpine`). | `go run` / `npm run dev` atau compose lokal. |
| **Test / CI** | Ephemeral, non-interactive, isolated mocks & test DB. | In-memory atau database kontainer sekali pakai. | `go test -v -race ./...` atau GitHub Actions CI runner. |
| **Staging** | Mirip produksi, data sintetis/anonymized, stress test. | Dedicated staging database instance. | Kontainer image immutable dengan tag versi. |
| **Production** | Zero downtime, immutable image, non-root user, hardened secrets. | Managed cloud DB / high-availability cluster. | Orchestration (Kubernetes / Podman Pod / Docker Swarm). |

---

## 2. Praktik Terbaik Kontainerisasi (Dockerfile & Containerfile)
1. **Multi-Stage Build Wajib**:
   - Tahap 1 (`builder`): Menggunakan base image dengan toolchain lengkap (misal `golang:1.24-alpine` atau `node:22-alpine`).
   - Tahap 2 (`runtime`): Menggunakan base minimal (`alpine:3.20` atau `gcr.io/distroless/static`) hanya memuat binary yang sudah di-compile.
2. **Efisiensi Caching Layer**:
   - Salin berkas definisi dependensi terlebih dahulu (`go.mod`, `package.json`) lalu unduh dependencies (`go mod download`, `npm install`).
   - Baru setelah itu salin seluruh source code aplikasi untuk memaksimalkan cache layer kontainer.
3. **Keamanan Eksekusi (Non-Root)**:
   - Dilarang menjalankan aplikasi kontainer sebagai `root`.
   - Buat user dan group khusus:
     ```dockerfile
     RUN addgroup -S appgroup && adduser -S appuser -G appgroup
     USER appuser
     ```
4. **Health Check Probes**:
   - Selalu sediakan instruksi `HEALTHCHECK` pada Dockerfile atau definisi probe di compose:
     ```dockerfile
     HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
       CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1
     ```

---

## 3. Orkestrasi Kontainer Lokal (Podman & Docker Compose)
1. **Dukungan Rootless Podman**:
   - Gunakan format standar compose specification (`compose.yaml` atau `docker-compose.yaml`) yang kompatibel dengan perintah `docker compose` maupun `podman compose`.
2. **Manajemen Port & Pencegahan Konflik**:
   - Gunakan variabel fallback untuk port mapping pada host machine:
     ```yaml
     ports:
       - "${APP_PORT:-8080}:8080"
       - "${DB_PORT:-5432}:5432"
     ```
3. **Dependency Readiness Probe**:
   - Layanan aplikasi wajib menunggu database benar-benar siap menerima koneksi sebelum booting:
     ```yaml
     depends_on:
       db:
         condition: service_healthy
     ```

---

## 4. Konfigurasi Variabel & Sanitasi Secrets
1. **Kebijakan `.env.example`**:
   - Seluruh variabel lingkungan yang dibutuhkan wajib didokumentasikan di `.env.example` dengan placeholder deskriptif.
2. **Sanitasi Kredensial**:
   - Dilarang keras menaruh plain password di repositori atau file compose publik.
   - Gunakan file `.env` lokal (diabaikan oleh `.gitignore`) untuk menyimpan kredensial aktual saat dev lokal.

---

## 5. Otomasi Makefile Standar DevOps
Setiap service wajib menyertakan target Make infrastruktur agar mudah dioperasikan:
```makefile
.PHONY: infra-up infra-down infra-logs infra-clean

infra-up:
	docker compose -f compose.yaml up -d --build

infra-down:
	docker compose -f compose.yaml down

infra-logs:
	docker compose -f compose.yaml logs -f

infra-clean:
	docker compose -f compose.yaml down -v
```
