#!/usr/bin/env python3
"""Export dat rodokmenu z data/osoby.py, zaznamy.json a svazky.json do formátu GEDCOM 5.5.1.

Vytváří data/rodokmen.ged a web/public/rodokmen.ged.
Kompatibilní s MyHeritage, Family Tree Maker, Gramps, Ancestry, Geneanet apod.
"""
import datetime, json, os, re, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
DATA = os.environ.get("RODOKMEN_DATA") or os.path.join(ROOT, "data")
PUBLIC = os.path.join(ROOT, "web", "public")

MONTHS = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
}

ZN_RX = re.compile(r"\{\{\s*(neověřeno|neovereno|rodina|strom|hypotéza|hypoteza)\s*(?::\s*(.*?))?\s*\}\}", re.S)


def bez_znacek(text):
    """{{strom: † 1849}} → „† 1849 (neověřeno)“ – GEDCOM značky nezná, ale informace o nejistotě zůstane."""
    return ZN_RX.sub(lambda m: ((m.group(2) or "").strip() + " (neověřeno)").strip(), text or "").strip()


# měsíce v 7. a 6. pádě („před červnem“, „v lednu“) → číslo měsíce
MESICE = {"lednem": 1, "únorem": 2, "březnem": 3, "dubnem": 4, "květnem": 5, "červnem": 6, "červencem": 7, "srpnem": 8,
          "zářím": 9, "říjnem": 10, "listopadem": 11, "prosincem": 12, "lednu": 1, "únoru": 2, "březnu": 3, "dubnu": 4,
          "květnu": 5, "červnu": 6, "červenci": 7, "srpnu": 8, "září": 9, "říjnu": 10, "listopadu": 11, "prosinci": 12}

ZIJE_LET = 110   # stejné pravidlo jako zije() v export_web.py


def zije(y, facts, *texty):
    """Žijící: u osoby stojí „žijící“, nebo se narodila před méně než ZIJE_LET lety a nemá úmrtí (rozsah let, †)."""
    if any("žijící" in (t or "").lower() for t in [*facts, *texty]):
        return True
    y = y or ""
    if "†" in y or re.search(r"–\D*\d{4}", y) or any(f.lstrip().startswith("†") for f in facts):
        return False
    m = re.search(r"\d{4}", y) or re.search(r"\d{4}", " ".join(f for f in facts if f.lstrip().startswith("*")))
    return bool(m) and int(m.group(0)) > datetime.date.today().year - ZIJE_LET


def parse_date_place(text):
    """Z textu typu '* 12. 11. 1891 Chlum čp. 9' získá (gedcom_date, place)."""
    t = text.lstrip("* ×†").strip()
    
    # Prefixy
    t = re.sub(r"\s*\([^)]*\)", "", t).strip()   # „(podle sčítání 1857)“ není místo
    t = re.split(r",\s*(?:pohřben|pochován)", t)[0].strip()   # „…, pohřbena 31. 5. 1946“ není místo
    m = re.match(r"^mezi\s+((?:\d{1,2}\.\s*\d{1,2}\.\s*)?\d{4})\s+a\s+((?:\d{1,2}\.\s*\d{1,2}\.\s*)?\d{4})(.*)$", t)
    if m:   # „† mezi 1911 a 1921“, „† mezi 31. 10. 1857 a 8. 3. 1860“
        return f"BET {parse_date_place(m.group(1))[0]} AND {parse_date_place(m.group(2))[0]}", m.group(3).strip(" ,") or None
    prefix = ""
    if t.startswith(("kol.", "cca")):   # vypočteno z věku (při sňatku, úmrtí, sčítání)
        prefix = "ABT "
        t = re.sub(r"^(kol\.|cca)\s*", "", t)
    elif t.startswith("asi"):           # odhad (např. podle narození dětí)
        prefix = "EST "
        t = re.sub(r"^asi\s*", "", t)
    elif t.startswith("před"):
        prefix = "BEF "
        t = re.sub(r"^před\s*", "", t)
    elif t.startswith("po"):
        prefix = "AFT "
        t = re.sub(r"^po\s*", "", t)
    
    # 1. Den. Měsíc. Rok Místo
    m = re.match(r"^(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})(.*)$", t)
    if m:
        d, mo, y, rest = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4).strip()
        date_str = f"{prefix}{d} {MONTHS.get(mo, 'JAN')} {y}".strip()
        return date_str, rest or None
    
    # 2. Měsíc slovem: „před červnem 1925“, „v lednu 1857“ → BEF JUN 1925
    m = re.match(r"^(?:v\s+)?(" + "|".join(MESICE) + r")\s+(\d{4})(.*)$", t)
    if m:
        return f"{prefix}{MONTHS[MESICE[m.group(1)]]} {m.group(2)}".strip(), m.group(3).strip() or None

    # 3. Století („20. stol. Holice“, „18.–19. stol.“): datum GEDCOM neumí, místo je až za ním
    m = re.match(r"^.*?stol\.\s*(.*)$", t)
    if m:
        return None, m.group(1).strip() or None

    # 4. Jen rok: 1891 Místo
    m = re.match(r"^(\d{4})(.*)$", t)
    if m:
        y, rest = m.group(1), m.group(2).strip()
        return f"{prefix}{y}".strip(), rest or None

    return None, t or None

def parse_marriage(fact):
    """„× 2. 16. 6. 1925 Antonín Holubář († 1950) z Okřešic“ → (2, „16 JUN 1925“, „Antonín Holubář“).
    Pořadí („2.“) se píše jen u více sňatků; od data ho pozná to, že po něm následuje celé datum, rok nebo jméno."""
    t = bez_znacek(fact).lstrip("× ").strip()
    m = re.match(r"(\d)\.\s+(?=\d{1,2}\.\s*\d{1,2}\.\s*\d{4}|\d{4}|\D)", t)
    order = int(m.group(1)) if m else None
    t = t[m.end():] if m else t
    m = re.match(r"((kol\.|asi|před|po)\s*)?(\d{1,2}\.\s*\d{1,2}\.\s*)?\d{4}", t)
    date = parse_date_place(m.group(0))[0] if m else None
    spouse = re.sub(r"\s*\(.*?\)", "", t[m.end():] if m else t)
    return order, date, re.split(r"\s+z\s+|,", spouse)[0].strip()


def jmeno_sedi(spouse, name):
    """Jméno ze sňatku patří osobě: stejné příjmení (první 4 písmena); je-li ve sňatku jen křestní, stejné křestní."""
    s = spouse.replace("roz. ", "").split()
    n = re.sub(r"\s*\(.*?\)", "", name or "").replace("roz. ", "").split()
    if not s or not n:
        return False
    if len(s) == 1 or len(n) == 1 or "…" in s[-1]:   # příjmení neznámé nebo nečitelné → stačí křestní
        return s[0] == n[0]
    return s[-1][:4] == n[-1][:4]


def split_name(full_name):
    """Rozdělí 'Jméno Příjmení' nebo 'Anna Matějíčková (?)' na jméno a příjmení."""
    clean = re.sub(r"\s*\([^)]*\)", "", full_name).strip()
    parts = clean.split()
    if len(parts) == 1:
        return parts[0], ""
    givn = " ".join(parts[:-1])
    surn = parts[-1].rstrip("?")
    return givn, surn

def generate_gedcom():
    ns = {}
    with open(os.path.join(DATA, "osoby.py"), encoding="utf-8") as f:
        exec(f.read(), ns)
    P = dict(ns.get("P", {}))
    SAME = ns.get("SAME", {})
    # širší rodina: strukturované položky SIDE (otec/matka/partner) – klíč = id (text), rodiče = Kekulé nebo id
    REL = {}
    for s in ns.get("SIDE", []):
        if not any(x in s for x in ("otec", "matka", "partner", "id")):
            continue
        sid = s.get("id") or re.sub(r"[^a-z0-9]+", "_", s["n"].lower())
        if sid in REL or sid in P:
            continue
        m = re.search(r"\(([^()]*\d{4}[^()]*)\)", s["n"])
        REL[sid] = dict(s, n=re.sub(r"\s*\(.*?\)\s*", " ", s["n"]).strip(), y=s.get("y") or (m.group(1) if m else ""))
    for sid, s in REL.items():
        P[sid] = s
    
    zaznamy = []
    if os.path.exists(os.path.join(DATA, "zaznamy.json")):
        with open(os.path.join(DATA, "zaznamy.json"), encoding="utf-8") as f:
            zaznamy = json.load(f)
    
    svazky = {}
    if os.path.exists(os.path.join(DATA, "svazky.json")):
        with open(os.path.join(DATA, "svazky.json"), encoding="utf-8") as f:
            svazky = json.load(f)

    # Identifikace rodin (otec, matka -> dítě)
    # Pro každou osobu k > 1:
    # otec = 2*k, matka = 2*k + 1
    families = {} # (f_k, m_k): {'id': 'F...', 'husb': f_k, 'wife': m_k, 'children': [k], 'marr': None}
    person_fams = {} # k: [fid]
    person_famc = {} # k: fid

    def canon(x):
        return SAME.get(x, x) if isinstance(x, int) else x

    def rodice(k):
        """(otec, matka) osoby k: u předků z Kekulého čísla, u širší rodiny z 'otec'/'matka'."""
        if isinstance(k, int):
            return (canon(2 * k) if 2 * k in P else None, canon(2 * k + 1) if 2 * k + 1 in P else None)
        s = P[k]
        o, m = canon(s.get("otec")), canon(s.get("matka"))
        return (o if o in P else None, m if m in P else None)

    kl = sorted(P.keys(), key=lambda x: (isinstance(x, str), x if isinstance(x, int) else 0, str(x)))
    for child in kl:
        fk, mk = rodice(child)
        if fk is not None or mk is not None:
            fkey = (fk, mk)
            if fkey not in families:
                fid = f"F{len(families) + 1}"
                families[fkey] = {
                    'id': fid,
                    'husb': fkey[0],
                    'wife': fkey[1],
                    'children': [child],
                    'marr': None
                }
            else:
                if child not in families[fkey]['children']:
                    families[fkey]['children'].append(child)
            person_famc[child] = families[fkey]['id']
            if fkey[0]:
                person_fams.setdefault(fkey[0], []).append(families[fkey]['id'])
            if fkey[1]:
                person_fams.setdefault(fkey[1], []).append(families[fkey]['id'])

    for sid, s in REL.items():
        pa = s.get("partner")
        for x in (pa if isinstance(pa, list) else [pa]):
            x = canon(x)
            if x is None or x not in P:
                continue
            male = (s.get("sex") or ("M" if not s["n"].split()[-1].endswith(("ová", "á")) else "F")) == "M"
            fkey = (sid, x) if male else (x, sid)
            if fkey not in families:
                families[fkey] = {'id': f"F{len(families) + 1}", 'husb': fkey[0], 'wife': fkey[1], 'children': [], 'marr': None}
                for y in fkey:
                    person_fams.setdefault(y, []).append(families[fkey]['id'])

    # Sňatek rodiny: ten údaj „×“ manžela, který jmenuje manželku (a naopak) – vdova/vdovec má i sňatky s jinými.
    # Pořadí sňatků každé osoby („× 2. …“, jinak rok) určí pořadí jejích rodin (FAMS).
    poradi = {}   # (osoba, id rodiny) → klíč řazení
    for fkey, fam in families.items():
        sn = []
        for a, b in ((fam['husb'], fam['wife']), (fam['wife'], fam['husb'])):
            if a is None or a not in P:
                continue
            for fact in P[a].get('f', []):
                if not fact.startswith('×'):
                    continue
                order, date, spouse = parse_marriage(fact)
                if b is not None and b in P and jmeno_sedi(spouse, P[b].get('n')):
                    sn.append(date)
                    y = re.search(r"\d{4}", date or "")
                    poradi[(a, fam['id'])] = (order or 99, int(y.group(0)) if y else 9999)
                    break
        if any(sn):
            fam['marr'] = (next(d for d in sn if d), None)
        elif sn:
            fam['marr'] = (None, None)
    for x, fids in person_fams.items():
        fids.sort(key=lambda fid: poradi.get((x, fid), (99, 9999)))

    web_cfg = {}
    web_json_p = os.path.join(DATA, "web.json")
    if os.path.exists(web_json_p):
        try:
            with open(web_json_p, "r", encoding="utf-8") as f:
                web_cfg = json.load(f)
        except Exception:
            pass
    tree_name = web_cfg.get("nazev") or "Rodokmen"
    subm_name = (web_cfg.get("kontakt") or {}).get("jmeno") or "Rodokmen"

    now_str = datetime.datetime.now().strftime("%d %b %Y").upper()
    lines = [
        "0 HEAD",
        "1 SOUR AntigravityRodokmen",
        "2 VERS 1.0",
        f"2 NAME {tree_name}",
        f"1 DATE {now_str}",
        "1 GEDC",
        "2 VERS 5.5.1",
        "2 FORM LINEAGE-LINKED",
        "1 CHAR UTF-8",
        "1 SUBM @SUBM1@",
        "0 @SUBM1@ SUBM",
        f"1 NAME {subm_name}",
    ]

    # Zápis osob (INDI)
    def iid(k):
        return f"@I{k}@" if isinstance(k, int) else f"@R_{k}@"

    for k in kl:
        p = P[k]
        name = p.get("n", "")
        givn, surn = split_name(name)
        sex = p.get("sex")
        if not sex:
            sex = ("M" if k % 2 == 0 or k == 1 else "F") if isinstance(k, int) else ("F" if surn.endswith(("ová", "á")) else "M")

        lines.append(f"0 {iid(k)} INDI")
        lines.append(f"1 NAME {givn} /{surn}/")
        lines.append(f"2 GIVN {givn}")
        if surn:
            lines.append(f"2 SURN {surn}")
        for fact in p.get("f", []):   # příjmení po svatbě („provdaná Rymešová, později Holubářová“) jako další jména
            m = re.match(r"provd(?:aná|\.)\s+(?!za\b)(.+)", bez_znacek(fact))
            for part in re.split(r",\s*(?:později\s+)?|\s+později\s+", m.group(1)) if m else []:
                if part[:1].isupper():
                    lines += [f"1 NAME {givn} /{part.split()[0]}/", "2 TYPE married"]
        lines.append(f"1 SEX {sex}")
        if isinstance(k, int):
            lines.append(f"1 _KEKULE {k}")

        # Fakta
        birt_done = False
        deat_done = False
        occupations = []
        for fact in [bez_znacek(x) for x in p.get("f", [])]:
            if fact.startswith("*") and not birt_done:
                birt_done = True
                d, pl = parse_date_place(fact)
                lines.append("1 BIRT")
                if d:
                    lines.append(f"2 DATE {d}")
                if pl:
                    lines.append(f"2 PLAC {pl}")
            elif fact.startswith("†") and not deat_done:
                deat_done = True
                d, pl = parse_date_place(fact)
                lines.append("1 DEAT")
                if d:
                    lines.append(f"2 DATE {d}")
                if pl:
                    lines.append(f"2 PLAC {pl}")
            elif any(w in fact.lower() for w in ["rolník", "sedlák", "chalupník", "půlláník", "výměnkář", "kยิ่ง"]):
                occupations.append(fact)

        # bez faktu * / † aspoň odhad z roků y („kol. 1790–1862“, „asi 1800 – před 1857“) – MyHeritage podle nich páruje
        y = (p.get("y") or "").strip()
        if not y.startswith("*") and re.search(r"\d{4}", y):
            # „1835 – před 1921“ / „18.–19. stol. – před 1818“ dělí mezera-pomlčka-mezera, „1830–1890“ jen pomlčka
            hlava, _, ocas = y.partition(" – ") if " – " in y else y.partition("–")
            for jde, cast, znacka in ((not birt_done, hlava, "BIRT"), (not deat_done, ocas, "DEAT")):
                d = parse_date_place(cast)[0] if jde and re.search(r"\d{4}", cast or "") else None
                if d:
                    lines += [f"1 {znacka}", f"2 DATE {d}"]
                    deat_done = deat_done or znacka == "DEAT"

        for occ in occupations:
            lines.append("1 OCCU " + occ)

        if not deat_done:
            is_living = zije(p.get("y"), p.get("f", []), p.get("note"), p.get("t"), p.get("pribeh"))
            if not is_living and (isinstance(k, str) or k > 3):
                lines.append("1 DEAT Y")

        if p.get("note"):
            lines.append(f"1 NOTE {bez_znacek(p['note'])}")
        if p.get("pribeh"):
            lines.append("1 NOTE " + bez_znacek(p["pribeh"]).replace("\n", " "))

        # Odkazy na rodiny
        if k in person_famc:
            lines.append(f"1 FAMC @{person_famc[k]}@")
        for fid in dict.fromkeys(person_fams.get(k, [])):
            lines.append(f"1 FAMS @{fid}@")

        # Odkazy na prameny
        for rk in p.get("r", []):
            lines.append(f"1 SOUR @S_{rk}@")

    # Zápis rodin (FAM)
    for fkey, fam in families.items():
        lines.append(f"0 @{fam['id']}@ FAM")
        if fam['husb']:
            lines.append(f"1 HUSB {iid(fam['husb'])}")
        if fam['wife']:
            lines.append(f"1 WIFE {iid(fam['wife'])}")
        for ch in fam['children']:
            lines.append(f"1 CHIL {iid(ch)}")
        if fam.get('marr'):
            md, mpl = fam['marr']
            lines.append("1 MARR" if md or mpl else "1 MARR Y")
            if md:
                lines.append(f"2 DATE {md}")
            if mpl:
                lines.append(f"2 PLAC {mpl}")

    # Zápis zdrojů (SOUR)
    for z in zaznamy:
        key = z["klic"]
        sv = svazky.get(z.get("svazek", ""), {})
        lines.append(f"0 @S_{key}@ SOUR")
        lines.append(f"1 TITL {z.get('nazev', key)}")
        if sv.get("archiv"):
            lines.append(f"1 AUTH {sv['archiv']}")
        if sv.get("svazek"):
            lines.append(f"1 PUBL {sv['svazek']}")
        note_parts = []
        if z.get("snimek"):
            note_parts.append(f"snímek {z['snimek']}")
        if z.get("shrnuti"):
            note_parts.append(z['shrnuti'])
        if z.get("odkaz") or sv.get("url"):
            note_parts.append(z.get("odkaz") or sv.get("url"))
        if note_parts:
            lines.append(f"1 NOTE {' · '.join(note_parts)}")

    lines.append("0 TRLR")
    content = "\n".join(lines) + "\n"

    # Uložit do data/rodokmen.ged i web/public/rodokmen.ged
    os.makedirs(PUBLIC, exist_ok=True)
    out_data = os.path.join(DATA, "rodokmen.ged")
    out_web = os.path.join(PUBLIC, "rodokmen.ged")
    with open(out_data, "w", encoding="utf-8") as f:
        f.write(content)
    with open(out_web, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"GEDCOM úspěšně vygenerován ({len(P)} osob, {len(families)} rodin, {len(zaznamy)} pramenů) -> {out_web}")

if __name__ == "__main__":
    generate_gedcom()
