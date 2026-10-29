# Penjadwalan Ujian (Pewarnaan Graf / CSP)

Membandingkan empat strategi backtracking untuk menjadwalkan ujian ke dalam sesi
tanpa bentrok. Mata kuliah = variabel, sesi = domain, pasangan bentrok = constraint `X != Y`.

## Persyaratan
Python 3.10+ (tanpa dependensi eksternal, lihat `requirements.txt`).

## Cara menjalankan
```bash
# semua strategi sekaligus
python main.py --input inputs/contoh.csv --algo all

# satu strategi + mode trace (langkah demi langkah)
python main.py --input inputs/contoh.csv --algo mrv_fc --trace

# ulang pengukuran waktu 5x, simpan log ke results/
python main.py --input inputs/bentrok_ditambah.csv --algo all --repeat 5 --log results/bentrok_ditambah.txt

# ganti jumlah sesi tanpa mengubah kode / file input
python main.py --input inputs/contoh.csv --algo all --num-sessions 4

# hitung semua jadwal sah (verifikasi)
python main.py --input inputs/contoh.csv --count-all
```

## Pilihan `--algo`
| Kode | Strategi |
|---|---|
| `bt` | Backtracking polos |
| `mrv` | Backtracking + MRV/Degree (tanpa FC) |
| `fc` | Backtracking + Forward Checking (tanpa MRV) |
| `mrv_fc` | Backtracking + MRV/Degree + Forward Checking |
| `all` | keempatnya (default) |

## Parameter (ubah satu nilai, tanpa menulis ulang program)
| Parameter | Lokasi | Nilai |
|---|---|---|
| Daftar sesi | `--sessions S1,S2` / `--num-sessions N` / kunci `sessions` di JSON / `DEFAULT_SESSIONS` di `main.py` | urutan sesi = urutan percobaan nilai |
| Urutan variabel (dan tie-break terakhir MRV) | `--var-order alpha\|given\|reverse` | default `alpha` |
| Urutan nilai | `--value-order asc\|desc` | default `asc` |
| Pengulangan waktu | `--repeat N` | default 1 (tugas meminta >= 5 untuk membandingkan waktu) |

Prioritas sesi: CLI > file input > default di `main.py`.

## Format input
**CSV/TXT**: satu atau beberapa pasangan `X,Y` per baris (dipisah spasi); baris/bagian setelah `#` diabaikan.
```
AI,BD   AI,GR
GR,MB
```
**JSON**: `{"courses": [...] (opsional), "sessions": [...] (opsional), "conflicts": [["X","Y"], ...]}`.
Gunakan `courses` bila ada mata kuliah tanpa bentrok sama sekali.

File contoh di `inputs/`: `contoh.csv`, `bentrok_ditambah.csv`, `empat_sesi.json`, `tanpa_solusi.json`.

## Keluaran
Jadwal akhir per sesi, jumlah assignment, jumlah backtrack, jumlah nilai yang dicoret FC,
verifikasi constraint, status feasible/tidak, dan waktu rata-rata. Bila tidak ada solusi,
program mencetak penyebab pada percabangan terdalam, bukan error. Kesalahan format input
dilaporkan dengan nomor baris dan kode keluar 2.

## Definisi hitungan (sesuai catatan tugas)
- **Assignment**: satu nilai yang lolos cek konsistensi lalu disimpan.
- **Backtrack**: satu assignment yang kemudian dibatalkan.
- **MRV**: variabel dengan domain tersimpan terkecil; seri -> degree terbesar (hanya tetangga
  yang belum terisi); seri lagi -> urutan variabel statis. Tanpa FC, domain tersimpan tidak
  pernah dicoret.
- **Forward checking**: setelah assignment, nilai itu dicoret dari domain tetangga yang belum
  terisi; domain kosong berarti assignment dibatalkan.

## Struktur
```
main.py          # CLI, baca input, jalankan & cetak ringkasan
algorithms.py    # model CSP, solver 4 strategi, penghitung semua solusi
inputs/          # file input contoh
results/         # log eksperimen (--log)
requirements.txt
README.md
```
