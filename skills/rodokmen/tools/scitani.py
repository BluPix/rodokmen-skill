#!/usr/bin/env python3
"""
scitani.py – sčítání lidu 1857–1921 na Moravě (MZA, portál Sčítací operáty, https://www.mza.cz/scitacioperaty/).
Veřejný portál bez přihlášení, jen prohlížení. Arch popisný = jeden dům: všichni obyvatelé s datem a místem narození,
vztahem k hlavě domácnosti, náboženstvím, povoláním. Nezávislý pramen proti matrikám – potvrdí data narození,
sourozence, kdo kdy v domě žil, a pomůže přečíst nejistá jména z matrik.

Na portálu se hledá jen podle obce (ne podle jména). Jmenný rejstřík má MyHeritage („Sčítání lidu v Česku, 1900“)
– odtud obec a číslo domu, list pak tady.

Použití (z kořene projektu):
  python3 -I tools/scitani.py sady "Dolní Roveň" [rok]          # sady (obec × rok): id, čp. od–do, počet snímků, kód sady
  python3 -I tools/scitani.py najdi "Dolní Roveň" 1900 7        # sada a odhad snímku s čp. 7 (pak --nahled a posunout)
  python3 -I tools/scitani.py hlavicky <sada_id> <od> <do> out.jpg   # pruhy s číslem domu pod sebou → správný snímek
  python3 -I tools/scitani.py snimek <sada_id> <n> out.jpg [--nahled] [--crop x0,y0,x1,y1]
  python3 -I tools/scitani.py svazek <sada_id>                # vstup pro zapis.py svazky.json (klíč scit_<kód sady>)
  python3 -I tools/scitani.py porovnej pracovni/scitani/prepis/<klíč>.json   # řádky archu × rodokmen: ✓ ≈ ✗ + ?
  python3 -I tools/scitani.py zapis pracovni/scitani/prepis/<klíč>.json      # vstupy pro zapis.py (svazek, zápis, přepis)
  python3 -I tools/scitani.py plan [--rok 1900] [--obec "Dolní Roveň"]
      projde data/osoby.py: kdo byl při kterém sčítání naživu a kde bydlel (obec + čp. z faktů) → domácnosti ke
      kontrole, seřazené podle obce a roku, s id sady a odhadem snímku. Uloží pracovni/scitani/plan.md.

Postup kontroly jedné domácnosti: `najdi` → `snimek … --nahled` (číslo domu je vpravo nahoře) → posunout na správný
snímek → plný snímek, přečíst VŠECHNY řádky (i lidi, které v rodokmenu nemáme) a porovnat s fakty. Shoda → do `r`
osoby; rozpor (jiné datum, jméno) → ISSUES a znovu se podívat do matriky; nový člověk/údaj → note + deník.
Zápis: druh "S", klíč `s_<rok>_<obec>_cp<čp>`, misto „Obec čp. N“, svazek z `svazek`, odkaz `…/detail/<id>?image=<název>`.
Nástroj nic nezapisuje do data/; mezipaměť a plán jsou v pracovni/scitani/.
"""
import http.cookiejar
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))   # -I nepřidá adresář skriptu
import mza  # noqa: E402

PORTAL = "https://www.mza.cz/scitacioperaty"
CACHE = os.path.join(ROOT, "pracovni", "scitani")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
# rozhodný den sčítání (1857: 31. 10.; 1921: 15. 2.; jinak 31. 12.)
ROKY = [1857, 1869, 1880, 1890, 1900, 1910, 1921]

_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _get(url, data=None):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None,
                                 headers={"User-Agent": UA, "Referer": PORTAL + "/"})
    for pokus in range(3):
        try:
            with _opener.open(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except OSError:
            if pokus == 2:
                raise
            time.sleep(5 * (pokus + 1))


def bez_diakritiky(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def _parse_vysledky(html):
    out = []
    for li in html.split('<li class="list-group-item">')[1:]:
        pole = {re.sub(r"\s+", " ", k).strip(): re.sub(r"<[^>]+>", "", v).strip()
                for k, v in re.findall(r'text-muted ">([^<]+)</span>\s*<p>(.*?)</p>', li, re.S)}
        d = re.search(r"digisada/detail/(\d+)", li)
        if not d:
            continue
        out.append({"id": int(d.group(1)), "rok": int(pole.get("Rok sčítání") or 0), "obec": pole.get("Město/obec", ""),
                    "cast": pole.get("Část obce/osada", ""), "ulice": pole.get("Ulice", ""),
                    "cp": pole.get("Rozpis čísel popisných") or pole.get("Číslo popisné od-do", ""),
                    "archiv": pole.get("Archiv", ""), "fond": pole.get("Název fondu", ""), "kod": pole.get("Kód sady", "")})
    return out


def sady(obec, obnovit=False):
    """Všechny sady, kde obec je obcí nebo částí obce (z mezipaměti, jinak z portálu – stránkování po 10)."""
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, f"sady_{re.sub(r'\W+', '_', obec.lower())}.json")   # s diakritikou: Číkov ≠ Čikov
    if os.path.exists(f) and not obnovit:
        return json.load(open(f, encoding="utf-8"))
    html = _get(f"{PORTAL}/digisada/do_search", {"search": obec, "submit": "Vyhledat"})
    vse = _parse_vysledky(html)
    celkem = int((re.search(r"celkem:\s*(\d+)", html) or [0, len(vse)])[1])
    strana = 2
    while len(vse) < celkem and strana < 60:
        time.sleep(1)
        nove = _parse_vysledky(_get(f"{PORTAL}/digisada/search/{strana}"))
        if not nove:
            break
        vse += nove
        strana += 1
    json.dump(vse, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return vse


def okres_obce(obec):
    """Okres z data/mista.json (pole osm „…, okres Třebíč, …“) – pro odlišení stejnojmenných obcí (Chlum, Lhota)."""
    try:
        e = json.load(open(os.path.join(ROOT, "data", "mista.json"), encoding="utf-8")).get(obec, {})
    except OSError:
        return None
    m = re.search(r"okres ([^,]+)", e.get("osm", ""))
    return m.group(1).strip() if m else None


def sady_obce(obec, rok=None):
    """Sady přesně pro obec (obec bez části, nebo část = obec), případně jen daný rok a okres obce."""
    okres = okres_obce(obec)
    out = [s for s in sady(obec) if (s["obec"] == obec and s["cast"] in ("", obec)) or s["cast"] == obec]
    kratce = obec.translate(str.maketrans("áéíóúůý", "aeiouuy"))   # portál má dobové tvary: Číkov → „Čikov“
    if not out and kratce != obec:
        out = [s for s in sady(kratce) if (s["obec"] == kratce and s["cast"] in ("", kratce)) or s["cast"] == kratce]
    if okres and any(s["archiv"] == okres for s in out):
        out = [s for s in out if s["archiv"] == okres]
    if rok:
        out = [s for s in out if s["rok"] == rok]
    return sorted(out, key=lambda s: (s["rok"], s["cast"], s["kod"]))


def detail(sada_id):
    """Seznam snímků sady: [(název, dzi_url)] (mezipaměť pracovni/scitani/detail_<id>.json)."""
    f = os.path.join(CACHE, f"detail_{sada_id}.json")
    if os.path.exists(f):
        return json.load(open(f, encoding="utf-8"))
    html = _get(f"{PORTAL}/digisada/detail/{sada_id}")
    m = re.search(r"CreateSeadragon\(\s*(\[.*?\])\s*,\s*(\[.*?\])", html, re.S)
    if not m:
        sys.exit(f"Sada {sada_id}: na stránce nejsou snímky.")
    snimky = list(zip(json.loads(m.group(2)), json.loads(m.group(1))))
    pole = {re.sub(r"\s+", " ", k).strip(): re.sub(r"<[^>]+>|&nbsp;", "", v).strip()
            for k, v in re.findall(r'text-muted"[^>]*>([^<]+)</div>\s*<div class="col-8[^"]*">(.*?)</div>', html, re.S)}
    # sjednotit s výsledky hledání: „Město/obec (česky)“ → „Město/obec“, „226104010 (SOkA Třebíč)“ → „Třebíč“
    for k in list(pole):
        if k.endswith(" (česky)"):
            pole[k[:-8]] = pole[k]
    pole["Archiv"] = re.sub(r".*\(SOkA\s*|\)$", "", pole.get("Archiv", "")).strip()
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"snimky": snimky, "pole": pole}, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"snimky": snimky, "pole": pole}


def rozsah_cp(text):
    """„1-33“, „1-12, 14-20“ → seznam čísel domů v pořadí sady."""
    out = []
    for a, b in re.findall(r"(\d+)\s*(?:-\s*(\d+))?", text or ""):
        out += list(range(int(a), int(b or a) + 1))
    return out


def odhad_snimku(sada, cp, pocet):
    """Archy jsou seřazené podle čísla domu, každý dům ~stejně snímků → lineární odhad (ověř náhledem, ±3)."""
    cisla = rozsah_cp(sada["cp"])
    if cp not in cisla or not pocet:
        return None
    return max(1, min(pocet, round(cisla.index(cp) / len(cisla) * pocet) + 1))


def odkaz(sada_id, nazev=None):
    return f"{PORTAL}/digisada/detail/{sada_id}" + (f"?image={nazev}" if nazev else "")


def cmd_sady(obec, rok=None):
    for s in sady_obce(obec, rok) or []:
        print(f"{s['id']:>6}  {s['rok']}  {s['obec']}{' / ' + s['cast'] if s['cast'] else ''}  čp. {s['cp']}  "
              f"[{s['kod']}, SOkA {s['archiv']}]")
    if not sady_obce(obec, rok):
        print("nic – zkus jiný tvar názvu (dobový, německý) nebo `sady` bez roku; "
              f"všechny shody na „{obec}“: {sorted({(s['obec'], s['cast']) for s in sady(obec)})[:15]}")


def cmd_najdi(obec, rok, cp):
    for s in sady_obce(obec, rok):
        if cp not in rozsah_cp(s["cp"]):
            continue
        sn = detail(s["id"])["snimky"]
        n = odhad_snimku(s, cp, len(sn))
        print(f"sada {s['id']} ({s['kod']}), {s['rok']} {s['obec']}{' / ' + s['cast'] if s['cast'] else ''}, "
              f"čp. {s['cp']}, {len(sn)} snímků → čp. {cp} asi na snímku {n}\n  {odkaz(s['id'], sn[n - 1][0])}\n"
              f"  python3 -I tools/scitani.py hlavicky {s['id']} {max(1, n - 3)} {min(len(sn), n + 3)} pracovni/scitani/hlavicky.jpg")
        return
    print(f"čp. {cp} v sadách {obec} {rok} není:")
    cmd_sady(obec, rok)


def cmd_snimek(sada_id, n, out, nahled, crop):
    sn = detail(sada_id)["snimky"]
    mza.snimek(sada_id, n, out, nahled=nahled, crop=crop, dzi_urls=[u for _, u in sn], referer=odkaz(sada_id))
    print(f"snímek {n}/{len(sn)}: {sn[n - 1][0]}\n  {odkaz(sada_id, sn[n - 1][0])}")


def cmd_hlavicky(sada_id, od, do, out):
    """Horní pruh (obec, číslo domu vpravo nahoře) snímků od–do pod sebou v jednom obrázku – najít správný dům
    jedním pohledem. Zadní strany archů (zvířata, podpis) mají pruh prázdný."""
    import subprocess
    import tempfile
    sn = detail(sada_id)["snimky"]
    tmp = tempfile.mkdtemp(prefix="scit_hl_")
    # ImageMagick bez výchozího písma text nenapíše – vezmi systémové, jinak bez popisku
    pismo = next((f for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", r"C:\Windows\Fonts\arial.ttf",
                              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if os.path.exists(f)), None)
    pruhy = []
    for n in range(od, min(do, len(sn)) + 1):
        f = os.path.join(tmp, f"{n:04d}.jpg")
        mza.snimek(sada_id, n, f, nahled=True, dzi_urls=[u for _, u in sn], referer=odkaz(sada_id))
        p = os.path.join(tmp, f"p{n:04d}.jpg")
        popis = ["-font", pismo, "-pointsize", "48", "-annotate", "+10+0", str(n)] if pismo else []
        subprocess.run([mza.magick(), f, "-crop", "100%x12%+0+0", "+repage", "-resize", "1600x",
                        "-gravity", "west", "-splice", "120x0", *popis, p], check=True)
        pruhy.append(p)
    subprocess.run([mza.magick(), *pruhy, "-append", out], check=True)
    print(f"hlavičky snímků {od}–{min(do, len(sn))} → {out} (číslo snímku vlevo, číslo domu vpravo nahoře)")


def cmd_svazek(sada_id):
    d = detail(sada_id)
    p = d["pole"]
    kod = p.get("Kód sady", str(sada_id)).strip()
    obec = p.get("Město/obec", "") + (" / " + p["Část obce/osada"] if p.get("Část obce/osada") else "")
    print(json.dumps({f"scit_{kod}": {
        "archiv": f"Moravský zemský archiv v Brně – SOkA {p.get('Archiv', '')}, fond {p.get('Název fondu', '')}",
        "portal": "MZA Sčítací operáty",
        "svazek": f"Sčítání lidu {p.get('Rok sčítání', '')} {obec}, čp. {p.get('Rozpis čísel popisných', '')}, sada {kod}",
        "popis": f"Archy popisné domů {obec} ({len(d['snimky'])} snímků).",
        "url": odkaz(sada_id)}}, ensure_ascii=False, indent=1))


# --- porovnání přepsaného archu s rodokmenem a příprava zápisu ------------------------------------------------------
# Přepis archu napiš do pracovni/scitani/prepis/s_<rok>_<obec>_cp<čp>.json (vzor v .agents/skills/scitani/SKILL.md):
# {"sada": 12345, "snimek": 58, "rok": 1900, "obec": "Dolní Roveň", "cp": 7,
#  "radky": [{"jmeno": "Jan Novák", "vztah": "majitel", "nar": "14. 2. 1890", "rodiste": "Holice",
#             "nab": "řk.", "stav": "ženatý", "povolani": "obuvník", "pozn": ""}, …]}
DEN = {1857: "31. 10. 1857", 1921: "15. 2. 1921"}   # rozhodný den, jinak 31. 12.
VARIANTY = [("rozalie", "rosalie"), ("rosalia", "rosalie"), ("marianna", "mariana"), ("johana", "jana"),
            ("frantiska", "frantiska"), ("katerina", "katharina"), ("josefa", "josepha")]


def _zaklad(s):
    s = bez_diakritiky(s).lower().replace("(?)", "").strip()
    for a, b in VARIANTY:
        s = s.replace(a, b)
    return re.sub(r"[^a-z ]", "", s)


def zenske(prijmeni):
    """Novák → Nováková, Dvořák → Dvořáková, Černý → Černá, Krejčí → Krejčí."""
    if prijmeni.endswith(("ová", "á", "í")):
        return prijmeni
    if prijmeni.endswith(("ec", "ek")) and len(prijmeni) > 3:
        return prijmeni[:-2] + prijmeni[-1] + "ová"
    if prijmeni.endswith(("a", "e", "o")):
        return prijmeni[:-1] + "ová"
    return prijmeni + "ová"


def _datum(t):
    """„30. 11. 1874“ / „1874“ / „* 30. 11. 1874 Dolní Roveň“ → (d, m, r) s None, kde chybí."""
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(1[5-9]\d\d)", t or "")
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    r = _roky(t)
    return (None, None, r[0]) if r else (None, None, None)


def _jmena_osoby(p):
    """Křestní jméno a všechna příjmení, pod kterými může osoba na archu být (žena i po muži)."""
    jm = re.sub(r"\s*\(.*?\)|\?|^P\.\s*", "", p.get("n", "")).split()
    if len(jm) < 2:
        return None, set()
    prij = {jm[-1]}
    fakta = " ".join(p.get("f", []))
    for m in re.finditer(r"provdaná ([A-ZÁ-Ž]\w+)|později ([A-ZÁ-Ž]\w+)", fakta):
        prij.add(m.group(1) or m.group(2))
    if jm[-1].endswith(("ová", "á")) or p.get("sex") == "F":
        for m in re.finditer(r"×[^,;]*?\b[A-ZÁ-Ž]\w+ ([A-ZÁ-Ž]\w+)", fakta):
            prij.add(zenske(m.group(1)))
    return jm[0], prij


def _lide():
    ns = {}
    exec(open(os.path.join(ROOT, "data", "osoby.py"), encoding="utf-8").read(), ns)
    return [(k, p) for k, p in ns["P"].items()] + [(p.get("id"), p) for p in ns.get("SIDE", []) if p.get("id")]


def najdi_osobu(radek, lide, obec=None, rok_scit=None):
    """Osoby z rodokmenu, které odpovídají řádku archu (jméno + příjmení + rok narození ±3)."""
    slova = _zaklad(radek.get("jmeno", "")).split()
    if len(slova) < 2:
        return []
    _, _, rok = _datum(radek.get("nar"))
    out = []
    for k, p in lide:
        krest, prij = _jmena_osoby(p)
        if not krest:
            continue
        if _zaklad(krest) not in slova:   # celé jméno: Františka ≠ František, Josefa ≠ Josef
            continue
        if not any(_zaklad(x)[:max(3, len(_zaklad(x)) - 2)] in " ".join(slova) for x in prij):
            continue
        fakt_nar = next((f for f in p.get("f", []) if f.startswith("*")), "")
        nar = _datum(fakt_nar or p.get("y", ""))
        # přesné datum z matriky ±3; přibližný rok („kol. 1810“, jen y) nebo staré sčítání (věk) ±8
        tol = 3 if fakt_nar and nar[0] and "kol" not in fakt_nar and (rok_scit or 1900) >= 1900 else 8
        if rok and nar[2] and abs(rok - nar[2]) > tol:
            continue
        # bez data narození: kdo je ve faktech doložen jako dospělý roku X, nenarodil se po X − 15
        # (dcera * 1910 není Anna Kroupová doložená 1863)
        prvni = min(_roky(" ".join(p.get("f", []))) or [9999])
        if rok and not nar[2] and rok > prvni - 15:
            continue
        # stejnojmenní: přednost má shoda celého data, pak roku, pak bydliště v obci; bez data narození nejméně
        skore = 3 if nar[2] and nar == _datum(radek.get("nar")) else 2 if nar[2] and rok and abs(rok - nar[2]) <= 1 else 0
        if obec and any(_zaklad(obec)[:5] in _zaklad(f) for f in p.get("f", [])):
            skore += 1
        out.append((skore, k, p))
    out.sort(key=lambda x: -x[0])
    if len(out) > 1 and out[0][0] > out[1][0]:
        out = out[:1]
    return [(k, p) for _, k, p in out]


def nacti_prepis(cesta):
    pr = json.load(open(cesta, encoding="utf-8"))
    pr["klic"] = pr.get("klic") or f"s_{pr['rok']}_{re.sub(r'[^a-z0-9]+', '_', bez_diakritiky(pr['obec']).lower())}_cp{pr['cp']}"
    return pr


def cmd_porovnej(cesta):
    """Každý řádek archu proti faktům osoby: ✓ shoda, ≈ jen rok, ✗ rozpor, + nový údaj, ? člověk mimo rodokmen."""
    pr, lide = nacti_prepis(cesta), _lide()
    print(f"{pr['klic']}: sčítání {pr['rok']}, {pr['obec']} čp. {pr['cp']} – {len(pr['radky'])} řádků")
    nalezeni = set()
    for i, r in enumerate(pr["radky"], 1):
        kand = najdi_osobu(r, lide, pr["obec"], pr["rok"])
        hl = f"{i}. {r.get('jmeno')} ({r.get('vztah', '')}, * {r.get('nar', '?')}, {r.get('rodiste', '')})"
        if not kand:
            # jiné příjmení (rodné, z dalšího sňatku, špatně čtené) – stejné křestní jméno a rok narození ±1
            # (rodiště zmíněné ve faktech + přesné narození ±1, jinak odhad z faktů ±5)
            krest, rok = _zaklad(r.get("jmeno", "")).split()[:1], _datum(r.get("nar"))[2]
            rodiste = _zaklad((r.get("rodiste") or "").split(",")[0])[:5]
            mozna = []
            for k, p in lide:
                kp = _jmena_osoby(p)[0]
                if not (krest and rok and kp and _zaklad(kp)[:4] == krest[0][:4]):
                    continue
                presne = _datum(next((f for f in p.get("f", []) if f.startswith("*")), ""))[2]
                fakta = _zaklad(" ".join(p.get("f", [])))
                if rodiste and rodiste in fakta and ((presne and abs(presne - rok) <= 1)
                                                     or (not presne and zivot(p)[0] and abs(zivot(p)[0] - rok) <= 5)):
                    mozna.append(f"{p['n']} [{k}]")
            print(f"  ? {hl}: v rodokmenu není → stopa do note příbuzného + deník"
                  + (f"; možná jde o: {', '.join(mozna)} (jiné příjmení?)" if mozna else ""))
            continue
        if len(kand) > 1:
            print(f"  ! {hl}: víc možných osob: {', '.join(f'{p['n']} [{k}]' for k, p in kand)} – rozhodni podle rodičů/domu")
            continue
        k, p = kand[0]
        nalezeni.add(k)
        fakt = next((f for f in p.get("f", []) if f.startswith("*")), "")
        a, b = _datum(r.get("nar")), _datum(fakt)
        if not fakt or not b[2]:
            stav = f"+ NOVÉ: narození v rodokmenu chybí → doplnit „* {r.get('nar')} {r.get('rodiste', '')}“ (podle sčítání {pr['rok']})"
        elif a == b or (a[0] is None and a[2] == b[2]):
            stav = "✓ shoda s " + fakt
        elif a[2] == b[2] or (a[2] and b[2] and abs(a[2] - b[2]) <= 1 and a[:2] == b[:2]):
            stav = f"≈ část sedí: arch {r.get('nar')} × rodokmen „{fakt}“ – hlášené datum, zkontroluj matriku"
        else:
            stav = f"✗ ROZPOR: arch {r.get('nar')} × rodokmen „{fakt}“ → ISSUES, znovu přečíst matriku"
        misto = r.get("rodiste", "").split()[0] if r.get("rodiste") else ""
        if fakt and misto and _zaklad(misto)[:4] not in _zaklad(fakt):
            stav += f"; rodiště „{r.get('rodiste')}“ ≠ „{fakt}“"
        print(f"  {hl} → {p['n']} [{k}]: {stav}")
    # kdo měl podle plánu v domě být, ale na archu není
    mista = json.load(open(os.path.join(ROOT, "data", "mista.json"), encoding="utf-8"))
    for k, p in lide:
        nar, umr = zivot(p)
        if k in nalezeni or not nar or not (nar <= pr["rok"] <= (umr or nar + 95)):
            continue
        if any(o == pr["obec"] and c == pr["cp"] and (rf is None or abs(rf - pr["rok"]) <= 10) for o, c, rf in bydliste(p, mista)):
            print(f"  – {p['n']} [{k}] má podle faktů v domě bydlet kolem roku {pr['rok']}, na archu není (odstěhoval/zemřel/jiné čp.?)")
    print(f"  do `r` těchto osob přidej „{pr['klic']}“: {', '.join(str(k) for k in sorted(nalezeni, key=str)) or '–'}")


def cmd_zapis(cesta):
    """Připraví vstupy pro zapis.py (svazek, zápis, přepis) do pracovni/scitani/zapis/ a vypíše příkazy."""
    pr = nacti_prepis(cesta)
    d = detail(pr["sada"])
    p, nazev = d["pole"], d["snimky"][pr["snimek"] - 1][0]
    kod = p.get("Kód sady", str(pr["sada"])).strip()
    obec = f"{pr['obec']} čp. {pr['cp']}"
    den = DEN.get(pr["rok"], f"31. 12. {pr['rok']}")
    lidi = "; ".join(f"{r['jmeno']} (" + (f"{r['vztah']}, " if r.get("vztah") else "") + f"* {r.get('nar', '?')}" +
                     (f" {r['rodiste']}" if r.get("rodiste") else "") + ")" for r in pr["radky"])
    sloupce = [("jmeno", "Jméno"), ("vztah", "Vztah k hlavě domácnosti"), ("nar", "Narození"), ("rodiste", "Rodiště"),
               ("nab", "Náboženství"), ("stav", "Rodinný stav"), ("povolani", "Povolání"), ("pozn", "Poznámka")]
    orig = [f"[Sčítání] {den}",
            f"[Obec] {pr['obec']}", f"[Číslo domu] {pr['cp']}"]
    for i, r in enumerate(pr["radky"], 1):
        orig.append(f"[{i}] " + " | ".join(f"{t}: {r[s]}" for s, t in sloupce if r.get(s)))
    out = {
        "svazek": (f"scit_{kod}", {
            "archiv": f"Moravský zemský archiv v Brně – SOkA {p.get('Archiv', '')}, fond {p.get('Název fondu', '')}",
            "portal": "MZA Sčítací operáty",
            "svazek": f"Sčítání lidu {pr['rok']} {p.get('Město/obec', pr['obec'])}"
                      f"{' / ' + p['Část obce/osada'] if p.get('Část obce/osada') else ''}, sada {kod}",
            "popis": f"Archy popisné domů, čp. {p.get('Rozpis čísel popisných', '')} ({len(d['snimky'])} snímků).",
            "url": odkaz(pr["sada"])}),
        "zaznam": (pr["klic"], {
            "klic": pr["klic"], "druh": "S", "datum": den,
            "nazev": f"Sčítání lidu {pr['rok']}: {obec}", "misto": obec, "svazek": f"scit_{kod}",
            "snimek": pr["snimek"], "odkaz": odkaz(pr["sada"], nazev),
            "shrnuti": f"Při sčítání lidu {pr['rok']} žili v domě {obec}: {lidi}."}),
        "prepis": (pr["klic"], {"orig": "\n".join(orig), "cs": pr.get("cs") or
                                f"Sčítání lidu k {den} – "
                                f"dům {obec}. {lidi}. DOPIŠ srozumitelnou větou: kdo byl hlava domácnosti, vztahy, povolání."}),
    }
    adr = os.path.join(CACHE, "zapis")
    os.makedirs(adr, exist_ok=True)
    soubory = {"svazek": "svazky", "zaznam": "zaznamy", "prepis": "prepisy"}
    for co, (klic, obsah) in out.items():
        f = os.path.join(adr, f"{pr['klic']}_{co}.json")
        json.dump(obsah, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"python3 -I tools/zapis.py {soubory[co]} {klic} {os.path.relpath(f, ROOT)}")
    print(f"\nPŘED zápisem: doplň „cs“ v {pr['klic']}_prepis.json (nebo pole \"cs\" v přepisu), pak:\n"
          f"python3 -I tools/vyrez.py pracovni/scitani/{pr['klic']}.jpg {pr['klic']} x0,y0,x1,y1   # celý arch s hlavičkou\n"
          f"python3 -I tools/ramecek.py {pr['klic']} x0,y0,x1,y1                                   # řádky domácnosti\n"
          f"a `r`/`f`/`note` osob podle `scitani.py porovnej {os.path.relpath(cesta, ROOT)}`.")


# --- plán kontroly podle data/osoby.py --------------------------------------------------------------------------
def _roky(text):
    return [int(y) for y in re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", text or "")]


def zivot(p):
    """(od, do) – roky, kdy mohl žít; bez data narození/úmrtí odhad z ostatních faktů."""
    fakta = p.get("f", [])
    nar = next((_roky(f)[0] for f in fakta if f.startswith("*") and _roky(f)), None)
    umr = next((_roky(f)[0] for f in fakta if f.startswith("†") and _roky(f)), None)
    y = re.findall(r"\b1[5-9]\d\d|20\d\d\b", p.get("y", ""))
    nar = nar or (int(y[0]) if y and not p.get("y", "").startswith(("–", "-")) else None)
    vse = _roky(" ".join(fakta))
    if not nar and vse:
        nar = min(vse) - 30
    if not umr:
        umr = (max(vse) + 30) if vse else (nar + 85 if nar else None)
        if nar:
            umr = min(umr, nar + 95)
        if any(f.startswith("†") for f in fakta) and vse:   # zemřel, ale datum nevíme přesně („† před 1922“)
            umr = max(vse)
    return nar, umr


def bydliste(p, mista):
    """[(obec, čp nebo None, rok faktu nebo None)] z faktů osoby (mista.json `re` chytá i skloňování)."""
    out = []
    for f in p.get("f", []):
        if "{{" in f:
            f = re.sub(r"\{\{.*?\}\}", "", f)
        for obec, e in mista.items():
            if e.get("dum"):
                continue
            for m in re.finditer(e.get("re") or re.escape(obec), f):
                za = f[m.end():m.end() + 25]
                cp = re.match(r"\w*\s*(?:čp\.|č\. ?p\.|č\.)\s*(\d+)", za)
                out.append((obec, int(cp.group(1)) if cp else None, (_roky(f) or [None])[0]))
    return out


def cmd_plan(rok_filtr=None, obec_filtr=None):
    ns = {}
    exec(open(os.path.join(ROOT, "data", "osoby.py"), encoding="utf-8").read(), ns)
    mista = json.load(open(os.path.join(ROOT, "data", "mista.json"), encoding="utf-8"))
    zaznamy = json.load(open(os.path.join(ROOT, "data", "zaznamy.json"), encoding="utf-8"))
    hotove = {(int(z["datum"][-4:]), z.get("misto", "")) for z in zaznamy if z.get("druh") == "S" and z.get("datum", "")[-4:].isdigit()}
    lide = [(k, p) for k, p in ns["P"].items()] + [(p.get("id"), p) for p in ns.get("SIDE", [])]
    domy = {}   # (obec, rok) -> {čp|None: [(id, jméno, roky)]}
    for k, p in lide:
        if p.get("st") == "fam" and isinstance(k, int) and k < 4:
            continue
        nar, umr = zivot(p)
        if not nar:
            continue
        byd = bydliste(p, mista)
        if not byd:
            continue
        for rok in ROKY:
            if rok_filtr and rok != rok_filtr or not (nar <= rok <= (umr or nar + 95)):
                continue
            s_cp = [b for b in byd if b[1]]
            # dům z faktu nejbližšího roku sčítání; bez čp. aspoň obec
            vyber = min(s_cp, key=lambda b: abs((b[2] or rok + 50) - rok)) if s_cp else byd[0]
            if obec_filtr and vyber[0] != obec_filtr:
                continue
            domy.setdefault((vyber[0], rok), {}).setdefault(vyber[1], []).append((k, p.get("n", ""), p.get("y", "")))
    radky = ["# Plán kontroly sčítání lidu (MZA Sčítací operáty)", "",
             "Vygenerováno `tools/scitani.py plan` z data/osoby.py. Dům = z faktu, jehož rok je nejblíž sčítání – "
             "lidé se stěhovali, nesedí-li dům, zkus jiné čp. z faktů nebo celou obec. ✓ = zápis sčítání už v datech.", ""]
    for (obec, rok) in sorted(domy, key=lambda x: (x[0], x[1])):
        try:
            ss = sady_obce(obec, rok)
        except OSError as e:
            ss = []
            print(f"POZOR: {obec}: portál neodpověděl ({e})", file=sys.stderr)
        time.sleep(0.3)
        okres = okres_obce(obec)
        if not ss:
            jine = sady_obce(obec)
            roky = ", ".join(map(str, sorted({s["rok"] for s in jine})))
            archivy = {s["archiv"] for s in jine}
            pozor = f", SOkA {', '.join(sorted(archivy))} – stejnojmenná jiná obec?" if okres and okres not in archivy else ""
            radky.append(f"## {obec} {rok} – nedochováno" + (f" (online jen {roky}{pozor})" if jine
                                                                   else " (obec na portálu není – jiný název?)"))
        else:
            archivy = {s["archiv"] for s in ss}
            pozor = " – pozor: jiný okres než v mista.json, ověř obec" if okres and okres not in archivy else ""
            radky.append(f"## {obec} {rok} (SOkA {', '.join(sorted(archivy))}){pozor}")
        for cp in sorted(domy[(obec, rok)], key=lambda c: (c is None, c or 0)):
            lid = ", ".join(f"{n} ({y}) [{k}]" for k, n, y in domy[(obec, rok)][cp])
            if cp is None:
                radky.append(f"- **bez čp.** – projít obec: {lid}")
                continue
            sada = next((s for s in ss if cp in rozsah_cp(s["cp"])), None)
            kde = ""
            if sada:
                try:
                    n = odhad_snimku(sada, cp, len(detail(sada["id"])["snimky"]))
                    kde = f" → `scitani.py snimek {sada['id']} {n} …` (odhad)"
                except (OSError, SystemExit):
                    kde = f" → sada {sada['id']}"
            hot = " ✓" if (rok, f"{obec} čp. {cp}") in hotove else ""
            radky.append(f"- čp. {cp}{hot}: {lid}{kde}")
        radky.append("")
    os.makedirs(CACHE, exist_ok=True)
    jmeno = "plan" + (f"_{rok_filtr}" if rok_filtr else "") + (f"_{re.sub(r'\W+', '_', obec_filtr.lower())}" if obec_filtr else "")
    out = os.path.join(CACHE, f"{jmeno}.md")   # filtrovaný plán nepřepisuje celý plan.md
    open(out, "w", encoding="utf-8").write("\n".join(radky))
    pocet = sum(len(v) for v in domy.values())
    print(f"{len(domy)} obcí×roků, {pocet} domácností ke kontrole → {out}")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "sady" and len(a) >= 2:
        return cmd_sady(a[1], int(a[2]) if len(a) > 2 else None)
    if a[0] == "najdi" and len(a) == 4:
        return cmd_najdi(a[1], int(a[2]), int(a[3]))
    if a[0] == "snimek" and len(a) >= 4:
        crop = [float(v) for v in a[a.index("--crop") + 1].split(",")] if "--crop" in a else None
        return cmd_snimek(int(a[1]), int(a[2]), a[3], "--nahled" in a, crop)
    if a[0] == "hlavicky" and len(a) == 5:
        return cmd_hlavicky(int(a[1]), int(a[2]), int(a[3]), a[4])
    if a[0] == "porovnej" and len(a) == 2:
        return cmd_porovnej(a[1])
    if a[0] == "zapis" and len(a) == 2:
        return cmd_zapis(a[1])
    if a[0] == "svazek" and len(a) == 2:
        return cmd_svazek(int(a[1]))
    if a[0] == "plan":
        rok = int(a[a.index("--rok") + 1]) if "--rok" in a else None
        obec = a[a.index("--obec") + 1] if "--obec" in a else None
        return cmd_plan(rok, obec)
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
