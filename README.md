# Scraper Harga Material Bangunan

> Dokumentasi lengkap untuk tim implementasi (cara kerja per situs, skema output,
> interpretasi harga, troubleshooting): [docs/DOKUMENTASI.md](docs/DOKUMENTASI.md)
>
> Perintah siap pakai untuk menjalankan scraping: [Perintah scraping](#perintah-scraping)

Mengambil nama produk, harga, harga coret, diskon, toko, lokasi, rating, jumlah terjual,
dan URL dari:

| Situs | Cara ambil data | Catatan |
|---|---|---|
| Mitra10 | Browser headless (Playwright) untuk pencarian, lalu GraphQL Mitra10 untuk harga per toko | 24 produk/halaman, harga mengikuti toko yang dipilih |
| Depo Bangunan | HTTP biasa + parse HTML | Pencarian situs dibatasi ~25 produk per kata kunci |
| Tokopedia | API GraphQL pencarian (HTTP biasa) | 60 produk/halaman, bisa diurutkan |
| Shopee | Browser tampil (bukan headless) dengan profil yang sudah Anda login-kan | Wajib login dulu, lihat di bawah |

## Instalasi

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Perintah scraping

Semua perintah dijalankan dari folder proyek. Ganti tanggal di nama file output
(`20261027`) dengan tanggal mulai menjalankan, dan pakai nama yang sama saat melanjutkan.

```bash
cd /Users/clairence/Documents/Dev/scrap-material
```

### 1. Daftar utama: 204 kata kunci (`keywords_20261021.txt`)

Dengan deskripsi produk (±1,5–2 jam):

```bash
.venv/bin/python main.py -f keywords_20261021.txt -o output/harga_material_20261027.xlsx --deskripsi >> output/scrape_20261027.log 2>&1
```

Tanpa deskripsi (±35 menit):

```bash
.venv/bin/python main.py -f keywords_20261021.txt -o output/harga_material_20261027.xlsx >> output/scrape_20261027.log 2>&1
```

Deskripsi untuk **semua** produk relevan, bukan hanya 10 per kata kunci (±5–6 jam):

```bash
.venv/bin/python main.py -f keywords_20261021.txt -o output/harga_material_20261027.xlsx --deskripsi --deskripsi-maks 0 >> output/scrape_20261027.log 2>&1
```

### 2. Daftar tambahan multi-material: 32 kata kunci (`keywords_20261022_tambahan.txt`)

Dengan deskripsi (±15 menit):

```bash
.venv/bin/python main.py -f keywords_20261022_tambahan.txt -o output/harga_material_20261027_tambahan.xlsx --deskripsi >> output/scrape_20261027_tambahan.log 2>&1
```

### 3. Cek progres (sudah berapa dari berapa)

Ringkasan progres, diperbarui terus selama berjalan:

```bash
cat output/harga_material_20261027_PROGRES.txt
```

Ikuti log secara langsung (di terminal lain; Ctrl+C hanya menghentikan pemantauan):

```bash
tail -f output/scrape_20261027.log
```

Hasil sementara bisa dibuka kapan saja di `output/harga_material_20261027.xlsx`
(diperbarui tiap 5 menit dan saat proses dihentikan).

### 4. Melanjutkan proses yang berhenti

Jalankan lagi **perintah yang sama persis**, terutama `-o` yang sama. Contoh untuk daftar
utama:

```bash
.venv/bin/python main.py -f keywords_20261021.txt -o output/harga_material_20261027.xlsx --deskripsi >> output/scrape_20261027.log 2>&1
```

- Yang sudah selesai dilewati, yang gagal dicoba lagi, dan deskripsi tidak diambil ulang.
- Berlaku setelah Ctrl+C, laptop mati/sleep, atau koneksi putus, termasuk dilanjutkan
  besok hari.
- Perintah lengkapnya juga tertulis di bagian bawah file `_PROGRES.txt`.
- Log memakai `>>` (menambah), jadi log jalan sebelumnya tidak tertimpa.
- Jangan ubah `-p`, `--mitra10-store`, `--sort`, atau `--min-price` saat melanjutkan;
  script akan menolak supaya hasil tidak tercampur.

Mulai dari awal (abaikan progres tersimpan untuk output ini), tambahkan `--ulang`:

```bash
.venv/bin/python main.py -f keywords_20261021.txt -o output/harga_material_20261027.xlsx --deskripsi --ulang >> output/scrape_20261027.log 2>&1
```

### 5. Isi deskripsi ke file hasil yang sudah ada (tanpa scraping ulang)

Hasil disimpan ke `<nama file>_deskripsi.xlsx`; file asli tidak diubah. Tambahkan
`--maks 0` untuk semua produk relevan (default 10 per kata kunci). Bisa dilanjutkan dengan
menjalankan perintah yang sama.

```bash
.venv/bin/python main.py deskripsi output/harga_material_20261021_New_22Okt.xlsx >> output/deskripsi_New_22Okt.log 2>&1
```

```bash
cat output/harga_material_20261021_New_22Okt_deskripsi_PROGRES.txt
```

### 6. Uji cepat satu kata kunci (sebelum dimasukkan ke file kata kunci)

```bash
.venv/bin/python main.py -k "kaca 8mm per m2" -s tokopedia
```

### 7. Harga Mitra10 dari toko lain

Lihat daftar ID toko:

```bash
.venv/bin/python main.py mitra10-stores
```

Scraping Mitra10 dengan toko tertentu (contoh ID 1 = MITRA10 CIBUBUR):

```bash
.venv/bin/python main.py -f keywords_20261021.txt -s mitra10 --mitra10-store 1 -o output/harga_mitra10_toko1_20261027.xlsx >> output/scrape_mitra10_toko1_20261027.log 2>&1
```

### Catatan

- Selalu pakai `-o` untuk jalan panjang; tanpa `-o` proses tidak bisa dilanjutkan.
- Hasil berisi kolom `relevant` (True/False): saring `relevant = True` sebelum analisa.
- Detail progres & melanjutkan: bagian 3.4 di [docs/DOKUMENTASI.md](docs/DOKUMENTASI.md).
- Bantuan semua opsi: `.venv/bin/python main.py --help`

## Contoh lain & opsi

```bash
# Satu/lebih kata kunci, default situs: mitra10, depobangunan, tokopedia
python main.py -k "semen 50kg" -k "bata ringan"

# Dari file kata kunci, 3 halaman per kata kunci, simpan ke Excel
python main.py -f keywords.txt --pages 3 -o output/harga.xlsx

# Pilih situs tertentu
python main.py -k "cat tembok" -s tokopedia depobangunan

# Tokopedia urut harga termurah, buang produk di bawah Rp10.000 (aksesoris/eceran)
python main.py -k "pipa pvc 4 inch" -s tokopedia --sort termurah --min-price 10000
```

Opsi:

- `-k/--keyword` kata kunci (boleh diulang), `-f/--keywords-file` file kata kunci
- `-s/--sites` `mitra10 depobangunan tokopedia shopee`
- `-p/--pages` jumlah halaman per kata kunci (default 1)
- `-o/--output` `.csv` atau `.xlsx` (default `output/harga_material_<waktu>.csv`)
- `--sort` urutan Tokopedia: `relevan`, `termurah`, `termahal`, `terbaru`, `ulasan`
- `--mitra10-store` ID toko Mitra10 untuk harga (default 18 = MITRA10 Q-BIG); daftar ID: `python main.py mitra10-stores`
- `--min-price` buang produk di bawah harga ini
- `--deskripsi` ambil juga deskripsi produk ke kolom `description`; `--deskripsi-maks N`
  batasi N produk relevan per kata kunci per situs untuk Tokopedia/Depo Bangunan
  (default 10, 0 = semua). Untuk file hasil lama: `python main.py deskripsi <file.xlsx>`
- `--ulang` abaikan progres tersimpan dan mulai dari awal
- `--show-browser` tampilkan jendela browser Mitra10 (untuk debug)

Kolom output: `source, keyword, name, price, url, relevant, match_score, original_price,
discount_percent, promo, brand, seller, location, rating, sold, in_stock, image, scraped_at,
description`.

## Kolom `relevant` dan `match_score`

Pencarian situs, terutama Mitra10, tetap menampilkan produk lain bila barang yang dicari
tidak dijual (mis. "tabung freon r32" memunculkan mesin cuci 2 tabung). Baris seperti itu
tidak dihapus, tapi ditandai (`scraper/relevance.py`):

- `match_score`: porsi kata dalam kata kunci yang ada di nama produk (0–1).
- `relevant`: `True` bila minimal separuh kata cocok (kata kunci 1–2 kata: semua) **dan**
  semua ukuran/spesifikasi yang mengandung angka cocok persis (9mm, 3x2.5, 20x20, 1/2).
  Merek pengganti tetap bisa lolos (kabel Supreme untuk kata kunci "eterna").

Penanda ini perkiraan. Di Mitra10 sebagian kecil yang `True` masih salah barang (mis.
"pipa ac hoda" meloloskan unit AC), jadi saring `relevant = True` lalu periksa sekilas.

## Tentang harga

- **Mitra10**: harga berbeda per toko. Scraper memakai harga toko yang dipilih
  (`--mitra10-store`), sama dengan yang tampil di halaman produk untuk toko itu. Harga di
  halaman *pencarian* Mitra10 adalah harga dasar katalog dan bisa jauh berbeda.
  `in_stock=False` berarti di toko itu statusnya Pre-Order.
- **Tokopedia**: harga yang diambil adalah harga umum. Browser yang dianggap "Pembeli Baru"
  bisa melihat harga lebih murah (potongan sekali pakai). Kolom `promo` berisi label promo
  yang terbaca, mis. "Harga Diskon".

## Shopee

Shopee langsung mengalihkan browser otomatis yang belum login ke halaman verifikasi.
Scraper ini **tidak** mem-bypass CAPTCHA atau verifikasi; Anda login sendiri satu kali:

```bash
python main.py shopee-login
```

Jendela Chromium terbuka; login dan selesaikan verifikasi yang diminta, lalu tekan Enter di
terminal. Sesi disimpan di `.browser-profile/shopee/` (jangan dibagikan, berisi cookie login).
Setelah itu:

```bash
python main.py -k "semen tiga roda" -s shopee
```

Jika muncul error `ShopeeBlocked`, ulangi `shopee-login`. Ketentuan layanan Shopee melarang
pengambilan data otomatis dan akun bisa dibatasi, jadi pakai jumlah halaman kecil dan
pertimbangkan akun terpisah.

## Catatan

- Ada jeda acak 1,5–3,5 detik antar kata kunci dan antar halaman (antar halaman Shopee
  3–6 detik). Jangan diperkecil agar tidak membebani server dan tidak diblokir.
- Hasil marketplace bercampur produk non-material (mis. "piyama motif Semen Tiga Roda").
  Gunakan kata kunci spesifik (merek + ukuran) dan `--min-price`, lalu saring di Excel.
- Struktur situs dan API bisa berubah sewaktu-waktu. Lokasi logika tiap situs:
  `scraper/mitra10.py`, `scraper/depobangunan.py`, `scraper/tokopedia.py`, `scraper/shopee.py`.
# scraping-material-bmga
