================================================================================
PANDUAN PENGAMBILAN BUKTI SCREENSHOT UI MANUAL (EVIDENCE GUIDE)
Test Case       : {tc}
Nama Bukti      : {name}
Target URL      : {url}
Dibuat Pada     : {created_at}
Model Sesi      : {session_model}
Viewport Target : {viewport}
================================================================================

1. PRASYARAT
   - Buka browser pilihan Anda (Chrome, Firefox, Safari, Edge).
   - Pastikan Anda sudah login ke lingkungan target ({url}) menggunakan
     kredensial yang sah (termasuk verifikasi SSO / MFA jika diperlukan).
   - Atur resolusi jendela browser mendekati viewport {viewport}.

2. LANGKAH PENGAMBILAN BUKTI
   - Navigasi ke URL target:
     {url}
   - Verifikasi bahwa halaman telah selesai dirender secara sempurna.
   - Lakukan inspeksi visual sesuai kriteria verifikasi Test Case {tc}.
   - Ambil screenshot halaman penuh (full-page) atau viewport aktif.

3. ATURAN MASKING & PRIVASI (WAJIB)
   - Jangan pernah menyertakan informasi sensitif dalam tangkapan layar!
   - Area yang wajib disamarkan (blur / black-box / sensor):
     * Kata sandi / PIN / token rahasia
     * Nomor identitas pribadi lengkap (NIK, Nomor Kartu Kredit/Rekening)
     * Mask selectors acuan: {masked_selectors}

4. PENYIMPANAN BERKAS BUKTI
   - Simpan berkas gambar screenshot dengan format PNG di direktori ini:
     {output_dir}/{name}.png
   - Berkas screenshot ini akan diaudit oleh Analis / Senior Tech Lead
     sebelum UAT pengguna.

================================================================================
