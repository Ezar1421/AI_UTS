from __future__ import annotations
"""
algorithms.py - Penjadwalan ujian sebagai CSP (pewarnaan graf).

Model:
  Variabel   : setiap mata kuliah
  Domain     : daftar sesi ujian (mis. S1, S2, S3)
  Constraint : untuk setiap pasangan bentrok (X, Y), sesi(X) != sesi(Y)

Strategi yang tersedia (kombinasi dua saklar: use_mrv dan use_fc):
  bt      : backtracking polos
  mrv     : backtracking + MRV/Degree
  fc      : backtracking + forward checking
  mrv_fc  : backtracking + MRV/Degree + forward checking

Definisi hitungan (sesuai catatan di tugas):
  assignment : satu nilai yang lolos cek konsistensi lalu disimpan ke assignment
  backtrack  : satu assignment yang kemudian dibatalkan
"""

from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# Model masalah
# --------------------------------------------------------------------------
@dataclass
class CSP:
    variables: list          # urutan variabel statis (dipakai backtracking polos)
    sessions: list           # domain awal, sudah dalam urutan percobaan nilai
    neighbors: dict          # variabel -> himpunan variabel yang bentrok
    edges: list              # daftar pasangan bentrok (X, Y) tanpa duplikat

    def degree(self, var):
        return len(self.neighbors[var])


def build_csp(courses, conflicts, sessions, var_order="alpha", value_order="asc"):
    """Bangun CSP dari data mentah.

    courses   : daftar mata kuliah sesuai urutan kemunculan di file
    conflicts : daftar pasangan (X, Y)
    sessions  : daftar sesi sesuai urutan di file/CLI
    var_order : 'alpha' | 'given' | 'reverse'
    value_order: 'asc' (sesuai urutan sesi) | 'desc' (dibalik)
    """
    if var_order == "alpha":
        variables = sorted(courses)
    elif var_order == "given":
        variables = list(courses)
    elif var_order == "reverse":
        variables = sorted(courses, reverse=True)
    else:
        raise ValueError(f"var_order tidak dikenal: {var_order!r}")

    if value_order == "asc":
        ordered_sessions = list(sessions)
    elif value_order == "desc":
        ordered_sessions = list(reversed(sessions))
    else:
        raise ValueError(f"value_order tidak dikenal: {value_order!r}")

    neighbors = {v: set() for v in variables}
    edges, seen = [], set()
    for x, y in conflicts:
        key = frozenset((x, y))
        if key in seen:
            continue
        seen.add(key)
        edges.append((x, y))
        neighbors[x].add(y)
        neighbors[y].add(x)
    return CSP(variables, ordered_sessions, neighbors, edges)


# --------------------------------------------------------------------------
# Hasil
# --------------------------------------------------------------------------
@dataclass
class Stats:
    assignments: int = 0
    backtracks: int = 0
    pruned: int = 0          # jumlah nilai yang dicoret oleh forward checking


@dataclass
class Result:
    solution: dict | None
    stats: Stats
    failure: dict | None = None   # info penyebab gagal (jika tidak ada solusi)


# --------------------------------------------------------------------------
# Solver
# --------------------------------------------------------------------------
def solve(csp, use_mrv=False, use_fc=False, trace=False, log=print):
    """Cari SATU jadwal sah. Mengembalikan Result."""
    rank = {s: i for i, s in enumerate(csp.sessions)}   # urutan percobaan nilai
    domains = {v: set(csp.sessions) for v in csp.variables}
    var_pos = {v: i for i, v in enumerate(csp.variables)}  # aturan tie-breaking akhir
    assignment = {}
    stats = Stats()
    deepest = {"depth": -1, "info": None}

    def legal_values(var):
        """Nilai di domain var yang tidak bentrok dengan tetangga yang sudah diisi."""
        used = {assignment[n] for n in csp.neighbors[var] if n in assignment}
        return sorted((s for s in domains[var] if s not in used), key=rank.get)

    def unassigned_degree(var):
        return sum(1 for n in csp.neighbors[var] if n not in assignment)

    def select_var():
        unassigned = [v for v in csp.variables if v not in assignment]
        if not use_mrv:
            return unassigned[0]                       # urutan statis
        # MRV: domain tersimpan paling kecil; seri -> degree terbesar (hanya
        # tetangga yang belum terisi); seri lagi -> urutan variabel statis.
        # Catatan: tanpa FC domain tersimpan tidak pernah dicoret, jadi semua
        # variabel berukuran sama dan pemilihan ditentukan oleh degree.
        return min(unassigned,
                   key=lambda v: (len(domains[v]), -unassigned_degree(v), var_pos[v]))

    def blockers(var):
        """Untuk tiap sesi, satu tetangga terisi yang memblokirnya (untuk laporan gagal)."""
        out = []
        for s in csp.sessions:
            for n in sorted(csp.neighbors[var]):
                if assignment.get(n) == s:
                    out.append((var, n, s))
                    break
        return out

    def note_failure(depth, var):
        if depth > deepest["depth"]:
            deepest["depth"] = depth
            deepest["info"] = {
                "variable": var,
                "partial": dict(assignment),
                "blocked_by": blockers(var),
            }

    def fmt_dom(var):
        return "{" + ",".join(sorted(domains[var], key=rank.get)) + "}"

    def rec(depth):
        if len(assignment) == len(csp.variables):
            return True
        var = select_var()
        values = legal_values(var)
        pad = "  " * depth
        if trace:
            log(f"{pad}pilih {var}  (nilai legal: {values}, "
                f"degree sisa: {unassigned_degree(var)})")
        if not values:
            note_failure(depth, var)
            if trace:
                log(f"{pad}  -> {var} tidak punya nilai legal, mundur")
            return False

        for val in values:
            assignment[var] = val
            stats.assignments += 1
            if trace:
                log(f"{pad}  assign {var}={val}  [assignment ke-{stats.assignments}]")

            pruned, ok = [], True
            if use_fc:
                for nb in sorted(csp.neighbors[var]):
                    if nb not in assignment and val in domains[nb]:
                        domains[nb].discard(val)
                        pruned.append((nb, val))
                        stats.pruned += 1
                        if not domains[nb]:
                            ok = False
                            note_failure(depth + 1, nb)
                            if trace:
                                log(f"{pad}    FC: coret {val} dari {nb} -> domain {nb} KOSONG")
                if trace and pruned and ok:
                    after = ", ".join(f"{n}{fmt_dom(n)}" for n in sorted({n for n, _ in pruned}))
                    log(f"{pad}    FC: coret {val} dari tetangga -> {after}")

            if ok and rec(depth + 1):
                return True

            # batalkan assignment ini
            for nb, v in pruned:
                domains[nb].add(v)
            del assignment[var]
            stats.backtracks += 1
            if trace:
                log(f"{pad}  batal {var}={val}  [backtrack ke-{stats.backtracks}]")
        return False

    if trace:
        log(f"urutan variabel statis : {csp.variables}")
        log(f"urutan nilai           : {csp.sessions}")
        log(f"MRV/Degree={use_mrv}  ForwardChecking={use_fc}")
    found = rec(0)
    if found:
        return Result(dict(assignment), stats)
    return Result(None, stats, deepest["info"])


def count_solutions(csp):
    """Hitung SEMUA jadwal sah (enumerasi sederhana, untuk verifikasi)."""
    assignment = {}

    def rec(i):
        if i == len(csp.variables):
            return 1
        var = csp.variables[i]
        total = 0
        for s in csp.sessions:
            if all(assignment.get(n) != s for n in csp.neighbors[var]):
                assignment[var] = s
                total += rec(i + 1)
                del assignment[var]
        return total

    return rec(0)


def violated_constraints(csp, schedule):
    """Pasangan bentrok yang berada di sesi sama pada jadwal (harus kosong)."""
    return [(x, y) for x, y in csp.edges if schedule.get(x) == schedule.get(y)]


STRATEGIES = {
    "bt":     dict(label="Backtracking polos",          use_mrv=False, use_fc=False),
    "mrv":    dict(label="BT + MRV/Degree saja",        use_mrv=True,  use_fc=False),
    "fc":     dict(label="BT + Forward Checking saja",  use_mrv=False, use_fc=True),
    "mrv_fc": dict(label="BT + MRV/Degree + FC",        use_mrv=True,  use_fc=True),
}
