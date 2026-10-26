# Scraper Harga Material Bangunan

> Dokumentasi lengkap untuk tim implementasi (cara kerja per situs, skema output,
> interpretasi harga, troubleshooting): [docs/DOKUMENTASI.md](docs/DOKUMENTASI.md)

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

## Pemakaian

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
