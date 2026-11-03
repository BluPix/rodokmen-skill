#!/usr/bin/env python3
"""
prameny.py – nezávislé prameny mimo matriky (noviny, vojenské databáze). Veřejná rozhraní, bez přihlášení.

Zdroje:
  kramerius  Česká digitální knihovna (agregátor všech Krameriů: NK, MZK, krajské…) + Kramerius NK ČR (rakousko-uherské
             seznamy ztrát 1914–1919) + Digitální studovna MO (vojenské úmrtní matriky, knihy zemřelých v polních
             nemocnicích): fulltext novin, parte, sborníků, vojenských tisků.
  vua        Vojenský ústřední archiv – databáze padlých v 1. sv. válce (volitelně legionáři, padlí 2. sv. v.).
  cevh       Centrální evidence válečných hrobů (MO ČR) – padlí a jména na pomnících/hrobech (pohřbení a připomenutí).

Výsledky jsou STOPY (ne doklady): zapisuj je do deníku a do `note` osoby s odkazem, do `r` jen matriční zápisy.
Nástroj nic nezapisuje do data/, vše je v pracovni/prameny/.

Použití (z kořene projektu):
  python3 -I tools/prameny.py hledat kramerius "Jan Novák" [--od 1914 --do 1920] [--volne] [--radky 20]
  python3 -I tools/prameny.py hledat kramerius Novák --seznamy-ztrat      # rakousko-uherské seznamy ztrát 1914–1919
  python3 -I tools/prameny.py hledat vua "Novák" [--jmeno Jan] [--misto Holice] [--db fallen-first|legio|fallen-second|abroad-second]
  python3 -I tools/prameny.py hledat cevh "Novák" [--jmeno Jan]
  python3 -I tools/prameny.py fronta pridej <zdroj> "<dotaz>" [stejné volby] [--osoba 18]
  python3 -I tools/prameny.py fronta navrhni          # naplní frontu podle data/osoby.py (jen nové položky)
  python3 -I tools/prameny.py fronta spustit [--limit 500] [--pauza 5 10]
  python3 -I tools/prameny.py fronta stav | vysledky   # stav fronty / přehled nálezů k zapracování
  python3 -I tools/prameny.py fronta vycisti           # odstraní hotové položky (výsledky zůstanou)

Noční běh (`fronta spustit`):
  - položky po jedné, každý výsledek hned do pracovni/prameny/vysledky/<id>.json, při pádu nic neztratí,
  - časový limit na každý požadavek, 3 chyby za sebou → pauza 10 min, položka po 3 pokusech „chyba“,
  - rovnoměrná pauza mezi dotazy (výchozí 5–10 s) a strop na počet dotazů za běh; deník pracovni/prameny/log.txt.
  Ráno: `fronta vysledky`, projít nálezy, zapsat stopy (deník, note) a `fronta vycisti`.
"""
import argparse
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path

for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "pracovni" / "prameny"
VYSLEDKY = DIR / "vysledky"
FRONTA = DIR / "fronta.json"
LOG = DIR / "log.txt"
ZDROJE = ("kramerius", "vua", "cevh")
TIMEOUT = 40
UA = "rodokmen-skill/1.0 (rodinna genealogie, jednotlive dotazy; python-urllib)"

CDK = "https://api.ceskadigitalniknihovna.cz/search/api/client/v7.0"
VUA = "https://www.vuapraha.cz"
CEVH = "https://evidencevh.mo.gov.cz"


# ---------------------------------------------------------------- pomocné
def log(msg):
    DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def bez_diakritiky(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def http(url, data=None, json_body=None, headers=None):
    """GET/POST s časovým limitem; vrací (status, text). Chyby HTTP vrací jako status, síťové chyby vyhazuje."""
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"} | (headers or {})
    body = None
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=h, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace") if e.fp else ""
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
        return http_curl(url, body, h)   # některé úřední weby (VÚA) nemají úplný řetězec certifikátů – curl má systémové


def http_curl(url, body, headers):
    """Totéž přes curl (systémové certifikáty, HTTP/2)."""
    import subprocess
    cmd = ["curl", "-sS", "--max-time", str(TIMEOUT), "-o", "-", "-w", "\n%{http_code}", url]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    if body is not None:
        cmd += ["--data-binary", "@-"]
    r = subprocess.run(cmd, input=body, capture_output=True, timeout=TIMEOUT + 10)
    out = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0:
        raise urllib.error.URLError(f"curl {r.returncode}: {r.stderr.decode('utf-8', 'replace')[:200]}")
    text, _, kod = out.rpartition("\n")
    return int(kod or 0), text


def text_z_html(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h, flags=re.S)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def rozdel_jmeno(cele):
    casti = (cele or "").strip().split()
    return (" ".join(casti[:-1]), casti[-1]) if len(casti) > 1 else ("", (cele or "").strip())


class DocasnaChyba(Exception):
    """Server nedostupný / přetížený – zkusit později."""


# ---------------------------------------------------------------- Kramerius
# Instance: ČDK (agregátor, API v7) + dvě, které v ČDK nejsou nebo tam chybí zvýraznění: Národní knihovna (v5; obsahuje
# rakousko-uherské seznamy ztrát 1914–1919 „Verlustliste“) a Digitální studovna MO (v5; vojenské úmrtní matriky,
# knihy zemřelých v polních nemocnicích, vojenské tisky).
KRAMERIUS = [
    ("ČDK", "v7", CDK, "https://www.digitalniknihovna.cz/{lib}/view/{root}?page={pid}"),
    ("NK ČR", "v5", "https://kramerius5.nkp.cz/search/api/v5.0", "https://kramerius5.nkp.cz/uuid/{pid}"),
    ("Dig. studovna MO", "v5", "https://digitalnistudovna.army.cz/search/api/v5.0", "https://digitalnistudovna.army.cz/uuid/{pid}"),
]


def kramerius_hledat(dotaz, od=None, do=None, volne=False, radky=20, seznamy_ztrat=False, misto=None, **_):
    """Fulltext ve všech instancích; dvě slova hledá v obou pořadích („Jan Novák“ i „Novák Jan“).
    misto: „Holice|Dolní Roveň“ – jen stránky, kde je i některá z obcí (u běžných jmen nutné, jinak tisíce shod)."""
    fraze = dotaz.strip()
    slova = fraze.split()
    if volne:
        jadro = "(" + " AND ".join(slova) + ")"
    elif len(slova) == 2:
        jadro = f'("{fraze}" OR "{slova[1]} {slova[0]}")'
    else:
        jadro = f'"{fraze}"'
    if misto:
        obce = [o.strip() for o in re.split(r"[|,]", misto) if o.strip()]
        jadro += " AND text_ocr:(" + " OR ".join(f'"{o}"' if " " in o else o for o in obce) + ")"
    shody, celkem, urls, chyby = [], 0, [], []
    for nazev, verze, base, odkaz in KRAMERIUS:
        if seznamy_ztrat and nazev != "NK ČR":
            continue
        try:
            if verze == "v7":
                q = f"text_ocr:{jadro} AND model:page"
                if od or do:
                    q += f" AND date_range_start.year:[{od or '*'} TO {do or '*'}]"
                par = {"q": q, "fl": "pid,root.pid,root.title,date.str,accessibility,page.number,cdk.collection",
                       "rows": str(min(int(radky) * 2, 100)), "sort": "date.min asc"}
                url = f"{base}/search?" + urllib.parse.urlencode(par)
                st, t = http(url)
            else:
                q = f"text_ocr:{jadro} AND fedora.model:page"
                if seznamy_ztrat:
                    q += " AND root_title:Verlustliste*"
                if od or do:
                    q += f" AND datum_begin:[{od or '*'} TO {do or '*'}]"
                par = {"q": q, "fl": "PID,root_pid,root_title,datum_str,details,dostupnost", "rows": str(min(int(radky), 50)),
                       "wt": "json", "hl": "true", "hl.fl": "text_ocr", "hl.fragsize": "160", "sort": "datum_begin asc"}
                url = f"{base}/search?" + urllib.parse.urlencode(par)
                st, t = http(url)
            urls.append(url)
            if st in (502, 503, 504, 429):
                raise DocasnaChyba(f"{nazev} HTTP {st}")
            if st != 200:
                raise RuntimeError(f"{nazev} HTTP {st}: {t[:120]}")
            d = json.loads(t)
            celkem += d["response"]["numFound"]
            hl = d.get("highlighting", {})
            for doc in d["response"]["docs"]:
                if verze == "v7":
                    lib = (doc.get("cdk.collection") or ["cdk"])[0]
                    s = {"zdroj": nazev, "titul": doc.get("root.title", ""), "rok": doc.get("date.str", ""),
                         "strana": doc.get("page.number", ""), "dostupnost": "online" if doc.get("accessibility") == "public" else "jen v knihovně",
                         "pid": doc["pid"], "odkaz": odkaz.format(lib=lib, root=doc.get("root.pid"), pid=doc["pid"]), "uryvek": ""}
                else:
                    det = doc.get("details") or [""]
                    s = {"zdroj": nazev, "titul": doc.get("root_title", ""), "rok": doc.get("datum_str", ""),
                         "strana": re.sub(r"\s.*", "", str(det[0])) if det else "",
                         "dostupnost": "online" if doc.get("dostupnost") == "public" else "jen v knihovně",
                         "pid": doc["PID"], "odkaz": odkaz.format(pid=doc["PID"], root=doc.get("root_pid")),
                         "uryvek": re.sub(r"\s+", " ", " … ".join(hl.get(doc["PID"], {}).get("text_ocr", []))).replace("<em>", "").replace("</em>", "")}
                shody.append(s)
        except DocasnaChyba as e:
            chyby.append(str(e))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, RuntimeError) as e:
            chyby.append(f"{nazev}: {type(e).__name__} {str(e)[:100]}")
    if chyby and not shody and len(chyby) == len([k for k in KRAMERIUS if not seznamy_ztrat or k[0] == "NK ČR"]):
        raise DocasnaChyba("; ".join(chyby))
    # odstranit duplicity (stejný titul, rok, strana napříč knihovnami) a doplnit úryvky z ČDK
    videno, vysl = set(), []
    for s in shody:
        k = (s["titul"], s["rok"], s["strana"])
        if k in videno:
            continue
        videno.add(k)
        vysl.append(s)
    vysl.sort(key=lambda s: (re.sub(r"\D", "", s["rok"])[-4:] if re.search(r"\d{4}", s["rok"]) else "9999"))
    vysl = vysl[:int(radky)]
    hledane = slova[-1] if volne else fraze
    for s in vysl:
        if s["zdroj"] == "ČDK" and s["dostupnost"] == "online":
            s["uryvek"] = kramerius_uryvek(s["pid"], hledane, slova)
    return " | ".join(urls), {"celkem": celkem, "chyby": chyby}, vysl


def kramerius_uryvek(pid, hledane, slova):
    """Úryvek OCR textu kolem hledaného výrazu (±120 znaků); při výpadku prázdný."""
    try:
        st, t = http(f"{CDK}/items/{pid}/ocr/text", headers={"Accept": "text/plain"})
    except Exception:  # noqa: BLE001
        return ""
    if st != 200 or not t:
        return ""
    plain = re.sub(r"\s+", " ", t)
    norm = bez_diakritiky(plain).lower()
    i = -1
    for kand in [hledane, " ".join(reversed(slova)), slova[-1]]:
        i = norm.find(bez_diakritiky(kand).lower())
        if i >= 0:
            break
    if i < 0:
        return plain[:200]
    return "…" + plain[max(0, i - 120):i + len(hledane) + 120] + "…"


# ---------------------------------------------------------------- VÚA – padlí 1. sv. válka
def vua_hledat(dotaz, jmeno="", misto="", db="fallen-first", detaily=10, **_):
    body = {"database": db or "fallen-first", "surname": dotaz.strip(), "name": jmeno or "", "place": misto or "", "date": ""}
    url = f"{VUA}/wp-json/mo/v1/archive-database/html"
    st, t = http(url, json_body=body)
    if st in (502, 503, 504, 429):
        raise DocasnaChyba(f"VÚA HTTP {st}")
    if st != 200:
        raise RuntimeError(f"VÚA HTTP {st}: {t[:200]}")
    h = json.loads(t).get("html", "")
    shody = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        bunky = [text_z_html(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        odkaz = re.search(r'href="([^"]*padli[^"]*|[^"]*/\d+)"', row)
        if not odkaz or not any(bunky):
            continue
        s = {"prijmeni": bunky[0] if bunky else "", "jmeno": bunky[1] if len(bunky) > 1 else "",
             "hodnost": bunky[2] if len(bunky) > 2 else "", "narozen": bunky[3] if len(bunky) > 3 else "",
             "misto_narozeni": bunky[4] if len(bunky) > 4 else "", "odkaz": urllib.parse.urljoin(VUA, odkaz.group(1))}
        shody.append(s)
    for s in shody[:int(detaily)]:   # detail: útvar, úmrtí, příčina, bojiště, pohřbení, poznámka
        time.sleep(random.uniform(1.0, 2.0))
        try:
            st, dt = http(s["odkaz"])
            if st == 200:
                txt = text_z_html(dt)
                for pole, nazev in [("domovem", "Domovem"), ("utvar", "Příslušnost k útvaru rakousko-uherské armády"),
                                    ("utvar", "Příslušnost k útvaru"), ("zemrel", "Datum úmrtí"), ("pricina", "Příčina úmrtí"),
                                    ("misto_umrti", "Místo úmrtí"), ("bojiste", "Bojiště"), ("pohrben", "Místo pohřbení"),
                                    ("poznamka", "Poznámka")]:
                    m = re.search(re.escape(nazev) + r":\s*(.*?)\s*(?=(?:Příjmení|Jméno|Datum narození|Místo narození|Domovem|Příslušnost|Datum úmrtí|Příčina úmrtí|Místo úmrtí|Bojiště|Místo pohřbení|Poznámka|©)\b)", txt)
                    if m and not s.get(pole):
                        s[pole] = m.group(1).strip()
        except Exception as e:  # noqa: BLE001
            s["detail_chyba"] = str(e)[:100]
    return url + " " + json.dumps(body, ensure_ascii=False), {"html": h}, shody


# ---------------------------------------------------------------- CEVH – evidence válečných hrobů
def cevh_hledat(dotaz, jmeno="", **_):
    vys, surove = [], {}
    # 1) padlí (databáze padlých vojáků)
    st, t = http(f"{CEVH}/Evidence/FallenPeople/Select", data={"Surname": dotaz.strip(), "FirstName": jmeno or "",
                                                               "page": 1, "pageSize": 100})
    if st in (502, 503, 504, 429):
        raise DocasnaChyba(f"CEVH HTTP {st}")
    if st == 200:
        try:
            d = json.loads(t); surove["padli"] = d
            for r in d.get("Data", []):
                vys.append({"typ": "padlý", "jmeno": f"{r.get('FirstName', '')} {r.get('Surname', '')}".strip(),
                            "narozen": r.get("BirthYear", ""), "zemrel": r.get("DeathYear", ""),
                            "odkaz": f"{CEVH}/Evidence/FallenPeople/Detail/{r.get('ICP')}"})
        except json.JSONDecodeError:
            pass
    time.sleep(random.uniform(1.0, 2.0))
    # 2) pohřbení a připomenutí (jména na hrobech a pomnících)
    cele = f"{jmeno} {dotaz}".strip() if jmeno else dotaz.strip()
    st, t = http(f"{CEVH}/Evidence/People/Select", data={"FirstAndLastName": cele, "page": 1, "pageSize": 100})
    if st == 200:
        try:
            d = json.loads(t); surove["pohrbeni"] = d
            for r in d.get("Data", []):
                vys.append({"typ": "na hrobě/pomníku", "jmeno": r.get("FullName", ""), "narozen": r.get("DateOfBirth", ""),
                            "zemrel": r.get("DateOfDeath", ""), "pricina": r.get("CauseOfDeath", ""),
                            "misto_narozeni": r.get("BirthLocation", ""), "misto_umrti": r.get("DeathLocation", ""),
                            "odkaz": f"{CEVH}/Evidence/People/Detail/{r.get('Id')}"})
        except json.JSONDecodeError:
            pass
    # k pomníkům doplnit, kde stojí (odkaz na hrob + popis), max 8 detailů
    for s in [v for v in vys if v["typ"] == "na hrobě/pomníku"][:8]:
        time.sleep(random.uniform(1.0, 2.0))
        try:
            st, dt = http(s["odkaz"])
            m = re.search(r'href="(/Evidence/Graves/Detail/[^"]+)"', dt) if st == 200 else None
            if m:
                s["hrob"] = CEVH + m.group(1)
                st2, gt = http(s["hrob"])
                if st2 == 200:
                    txt = text_z_html(gt)
                    kod = re.search(r"\b(CZE\d{4}-\d+)\b", txt)
                    popis = re.search(r"Popis vzhledu\s*(.{0,300})", txt)
                    s["hrob_kod"] = kod.group(1) if kod else ""
                    s["hrob_popis"] = popis.group(1).strip() if popis else ""
        except Exception as e:  # noqa: BLE001
            s["detail_chyba"] = str(e)[:100]
    return f"{CEVH} ({dotaz} {jmeno})".strip(), surove, vys


# ---------------------------------------------------------------- společné
HLEDAT = {"kramerius": kramerius_hledat, "vua": vua_hledat, "cevh": cevh_hledat}


def hledej(zdroj, dotaz):
    d = dict(dotaz)
    q = d.pop("dotaz")
    return HLEDAT[zdroj](q, **d)


def dotaz_z_args(a):
    d = {"dotaz": a.dotaz}
    for k in ("od", "do", "volne", "radky", "jmeno", "misto", "db", "seznamy_ztrat"):   # misto: vua i kramerius
        v = getattr(a, k, None)
        if v not in (None, False, ""):
            d[k] = v
    return d


def vypis(zdroj, shody):
    if not shody:
        print("  (žádná shoda)")
    for s in shody:
        if zdroj == "kramerius":
            print(f"- {s['rok']} | {s['titul'][:70]} | s. {s['strana']} | {s['dostupnost']} | {s['zdroj']} | {s['odkaz']}")
            if s.get("uryvek"):
                print(f"    {s['uryvek'][:300]}")
        elif zdroj == "vua":
            print(f"- {s['prijmeni']} {s['jmeno']} | * {s['narozen']} {s['misto_narozeni']} | domovem {s.get('domovem', '')} | "
                  f"{s.get('utvar', '')} | † {s.get('zemrel', '')} {s.get('pricina', '')} {s.get('misto_umrti', '')} | "
                  f"{s.get('bojiste', '')} | pohřben {s.get('pohrben', '')} | {s.get('poznamka', '')} | {s['odkaz']}")
        else:
            print(f"- [{s['typ']}] {s['jmeno']} | * {s.get('narozen', '')} {s.get('misto_narozeni', '')} | † {s.get('zemrel', '')} "
                  f"{s.get('pricina', '')} {s.get('misto_umrti', '')} | {s.get('hrob_kod', '')} {s.get('hrob_popis', '')[:120]} | {s['odkaz']}")


# ---------------------------------------------------------------- fronta
def nacti_frontu():
    return json.loads(FRONTA.read_text(encoding="utf-8")) if FRONTA.exists() else []


def uloz_frontu(fr):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = FRONTA.with_suffix(".tmp")
    tmp.write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FRONTA)


def nove_id(fr, zdroj, dotaz, osoba=None):
    zaklad = re.sub(r"[^a-z0-9]+", "_", bez_diakritiky(dotaz.get("dotaz", "") + " " + dotaz.get("jmeno", "")).lower()).strip("_")
    pid = f"{zdroj}_{zaklad}" + (f"_{osoba}" if osoba else "")
    n, kandidat = 1, pid
    while any(x["id"] == kandidat for x in fr):
        n += 1
        kandidat = f"{pid}_{n}"
    return kandidat


def pridej_polozku(fr, zdroj, dotaz, osoba=None, proc=""):
    if any(x["zdroj"] == zdroj and x["dotaz"] == dotaz and x.get("osoba") == osoba for x in fr):
        return None
    item = {"id": nove_id(fr, zdroj, dotaz, osoba), "zdroj": zdroj, "osoba": osoba, "dotaz": dotaz, "proc": proc,
            "stav": "ceka", "pokusy": 0, "pridano": datetime.now().isoformat(timespec="seconds")}
    fr.append(item)
    return item


def fronta_pridej(a):
    fr = nacti_frontu()
    it = pridej_polozku(fr, a.zdroj, dotaz_z_args(a), a.osoba)
    uloz_frontu(fr)
    print("přidáno:", it["id"] if it else "(už ve frontě)")


def fronta_navrhni(a):
    """Z data/osoby.py navrhne dotazy: noviny pro každého s rokem narození, vojenské databáze pro ročníky 1860–1925."""
    ns = {}
    exec((ROOT / "data" / "osoby.py").read_text(encoding="utf-8"), ns)
    P = ns.get("P", {})
    mista_f = ROOT / "data" / "mista.json"
    mista = json.loads(mista_f.read_text(encoding="utf-8")) if mista_f.exists() else {}
    fr = nacti_frontu()
    n = 0
    for k in sorted(P):
        p = P[k]
        if p.get("st") in ("fam",) and k < 8:
            continue   # žijící / nejbližší rodina – noviny by našly spíš současnost
        jm = re.sub(r"\s*\(.*?\)|\?", "", p.get("n", "")).strip()
        if len(jm.split()) < 2 or jm.split()[-1][0].islower():
            continue
        fakta = " ".join(p.get("f", []))
        roky = [int(y) for y in re.findall(r"\b(1[6-9]\d\d|20\d\d)\b", fakta + " " + p.get("y", ""))]
        if not roky:
            continue
        nar = min(roky)
        umrti = [int(y) for f in p.get("f", []) if f.startswith("†") for y in re.findall(r"\b(1[6-9]\d\d|20\d\d)\b", f)]
        do = (umrti[0] + 2) if umrti else min(nar + 95, datetime.now().year)
        # obce z faktů (podle mista.json) – noviny jen tam, kde je i obec; bez obce by běžné jméno dalo tisíce shod
        obce = [o for o, e in mista.items() if not e.get("dum") and not e.get("hypoteza") and re.search(e.get("re") or re.escape(o), fakta)]
        if nar >= 1800 and obce:
            d = {"dotaz": jm, "od": nar, "do": do, "radky": 15, "misto": "|".join(obce[:6])}
            if pridej_polozku(fr, "kramerius", d, k, f"noviny {nar}–{do} s obcí"):
                n += 1
        if 1860 <= nar <= 1925 and k % 2 == 0:
            kr, pr = rozdel_jmeno(jm)
            if pridej_polozku(fr, "vua", {"dotaz": pr, "jmeno": kr}, k, "padlí 1. sv. válka"):
                n += 1
            if nar <= 1900 and pridej_polozku(fr, "kramerius", {"dotaz": pr, "seznamy_ztrat": True, "radky": 30}, k,
                                              "seznamy ztrát 1914–1919 (hledej křestní jméno, i německy)"):
                n += 1
        if 1850 <= nar <= 1925:
            kr, pr = rozdel_jmeno(jm)
            if pridej_polozku(fr, "cevh", {"dotaz": pr, "jmeno": kr}, k, "válečné hroby a pomníky"):
                n += 1
    uloz_frontu(fr)
    print(f"přidáno {n} položek, ve frontě celkem {len(fr)} (čeká {sum(1 for x in fr if x['stav'] == 'ceka')})")


def fronta_stav(a=None):
    fr = nacti_frontu()
    from collections import Counter
    print(f"položek: {len(fr)}", dict(Counter(x["stav"] for x in fr)))
    for x in fr:
        if x["stav"] != "hotovo":
            print(f"  {x['stav']:8} {x['id']:45} pokusy={x['pokusy']}  {x.get('chyba', '')}")


def fronta_vysledky(a=None):
    """Přehled hotových položek se shodami – co ráno projít a zapracovat."""
    fr = nacti_frontu()
    for x in fr:
        if x["stav"] != "hotovo":
            continue
        f = VYSLEDKY / f"{x['id']}.json"
        if not f.exists():
            continue
        v = json.loads(f.read_text(encoding="utf-8"))
        shody = v.get("shody", [])
        hlav = f"osoba {x['osoba']}: " if x.get("osoba") else ""
        celk = f", celkem stránek {v['celkem']}" if v.get("celkem") is not None else ""
        print(f"\n== {x['id']}  ({hlav}{x['zdroj']} „{x['dotaz'].get('dotaz')}“ {x.get('proc', '')}) – {len(shody)} shod{celk}")
        vypis(x["zdroj"], shody[:10])


def fronta_vycisti(a=None):
    fr = nacti_frontu()
    zbyva = [x for x in fr if x["stav"] != "hotovo"]
    uloz_frontu(zbyva)
    print(f"odstraněno {len(fr) - len(zbyva)} hotových, zbývá {len(zbyva)}")


def fronta_spustit(a):
    fr = nacti_frontu()
    ceka = [x for x in fr if x["stav"] in ("ceka", "znovu")]
    if not ceka:
        print("fronta je prázdná"); return
    log(f"START fronta: {len(ceka)} položek, limit {a.limit}, pauza {a.pauza[0]}–{a.pauza[1]} s")
    VYSLEDKY.mkdir(parents=True, exist_ok=True)
    hotovo, chyby_za_sebou = 0, 0
    for item in ceka:
        if hotovo >= a.limit:
            log(f"dosažen limit {a.limit} dotazů, končím"); break
        z = item["zdroj"]
        try:
            url, surove, shody = hledej(z, item["dotaz"])
            (VYSLEDKY / f"{item['id']}.json").write_text(json.dumps(
                {"id": item["id"], "zdroj": z, "osoba": item.get("osoba"), "dotaz": item["dotaz"], "url": url,
                 "kdy": datetime.now().isoformat(timespec="seconds"), "celkem": surove.get("celkem") if isinstance(surove, dict) else None,
                 "shody": shody, "surove": surove}, ensure_ascii=False, indent=1), encoding="utf-8")
            item.update(stav="hotovo", pokusy=item["pokusy"] + 1, shod=len(shody), chyba="")
            hotovo += 1; chyby_za_sebou = 0
            log(f"OK {item['id']}: {len(shody)} shod")
        except (DocasnaChyba, urllib.error.URLError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as e:
            item.update(pokusy=item["pokusy"] + 1, chyba=f"{type(e).__name__}: {str(e)[:200]}")
            item["stav"] = "znovu" if item["pokusy"] < 3 else "chyba"
            chyby_za_sebou += 1
            log(f"CHYBA {item['id']} (pokus {item['pokusy']}): {item['chyba']}")
            if chyby_za_sebou >= 3:
                log("3 chyby za sebou – pauza 10 minut")
                uloz_frontu(fr)
                time.sleep(600); chyby_za_sebou = 0
        finally:
            uloz_frontu(fr)
        time.sleep(random.uniform(a.pauza[0], a.pauza[1]))
    log(f"KONEC fronta: hotovo {hotovo}, zbývá {sum(1 for x in fr if x['stav'] in ('ceka', 'znovu'))}, "
        f"chyby {sum(1 for x in fr if x['stav'] == 'chyba')}")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def volby(sp):
        sp.add_argument("dotaz", help="kramerius: celé jméno / fráze; vua, cevh: příjmení")
        sp.add_argument("--od", type=int); sp.add_argument("--do", type=int)
        sp.add_argument("--volne", action="store_true", help="kramerius: slova kdekoli na stránce, ne jako fráze")
        sp.add_argument("--radky", type=int, default=20)
        sp.add_argument("--seznamy-ztrat", dest="seznamy_ztrat", action="store_true",
                        help="kramerius: jen rakousko-uherské seznamy ztrát 1914–1919 (NK ČR); dotaz = příjmení")
        sp.add_argument("--jmeno", help="vua, cevh: křestní jméno")
        sp.add_argument("--misto", help="vua: místo narození / domovská obec; kramerius: obce oddělené | (zúží hledání)")
        sp.add_argument("--db", choices=["fallen-first", "legio", "fallen-second", "abroad-second"], help="vua: databáze")

    sp = sub.add_parser("hledat"); sp.add_argument("zdroj", choices=ZDROJE); volby(sp); sp.add_argument("--json", action="store_true")
    fp = sub.add_parser("fronta"); fsub = fp.add_subparsers(dest="fcmd", required=True)
    sp = fsub.add_parser("pridej"); sp.add_argument("zdroj", choices=ZDROJE); volby(sp); sp.add_argument("--osoba", type=int)
    fsub.add_parser("navrhni")
    sp = fsub.add_parser("spustit"); sp.add_argument("--limit", type=int, default=500)
    sp.add_argument("--pauza", type=float, nargs=2, default=[5, 10], metavar=("OD", "DO"))
    fsub.add_parser("stav"); fsub.add_parser("vysledky"); fsub.add_parser("vycisti")
    a = ap.parse_args()

    if a.cmd == "hledat":
        url, surove, shody = hledej(a.zdroj, dotaz_z_args(a))
        if a.json:
            print(json.dumps({"url": url, "shody": shody}, ensure_ascii=False, indent=1))
        else:
            print("dotaz:", url)
            if isinstance(surove, dict) and surove.get("celkem") is not None:
                print("celkem nalezeno stránek:", surove["celkem"])
            vypis(a.zdroj, shody)
    else:
        {"pridej": fronta_pridej, "navrhni": fronta_navrhni, "spustit": fronta_spustit, "stav": fronta_stav,
         "vysledky": fronta_vysledky, "vycisti": fronta_vycisti}[a.fcmd](a)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\npřerušeno")
