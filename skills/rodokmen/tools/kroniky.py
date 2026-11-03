#!/usr/bin/env python3
"""
kroniky.py – školní a obecní kroniky (MZA ARON / SOkA, Morava).

Zdroje:
  kroniky     MZA ARON – archivní fondy okresních archivů (SOkA Třebíč, SOkA Jihlava,
              SOkA Žďár nad Sázavou, SOkA Brno-venkov atd.):
              - Pamětní knihy a kroniky obcí (zápisy o požárech, epidemiích, výstavbě, válkách)
              - Školní kroniky (založení školy, seznamy učitelů, žáků, události)
              - Fondy Archiv obce (zápisy ze zasedání obecního zastupitelstva, spisy starostů)
              - Digitalizované snímky (IIPSrv Deepzoom) i inventární popisy prezenčních svazků.

Použití (z kořene projektu):
  python3 -I tools/kroniky.py hledat "Holice"
  python3 -I tools/kroniky.py hledat "Chrudim"
  python3 -I tools/kroniky.py hledat "Pardubice" [--druh skola|obec|vse] [--digitalizovane]
  python3 -I tools/kroniky.py info "009b1fbc-05e9-4498-833a-4f8507be94c9"
  python3 -I tools/kroniky.py snimek "009b1fbc-05e9-4498-833a-4f8507be94c9" 1 out.jpg [--nahled] [--crop x0,y0,x1,y1]
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

try:
    import sit
    from sit import Sit, ziskej_klienta
except ImportError:
    sit = None
    Sit = None
    ziskej_klienta = None

ARON_API = "https://www.mza.cz/aron/api/aron"


def _odstran_diakritiku(text: str) -> str:
    """Převede text na ASCII malými písmeny."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    ).lower()


def hledat_kroniky(obec: str, druh: str = "vse", pouze_digitalizovane: bool = False,
                   sit_klient: Optional[Any] = None, max_vysledku: int = 40) -> List[Dict[str, Any]]:
    """Vyhledá školní a obecní kroniky a archivní popisy pro zadanou obec v MZA ARON."""
    s = sit_klient or (ziskej_klienta() if ziskej_klienta else None)
    if not s:
        sys.stderr.write("Chyba: Knihovna sit není dostupná.\n")
        return []

    url = f"{ARON_API}/apu/listview?listType=SEARCH"
    body = {
        "filters": [
            {"operation": "FTXF", "field": "description", "value": obec}
        ],
        "sort": [],
        "offset": 0,
        "size": 60,
        "aggregations": []
    }

    try:
        data = s.post_json(url, json_data=body)
    except Exception as e:
        sys.stderr.write(f"Chyba při dotazu na ARON pro obec '{obec}': {e}\n")
        return []

    items = data.get("items", [])
    norm_obec = _odstran_diakritiku(obec)

    vysledky = []
    # Klíčová slova pro kroniky a významné obecní prameny
    klice_obec = ("kronik", "pamětn", "pametn", "archiv obce", "obecní rada", "představenstvo", "zastupitelstv", "starost")
    klice_skola = ("škola", "skola", "školn", "skoln", "učitel", "žák", "vyučov")

    for it in items:
        apu_id = it.get("id")
        name = it.get("name") or ""
        desc = it.get("description") or ""
        full = (name + " " + desc).lower()

        je_obecni = any(k in full for k in klice_obec)
        je_skolni = any(k in full for k in klice_skola)

        if druh == "obec" and not je_obecni:
            continue
        if druh == "skola" and not je_skolni:
            continue
        if druh == "vse" and not (je_obecni or je_skolni):
            # Pokud se nejedná o kroniku, školu ani obecní archiv, přeskočíme
            continue

        # Zjistíme detail (počet snímků a archivní instituci)
        detail = detail_kroniky(apu_id, sit_klient=s, rychly=True)
        pocet_snimku = detail.get("pocet_snimku", 0)

        if pouze_digitalizovane and pocet_snimku == 0:
            continue

        kategorie = "Školní pramen" if je_skolni and not je_obecni else ("Obecní pramen" if je_obecni and not je_skolni else "Kronika / archiválie")

        vysledky.append({
            "id": apu_id,
            "nazev": name or "Bez názvu",
            "popis": desc,
            "kategorie": kategorie,
            "pocet_snimku": pocet_snimku,
            "casovy_rozsah": detail.get("rozsah", ""),
            "instituce": detail.get("instituce", ""),
            "fond": detail.get("fond", ""),
            "signatura": detail.get("signatura", ""),
            "permalink": f"https://www.mza.cz/aron/apu/{apu_id}"
        })

        if len(vysledky) >= max_vysledku:
            break

    return vysledky


def detail_kroniky(apu_id: str, sit_klient: Optional[Any] = None, rychly: bool = False) -> Dict[str, Any]:
    """Získá úplné podrobnosti archiválie či kroniky z MZA ARON včetně inventárního popisu a seznamu snímků."""
    s = sit_klient or (ziskej_klienta() if ziskej_klienta else None)
    if not s:
        return {}

    url = f"{ARON_API}/apu/{apu_id}"
    try:
        data = s.get_json(url)
    except Exception as e:
        sys.stderr.write(f"Chyba při čtení APU {apu_id}: {e}\n")
        return {}

    name = data.get("name") or ""
    desc = data.get("description") or ""

    # Digitální objekty (snímky)
    files = []
    for do in data.get("digitalObjects", []) or []:
        for f in do.get("files", []) or []:
            ref = f.get("referencedFile")
            if ref and "Deepzoom=" in ref:
                files.append({
                    "id": f.get("id"),
                    "order": f.get("order"),
                    "name": f.get("name"),
                    "deepzoom_url": ref
                })
    files.sort(key=lambda x: x.get("order") or 0)

    # Metadata z parts / items
    obsah = ""
    poznamka = ""
    signatura = ""
    ulozeni = ""
    rozsah = ""
    stav = ""

    for part in data.get("parts", []):
        for it in part.get("items", []):
            itype = it.get("type")
            ival = it.get("value")
            if not ival:
                continue
            if itype == "UNIT~CONTENT":
                obsah = str(ival).strip()
            elif itype == "NOTE":
                poznamka = str(ival).strip()
            elif itype in ("OTHERID~SIG", "OTHER_ID_PROC_INDEX"):
                if not signatura:
                    signatura = str(ival).strip()
            elif itype == "STORAGE":
                ulozeni = str(ival).strip()
            elif itype == "UNIT~CURRENT~STATUS":
                stav = str(ival).strip()
            elif itype == "UNIT~DATE":
                try:
                    if isinstance(ival, str) and "{" in ival:
                        d_obj = json.loads(ival)
                        f_rok = d_obj.get("from", "")[:4]
                        t_rok = d_obj.get("to", "")[:4]
                        if f_rok and t_rok:
                            rozsah = f"{f_rok}–{t_rok}" if f_rok != t_rok else f_rok
                    elif isinstance(ival, dict):
                        f_rok = str(ival.get("from", ""))[:4]
                        t_rok = str(ival.get("to", ""))[:4]
                        if f_rok and t_rok:
                            rozsah = f"{f_rok}–{t_rok}" if f_rok != t_rok else f_rok
                except Exception:
                    pass

    # Rodičovský fond a instituce
    parent_data = data.get("parent") or {}
    fond = parent_data.get("name") or ""
    instituce = ""

    # Hledáme instituci v result JSON řetězci parentu
    p_result = parent_data.get("result")
    if p_result and isinstance(p_result, str):
        try:
            r_obj = json.loads(p_result)
            for row in r_obj.get("l", []):
                for cell in row:
                    if cell.get("t") == "J_I":  # Jurisdikční instituce (archiv)
                        for val in cell.get("v", []):
                            instituce = val.get("v", "")
                    elif cell.get("t") == "J_F" and not fond:
                        for val in cell.get("v", []):
                            fond = val.get("v", "")
        except Exception:
            pass

    return {
        "id": apu_id,
        "nazev": name,
        "popis": desc,
        "obsah": obsah,
        "poznamka": poznamka,
        "signatura": signatura,
        "ulozeni": ulozeni,
        "rozsah": rozsah,
        "stav": stav,
        "fond": fond,
        "instituce": instituce,
        "pocet_snimku": len(files),
        "snimky": files,
        "permalink": f"https://www.mza.cz/aron/apu/{apu_id}"
    }


def stahni_snimek_kroniky(apu_id: str, cislo_snimku: int, vystup_cesta: str,
                          crop: Optional[Tuple[float, float, float, float]] = None,
                          nahled: bool = False, sit_klient: Optional[Any] = None) -> bool:
    """Stáhne snímek nebo výřez z digitalizované kroniky v MZA ARON přes IIPSrv Deepzoom."""
    import mza
    detail = detail_kroniky(apu_id, sit_klient=sit_klient)
    snimky = detail.get("snimky", [])
    if not snimky:
        sys.stderr.write(f"Archiválie {apu_id} nemá žádné digitalizované snímky online.\n")
        return False

    if cislo_snimku < 1 or cislo_snimku > len(snimky):
        sys.stderr.write(f"Číslo snímku {cislo_snimku} je mimo rozsah (1..{len(snimky)}).\n")
        return False

    mza.snimek(apu_id, cislo_snimku, vystup_cesta, nahled=nahled, crop=crop,
               dzi_urls=[f["deepzoom_url"] for f in snimky], referer=f"https://www.mza.cz/aron/apu/{apu_id}")
    return True


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Školní a obecní kroniky (MZA ARON / SOkA)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # hledat
    p_h = sub.add_parser("hledat", help="Vyhledá kroniky a fondy obcí a škol pro danou obec")
    p_h.add_argument("obec", help="Název obce (např. Holice, Chrudim, Pardubice)")
    p_h.add_argument("--druh", choices=["obec", "skola", "vse"], default="vse", help="Druh fondu / kroniky")
    p_h.add_argument("--digitalizovane", action="store_true", help="Zobrazit pouze záznamy s online snímky")
    p_h.add_argument("--max", type=int, default=30, help="Maximální počet výsledků")

    # info
    p_i = sub.add_parser("info", help="Zobrazí úplný inventární popis a metadata svazku")
    p_i.add_argument("apu_id", help="ID záznamu (UUID z MZA ARON)")

    # snimek
    p_s = sub.add_parser("snimek", help="Stáhne stránku/snímek z digitalizované kroniky")
    p_s.add_argument("apu_id", help="ID záznamu z MZA ARON")
    p_s.add_argument("snimek", type=int, help="Číslo snímku (1..N)")
    p_s.add_argument("vystup", help="Cesta k výstupnímu souboru .jpg")
    p_s.add_argument("--nahled", action="store_true", help="Rychlý náhled v menším rozlišení")
    p_s.add_argument("--crop", help="Výřez jako x0,y0,x1,y1 (hodnoty 0..1)")

    args = parser.parse_args()
    s = ziskej_klienta() if ziskej_klienta else None

    if args.cmd == "hledat":
        print(f"Hledám kroniky a obecní/školní fondy pro obec '{args.obec}' v MZA ARON...")
        vysledky = hledat_kroniky(args.obec, druh=args.druh, pouze_digitalizovane=args.digitalizovane,
                                  sit_klient=s, max_vysledku=args.max)
        if not vysledky:
            print(f"Nenalezeny žádné záznamy pro obec '{args.obec}'.")
            return

        print(f"\nNalezeno {len(vysledky)} záznamů pro obec '{args.obec}':")
        print("=" * 80)
        for i, it in enumerate(vysledky, 1):
            snimky_info = f"📸 {it['pocet_snimku']} snímků ONLINE" if it['pocet_snimku'] > 0 else "🏛️  Pouze prezenčně v SOkA"
            print(f"{i}. [{it['kategorie']}] {it['nazev']}")
            if it.get("casovy_rozsah"):
                print(f"   Období: {it['casovy_rozsah']}")
            if it.get("instituce") or it.get("fond"):
                print(f"   Uložení: {it.get('instituce', '?')} | {it.get('fond', '?')}")
            if it.get("signatura"):
                print(f"   Signatura / uložení: {it['signatura']}")
            print(f"   Stav: {snimky_info}")
            print(f"   Odkaz: {it['permalink']}")
            if it.get("popis") and it["popis"] != it["nazev"]:
                print(f"   Popis: {it['popis'][:160]}...")
            print()

    elif args.cmd == "info":
        d = detail_kroniky(args.apu_id, sit_klient=s)
        if not d:
            print("Záznam nebyl nalezen.")
            return

        print(f"\n📖 Detail archiválie: {d['nazev']}")
        print("=" * 80)
        print(f"ID (UUID): {d['id']}")
        print(f"Odkaz: {d['permalink']}")
        if d.get("instituce"):
            print(f"Archiv: {d['instituce']}")
        if d.get("fond"):
            print(f"Fond: {d['fond']}")
        if d.get("rozsah"):
            print(f"Časový rozsah: {d['rozsah']}")
        if d.get("signatura") or d.get("ulozeni"):
            print(f"Signatura / uložení: {d.get('signatura', '')} {d.get('ulozeni', '')}")
        if d.get("stav"):
            print(f"Fyzický stav: {d['stav']}")
        print(f"Počet digitalizovaných snímků: {d['pocet_snimku']}")

        if d.get("obsah"):
            print(f"\n📜 Podrobný obsah archiválie:\n{d['obsah']}")
        if d.get("poznamka"):
            print(f"\n📌 Poznámka inventáře:\n{d['poznamka']}")

    elif args.cmd == "snimek":
        crop = None
        if args.crop:
            try:
                parts = [float(x.strip()) for x in args.crop.split(",")]
                if len(parts) == 4:
                    crop = tuple(parts)
            except Exception:
                sys.stderr.write("Chybný formát crop, očekáván x0,y0,x1,y1.\n")
                sys.exit(1)

        print(f"Stahuji snímek {args.snimek} z archiválie {args.apu_id}...")
        uspech = stahni_snimek_kroniky(args.apu_id, args.snimek, args.vystup, crop=crop,
                                       nahled=args.nahled, sit_klient=s)
        if uspech:
            print(f"Snímek úspěšně uložen do: {args.vystup}")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
