#!/usr/bin/env python3
"""Vypíše jen to, co potřebuješ z velkých datových souborů – místo čtení celého data/osoby.py (540 kB) nebo JSONů.

Použití (z kořene projektu):
  osoba.py <číslo|id> [...]        osoba podle Kekulého čísla (64) nebo id boční osoby (josef_novak_1865):
                                   řádek v data/osoby.py, n, y, st, fakta f, zápisy r, t, začátek note
                                   (celá poznámka s --note, příběh s --pribeh)
  osoba.py --hledej <text>         čísla a id osob, jejichž jméno obsahuje text (bez diakritiky, malá/velká písmena)
  osoba.py --fakta <text>          osoby a jen ta jejich fakta, která obsahují text (místo, rok, čp., povolání) –
                                   místo `grep` nad osoby.py, který vrací celé dlouhé řádky
  osoba.py --zaznam <klíč> [...]   položka zápisu ze zaznamy.json + přepis (prepisy.json) + rámeček (zvyrazneni.json)
  osoba.py --issues <text>         otázky z ISSUES, jejichž nadpis obsahuje text
Fakta se vypisují přesně jako ve zdroji (v uvozovkách), takže je jde rovnou použít jako old_string pro Edit.
"""
import json, os, sys, unicodedata
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def bez(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def nacti():
    path = os.path.join(DATA, "osoby.py")
    text = open(path, encoding="utf-8").read()
    ns = {}
    exec(text, ns)
    return ns, text.split("\n")


def radek(lines, hledane):
    return next((i + 1 for i, l in enumerate(lines) if hledane in l), "?")


def vypis(o, cislo, lines, pribeh, note):
    if cislo is not None:
        hdr, rr = f"#{cislo}", radek(lines, f"    {cislo}: dict(")
    else:
        hdr, rr = f"SIDE id={o['id']} (k={o.get('k')})", radek(lines, f'id="{o["id"]}"')
    print(f"=== {hdr} – {o.get('n', '')} ({o.get('y', '')}), st={o.get('st', '')}   [data/osoby.py ř. {rr}]")
    for k in ("sex", "partner", "otec", "matka"):
        if k in o:
            print(f"{k}: {o[k]}")
    for f in o.get("f", []):
        print("  f:", json.dumps(f, ensure_ascii=False))
    if o.get("r"):
        print("r:", ", ".join(o["r"]))
    n = o.get("note") or ""
    if not note and len(n) > 300:   # poznámky jsou 43 % osoby.py – celé jen na vyžádání
        n = f"{n[:300]}… (celkem {len(n)} znaků – celé s --note)"
    for k, v in (("t", o.get("t")), ("note", n)) + ((("pribeh", o.get("pribeh")),) if pribeh else ()):
        if v:
            print(f"{k}: {v}")
    if not pribeh and o.get("pribeh"):
        print(f"pribeh: ({len(o['pribeh'])} znaků – vypiš s --pribeh)")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--zaznam":
        z = {x.get("klic"): x for x in json.load(open(os.path.join(DATA, "zaznamy.json"), encoding="utf-8"))}
        p = json.load(open(os.path.join(DATA, "prepisy.json"), encoding="utf-8"))
        v = json.load(open(os.path.join(DATA, "zvyrazneni.json"), encoding="utf-8"))
        for k in args[1:]:
            print(f"=== {k}")
            for nazev, src in (("zaznamy", z), ("prepisy", p), ("zvyrazneni", v)):
                print(f"{nazev}:", json.dumps(src[k], ensure_ascii=False, indent=1) if k in src else "— chybí —")
        return
    ns, lines = nacti()
    P, SIDE = ns.get("P", {}), [s for s in ns.get("SIDE", []) if isinstance(s, dict)]
    if args[0] in ("--hledej", "--fakta"):
        q, fakta = bez(" ".join(args[1:])), args[0] == "--fakta"
        if not q:
            sys.exit(__doc__)
        vsichni = [(f"#{n}", o) for n, o in sorted(P.items())] + \
                  [(o.get("id", "(bez id, k=%s)" % o.get("k")), o) for o in SIDE]
        for oid, o in vsichni:
            hity = [json.dumps(f, ensure_ascii=False) for f in o.get("f", [])] if fakta else []
            hity = [h for h in hity if q in bez(h)]
            if hity or (not fakta and q in bez(o.get("n", ""))):
                print(f"{oid}  {o.get('n')} ({o.get('y', '')})")
                for h in hity:
                    print("  f:", h)
        return
    if args[0] == "--issues":
        q = bez(" ".join(args[1:]))
        for i, it in enumerate(ns.get("ISSUES", [])):
            nadpis, text = (it[0], it[1]) if isinstance(it, (tuple, list)) else (str(it), "")
            if q in bez(nadpis):
                print(f"=== ISSUES[{i}] {nadpis}\n{text}")
        return
    pribeh, note = "--pribeh" in args, "--note" in args
    for a in (a for a in args if a not in ("--pribeh", "--note")):
        if a.lstrip("#").isdigit():
            o = P.get(int(a.lstrip("#")))
            if o is None:
                print(f"=== #{a}: není v P (volné číslo)")
            else:
                vypis(o, int(a.lstrip("#")), lines, pribeh, note)
        else:
            o = next((s for s in SIDE if s.get("id") == a), None)
            if o is None:
                print(f"=== {a}: id nenalezeno (zkus --hledej)")
            else:
                vypis(o, None, lines, pribeh, note)


if __name__ == "__main__":
    main()
