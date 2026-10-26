# Dokumentasi Sistem Scraper Harga Material Bangunan

Dokumen ini untuk tim implementasi yang akan menjalankan, memelihara, atau
mengembangkan script ini. Untuk panduan singkat pemakaian, lihat [README](../README.md).

Kondisi per 16 Oktober 2026. Diuji dengan Python 3.14.3, Playwright 1.64.0,
httpx 0.28.1, beautifulsoup4 4.15.0, openpyxl 3.1.5, di macOS.

---

## 1. Ringkasan

Script ini mencari daftar material bangunan di beberapa toko online, lalu menyimpan
nama produk, harga, harga coret, toko, dan URL ke file CSV/Excel. Tujuannya menyediakan
harga pasar pembanding untuk item pekerjaan renovasi (RAB).

Daftar material yang dicari (`keywords.txt`, 99 kata kunci) diturunkan dari file audit
`Compile Gedung All Auditor.xlsx` (6.927 baris pekerjaan, 356 proyek, 2017–2022).

| Situs | Metode | Status |
|---|---|---|
| Mitra10 | Browser headless (Playwright) untuk pencarian + GraphQL Mitra10 untuk harga per toko | Berjalan, link & harga dicek ke halaman produk |
| Depo Bangunan | HTTP biasa + parse HTML | Berjalan, link & harga dicek ke halaman produk |
| Tokopedia | API GraphQL pencarian (HTTP biasa) | Berjalan, link & nama dicek di browser |
| Shopee | Browser tampil + profil yang sudah login | **Belum pernah berhasil diuji**: butuh login akun |

Satu kali jalan penuh (99 kata kunci × Mitra10, Depo Bangunan, Tokopedia, 1 halaman)
memakan ±17 menit dan menghasilkan ±7.000 baris.

---

## 2. Instalasi

Butuh Python 3.10 atau lebih baru (baru diuji di 3.14) dan koneksi internet.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

`playwright install chromium` mengunduh browser (±100 MB) yang dipakai untuk Mitra10
dan Shopee. Depo Bangunan dan Tokopedia hanya butuh HTTP biasa.

---

## 3. Menjalankan

### 3.1 Perintah utama

```bash
# Semua kata kunci di keywords.txt, situs default (mitra10, depobangunan, tokopedia)
python main.py -f keywords.txt -o output/harga_material.xlsx

# Kata kunci langsung (boleh diulang)
python main.py -k "semen instan acian" -k "gypsum jayaboard 9mm"

# Situs tertentu, 3 halaman per kata kunci
python main.py -f keywords.txt -s tokopedia depobangunan -p 3

# Harga Mitra10 dari toko lain (lihat daftar ID di 3.2)
python main.py -f keywords.txt -s mitra10 --mitra10-store 1
```

| Opsi | Default | Keterangan |
|---|---|---|
| `-k`, `--keyword` | – | Kata kunci, boleh diulang |
| `-f`, `--keywords-file` | – | File kata kunci (lihat bagian 8). **Tidak dibaca otomatis**: wajib disebut |
| `-s`, `--sites` | `mitra10 depobangunan tokopedia` | Pilihan: `mitra10 depobangunan tokopedia shopee`. Shopee tidak masuk default karena butuh login |
| `-p`, `--pages` | `1` | Jumlah halaman hasil per kata kunci |
| `-o`, `--output` | `output/harga_material_<waktu>.csv` | Ekstensi `.xlsx` → Excel, selain itu CSV (UTF-8 dengan BOM, aman dibuka Excel) |
| `--sort` | `relevan` | Urutan hasil Tokopedia: `relevan`, `termurah`, `termahal`, `terbaru`, `ulasan` |
| `--mitra10-store` | `18` (MITRA10 Q-BIG) | ID toko Mitra10 sumber harga |
| `--min-price` | – | Buang produk di bawah harga ini (mis. aksesoris murah) |
| `--deskripsi` | mati | Ambil juga deskripsi produk ke kolom `description` (bagian 6.1) |
| `--deskripsi-maks` | `10` | Maks produk relevan per kata kunci per situs yang diambil deskripsinya (Tokopedia/Depo Bangunan; `0` = semua). Mitra10 selalu semua |
| `--show-browser` | mati | Tampilkan jendela browser Mitra10 (untuk debug) |
| `-v`, `--verbose` | mati | Log level DEBUG |

### 3.2 Perintah khusus

```bash
python main.py mitra10-stores   # daftar 61 toko Mitra10: ID, nama, alamat
python main.py shopee-login     # buka Shopee untuk login manual (lihat 5.4)

# Isi kolom description ke file hasil yang sudah ada (tanpa scraping ulang).
# Hasil ke <file>_deskripsi.xlsx; file asli tidak diubah. Lihat bagian 6.1.
python main.py deskripsi output/harga_material_20261021.xlsx
python main.py deskripsi output/harga_material_20261021.xlsx --maks 0   # semua produk relevan
```

### 3.3 Hasil dan kode keluar

Di akhir, script mencetak jumlah produk per situs beserta jumlah yang relevan, dan daftar
kata kunci yang gagal (bila ada). Satu kata kunci yang gagal tidak menghentikan kata
kunci lain. Situs yang gagal dibuka (mis. Shopee belum login) dilewati.

| Kode keluar | Arti |
|---|---|
| `0` | Ada produk tersimpan |
| `1` | Jalan selesai tapi tidak ada produk sama sekali |
| `2` | Tidak ada kata kunci (lupa `-k`/`-f`) |

Untuk jalan panjang, simpan log ke file:

```bash
python main.py -f keywords.txt -o output/harga.xlsx > output/scrape.log 2>&1
```

---

## 4. Struktur proyek dan alur kerja

```
main.py                 CLI: baca argumen & kata kunci, jalankan scraper, beri penanda, simpan
keywords.txt            daftar kata kunci (satu per baris, '#' = komentar)
requirements.txt
scraper/
  models.py             dataclass Product = satu baris output (urutan field = urutan kolom)
  utils.py              user agent, parse rupiah, jeda acak antar request
  relevance.py          penanda relevan/match_score
  description.py        pengisi kolom description (memilih produk, paralel, cache per URL)
  mitra10.py            scraper Mitra10
  depobangunan.py       scraper Depo Bangunan
  tokopedia.py          scraper Tokopedia
  shopee.py             scraper Shopee + login interaktif
output/                 hasil & log (diabaikan git)
.browser-profile/       sesi login Shopee (diabaikan git, JANGAN dibagikan)
```

Alur satu kali jalan:

```
keywords.txt / -k
      │
      ▼
untuk tiap situs ──► buka scraper (context manager: browser/HTTP client)
      │                 │
      │                 └─ untuk tiap kata kunci: search(kw, max_pages) → list[Product]
      │                    (jeda acak 1,5–3,5 dtk antar kata kunci)
      ▼
filter --min-price  →  relevance.score() mengisi relevant & match_score  →  simpan CSV/XLSX
```

Setiap scraper punya antarmuka yang sama: kelas dengan atribut `name`, dipakai sebagai
context manager (`with ... as scraper`), dan method `search(keyword, max_pages) -> list[Product]`.
Menambah situs baru = membuat modul dengan antarmuka ini, lalu mendaftarkannya di
`SITES` dan `build_scraper()` di `main.py`.

---

## 5. Detail per situs

Bagian ini menjelaskan cara tiap scraper bekerja dan **bagian mana yang paling mungkin
rusak** bila situs berubah.

### 5.1 Mitra10 (`scraper/mitra10.py`)

**Cara kerja:**
1. Saat dibuka, scraper mengambil daftar toko dari GraphQL Mitra10
   (`web.mitra10.com/graphql`, query `storeSwitcher`) dan memastikan `--mitra10-store` valid.
2. Untuk tiap halaman, Playwright membuka `www.mitra10.com/catalogsearch/result?q=<kw>&page=<n>`
   dan menangkap respons API pencarian WizSearch (`api.wizsearch.in/v1/products/...`).
   - Halaman 1 memanggil `/products/search`, halaman 2+ memanggil `/products/filter`.
   - Satu halaman bisa memanggil API dua kali (versi `page:1` dan versi `filters.page:N`,
     urutannya acak). Scraper menunggu respons yang nomor halamannya cocok (`_requested_page`).
   - API key WizSearch disisipkan JavaScript situs dan bisa berganti, jadi sengaja
     **tidak** di-hardcode. Browser yang mengirimnya.
3. Harga dari hasil pencarian adalah **harga dasar katalog**, bukan harga yang dibayar
   pembeli. Karena itu, setelah tiap halaman, scraper mengambil harga toko terpilih untuk
   semua produk sekaligus (GraphQL `products(filter: {url_key: {in: [...]}})` →
   `vendor_product_data(selectedStore: <id>)`).
   - `price` = `vendor_special_price` (atau `flash_sale_price` bila periode flash sale
     sedang berlaku), `original_price` = `vendor_cost`.
   - `in_stock` = `vendor_stock > 0`. `False` tampil sebagai "Pre-Order" di situs.
   - Bila sebuah produk tidak punya harga toko, harga katalog yang dipakai dan log
     mencatat `WARNING ... tanpa harga toko`.
4. URL produk: API memberi URL backend Magento (`web.mitra10.com/<slug>.html`). Halaman
   publiknya adalah `www.mitra10.com/product/<slug>` (`_product_url`).

**Contoh perbedaan harga katalog vs harga toko** (Cendana Prime White 25 Kg): katalog
Rp629.900, toko Q-BIG Rp861.544.

**Toko default 18 (MITRA10 Q-BIG)** adalah toko yang dipakai situs untuk pengunjung yang
belum memilih lokasi.

**Yang paling mungkin rusak:** konstanta `API_MARKER`, bentuk body request WizSearch
(`_requested_page`), format URL halaman produk, dan nama field GraphQL
`vendor_product_data`.

### 5.2 Depo Bangunan (`scraper/depobangunan.py`)

**Cara kerja:** situs Magento yang merender hasil pencarian di server. Scraper mengambil
`www.depobangunan.co.id/catalogsearch/result/?q=<kw>&p=<n>` dengan HTTP biasa dan mem-parse
`li.product-item`:
- `price` dari `[data-price-type="finalPrice"]` (atribut `data-price-amount`), dan
  `original_price` dari `oldPrice`.
- `sold` dari `.sold-qty-count`.
- Elemen product-item template tanpa nama dilewati.
- Paginasi berhenti saat halaman tidak memberi produk baru (Magento mengulang halaman
  terakhir bila `p` kelebihan).

**Sifat pencarian situs:** semua kata harus ada di nama produk, dan katalognya kecil
(±25 hasil per kata kunci). Kata kunci spesifik sering tidak memberi hasil. Contohnya,
"kabel nym 3x2.5 eterna 50 meter" tidak ada hasil, sedangkan "kabel nym" ada 8. Dari 99
kata kunci, hanya 20 yang ada hasilnya di Depo Bangunan. Ini **bukan** pemblokiran.

**Yang paling mungkin rusak:** selector CSS (`li.product-item`, `a.product-item-link`,
`data-price-type`).

### 5.3 Tokopedia (`scraper/tokopedia.py`)

**Cara kerja:** memanggil endpoint GraphQL yang juga dipakai halaman pencarian web,
`gql.tokopedia.com/graphql/SearchProductV5Query`, dengan header `X-Source: tokopedia-lite`,
`X-Tkpd-Lite-Service: zeus`, `X-Device: desktop-0.0`. Tidak perlu browser.
- 60 produk per halaman (`rows=60`, `start=(halaman-1)*60`).
- `--sort` dipetakan ke parameter `ob` (`SORT_OPTIONS`).
- `sold` dari `labelGroups` posisi `ri_product_credibility` (mis. "250+").
- `promo` dari `labelGroups` posisi `promotion_label` (mis. "Harga Diskon").
- `discount_percent` dari `price.discountPercentage`, atau dari label pita `ri_ribbon` ("38%").
- Parameter tracking dibuang dari URL produk.

**Catatan harga:** yang diambil adalah harga umum. Browser yang dianggap "Pembeli Baru"
melihat harga lebih murah (contoh: Rp485.495 vs Rp460.495) karena potongan sekali pakai.
Ini sudah ditelusuri: bukan karena lokasi, cookie, atau header `x-price-center`.

**Yang paling mungkin rusak:** endpoint ini tidak resmi. Nama operasi, field GraphQL,
atau header wajibnya bisa berubah tanpa pemberitahuan. Bila semua kata kunci Tokopedia
gagal dengan `Tokopedia GraphQL error`, buka pencarian Tokopedia di browser, lalu
bandingkan request `SearchProductV5Query` yang dikirim browser dengan `QUERY` di modul ini.

### 5.4 Shopee (`scraper/shopee.py`)

**Status: belum pernah berhasil mengambil data.** Shopee mengalihkan browser otomatis
yang belum login ke `/verify/traffic`. Tanpa login, scraper berhenti dengan error
`ShopeeBlocked` yang jelas (sudah diuji), dan situs lain tetap jalan.

**Cara pakai:**
1. `python main.py shopee-login` membuka jendela Chromium. **Login dan selesaikan
   verifikasi sendiri secara manual**, lalu tekan Enter di terminal. Sesi tersimpan di
   `.browser-profile/shopee/`.
2. `python main.py -f keywords.txt -s shopee`. Browser akan tampil (bukan headless),
   karena mode headless lebih sering diblokir.

**Cara kerja:** membuka `shopee.co.id/search?keyword=<kw>&page=<n>` dan menangkap respons
`/api/v4/search/search_items`. Harga Shopee dalam satuan 1/100.000 rupiah
(`PRICE_DIVISOR`).

**Kepatuhan:** ketentuan layanan Shopee melarang pengambilan data otomatis, dan akun
bisa dibatasi. Script ini sengaja **tidak** mem-bypass CAPTCHA atau verifikasi. Pakai
halaman sedikit dan pertimbangkan akun terpisah. Karena belum pernah diuji dengan login,
pemetaan field (`_to_product`) perlu diverifikasi pada jalan pertama.

---

## 6. Skema output

Satu baris = satu produk hasil pencarian untuk satu kata kunci di satu situs. Produk
yang sama bisa muncul lebih dari sekali bila cocok dengan beberapa kata kunci.

| Kolom | Tipe | Arti |
|---|---|---|
| `source` | teks | `mitra10`, `depobangunan`, `tokopedia`, `shopee` |
| `keyword` | teks | Kata kunci yang menghasilkan baris ini |
| `name` | teks | Nama produk di situs |
| `price` | angka (Rp) | Harga jual saat scraping (lihat bagian 9) |
| `url` | teks | Link halaman produk |
| `relevant` | True/False | Apakah produk cocok dengan kata kunci (bagian 7) |
| `match_score` | 0–1 | Porsi kata kunci yang ada di nama produk |
| `original_price` | angka (Rp) | Harga sebelum diskon/harga coret, kosong bila tidak ada diskon |
| `discount_percent` | angka | Persen diskon |
| `promo` | teks | Label promo (Tokopedia saja) |
| `brand` | teks | Merek (Mitra10 saja) |
| `seller` | teks | Nama toko. Mitra10: nama cabang sumber harga |
| `location` | teks | Kota toko (Tokopedia/Shopee) |
| `rating` | angka | Rating bintang |
| `sold` | teks | Jumlah terjual apa adanya dari situs (mis. "250+", "10rb+") |
| `in_stock` | True/False | Ketersediaan (Mitra10: stok di cabang terpilih) |
| `image` | teks | URL gambar |
| `scraped_at` | teks | Waktu pengambilan (ISO 8601) |

**Keterisian kolom per situs** (diukur dari jalan 15 Oktober 2026, 6.973 baris):

| Kolom | Mitra10 | Depo Bangunan | Tokopedia |
|---|---|---|---|
| `original_price` / `discount_percent` | 81% | 72% | 13% / 9% |
| `brand` | 96% | – | – |
| `location` | – | – | 100% |
| `rating` | 2% | – | 83% |
| `sold` | – | 100% | 87% |
| `in_stock` | 100% | – | – |
| `promo` | – | – | 3% |

Kolom lain terisi 100% di ketiga situs. Urutan kolom ditentukan oleh urutan field di
`scraper/models.py`. Kolom `description` (paling kanan) hanya terisi bila diminta
(bagian 6.1).

### 6.1 Kolom `description` (deskripsi produk)

Deskripsi berguna untuk analisa yang lebih detail, misalnya **daya sebar cat**
("Daya sebar teoritis 10–12 m²/kg/lapis"), isi kemasan, mutu beton, atau standar SNI.
Deskripsi tidak ada di hasil pencarian, jadi diambil dari halaman produk:

| Situs | Sumber | Yang diambil | Kecepatan |
|---|---|---|---|
| Mitra10 | GraphQL `description` + `short_description`, 50 produk per request | **Semua** produk | ±10 dtk per 500 produk |
| Depo Bangunan | Halaman produk: deskripsi + tabel "Product Spesifikasi" (tipe, ukuran, merek, material, finishing) | Produk relevan, maks N per kata kunci | ±2–3 dtk per produk |
| Tokopedia | Halaman produk (dirender server), elemen `lblPDPDescriptionProduk` | Produk relevan, maks N per kata kunci | ±2 dtk per produk (3 paralel) |
| Shopee | – | Belum didukung | – |

- N diatur dengan `--deskripsi-maks` (scraping baru) atau `--maks` (perintah
  `deskripsi`), default 10, `0` = semua. Produk diambil urut hasil pencarian. URL yang
  sama hanya diambil sekali.
- **Perkiraan waktu** untuk hasil 21 Oktober (204 kata kunci): N=10 → ±2.000 halaman
  Tokopedia ≈ 1–1,5 jam; N=0 → ±10.000 halaman ≈ 5–6 jam.
- Server Tokopedia lambat (rata-rata ±4,5 dtk per halaman) dan ±1 dari 4–8 permintaan
  dibalas kerangka halaman kosong (±22 KB, bukan halaman lengkap ±250 KB). Setiap
  halaman dicoba ulang sampai 3 kali.
- Deskripsi kosong bisa berarti penjual memang tidak mengisi deskripsinya (elemen
  deskripsi hanya berisi `<br/>`).
- Teks deskripsi apa adanya dari penjual. Sering diawali salam toko atau info
  pengiriman, dan klaim spesifikasi tidak diverifikasi. Teks dipotong di 32.000 karakter
  (batas sel Excel).

---

## 7. Penanda relevansi (`scraper/relevance.py`)

**Masalahnya:** pencarian situs tetap mengembalikan produk lain bila barang yang dicari
tidak dijual. Ini paling parah di Mitra10. Contohnya, "tabung freon r32" memunculkan
mesin cuci 2 tabung, dan "gypsum jayaboard 9mm" memunculkan papan Conwood. Baris seperti
itu **tidak dihapus**, hanya ditandai.

**Aturan:** kata kunci dipecah jadi token. Produk dianggap `relevant = True` bila:
1. minimal separuh token ada di nama produk. Untuk kata kunci 1–2 token, semua token
   wajib ada (supaya "pasir beton" tidak meloloskan "mesin bor beton"); **dan**
2. semua token spesifikasi yang mengandung angka cocok persis. Jadi keramik 20x40 tidak
   lolos untuk "20x20", AC 1/2 PK tidak lolos untuk "1 PK", dan pipa 1 1/2" tidak lolos
   untuk "1/2".

Merek pengganti boleh lolos (kabel Supreme untuk kata kunci "eterna"), karena RAB juga
sering menulis "setara".

**Normalisasi yang dilakukan:** huruf kecil; `0,5` → `0.5`; `20 x 20` → `20x20`;
`9 mm` → `9mm`; `4"`/`4" inch`/`4 inch` → `4inch`; `650 liter`/`650 L` → `650l`;
`1-2`/`1:2` → `1/2`; `1 1/2` dibedakan dari `1/2`. Kata satuan jual (`per`, `kubik`, `lembar`, `meter`, `tebal`) dan angka pendek
lepas ("12" di "12 meter") diabaikan. Ejaan lain ada di `SYNONYMS` (kran/keran,
kloset/closet, kompon/compound, dll.). Merek yang ditulis terpisah ("AQUA PROOF") tetap
cocok dengan "aquaproof".

**Akurasi terukur** (sampel acak, 15 Oktober 2026):

| Situs | Ditandai relevan | Sampel `True` yang benar | Sampel `False` yang benar |
|---|---|---|---|
| Tokopedia | 97% | 20/20 | sebagian besar; pola salah yang ditemukan sudah diperbaiki |
| Depo Bangunan | 87% | 8/8 | – |
| Mitra10 | 23% | **17/20** | 15/15 |

Untuk Mitra10, setelah filter `relevant = True` tetap periksa sekilas. Contoh yang masih
lolos keliru: "pipa ac hoda" meloloskan unit AC, "handle pintu huben" meloloskan pintu
PVC berikut handle-nya.

**Menandai ulang file hasil lama** (mis. setelah aturan diubah), tanpa scraping ulang:

```bash
python - <<'EOF'
import pathlib
from openpyxl import load_workbook
from scraper.models import Product
from scraper import relevance
from main import save

path = "output/harga_material_20261015.xlsx"
rows = list(load_workbook(path, read_only=True).active.iter_rows(values_only=True))
products = [Product(**dict(zip(rows[0], r))) for r in rows[1:]]
for p in products:
    p.match_score, p.relevant = relevance.score(p.keyword, p.name)
save(products, pathlib.Path(path))
EOF
```

Kalau aturan diubah, tambahkan kasus uji dari data nyata (pasangan kata kunci, nama
produk, dan hasil yang diharapkan) dan pastikan kasus lama tetap benar.

---

## 8. Kata kunci (`keywords*.txt`)

- Satu kata kunci per baris. Baris diawali `#` diabaikan (dipakai untuk judul kategori
  dan catatan).
- Ada dua daftar:

| File | Isi | Sumber |
|---|---|---|
| `keywords.txt` | 99 kata kunci, 11 kategori | `Compile Gedung All Auditor.xlsx`, diklasifikasikan dari uraian & spesifikasi |
| `keywords_20261021.txt` | 204 kata kunci, 12 kategori | `Compile Gedung Part 2 - 16 Oct 26 - Kategori Material.xlsx`, sheet `Compile All Auditor - Kategori` (kolom Material, Merk, Tipe / Seri, Ukuran / Detail) |

  Kolom Merk/Ukuran di file Part 2 diisi otomatis dan cukup sering salah tempel (mis.
  keramik bermerk "Sika", gypsum bermerk "Vinilex"), jadi kata kunci disusun per material
  hanya dengan merek/ukuran yang cocok untuk material itu, dan masing-masing harus
  didukung minimal 2 baris data. Kolom "Keyword Scraping" bawaan file (1.870 kata kunci)
  tidak dipakai langsung karena memuat jasa ("jasa furniture custom hpl per meter") dan
  hasil salah kategori ("cermin taco 9mm" untuk multiplek + HPL).
- Daftar baru dibuat sebagai file bertanggal; daftar lama tidak diubah.

**Asal-usul `keywords.txt`:** setiap baris file audit diklasifikasikan berdasarkan uraian dan
spesifikasinya. Spesifikasi biasanya ditulis "ex <merek> <tipe/ukuran>", misalnya
"ex Vinilex S300" atau "ex eterna, NYM 3 x 2,5 mm2". Merek dan ukuran yang paling sering
dipakai dijadikan kata kunci. Lalu setiap kata kunci diuji di Tokopedia, dan yang hasilnya
melenceng diganti dengan versi lebih spesifik. Contohnya, "bata merah" memunculkan kaos,
lalu diganti "bata merah press".

**Sengaja tidak dimasukkan:**
- Pekerjaan non-material: mobilisasi/persiapan, keamanan & kebersihan, jasa kontraktor,
  bongkar, servis/perbaikan, furnitur custom, signage/stiker, roller blind, peralatan
  elektronik, pekerjaan tanah.
- Material yang kurang cocok dicari online:
  - kaca polos/tempered/cermin (dipotong sesuai ukuran di toko kaca),
  - kusen aluminium Alexindo (hasilnya profil umum),
  - pintu PVC kamar mandi (hasilnya tirai/karpet).

**Tips menambah kata kunci:**
- Pakai merek + ukuran ("semen tiga roda 50kg", bukan "semen").
- Tambahkan satuan jual bila hasil bercampur aksesoris ("besi ulir 13mm 12 meter",
  "bata ringan per kubik").
- Coba dulu dengan `python main.py -k "<kata kunci>" -s tokopedia`, lalu cek nama produk
  teratasnya.
- Tiap kata kunci menambah ±3–10 detik per situs.

---

## 9. Interpretasi harga (penting sebelum analisa)

- **Satuan jual tidak seragam.** Semen sering dijual per DO (100–200 sak), pasir dan bata
  ringan per kubik/truk, kabel per roll 50 meter, gypsum per lembar. Kolom `price` adalah
  harga listing apa adanya. Normalisasi satuan **belum** dilakukan dan direncanakan di
  tahap pencocokan dengan data master (bagian 12).
- **Harga RAB di file audit umumnya harga pekerjaan terpasang** (material + upah +
  material bantu, per m²/m'/unit), bukan harga material saja. Membandingkannya dengan
  harga scraping butuh analisa kebutuhan material per satuan pekerjaan.
- **Mitra10:** harga per toko (bagian 5.1). Bandingkan hanya dengan toko yang sama, atau
  jalankan ulang dengan `--mitra10-store` lain.
- **Tokopedia:** harga umum, tanpa potongan pembeli baru (bagian 5.3). Listing
  marketplace termasuk penjual eceran dan grosir, jadi sebarannya lebar. Pakai median,
  bukan nilai minimum.
- **Harga berubah setiap saat.** `scraped_at` mencatat waktu pengambilan.

---

## 10. Etika, keamanan, dan kepatuhan

- **Jeda antar request.**
  - Antar kata kunci dan antar halaman: jeda acak 1,5–3,5 detik.
  - Antar halaman Shopee: 3–6 detik.
  - Jangan diperkecil, supaya tidak membebani server dan tidak diblokir.
- **Tidak ada bypass CAPTCHA/verifikasi.** Bila situs meminta verifikasi, prosesnya
  berhenti dengan pesan yang jelas.
- **Tidak ada kredensial di kode.** API key WizSearch (Mitra10) diambil oleh browser saat
  runtime, tidak disimpan.
- **`.browser-profile/` berisi cookie login Shopee.** Folder ini jangan di-commit, jangan
  dibagikan, dan jangan disalin ke mesin lain. Sudah masuk `.gitignore`.
- **Shopee melarang scraping** di ketentuan layanannya (bagian 5.4). Keputusan memakai
  modul Shopee ada di pemilik akun.
- **Data yang diambil hanya informasi produk publik** (nama, harga, toko). Tidak ada data
  pribadi pembeli.

---

## 11. Pemeliharaan dan troubleshooting

| Gejala | Kemungkinan penyebab | Tindakan |
|---|---|---|
| Mitra10: `Timeout 45000ms exceeded while waiting for event "response"` | Endpoint WizSearch atau bentuk request-nya berubah | Jalankan dengan `--show-browser -v`, buka DevTools, cari request ke `wizsearch`, sesuaikan `API_MARKER`/`_requested_page` |
| Mitra10: banyak `WARNING ... tanpa harga toko` | Query `vendor_product_data` berubah, atau produk memang tidak dijual di toko itu | Cek satu produk di halaman produknya. Bila semua produk kena, periksa GraphQL `STORE_PRICE_QUERY` |
| Mitra10: `ID toko Mitra10 ... tidak ada` | Toko tutup/ID berubah | `python main.py mitra10-stores` |
| Depo Bangunan: semua kata kunci 0 produk | Selector HTML berubah | Buka halaman pencarian di browser, cek class `product-item` & atribut `data-price-amount` |
| Depo Bangunan: sebagian kata kunci 0 produk | Normal: pencarian ketat & katalog kecil (5.2) | Pakai kata kunci lebih pendek bila perlu |
| Tokopedia: `Tokopedia GraphQL error` / HTTP 4xx | Query/header GraphQL berubah | Bandingkan dengan request asli browser (5.3) |
| Shopee: `ShopeeBlocked` | Belum login / sesi kedaluwarsa / terdeteksi bot | `python main.py shopee-login` |
| Banyak produk tidak relevan | Kata kunci terlalu umum, atau barang tidak dijual di situs itu | Filter `relevant = True`, perbaiki kata kunci (bagian 8) |
| Deskripsi: `... gagal berturut-turut, berhenti` | Situs menolak/membatasi permintaan halaman produk | Tunggu beberapa saat, jalankan ulang `main.py deskripsi` pada file hasilnya (baris yang sudah terisi dilewati) |
| Deskripsi Tokopedia banyak yang kosong | Elemen `lblPDPDescriptionProduk` berganti nama, atau kerangka kosong makin sering | Buka satu halaman produk, cek elemen deskripsinya; sesuaikan `fetch_description` di `scraper/tokopedia.py` |

**Checklist verifikasi setelah mengubah scraper** (kesalahan yang pernah terjadi selama
pengembangan dan baru ketahuan lewat pengecekan ini):
1. **Link valid.** Buka beberapa URL hasil di browser. Status HTTP saja tidak cukup:
   Tokopedia membalas 200 juga untuk link palsu. Pernah terjadi: semua link Mitra10 404
   karena format URL salah.
2. **Harga cocok dengan halaman produk.** Pernah terjadi: harga Mitra10 ternyata harga
   katalog, bukan harga toko.
3. **Paginasi tidak menghasilkan duplikat.** Bandingkan jumlah baris dengan jumlah URL
   unik. Pernah terjadi: halaman 2–3 Mitra10 mengulang halaman 1.
4. **Nama produk teratas sesuai kata kunci.**

---

## 12. Batasan yang diketahui dan pekerjaan lanjutan

**Batasan:**
- Belum ada tes otomatis. Verifikasi selama ini dilakukan manual dengan checklist di
  bagian 11.
- Modul Shopee belum pernah diuji dengan akun login, dan belum mengambil deskripsi.
- Depo Bangunan tidak menyediakan merek dan status stok yang andal. `in_stock` hanya
  `False` bila tombol keranjang tidak ada.
- Penanda relevansi berbasis kata, bukan pemahaman makna. Ada salah tandai sekitar 15%
  untuk Mitra10 yang ditandai relevan (bagian 7).
- Semua endpoint yang dipakai tidak resmi dan bisa berubah tanpa pemberitahuan.

**Pekerjaan lanjutan yang sudah direncanakan:** mencocokkan hasil scraping dengan data
master pekerjaan (`Compile Gedung All Auditor.xlsx`), termasuk normalisasi satuan harga
(bagian 9).
