#!/usr/bin/env python3
"""Kontrola výsledků pomocníka (vysledky.md) dřív, než je hlavní session čte a zapisuje.

Použití (z kořene projektu):
  python3 -I tools/kontrola_vysledku.py pracovni/<složka>/vysledky.md

Hlídá chyby, které se skutečně staly (31. 10. 2026):
  - čísla osob „#N“, která v data/osoby.py nejsou, nebo jméno před „(#N)“, které k číslu nepatří,
  - odkazy na obrázky, které neexistují, a citace z náhledů (…_nahled.jpg nebo šířka pod 1600 px),
  - výřezy …_cely/_radek.jpg, které nepocházejí ze své stránky …_stranka.jpg (vypíše i polohu – levá/pravá strana),
  - úkoly bez řádku „nečteno:“ (co pomocník na výřezu nepřečetl – prázdné „nečteno: nic“ je v pořádku),
  - slova jistoty („nezvratně“, „definitivně“…), která patří až do závěru hlavní session.
Nic neopravuje; výstup je seznam věcí k prověření. Návratový kód 1, když je nějaká CHYBA.
"""
import os
import re
import subprocess
import sys
import unicodedata

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_SIRKA = 1600  # pod tím je to náhled – stačí na nalezení řádku, ne na přepis
JISTOTA = ("nezvratn", "definitivn", "jednoznačn", "zásadní objev", "naprosto zřeteln", "bez pochyb")


def bez_diakritiky(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def rozmery(cesta):
    r = subprocess.run(["magick", "identify", "-format", "%w %h", cesta + "[0]"], capture_output=True, text=True)
    try:
        return tuple(map(int, r.stdout.split()))
    except ValueError:
        return None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    md = sys.argv[1]
    slozka = os.path.dirname(os.path.abspath(md))
    text = open(md, encoding="utf-8").read()
    ns = {}
    exec(open(os.path.join(ROOT, "data", "osoby.py"), encoding="utf-8").read(), ns)
    P = ns.get("P", {})
    chyby, pozor = [], []

    # 1. čísla osob
    for m in re.finditer(r"(?:([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][\wáčďéěíňóřšťúůýž]+)\s*)?\(?#(\d+)\b", text):
        c = int(m.group(2))
        if c not in P:
            chyby.append(f"#{c} v osoby.py neexistuje (…{' '.join(text[max(0, m.start() - 40):m.end()].split())})")
        elif m.group(1):
            slovo = bez_diakritiky(m.group(1))[:4]
            jmeno = bez_diakritiky(P[c].get("n", ""))
            if slovo not in jmeno and len(slovo) == 4 and slovo not in ("otec", "matk", "pred", "osob", "rodi", "syn ", "dcer"):
                pozor.append(f"„{m.group(1)} #{c}“ – v osoby.py je #{c} {P[c].get('n')}")

    # 2. obrázky
    obrazky = sorted(set(re.findall(r"(?<![\w*])[A-Za-z0-9][\w./-]*\.jpe?g", text)))
    nalezene = {}
    for o in obrazky:
        kandidati = [os.path.join(slozka, o), os.path.join(ROOT, o), os.path.join(slozka, os.path.basename(o))]
        cesta = next((k for k in kandidati if os.path.exists(k)), None)
        if not cesta:
            chyby.append(f"obrázek {o} neexistuje")
            continue
        nalezene[os.path.basename(o)] = cesta
        rz = rozmery(cesta)
        if "nahled" in os.path.basename(o) or (rz and rz[0] < MIN_SIRKA and "radek" not in o and "cely" not in o):
            pozor.append(f"{o} je náhled ({rz[0]}×{rz[1]} px) – smí sloužit jen k nalezení zápisu, ne k přepisu" if rz else f"{o} je náhled")

    # 3. výřez pochází ze své stránky
    for jm, cesta in nalezene.items():
        m = re.match(r"(.+)_(cely|radek)\.jpe?g$", jm)
        if not m:
            continue
        stranka = os.path.join(os.path.dirname(cesta), m.group(1) + "_stranka.jpg")
        if not os.path.exists(stranka):
            pozor.append(f"{jm}: chybí stránka {os.path.basename(stranka)} – výřez nejde ověřit")
            continue
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "najdi_vyrez.py"), stranka, cesta],
                           capture_output=True, text=True)
        shoda = re.search(r"Shoda:\s*([\d.]+)", r.stdout)
        poloha = re.search(r"^([\d.]+),([\d.]+),([\d.]+),([\d.]+)\s*$", r.stdout, re.M)
        if not shoda or float(shoda.group(1)) < 90:
            chyby.append(f"{jm} není výřezem stránky {os.path.basename(stranka)} (shoda {shoda.group(1) if shoda else '?'} %)")
        elif poloha:
            x0, x1 = float(poloha.group(1)), float(poloha.group(3))
            strana = "levá strana" if x1 <= 0.55 else "pravá strana" if x0 >= 0.45 else "přes obě strany"
            print(f"  {jm}: {strana} stránky ({poloha.group(0).strip()}) – sedí se stranou/pag. ve výsledcích?")

    # 4. „nečteno:“ u každého úkolu, 5. slova jistoty
    oddily = re.split(r"\n(?=###\s)", text)
    for o in oddily[1:]:
        nadpis = o.splitlines()[0].strip("# ").strip()
        if "nečteno" not in o.lower():
            pozor.append(f"úkol „{nadpis[:60]}“ nemá řádek „nečteno:“ (co na výřezu přečteno nebylo)")
    nic = len(re.findall(r"nečteno\W{0,4}:?\**\s*nic\b", text, re.I))
    if nic >= 3 and nic >= 0.8 * len(re.findall(r"nečteno", text, re.I)):
        pozor.append(f"{nic}× „nečteno: nic“ – u kurentu 18.–19. stol. nepravděpodobné; přepisy číst znovu celé, "
                     "hlavně kněze, kmotry, bábu a přípisky (dávky 4–5: právě tam bylo vymyšleno)")
    for i, radek in enumerate(text.splitlines(), 1):
        for s in JISTOTA:
            if s in radek.lower():
                pozor.append(f"ř. {i}: „{s}…“ – jistotu posoudí až hlavní session na snímku")

    print(f"\nKontrola {md}: {len(chyby)} CHYB, {len(pozor)} k prověření")
    for c in chyby:
        print("CHYBA:", c)
    for p in pozor:
        print("pozor:", p)
    sys.exit(1 if chyby else 0)


if __name__ == "__main__":
    main()
