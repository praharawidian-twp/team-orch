# Meta-Studio MCP Repository

Folder ini adalah direktori khusus penyimpanan server **Model Context Protocol (MCP)** yang dirancang dan dibangun oleh tim Meta-Studio (`meta-architect` & `agent-builder`).

## Struktur
- `servers/`: Tempat kode sumber MCP Server mandiri (FastMCP / Python SDK / TypeScript).
- `configs/`: File katalog registrasi dan skema konfigurasi integrasi ke Antigravity (`mcp_config.json`).

## Standar Pembuatan MCP Server
1. Dibuat menggunakan Python (FastMCP) atau TypeScript SDK resmi.
2. Setiap tool wajib memiliki type-hinting dan deskripsi argumen yang jelas.
3. Seluruh eksekusi eksternal wajib menerapkan validasi input dan sanitasi (mencegah arbitrary command execution).
