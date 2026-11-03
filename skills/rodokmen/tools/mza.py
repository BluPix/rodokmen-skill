#!/usr/bin/env python3
"""Matriky Moravského zemského archivu v Brně (MZA Acta Publica / iipsrv Deepzoom) bezpečně a spolehlivě.

Použití (z kořene projektu):
  mza.py snimek <detail_id> <cislo_snimku> <vystup.jpg> [--nahled] [--crop x0,y0,x1,y1]
      detail_id     = ID matriky v URL (např. 14439 z https://www.mza.cz/actapublica/matrika/detail/14439)
      cislo_snimku  = 1-based číslo snímku (1..N)
      vystup.jpg    = kam snímek uložit
      --nahled      = stáhne rychlý náhled v menším rozlišení (~1000–1800 px, jen několik málo dlaždic)
      --crop x0,y0,x1,y1 = stáhne POUZE dlaždice pokrývající zadaný výřez (0..1 zlomky šířky a výšky).
                           Díky tomu se nestahuje celá dvoustrana (700+ dlaždic), ale jen cca 15–30 dlaždic!
  mza.py svazky "Obec" [N|O|Z] [rok] [--fara "Fara"]
      vypíše matriky, které obec obsahují: číslo knihy (signatura), fara, roky N/O/Z, počet snímků a detail_id.
      N/O/Z = jen knihy s narozenými / oddanými / zemřelými, rok = jen knihy, které ten rok pokrývají,
      --fara = jen knihy fary, jejíž název obsahuje daný text (u častých jmen obcí: Chlum, Lhota…).
  mza.py svazky --sig 11111
      totéž podle čísla knihy (signatury).

Bezpečnost a ohleduplnost k serveru MZA:
  - Používá HTTP/2 a přísné timeouty (--connect-timeout 8, --max-time 15).
  - Nikdy nezahltí server: omezuje souběh na max. 2–3 vlákna, ověřuje platnost JPEG hlaviček.
  - Při chybě 503/429 automaticky počká a zopakuje pokus.
"""
import base64, glob, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, time, urllib.parse
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    import cache
except ImportError:
    cache = None

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://www.mza.cz"
CHROME_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
COOKIE_FILE = os.path.join(tempfile.gettempdir(), "mza_cookies.txt")


def solve_altcha(referer):
    """Automatické vyřešení ALTCHA Proof-of-Work kontroly MZA v Pythonu (SHA-256 trvá ~0.2 s)."""
    cmd = [
        "curl", "-s", "--http2",
        "-c", COOKIE_FILE, "-b", COOKIE_FILE,
        "-H", f"User-Agent: {CHROME_UA}",
        "-H", f"Referer: {referer}",
        f"{BASE}/actapublica/altcha/challenge"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        ch = json.loads(res.stdout)
    except Exception as e:
        raise RuntimeError(f"Chyba při čtení ALTCHA challenge: {res.stdout[:200]}") from e

    salt = ch["salt"]
    target = ch["challenge"]
    max_n = ch.get("maxNumber", 1000000)
    found = None
    for n in range(max_n + 1):
        if hashlib.sha256((salt + str(n)).encode("utf-8")).hexdigest() == target:
            found = n
            break
    if found is None:
        raise RuntimeError("Nepodařilo se vyřešit ALTCHA kontrolu")

    payload = {
        "algorithm": ch["algorithm"],
        "challenge": ch["challenge"],
        "number": found,
        "salt": ch["salt"],
        "signature": ch["signature"]
    }
    b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    cmd2 = [
        "curl", "-s", "--http2",
        "-c", COOKIE_FILE, "-b", COOKIE_FILE,
        "-H", f"User-Agent: {CHROME_UA}",
        "-H", f"Referer: {referer}",
        "-H", "Accept: application/json",
        "-d", f"altcha={urllib.parse.quote(b64)}",
        f"{BASE}/actapublica/altcha/verify"
    ]
    res2 = subprocess.run(cmd2, capture_output=True, text=True)
    if '"ok":true' not in res2.stdout and '"ok": true' not in res2.stdout:
        raise RuntimeError(f"Ověření ALTCHA selhalo: {res2.stdout[:200]}")


def nahled_cesta(out_file):
    """Náhled se pozná podle názvu (…_nahled.jpg) – z náhledu se nesmí opisovat ani citovat, jen hledat rok, oddíl a řádek."""
    root, ext = os.path.splitext(out_file)
    return out_file if "nahled" in os.path.basename(root) else f"{root}_nahled{ext or '.jpg'}"


def magick():
    """Cesta k ImageMagicku."""
    m = (shutil.which("magick") or next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))), None)
         or (os.name != "nt" and shutil.which("convert")))
    if not m:
        sys.exit("Chybí ImageMagick (příkaz magick).")
    return m


def get_detail_page(detail_id, force=False):
    """Stáhne nebo načte z cache seznam snímků pro danou matriku."""
    cache_path = os.path.join(ROOT, "pracovni", f"mza_detail_{detail_id}.html")
    if not force and os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        # Tokeny v MZA od podzimu 2026 expirují po několika hodinách
        if time.time() - os.path.getmtime(cache_path) < 7200:
            with open(cache_path, "r", encoding="utf-8") as f:
                content = f.read()
                if "CreateSeadragon" in content and "altcha-gate" not in content and "/iip-srv/" in content:
                    return content

    url = f"{BASE}/actapublica/matrika/detail/{detail_id}"
    cmd = [
        "curl", "-s", "-L", "--http2",
        "--connect-timeout", "6", "--max-time", "20",
        "-c", COOKIE_FILE, "-b", COOKIE_FILE,
        "-H", f"User-Agent: {CHROME_UA}",
        "-H", "Referer: https://www.mza.cz/actapublica/matrika/hledani",
        url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if "altcha-gate" in res.stdout or "<altcha-widget" in res.stdout or "CreateSeadragon" not in res.stdout:
        solve_altcha(url)
        res = subprocess.run(cmd, capture_output=True, text=True)

    if len(res.stdout) > 1000 and "CreateSeadragon" in res.stdout:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(res.stdout)
        return res.stdout
    raise RuntimeError(f"Nepodařilo se stáhnout stránku detailu {detail_id} z MZA (kód {res.returncode}, délka {len(res.stdout)})")


def get_scan_dzi_urls(detail_id, force=False):
    """Vrátí seznam všech DZI adres pro dané detail_id."""
    html = get_detail_page(detail_id, force=force)
    # Hledáme CreateSeadragon([...])
    m = re.search(r'CreateSeadragon\(\s*(\[[^\]]+\])', html)
    if m:
        return json.loads(m.group(1))
    dzis = re.findall(r'https?://[^\s\"\'<>]+?\.dzi', html)
    if dzis:
        return dzis
    raise RuntimeError(f"V detailu {detail_id} se nepodařilo najít DZI odkazy snímků.")


def get_dzi_dimensions(dzi_url, referer):
    """Získá rozměry obrázku a velikost dlaždice z DZI XML."""
    cmd = [
        "curl", "-s", "--http2",
        "--connect-timeout", "5", "--max-time", "10",
        "-c", COOKIE_FILE, "-b", COOKIE_FILE,
        "-H", f"User-Agent: {CHROME_UA}",
        "-H", f"Referer: {referer}",
        dzi_url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    w_m = re.search(r'Width="(\d+)"', res.stdout)
    h_m = re.search(r'Height="(\d+)"', res.stdout)
    t_m = re.search(r'TileSize="(\d+)"', res.stdout)
    if not (w_m and h_m):
        raise RuntimeError(f"Nepodařilo se získat rozměry z DZI {dzi_url}: {res.stdout[:200]}")
    W = int(w_m.group(1))
    H = int(h_m.group(1))
    T = int(t_m.group(1)) if t_m else 256
    return W, H, T


def is_valid_jpeg(path):
    if os.path.exists(path) and os.path.getsize(path) > 200:
        try:
            with open(path, "rb") as f:
                return f.read(2) == b"\xff\xd8"
        except OSError:
            pass
    return False


def download_tile(url, out_path, referer, retries=2):
    """Stáhne jednu dlaždici samostatně (fallback), ověří JPEG hlavičku."""
    for attempt in range(retries):
        cmd = [
            "curl", "-s", "--http2",
            "--connect-timeout", "5", "--max-time", "10",
            "-c", COOKIE_FILE, "-b", COOKIE_FILE,
            "-H", f"User-Agent: {CHROME_UA}",
            "-H", f"Referer: {referer}",
            "-o", out_path,
            url
        ]
        subprocess.run(cmd)
        if is_valid_jpeg(out_path):
            return True
        time.sleep(0.5 * (attempt + 1))
    return False


def download_tiles_batch(items, referer):
    """Stáhne dávku dlaždic v jednom curl procesu (jedno HTTP/2 TLS spojení)."""
    if not items:
        return True
    cmd = [
        "curl", "-s", "--http2",
        "--connect-timeout", "5",
        "--max-time", str(max(10, len(items) * 3)),
        "-c", COOKIE_FILE, "-b", COOKIE_FILE,
        "-H", f"User-Agent: {CHROME_UA}",
        "-H", f"Referer: {referer}",
    ]
    for url, out_path in items:
        cmd.extend(["-o", out_path, url])
    subprocess.run(cmd)

    # Ověříme stažené dlaždice a případné chybějící dotáhneme jednotlivě
    for url, out_path in items:
        if not is_valid_jpeg(out_path):
            if not download_tile(url, out_path, referer):
                return False
    return True


def snimek(detail_id, scan_num, out_file, nahled=False, crop=None, dzi_urls=None, referer=None):
    """Stáhne snímek nebo jeho výřez. dzi_urls/referer předává scitani.py (sčítací operáty MZA mají stejný server)."""
    if crop is None and cache:
        klic = f"mza/{detail_id}/sn{int(scan_num):04d}{'-nahled' if nahled else ''}.jpg"
        cache.soubor(klic, out_file, lambda cil: _stahni_snimek(detail_id, scan_num, cil, nahled, None, dzi_urls, referer))
        return
    _stahni_snimek(detail_id, scan_num, out_file, nahled, crop, dzi_urls, referer)


def _stahni_snimek(detail_id, scan_num, out_file, nahled=False, crop=None, dzi_urls=None, referer=None):
    MAGICK = magick()
    referer = referer or f"{BASE}/actapublica/matrika/detail/{detail_id}"
    dzi_urls = dzi_urls or get_scan_dzi_urls(detail_id)
    if not (1 <= scan_num <= len(dzi_urls)):
        sys.exit(f"Číslo snímku {scan_num} je mimo rozsah (kniha má 1..{len(dzi_urls)} snímků).")

    dzi_url = dzi_urls[scan_num - 1]
    # Odstraníme .dzi na konci pro základ dlaždic
    base_tile_url = dzi_url[:-4] + "_files"

    try:
        W, H, T = get_dzi_dimensions(dzi_url, referer)
    except Exception:
        # Zkusíme obnovit detail (např. při vypršení časového tokenu v URL snímků)
        dzi_urls = get_scan_dzi_urls(detail_id, force=True)
        dzi_url = dzi_urls[scan_num - 1]
        base_tile_url = dzi_url[:-4] + "_files"
        W, H, T = get_dzi_dimensions(dzi_url, referer)
    max_level = math.ceil(math.log2(max(W, H)))

    if nahled:
        level = max(8, max_level - 2)
        scale = 2 ** (max_level - level)
        cur_w = math.ceil(W / scale)
        cur_h = math.ceil(H / scale)
        cols_range = range(math.ceil(cur_w / T))
        rows_range = range(math.ceil(cur_h / T))
        crop_box = None
    elif crop:
        level = max_level
        scale = 1
        x0, y0, x1, y1 = crop
        c_min = max(0, int(math.floor((x0 * W) / T)))
        c_max = min(int(math.ceil((x1 * W) / T)), math.ceil(W / T))
        r_min = max(0, int(math.floor((y0 * H) / T)))
        r_max = min(int(math.ceil((y1 * H) / T)), math.ceil(H / T))
        cols_range = range(c_min, c_max)
        rows_range = range(r_min, r_max)
        # Výsledné souřadnice uvnitř složeného obrázku dlaždic
        crop_box = (
            round(x0 * W - c_min * T),
            round(y0 * H - r_min * T),
            round((x1 - x0) * W),
            round((y1 - y0) * H)
        )
    else:
        level = max_level
        scale = 1
        cols_range = range(math.ceil(W / T))
        rows_range = range(math.ceil(H / T))
        crop_box = None

    total_tiles = len(cols_range) * len(rows_range)
    print(f"MZA detail {detail_id}, snímek {scan_num}/{len(dzi_urls)}: rozměry {W}x{H}, úroveň {level}, dlaždic {total_tiles} ({len(cols_range)}x{len(rows_range)})")

    tmp_dir = tempfile.mkdtemp(prefix="mza_tiles_")
    try:
        # Připravíme seznam všech dlaždic
        tile_jobs = []
        for r_idx, r in enumerate(rows_range):
            for c_idx, c in enumerate(cols_range):
                t_url = f"{base_tile_url}/{level}/{c}_{r}.jpg"
                t_file = os.path.join(tmp_dir, f"{r_idx:03d}_{c_idx:03d}.jpg")
                tile_jobs.append((t_url, t_file))

        # Stahování dlaždic v dávkách po 10 přes jedno HTTP/2 spojení (recykluje TLS)
        # s pauzou mezi dávkami, aby server nebyl přetížen nárazově.
        BATCH_SIZE = 10
        downloaded = 0
        for i in range(0, len(tile_jobs), BATCH_SIZE):
            batch = tile_jobs[i:i + BATCH_SIZE]
            ok = download_tiles_batch(batch, referer)
            if not ok:
                raise RuntimeError(f"Chyba při stahování dlaždic z {base_tile_url}")
            downloaded += len(batch)
            if downloaded % 20 < BATCH_SIZE or downloaded == total_tiles:
                print(f"  staženo {downloaded}/{total_tiles} dlaždic...")
            # Šetrná pauza mezi dávkami pro ochranu serveru
            time.sleep(0.08)

        raw_montage = os.path.join(tmp_dir, "montage.jpg")
        subprocess.run([
            MAGICK, "montage", os.path.join(tmp_dir, "*.jpg"),
            "-tile", f"{len(cols_range)}x{len(rows_range)}",
            "-geometry", "+0+0",
            raw_montage
        ], check=True)

        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        if crop_box:
            bx, by, bw, bh = crop_box
            subprocess.run([
                MAGICK, raw_montage,
                "-crop", f"{bw}x{bh}+{bx}+{by}",
                "+repage",
                "-quality", "92",
                out_file
            ], check=True)
        else:
            shutil.copy2(raw_montage, out_file)

        dim_res = subprocess.run([MAGICK, out_file + "[0]", "-format", "%wx%h", "info:"],
                                capture_output=True, text=True, check=True)
        print(f"Uloženo: {out_file} ({dim_res.stdout.strip()})")
        if nahled:
            print("  NÁHLED – jen k orientaci (rok, oddíl, řádek, folio). Přepis a citace jen z plného rozlišení (bez --nahled).")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def svazky(dotaz, druh=None, rok=None, podle="obec", farafiltr=None):
    """Seznam matrik z vyhledávání MZA podle obce nebo čísla knihy (signatury); projde všechny stránky výsledků."""
    import html as htmlmod
    import urllib.parse
    q = {"typ": podle, ("search_by_obec" if podle == "obec" else "signatura"): dotaz}
    stranky, strana = [], 1
    while True:
        url = f"{BASE}/actapublica/matrika/hledani?" + urllib.parse.urlencode({**q, "page": strana})
        res = subprocess.run(["curl", "-s", "-L", "--http2", "--connect-timeout", "6", "--max-time", "25",
                              "-H", f"User-Agent: {CHROME_UA}", url], capture_output=True, text=True)
        if res.returncode != 0 or "<table" not in res.stdout:
            if strana == 1:
                sys.exit(f"Vyhledávání MZA nevrátilo tabulku (kód {res.returncode}): {url}")
            break
        stranky.append(res.stdout)
        m = re.search(r"záznamy:\s*\d+\s*-\s*(\d+),\s*celkem:\s*(\d+)", res.stdout)
        if not m or int(m.group(1)) >= int(m.group(2)) or strana >= 30:
            break
        strana += 1
        time.sleep(0.5)   # ohleduplnost k serveru
    sloupce = {"N": 2, "O": 3, "Z": 4}
    radky = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", "".join(stranky), re.S):
        bunky = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        det = re.search(r"detail/(\d+)", r)
        if len(bunky) < 7 or not det:
            continue
        txt = lambda s: " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", s)).split())
        fara = txt(re.sub(r"<small>.*", "", bunky[1], flags=re.S))
        roky = {d: txt(bunky[i]).replace(" - - ", "").strip(" -") for d, i in sloupce.items()}
        obce = re.findall(r"<strong>([^<]+)</strong>", htmlmod.unescape(bunky[5]))
        snimku = txt(bunky[6])
        if farafiltr and farafiltr.lower() not in fara.lower():
            continue
        if druh and not roky.get(druh):
            continue
        if rok:
            ok = False
            for d, s in roky.items():
                if druh and d != druh:
                    continue
                m = re.match(r"(\d{4})\s*-\s*(\d{4})", s)
                if m and int(m.group(1)) <= rok <= int(m.group(2)):
                    ok = True
            if not ok:
                continue
        radky.append((txt(bunky[0]), fara, roky, snimku, det.group(1), obce))
    if not radky:
        print("Nic nenalezeno.")
    for sig, fara, roky, snimku, det, obce in radky:
        r = "  ".join(f"{d} {s}" for d, s in roky.items() if s)
        print(f"sign. {sig:>6} | {fara} | {r} | {snimku} sn. | detail {det} | {', '.join(obce)[:120]}")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "svazky":
        if sys.argv[2] == "--sig":
            return svazky(sys.argv[3], podle="signatura")
        druh = next((a for a in sys.argv[3:] if a in ("N", "O", "Z")), None)
        rok = next((int(a) for a in sys.argv[3:] if a.isdigit() and len(a) == 4), None)
        fara = sys.argv[sys.argv.index("--fara") + 1] if "--fara" in sys.argv else None
        return svazky(sys.argv[2], druh, rok, farafiltr=fara)
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "snimek":
        detail_id = sys.argv[2]
        scan_num = int(sys.argv[3])
        out_file = sys.argv[4]
        nahled = "--nahled" in sys.argv
        if nahled:
            out_file = nahled_cesta(out_file)
        crop = None
        for arg in sys.argv[5:]:
            if arg.startswith("--crop="):
                crop = [float(v) for v in arg.split("=")[1].split(",")]
            elif arg == "--crop" and sys.argv.index(arg) + 1 < len(sys.argv):
                crop = [float(v) for v in sys.argv[sys.argv.index(arg) + 1].split(",")]
        snimek(detail_id, scan_num, out_file, nahled=nahled, crop=crop)
    else:
        sys.exit(f"Neznámý příkaz: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
