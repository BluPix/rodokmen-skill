#!/usr/bin/env python3
"""
roky.py – roky života osob (pole `y` v data/osoby.py) podle faktů a zvyklostí genealogie.

Roky se ukazují ve stromu, na webu a jdou do GEDCOMu (MyHeritage podle nich páruje) – mají proto být vždy co
nejpřesnější a nejistota musí být vidět:
  1835            přesně (křest, úmrtní zápis, sčítání s celým datem)          GEDCOM 1835
  kol. 1790       vypočteno z věku (při sňatku, úmrtí, ve sčítání jen rok)       GEDCOM ABT 1790
  asi 1790        odhad podle narození nejstaršího dítěte (matka −25, otec −30) GEDCOM EST 1790
  před 1860       jen horní mez (úmrtí: „† před 1860“, „† mezi 1857 a 1860“)    GEDCOM BEF 1860
  po 1910         žil ještě v tom roce                                           GEDCOM AFT 1910
  ?               nevíme
Celek „narození–úmrtí“: „1835–1890“, s nejistotou mezery kolem pomlčky: „kol. 1790 – před 1857“, „asi 1800 – ?“.

Použití (z kořene projektu):
  python3 -I tools/roky.py                 # návrhy změn (osoba | teď | návrh | proč)
  python3 -I tools/roky.py --zapis         # zapíše návrhy do data/osoby.py (mění jen pole y)
  python3 -I tools/roky.py --vse           # vypíše i osoby beze změny
Žijící lidé (st="fam" a narození po 1925) se nemění. Odhad „asi“ se nepřepíše, pokud fakta dávají přesnější údaj.
"""
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("RODOKMEN_DATA") or os.path.join(ROOT, "data")
OSOBY = os.path.join(DATA, "osoby.py")
ROK = r"(1[4-9]\d\d|20\d\d)"


def bez_znacek(t):
    return re.sub(r"\{\{\s*(?:neověřeno|rodina|strom|hypotéza)\s*:?\s*(.*?)\}\}", r"\1", t or "")


def cast_narozeni(fakta):
    """(text, důvod) pro narození z faktu „* …“, nebo (None, None)."""
    for f in fakta:
        f = bez_znacek(f).strip()
        if not f.startswith("*"):
            continue
        t = f.lstrip("* ").strip()
        m = re.match(r"(kol\.|asi|cca|před|po)\s*(?:\d{1,2}\.\s*\d{1,2}\.\s*)?" + ROK, t)
        if m:
            pre = {"cca": "kol."}.get(m.group(1), m.group(1))
            return f"{pre} {m.group(2)}", "fakt " + f[:60]
        m = re.match(r"(\d{1,2}\.\s*\d{1,2}\.\s*)?" + ROK, t)
        if m:
            # jen rok ze sčítání = hlášený věk → kol.; celé datum (matrika i sčítání) → přesně
            jen_rok = not m.group(1)
            return (f"kol. {m.group(2)}" if jen_rok and "sčítání" in t else m.group(2)), "fakt " + f[:60]
    return None, None


def cast_umrti(fakta):
    for f in fakta:
        f = bez_znacek(f).strip()
        if not f.startswith("†"):
            continue
        t = f.lstrip("† ").strip()
        m = re.match(r"mezi\s+(?:\d{1,2}\.\s*\d{1,2}\.\s*)?" + ROK + r"\s+a\s+(?:\d{1,2}\.\s*\d{1,2}\.\s*)?" + ROK, t)
        if m:
            return f"před {m.group(2)}", "fakt " + f[:60]
        m = re.match(ROK + r"\s*[–-]\s*" + ROK + r"(?!\.)", t)   # „† 1891–1900 (podle sčítání)“ → zemřel do konce 1900
        if m:
            return f"před {int(m.group(2)) + 1}", "fakt " + f[:60]
        m = re.match(r"(před|po|kol\.|asi)\s*(?:\w+\s+)?(?:\d{1,2}\.\s*\d{1,2}\.\s*)?" + ROK, t)
        if m:
            return f"{m.group(1)} {m.group(2)}", "fakt " + f[:60]
        m = re.match(r"(?:\d{1,2}\.\s*\d{1,2}\.\s*)?" + ROK, t)
        if m:
            return m.group(1), "fakt " + f[:60]
    return None, None


def rozloz(y):
    """„kol. 1790 – před 1857“ → („kol. 1790“, „před 1857“); „1830–1890“ → („1830“, „1890“); „* 1931“ → („* 1931“, None)."""
    y = (y or "").strip()
    if " – " in y:
        a, b = y.split(" – ", 1)
    elif re.search(r"\d–", y):
        a, b = y.split("–", 1)
    else:
        a, b = y, None
    return a.strip(), (b.strip() if b is not None else None)


def sloz(nar, umr):
    nar = nar or "?"
    if umr is None:
        return nar if nar != "?" else "?"
    jiste = re.fullmatch(r"\d{4}", nar) and re.fullmatch(r"\d{4}", umr)
    return f"{nar}–{umr}" if jiste else f"{nar} – {umr}"


def navrhy():
    ns = {}
    exec(open(OSOBY, encoding="utf-8").read(), ns)
    P, SIDE = ns["P"], ns.get("SIDE", [])
    lide = [(k, p) for k, p in P.items()] + [(p.get("id"), p) for p in SIDE if p.get("id")]
    deti = {}   # klíč rodiče → [rok narození dítěte]
    for k, p in P.items():
        r = cast_narozeni(p.get("f", []))[0]
        if r and re.search(ROK, r):
            for rod in (2 * k, 2 * k + 1):   # Kekulé: rodiče osoby k jsou 2k a 2k+1
                deti.setdefault(rod, []).append(int(re.search(ROK, r).group(1)))
    for p in SIDE:
        r = cast_narozeni(p.get("f", []))[0]
        if r and re.search(ROK, r):
            for rod in (p.get("otec"), p.get("matka")):
                if rod is not None:
                    deti.setdefault(rod, []).append(int(re.search(ROK, r).group(1)))
    out = []
    for k, p in lide:
        if re.search(r"\b(neuveden|neznám)", p.get("n", ""), re.I):
            continue   # zástupná osoba („otec neuveden“) – žádné roky
        y = p.get("y", "")
        fakta = p.get("f", [])
        nar_ted, umr_ted = rozloz(y)
        nar, proc_n = cast_narozeni(fakta)
        if p.get("st") == "fam" and nar and re.search(ROK, nar) and int(re.search(ROK, nar).group(1)) > 1925:
            continue   # žijící / nedávní – roky se nepřepisují
        if nar_ted.startswith("†"):   # „† 1924“ – rok narození neznáme
            nar_ted = "?"
        if not nar:
            vek = next((re.search(r"(\d{1,3}) (?:let|roky?)\b", bez_znacek(f)) for f in fakta
                        if f.startswith("†") and re.search(r"\d{1,3} (?:let|roky?)\b", f)), None)
            rok_umr = cast_umrti(fakta)[0]
            if vek and rok_umr and re.fullmatch(ROK, rok_umr):
                nar, proc_n = f"kol. {int(rok_umr) - int(vek.group(1))}", f"{vek.group(1)} let při úmrtí"
        if not nar:
            if re.search(ROK, nar_ted) and not nar_ted.startswith("*"):
                nar, proc_n = nar_ted, "ponecháno"
            elif deti.get(k):
                zena = p.get("sex") == "F" or (isinstance(k, int) and k % 2 == 1)
                nar = f"asi {min(deti[k]) - (25 if zena else 30)}"
                proc_n = f"nejstarší známé dítě * {min(deti[k])}"
        umr, proc_u = cast_umrti(fakta)
        if not umr:
            if umr_ted and re.search(ROK + r"|\?", umr_ted):
                umr, proc_u = umr_ted, "ponecháno"
            elif nar and re.search(ROK, nar) and int(re.search(ROK, nar).group(1)) < 1925:
                umr, proc_u = "?", "úmrtí neznáme"
        if nar_ted.startswith("*") and not umr:
            continue   # „* 1931“ – žijící nebo úmrtí neznáme, nesahat
        novy = sloz(nar, umr)
        if not nar and not umr:
            continue
        out.append((k, p.get("n", ""), y, novy, "; ".join(x for x in (proc_n, proc_u) if x and x != "ponecháno")))
    return out


def zapis(zmeny):
    text = open(OSOBY, encoding="utf-8").read()
    hotovo = 0
    for k, _, stary, novy, _ in zmeny:
        if isinstance(k, int):
            m = re.search(rf"^\s*{k}: dict\(", text, re.M)
        else:
            m = re.search(rf"id=[\"']{re.escape(k)}[\"']", text)
            if m:   # začátek té položky SIDE
                m = list(re.finditer(r"dict\(", text[:m.start()]))[-1]
        if not m:
            print(f"POZOR: osoba {k} v osoby.py nenalezena", file=sys.stderr)
            continue
        konec = re.search(r"^\s*(?:\d+: )?dict\(", text[m.end():], re.M)
        konec = m.end() + konec.start() if konec else len(text)
        usek = text[m.start():konec]
        nov_usek, n = re.subn(r"""\by=(["'])""" + re.escape(stary) + r"\1", lambda mm: f'y="{novy}"', usek, count=1)
        if not n and not stary:   # osoba zatím bez y – přidat za jméno
            nov_usek, n = re.subn(r"""(\bn=(["']).*?\2,)""", lambda mm: f'{mm.group(1)} y="{novy}",', usek, count=1)
        if not n:
            print(f"POZOR: u osoby {k} nenalezeno y=\"{stary}\"", file=sys.stderr)
            continue
        text = text[:m.start()] + nov_usek + text[konec:]
        hotovo += 1
    open(OSOBY, "w", encoding="utf-8", newline="\n").write(text)
    print(f"zapsáno {hotovo} změn roků do data/osoby.py")


def main():
    vse = navrhy()
    zmeny = [x for x in vse if x[2] != x[3]]
    for k, n, stary, novy, proc in (vse if "--vse" in sys.argv else zmeny):
        print(f"{str(k):28} {n[:28]:28} {stary or '–':26} → {novy:26} {proc}")
    print(f"\n{len(zmeny)} změn z {len(vse)} osob" + ("" if "--zapis" in sys.argv else " (zapsat: --zapis)"))
    if "--zapis" in sys.argv and zmeny:
        zapis(zmeny)


if __name__ == "__main__":
    main()
