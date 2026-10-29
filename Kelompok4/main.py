"""
main.py - titik masuk program Penjadwalan Ujian (pewarnaan graf / CSP).

Contoh:
  python main.py --input inputs/contoh.csv --algo all
  python main.py --input inputs/contoh.csv --algo mrv_fc --trace
  python main.py --input inputs/empat_sesi.json --algo all --repeat 5 --log results/empat_sesi.txt
"""

import argparse
import json
import re
import sys
import time

from algorithms import (STRATEGIES, build_csp, count_solutions, solve,
                        violated_constraints)

# --------------------------------------------------------------------------
# PARAMETER (satu tempat). Semuanya bisa ditimpa lewat argumen CLI.
# --------------------------------------------------------------------------
DEFAULT_SESSIONS = ["S1", "S2", "S3"]   # domain (urutan = urutan percobaan nilai)
DEFAULT_VAR_ORDER = "alpha"             # alpha | given | reverse (juga tie-break MRV)
DEFAULT_VALUE_ORDER = "asc"             # asc | desc
DEFAULT_REPEAT = 1                      # ulang pengukuran waktu (tugas minta >= 5)


class InputError(Exception):
    """Kesalahan format/isi file input."""


# --------------------------------------------------------------------------
# Membaca input
# --------------------------------------------------------------------------
PAIR_RE = re.compile(r"([A-Za-z0-9_\-]+)\s*,\s*([A-Za-z0-9_\-]+)")


def load_csv_like(path):
    """CSV/TXT: pasangan 'X,Y'; satu atau beberapa pasangan per baris, baris '#...' diabaikan."""
    courses, conflicts = [], []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            pairs = PAIR_RE.findall(line)
            leftover = PAIR_RE.sub("", line).strip()
            if not pairs or leftover:
                raise InputError(
                    f"{path}, baris {lineno}: format tidak dikenali -> {raw.strip()!r} "
                    f"(harapan: pasangan 'X,Y' dipisah spasi)")
            for x, y in pairs:
                conflicts.append((x, y))
    for x, y in conflicts:
        for c in (x, y):
            if c not in courses:
                courses.append(c)
    return courses, conflicts, None


def load_json(path):
    """JSON: {"courses": [...] (opsional), "sessions": [...] (opsional), "conflicts": [[X,Y],...]}"""
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise InputError(f"{path}: JSON tidak valid ({e})")
    if not isinstance(data, dict) or "conflicts" not in data:
        raise InputError(f"{path}: JSON harus berupa objek dengan kunci 'conflicts'")
    conflicts = []
    for item in data["conflicts"]:
        if not (isinstance(item, (list, tuple)) and len(item) == 2):
            raise InputError(f"{path}: setiap konflik harus pasangan [X, Y], ditemukan {item!r}")
        conflicts.append((str(item[0]), str(item[1])))
    courses = [str(c) for c in data.get("courses", [])]
    for x, y in conflicts:
        for c in (x, y):
            if c not in courses:
                courses.append(c)
    sessions = [str(s) for s in data["sessions"]] if "sessions" in data else None
    return courses, conflicts, sessions


def load_input(path):
    try:
        if path.lower().endswith(".json"):
            courses, conflicts, sessions = load_json(path)
        else:
            courses, conflicts, sessions = load_csv_like(path)
    except FileNotFoundError:
        raise InputError(f"File input tidak ditemukan: {path}")
    if not conflicts and not courses:
        raise InputError(f"{path}: tidak ada data mata kuliah/bentrok")
    for x, y in conflicts:
        if x == y:
            raise InputError(f"{path}: mata kuliah bentrok dengan dirinya sendiri ({x},{y})")
    return courses, conflicts, sessions


# --------------------------------------------------------------------------
# Menjalankan & mencetak
# --------------------------------------------------------------------------
def run_strategy(csp, key, repeat, trace, log):
    spec = STRATEGIES[key]
    first = None
    times = []
    for i in range(repeat):
        t0 = time.perf_counter()
        res = solve(csp, spec["use_mrv"], spec["use_fc"],
                    trace=(trace and i == 0), log=log)
        times.append((time.perf_counter() - t0) * 1000)
        if first is None:
            first = res
    return first, sum(times) / len(times)


def print_summary(csp, key, res, avg_ms, repeat, log):
    spec = STRATEGIES[key]
    log(f"=== {spec['label']} ({key}) ===")
    if res.solution is not None:
        bad = violated_constraints(csp, res.solution)
        log("Status      : FEASIBLE (jadwal sah ditemukan)")
        for s in sorted(set(csp.sessions), key=csp.sessions.index):
            members = [v for v in csp.variables if res.solution[v] == s]
            log(f"  {s}: {', '.join(sorted(members)) if members else '-'}")
        log(f"Constraint dilanggar (verifikasi akhir): {bad if bad else 'tidak ada'}")
    else:
        log("Status      : TIDAK FEASIBLE - tidak ada jadwal sah untuk data & jumlah sesi ini")
        f = res.failure
        if f:
            log(f"Penyebab    : {f['variable']} tidak mendapat sesi pada percabangan terdalam")
            for var, nb, s in f["blocked_by"]:
                log(f"  constraint ({var},{nb}) menutup {s} karena {nb} sudah di {s}")
    log(f"Assignment  : {res.stats.assignments}")
    log(f"Backtrack   : {res.stats.backtracks}")
    log(f"Nilai dicoret FC: {res.stats.pruned}")
    log(f"Waktu       : {avg_ms:.4f} ms (rata-rata {repeat}x)")
    log("")


def main(argv=None):
    p = argparse.ArgumentParser(description="Penjadwalan ujian sebagai CSP / pewarnaan graf")
    p.add_argument("--input", required=True, help="file input (.csv/.txt/.json)")
    p.add_argument("--algo", default="all", choices=list(STRATEGIES) + ["all"],
                   help="strategi: bt, mrv, fc, mrv_fc, atau all (default)")
    p.add_argument("--sessions", help="daftar sesi dipisah koma, mis. S1,S2,S3,S4")
    p.add_argument("--num-sessions", type=int, help="jumlah sesi (membuat S1..SN)")
    p.add_argument("--var-order", choices=["alpha", "given", "reverse"], default=None)
    p.add_argument("--value-order", choices=["asc", "desc"], default=None)
    p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT,
                   help="ulangi pengukuran waktu N kali, laporkan rata-rata")
    p.add_argument("--count-all", action="store_true", help="hitung semua jadwal sah")
    p.add_argument("--trace", action="store_true", help="cetak proses langkah demi langkah")
    p.add_argument("--log", help="simpan keluaran ke file ini (ditambahkan di akhir)")
    args = p.parse_args(argv)

    out_lines = []

    def log(msg=""):
        print(msg)
        out_lines.append(str(msg))

    try:
        if args.repeat < 1:
            raise InputError("--repeat harus >= 1")
        courses, conflicts, file_sessions = load_input(args.input)
        # prioritas sesi: CLI > file input > default di atas
        if args.sessions:
            sessions = [s.strip() for s in args.sessions.split(",") if s.strip()]
        elif args.num_sessions:
            sessions = [f"S{i}" for i in range(1, args.num_sessions + 1)]
        else:
            sessions = file_sessions or DEFAULT_SESSIONS
        if not sessions or len(set(sessions)) != len(sessions):
            raise InputError("daftar sesi kosong atau ada sesi ganda")
        csp = build_csp(courses, conflicts, sessions,
                        var_order=args.var_order or DEFAULT_VAR_ORDER,
                        value_order=args.value_order or DEFAULT_VALUE_ORDER)
    except InputError as e:
        print(f"[ERROR input] {e}", file=sys.stderr)
        return 2

    log(f"Input       : {args.input}")
    log(f"Mata kuliah : {len(csp.variables)}  | Bentrok (edge): {len(csp.edges)}  "
        f"| Sesi: {csp.sessions}")
    log(f"Urutan variabel: {csp.variables}")
    log("")

    keys = list(STRATEGIES) if args.algo == "all" else [args.algo]
    for key in keys:
        res, avg_ms = run_strategy(csp, key, args.repeat, args.trace, log)
        print_summary(csp, key, res, avg_ms, args.repeat, log)

    if args.count_all:
        log(f"Jumlah jadwal sah (semua kemungkinan): {count_solutions(csp)}")

    if args.log:
        with open(args.log, "a", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
