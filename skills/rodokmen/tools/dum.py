#!/usr/bin/env python3
"""
dum.py – souřadnice konkrétního domu (obec + číslo popisné) pro mapu na webu.

Zdroj: OpenStreetMap Nominatim, kde jsou adresní body z českého registru RÚIAN (otevřená data ČÚZK), tedy
každé číslo popisné má přesný bod. Pozor: v některých obcích se domy po r. 1850–1880 přečíslovaly – staré čp.
z matriky pak nemusí být dnešní dům. Ověř v indikační skice (ČÚZK Archiv, viz výpis) nebo u rodiny.

Použití (z kořene projektu):
  python3 -I tools/dum.py "Holice" 112             vypíše souřadnice a odkazy (nic nezapisuje)
  python3 -I tools/dum.py "Holice" 112 --zapis     přidá do data/mista.json položku „Holice čp. 112“
  python3 -I tools/dum.py --vsechny [--zapis]      projde fakta v data/osoby.py, najde „Obec čp. N“ a geokóduje
                                                   všechny domy (1 dotaz za sekundu; už známé přeskočí)

Položka v mista.json: {"Holice čp. 112": {"re": "Holice čp\\. 112(?!\\d)", "dum": true, "lat": …, "lon": …}}
– web ji ukáže jako samostatný bod s osobami, jejichž fakta obsahují „Holice čp. 112“.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISTA = os.path.join(ROOT, "data", "mista.json")
OSOBY = os.path.join(ROOT, "data", "osoby.py")
UA = "rodokmen-skill/1.0 (family genealogy map, occasional geocoding)"


def bez_diakritiky(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def nominatim(q):
    par = {"q": q, "format": "json", "limit": 8, "countrycodes": "cz", "addressdetails": 1}
    req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(par), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    time.sleep(1.1)
    return res


def geokoduj(obec, cp):
    """Dům v obci. Stejnojmenných obcí je v Česku mnoho (Chlum, Třebenice…) – rozhoduje okres z data/mista.json
    (položka obce má v 'osm' „okres Třebíč“; obec proto nejdřív přidej přes tools/mista.py)."""
    m = mista_nazvy().get(obec, {})
    okres = re.search(r"okres [^,]+", m.get("osm", "") or "")
    okres = bez_diakritiky(okres.group(0)).lower() if okres else None
    ob = bez_diakritiky(obec).lower()
    dotazy = [f"{obec} {cp}"]
    if m.get("dotaz"):
        dotazy.append(re.sub(r"^([^,]+)", rf"\1 {cp}", m["dotaz"]))   # „Chlum u Třebíče 9, Česko“
    for q in dotazy:
        for x in nominatim(q):
            adr = x.get("address", {})
            cislo = adr.get("house_number", "")
            kde = bez_diakritiky(x.get("display_name", "")).lower()
            if ob not in kde or cislo.split("/")[0] != str(cp):
                continue
            if okres and okres not in kde:
                continue
            return {"lat": round(float(x["lat"]), 5), "lon": round(float(x["lon"]), 5), "osm": x["display_name"],
                    "okres_overen": bool(okres)}
    return None


def odkazy(lat, lon):
    return (f"mapy.cz: https://mapy.cz/zakladni?x={lon}&y={lat}&z=18&source=coor&id={lon},{lat}\n"
            f"ČÚZK Archiv (císařské otisky 1824–1843, ručně najít dům): https://ags.cuzk.gov.cz/archiv/\n"
            f"OSM: https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}")


def polozka(obec, cp, g):
    return {"re": rf"{re.escape(obec)} čp\. {cp}(?!\d)", "dotaz": f"{obec} {cp}, Česko", "dum": True,
            "lat": g["lat"], "lon": g["lon"], "osm": g["osm"]}


def domy_z_osob():
    ns = {}
    exec(open(OSOBY, encoding="utf-8").read(), ns)
    domy = {}
    V = "A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ"   # jen 1. pád: „Holice čp. 112“, ne „v Holicích čp. 112“ (ten tvar mapa nezná)
    for k, p in sorted(ns.get("P", {}).items()):
        for f in p.get("f", []):
            for m in re.finditer(rf"(?<![\w'-])([{V}][\w'-]*(?: [{V}][\w'-]*){{0,2}}) čp\. (\d+)", f):
                obec = nominativ(m.group(1).strip())
                if obec:
                    domy.setdefault((obec, m.group(2)), set()).add(k)
    return domy


def nominativ(obec):
    """„Panské Lhotě“ → „Panská Lhota“ podle data/mista.json; neznámý skloněný tvar vynechá."""
    mista = mista_nazvy()
    if obec in mista:
        return obec
    for nazev, e in mista.items():
        if not e.get("dum") and e.get("re") and re.search(e["re"], obec):
            return nazev
    if re.search(r"(ě|u|i|ích|ím|ém|ově|ech|ic|ách)$", obec.split()[-1]):
        return None   # skloněný tvar a obec není v mista.json – nejdřív ji přidejte přes tools/mista.py
    return obec


_MISTA = None


def mista_nazvy():
    global _MISTA
    if _MISTA is None:
        _MISTA = json.load(open(MISTA, encoding="utf-8")) if os.path.exists(MISTA) else {}
    return _MISTA


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    zapis, vsechny = "--zapis" in sys.argv, "--vsechny" in sys.argv
    mista = json.load(open(MISTA, encoding="utf-8")) if os.path.exists(MISTA) else {}
    if vsechny:
        cile = domy_z_osob()
    elif len(args) >= 2:
        cile = {(args[0], args[1]): set()}
    else:
        sys.exit(__doc__)
    zmena = False
    for (obec, cp), osoby in cile.items():
        klic = f"{obec} čp. {cp}"
        if klic in mista and "lat" in mista[klic]:
            print(f"{klic:32} {mista[klic]['lat']:>9} {mista[klic]['lon']:>9}  (už v mista.json)")
            continue
        try:
            g = geokoduj(obec, cp)
        except Exception as e:  # noqa: BLE001
            print(f"{klic:32} CHYBA dotazu: {e}")
            continue
        if not g:
            print(f"{klic:32} NENALEZENO – zkuste jiný tvar názvu obce, nebo dům už neexistuje / byl přečíslován")
            continue
        pozn = "" if g.get("okres_overen") else "  POZOR: obec není v mista.json, okres neověřen – zkontroluj, že je to ta pravá"
        print(f"{klic:32} {g['lat']:>9} {g['lon']:>9}  {g['osm'][:70]}" + (f"  osoby {sorted(osoby)}" if osoby else "") + pozn)
        if not vsechny:
            print(odkazy(g["lat"], g["lon"]))
        if zapis:
            mista[klic] = polozka(obec, cp, g)
            zmena = True
    if zmena:
        json.dump(mista, open(MISTA, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
        print(f"zapsáno do {MISTA} – spusťte python3 -I tools/kontrola.py a ve web/ npm run data")


if __name__ == "__main__":
    main()
