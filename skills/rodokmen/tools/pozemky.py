#!/usr/bin/env python3
"""
pozemky.py – pozemkové a majetkové prameny pro Moravu a ČR (pozemkové knihy, lánové rejstříky, stabilní katastr).

Zdroje:
  pozemkove_knihy   Moravský zemský archiv (MZA ARON / fond C 17 a velkostatky) – gruntovnice,
                    smlouvy o koupi/prodeji, předání usedlosti, výminky, dědické podíly.
  lanove_rejstriky  Lánové rejstříky 1669–1679 (MZA fond D 1) – nejstarší moravský katastr gruntů
                    a hospodářů (často s uvedením držitele z r. 1657 po třicetileté válce).
  stabilni_katastr  Archiv ČÚZK (https://ags.cuzk.gov.cz/archiv/) a MZA (https://www.mza.cz/indikacniskici/):
                    Císařské otisky (1824–1843), originální mapy a indikační skici (obsahují jména
                    vlastníků domů a parcel v době zaměření).

Použití (z kořene projektu):
  python3 -I tools/pozemky.py predci "Obec"
      Kdo z rodokmenu (data/osoby.py) v obci žil, v kterém domě a kdy – koho hledat v rejstříku knihy. Bez sítě.
  python3 -I tools/pozemky.py rejstrik <apu_id> [--od 2] [--do 8]
      Náhledy rejstříku knihy (…_nahled.jpg) – jen k nalezení folia, nic z nich necitovat.
  python3 -I tools/pozemky.py hledat "Obec" [--dum CP]
      Souhrnný přehled všech pozemkových a majetkových pramenů pro danou obec (knihy, lánový rejstřík, katastr).
  python3 -I tools/pozemky.py knihy "Obec" [--max 20]
      Vyhledá pozemkové a gruntovní knihy v MZA ARON pro danou obec/panství (včetně počtu digitalizovaných snímků).
  python3 -I tools/pozemky.py info <apu_id>
      Detail konkrétní pozemkové knihy v ARONu, struktura, časový rozsah a seznam digitalizovaných snímků.
  python3 -I tools/pozemky.py snimek <apu_id> <cislo_snimku> <vystup.jpg> [--crop x0,y0,x1,y1] [--nahled]
      Stáhne snímek nebo výřez z pozemkové knihy (přes MZA IIPSrv Deepzoom). S --nahled dostane název …_nahled.jpg.
  python3 -I tools/pozemky.py katastr "Obec" [--dum CP]
      Vygeneruje odkazy na císařský otisk a indikační skicu se jmény majitelů (ČÚZK archiv a MZA).
  python3 -I tools/pozemky.py lanove "Obec"
      Vyhledá svazky lánových rejstříků (fond D 1) pokrývající danou obec.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from sit import Sit, ziskej_klienta

ARON_API = "https://www.mza.cz/aron/api/aron"
MZA_IIPSRV = "https://www.mza.cz/iipsrv/iipsrv.fcgi"
MZA_SKICI = "https://www.mza.cz/indikacniskici/skica"


def hledat_pozemkove_knihy(obec: str, sit: Optional[Sit] = None, max_vysledku: int = 25) -> List[Dict[str, Any]]:
    """Vyhledá pozemkové, gruntovní a domovní knihy v MZA ARON pro zadanou obec či panství."""
    s = sit or ziskej_klienta()
    url = f"{ARON_API}/apu/listview?listType=SEARCH"

    # Hledáme archivní popisy s výskytem obce
    body = {
        "filters": [
            {"field": "type", "operation": "EQ", "value": "ARCH_DESC"},
            {"operation": "FTXF", "field": "description", "value": obec}
        ],
        "sort": [],
        "offset": 0,
        "size": 50,
        "aggregations": []
    }

    try:
        data = s.post_json(url, json_data=body)
    except Exception as e:
        sys.stderr.write(f"Chyba při dotazu na ARON: {e}\n")
        return []

    items = data.get("items", [])
    knihy = []
    klice = ("pozemkov", "gruntov", "kniha", "urbář", "urbar", "katastr", "držitel", "panství", "emfyteut")

    for it in items:
        name = it.get("name") or ""
        desc = it.get("description") or ""
        full_text = (name + " " + desc).lower()
        if any(k in full_text for k in klice):
            knihy.append({
                "id": it.get("id"),
                "name": name,
                "description": desc,
                "permalink": f"https://www.mza.cz/aron/apu/{it.get('id')}"
            })
            if len(knihy) >= max_vysledku:
                break

    return knihy


def detail_knihy(apu_id: str, sit: Optional[Sit] = None) -> Dict[str, Any]:
    """Získá detail svazku z MZA ARON včetně seznamu snímků."""
    s = sit or ziskej_klienta()
    url = f"{ARON_API}/apu/{apu_id}"
    data = s.get_json(url)

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

    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "description": data.get("description"),
        "parts": data.get("parts", []),
        "pocet_snimku": len(files),
        "snimky": files,
        "permalink": f"https://www.mza.cz/aron/apu/{apu_id}"
    }


def hledat_lanove_rejstriky(obec: str, sit: Optional[Sit] = None) -> List[Dict[str, Any]]:
    """Vyhledá svazky fondu D 1 Lánové rejstříky (1669–1679) pro danou obec."""
    s = sit or ziskej_klienta()
    url = f"{ARON_API}/apu/listview?listType=SEARCH"

    body = {
        "filters": [
            {"field": "type", "operation": "EQ", "value": "ARCH_DESC"},
            {"operation": "FTXF", "field": "description", "value": f"lánový rejstřík {obec}"}
        ],
        "sort": [],
        "offset": 0,
        "size": 15,
        "aggregations": []
    }

    try:
        data = s.post_json(url, json_data=body)
    except Exception:
        return []

    vysledky = []
    for it in data.get("items", []):
        name = it.get("name") or ""
        desc = it.get("description") or ""
        text = (name + " " + desc).lower()
        if "lánov" in text or "d 1" in text or "rejstřík" in text:
            vysledky.append({
                "id": it.get("id"),
                "name": name,
                "description": desc,
                "permalink": f"https://www.mza.cz/aron/apu/{it.get('id')}"
            })

    return vysledky


def katastr_odkazy(obec: str, dum_cp: Optional[int] = None) -> Dict[str, Any]:
    """Sestaví odkazy a informace pro stabilní katastr ČÚZK a MZA."""
    obec_enc = urllib.parse.quote(obec)

    # Pokusíme se zjistit souřadnice obce nebo domu z data/mista.json nebo dum.py
    lat, lon = None, None
    mista_path = ROOT / "data" / "mista.json"
    if mista_path.exists():
        try:
            with open(mista_path, "r", encoding="utf-8") as f:
                mista = json.load(f)
                info = mista.get(obec)
                if info and isinstance(info, dict) and "lat" in info and "lon" in info:
                    lat, lon = info["lat"], info["lon"]
        except Exception:
            pass

    # Když máme dům, zkusíme najít souřadnice přes tools/dum.py
    if dum_cp and (lat is None or lon is None):
        try:
            cmd = [sys.executable, "-I", str(ROOT / "tools" / "dum.py"), obec, str(dum_cp)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            m = re.search(r"([0-9]+\.[0-9]+),\s*([0-9]+\.[0-9]+)", res.stdout)
            if m:
                lat, lon = float(m.group(1)), float(m.group(2))
        except Exception:
            pass

    # ČÚZK Archiv odkaz na mapu
    cuzk_url = "https://ags.cuzk.gov.cz/archiv/"   # obec v aplikaci najít podle názvu katastru (souřadnice v URL nejsou ověřené)

    mza_skici_url = f"{MZA_SKICI}?nazev={obec_enc}"
    skici = []
    try:
        html = ziskej_klienta().get(mza_skici_url).text()
        skici = [f"{MZA_SKICI}/detail/{m}" for m in dict.fromkeys(re.findall(r"skica/detail/(MOR\d+)", html))]
    except Exception as e:
        sys.stderr.write(f"[MZA indikační skici]: {e}\n")

    return {
        "obec": obec,
        "dum_cp": dum_cp,
        "souradnice": (lat, lon) if lat and lon else None,
        "cuzk_mapa_url": cuzk_url,
        "mza_indikační_skici_url": mza_skici_url,
        "mza_skici": skici,
        "popis_vrstev": {
            "cisarske_otisky": "Císařské povinné otisky (1824–1843) – kolorované originály se zakreslenými usedlostmi.",
            "indikacni_skici": "Indikační skici – pracovní mapy, které obsahují jména a příjmení majitelů u čísel popisných!",
            "pozemkovy_katastr": "Pozemkový katastr (navazující stav parcel z přelomu 19./20. století)."
        }
    }


def stahni_snimek_knihy(apu_id: str, cislo_snimku: int, vystup_cesta: str,
                        crop: Optional[Tuple[float, float, float, float]] = None,
                        nahled: bool = False, sit: Optional[Sit] = None) -> bool:
    """Stáhne snímek nebo výřez z pozemkové knihy v MZA ARON (stejný IIPSrv jako Acta Publica → mza.snimek)."""
    import mza
    snimky = detail_knihy(apu_id, sit=sit).get("snimky", [])
    if not snimky:
        sys.stderr.write(f"Kniha {apu_id} nemá žádné digitalizované snímky online.\n")
        return False
    snimky.sort(key=lambda f: f.get("order") or 0)
    mza.snimek(apu_id, cislo_snimku, vystup_cesta, nahled=nahled, crop=crop,
               dzi_urls=[f["deepzoom_url"] for f in snimky], referer=f"https://www.mza.cz/aron/apu/{apu_id}")
    return True


def _bez_diakritiky(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def predci_v_obci(obec: str) -> List[Dict[str, Any]]:
    """Osoby z data/osoby.py, jejichž fakta zmiňují obec (i ve skloňovaném tvaru), s čísly domů.

    Slouží jako vstup pro rejstřík pozemkové knihy: koho a který dům v knize hledat. Přídavná jména a příjmení
    odvozená od obce (Lhotský, holický) se nepočítají."""
    ns: Dict[str, Any] = {}
    exec(open(ROOT / "data" / "osoby.py", encoding="utf-8").read(), ns)
    kmen = re.sub(r"[aeiouy]+$", "", _bez_diakritiky(obec).strip()) or _bez_diakritiky(obec)
    rx = re.compile(r"\b" + re.escape(kmen) + r"([a-z]{0,4})\b")
    osoby = [(f"#{k}", v) for k, v in ns.get("P", {}).items()] + \
            [(f"{v.get('id', '?')} (širší rodina)", v) for v in ns.get("SIDE", [])]
    out = []
    for oznac, o in osoby:
        fakta = []
        for f in o.get("f", []):
            norm = _bez_diakritiky(f)
            if re.match(r"(krest|×|x )", norm) or "pohrb" in norm:  # farní kostel, ne bydliště
                continue
            if any(not m.group(1).startswith("sk") for m in rx.finditer(norm)):
                fakta.append(f)
        if fakta:
            domy = sorted({int(d) for f in fakta for d in re.findall(r"čp\.\s*(\d+)", f)})
            out.append({"oznaceni": oznac, "jmeno": o.get("n", "?"), "roky": o.get("y", ""),
                        "stav": o.get("st", ""), "domy": domy, "fakta": fakta})
    return out


def stahni_rejstrik_knihy(apu_id: str, vystup_slozka: str = "pracovni/pozemky_rejstriky",
                          od_snimku: int = 2, do_snimku: int = 8,
                          sit: Optional[Sit] = None) -> List[str]:
    """Stáhne náhledy snímků rejstříku (indexu) pozemkové knihy pro rychlé vyhledání folia."""
    det = detail_knihy(apu_id, sit=sit)
    pocet = det.get("pocet_snimku", 0)
    if not pocet:
        sys.stderr.write(f"Kniha {apu_id} nemá digitalizované snímky.\n")
        return []

    out_dir = Path(vystup_slozka)
    out_dir.mkdir(parents=True, exist_ok=True)

    stazeno = []
    print(f"Stahuji náhledy rejstříku pro '{det['name']}' (snímky {od_snimku} až {min(do_snimku, pocet)} z {pocet}):")
    for sn in range(od_snimku, min(do_snimku, pocet) + 1):
        target = out_dir / f"{apu_id[:8]}_sn{sn:03d}_nahled.jpg"
        ok = stahni_snimek_knihy(apu_id, sn, str(target), nahled=True, sit=sit)
        if ok:
            stazeno.append(str(target))
            print(f"  • Snímek {sn}: {target}")

    print("\nJak postupovat v rejstříku pozemkové knihy:")
    print("  1. Prohlédněte stažené náhledy (rejstřík je řazen podle vsí a uvádí jména hospodářů a čísla listů).")
    print("  2. Najděte své příjmení / grunt a poznamenejte si číslo listu (folia), např. 'fol. 111'.")
    print("  3. List najdete na snímku přibližně: číslo folia + počet listů předsádky (obvykle o 1 až 8 snímků dále).")
    print("  4. Až najdete správný list, stáhněte ho v plném rozlišení k přepisu:")
    print(f"     python3 -I tools/pozemky.py snimek {apu_id} <číslo_snímku> <vystup.jpg>")
    print("  Náhledy (…_nahled.jpg) slouží jen k nalezení folia – nic z nich neopisujte ani necitujte.")
    print("  Hledejte jen hospodáře z rodokmenu: python3 -I tools/pozemky.py predci \"<obec>\"")
    return stazeno


# CLI rozhraní
def main():
    parser = argparse.ArgumentParser(description="Pozemkové a majetkové prameny pro Moravu a ČR.")
    sub = parser.add_subparsers(dest="cmd")

    # hledat
    p_h = sub.add_parser("hledat", help="Souhrnné vyhledání všech pramenů pro obec")
    p_h.add_argument("obec", help="Název obce")
    p_h.add_argument("--dum", type=int, help="Číslo popisné domu (volitelné)")

    # knihy
    p_k = sub.add_parser("knihy", help="Hledání pozemkových knih v MZA ARON")
    p_k.add_argument("obec", help="Název obce nebo panství")
    p_k.add_argument("--max", type=int, default=20, help="Maximální počet výsledků")

    # info
    p_i = sub.add_parser("info", help="Detail pozemkové knihy z ARONu")
    p_i.add_argument("apu_id", help="ID záznamu (UUID z ARONu)")

    # snimek
    p_s = sub.add_parser("snimek", help="Stažení snímku z pozemkové knihy")
    p_s.add_argument("apu_id", help="ID záznamu z ARONu")
    p_s.add_argument("snimek", type=int, help="Číslo snímku (1..N)")
    p_s.add_argument("vystup", help="Cesta k výstupnímu JPG")
    p_s.add_argument("--nahled", action="store_true", help="Menší rozlišení (rychlý náhled)")
    p_s.add_argument("--crop", help="Výřez jako x0,y0,x1,y1 (zlomky 0..1)")

    # katastr
    p_kat = sub.add_parser("katastr", help="Odkazy na stabilní katastr a indikační skici")
    p_kat.add_argument("obec", help="Název obce")
    p_kat.add_argument("--dum", type=int, help="Číslo popisné domu")

    # lanove
    p_l = sub.add_parser("lanove", help="Lánové rejstříky 1669–1679 pro obec")
    p_l.add_argument("obec", help="Název obce")

    # rejstrik
    p_r = sub.add_parser("rejstrik", help="Stažení náhledů rejstříku pozemkové knihy pro vyhledání folia")
    p_r.add_argument("apu_id", help="ID záznamu z ARONu (UUID)")
    p_r.add_argument("--od", type=int, default=2, help="Počáteční snímek (výchozí 2)")
    p_r.add_argument("--do", type=int, default=8, help="Koncový snímek (výchozí 8)")
    p_r.add_argument("--dir", default="pracovni/pozemky_rejstriky", help="Cílová složka")

    # predci (bez sítě)
    p_p = sub.add_parser("predci", help="Kdo z rodokmenu žil v obci (domy, roky) – koho hledat v rejstříku knihy")
    p_p.add_argument("obec", help="Název obce")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    if args.cmd == "predci":
        lide = predci_v_obci(args.obec)
        print(f"\nOsoby z rodokmenu s fakty v obci '{args.obec}' ({len(lide)}):")
        print("=" * 80)
        if not lide:
            print("  Nikdo – v této obci zatím žádný doložený předek. Gruntovní kniha obce pro rodokmen nic nedoloží.")
        for o in lide:
            domy = ", ".join(f"čp. {d}" for d in o["domy"]) or "dům neznámý"
            print(f"{o['oznaceni']} {o['jmeno']} ({o['roky']}, {o['stav']}) – {domy}")
            for f in o["fakta"]:
                print(f"     · {f}")
        if lide:
            prijmeni = sorted({o["jmeno"].split()[-1].rstrip("(?)").strip() for o in lide if " " in o["jmeno"]})
            print("\nV rejstříku knihy hledej tato příjmení (i v německém/starém pravopisu):", ", ".join(prijmeni))
            print("Nález v knize patří předkovi jen při shodě jména, domu a let s fakty výše; jinak je to stopa, ne doklad.")
        return

    sit = ziskej_klienta()

    try:
        if args.cmd == "knihy":
            knihy = hledat_pozemkove_knihy(args.obec, sit=sit, max_vysledku=args.max)
            print(f"\nNalezené pozemkové knihy v MZA ARON pro '{args.obec}' ({len(knihy)}):")
            print("=" * 80)
            if not knihy:
                print("  Žádné pozemkové knihy nenalezeny.")
            for i, k in enumerate(knihy, 1):
                print(f"{i}. {k['name']}")
                print(f"   ID: {k['id']}")
                print(f"   Odkaz: {k['permalink']}")
                if k['description']:
                    print(f"   Popis: {k['description'][:120]}...")
                print()

        elif args.cmd == "info":
            info = detail_knihy(args.apu_id, sit=sit)
            print(f"\nDetail pozemkové knihy:")
            print("=" * 80)
            print(f"Název:  {info['name']}")
            print(f"ID:     {info['id']}")
            print(f"Snímků: {info['pocet_snimku']} (online v prohlížeči)")
            print(f"Odkaz:  {info['permalink']}")
            if info['description']:
                print(f"Popis:  {info['description']}")

        elif args.cmd == "snimek":
            crop_coords = None
            if args.crop:
                crop_coords = tuple(map(float, args.crop.split(",")))
            if args.nahled:
                import mza
                args.vystup = mza.nahled_cesta(args.vystup)
            ok = stahni_snimek_knihy(args.apu_id, args.snimek, args.vystup,
                                     crop=crop_coords, nahled=args.nahled, sit=sit)
            if not ok:
                sys.exit(1)

        elif args.cmd == "rejstrik":
            stahni_rejstrik_knihy(args.apu_id, vystup_slozka=args.dir,
                                  od_snimku=args.od, do_snimku=args.do, sit=sit)

        elif args.cmd == "lanove":
            rejstriky = hledat_lanove_rejstriky(args.obec, sit=sit)
            print(f"\nLánové rejstříky (fond D 1, 1669–1679) pro '{args.obec}':")
            print("=" * 80)
            if not rejstriky:
                print(f"  Pro '{args.obec}' vyhledejte příslušné panství v inventáři MZA D 1:")
                print("  👉 http://www.mza.cz/a8web/a8apps1/d1/a8sl4dd2bad3D1.htm nebo přes MZA ARON.")
            for r in rejstriky:
                print(f"- {r['name']}")
                print(f"  ID: {r['id']} | Odkaz: {r['permalink']}")

        elif args.cmd == "katastr":
            kat = katastr_odkazy(args.obec, dum_cp=args.dum)
            print(f"\nStabilní katastr a indikační skici pro '{args.obec}':")
            print("=" * 80)
            if kat.get("souradnice"):
                lat, lon = kat["souradnice"]
                print(f"Souřadnice: {lat:.6f}, {lon:.6f}")
            print(f"1. ČÚZK Archivní mapy (císařské otisky + indikační skici):")
            print(f"   👉 {kat['cuzk_mapa_url']}")
            print(f"2. MZA Indikační skici (Morava):")
            print(f"   👉 {kat['mza_indikační_skici_url']}")
            for u in kat["mza_skici"]:
                print(f"   • {u}")
            print("\nVrstvy:")
            for k, v in kat["popis_vrstev"].items():
                print(f" - {k}: {v}")

        elif args.cmd == "hledat":
            print(f"\n================================================================================")
            print(f"   POZEMKOVÉ A MAJETKOVÉ PRAMENY PRO OBEC: {args.obec.upper()}")
            if args.dum:
                print(f"   Číslo popisné: {args.dum}")
            print(f"================================================================================\n")

            # 1. Pozemkové knihy
            knihy = hledat_pozemkove_knihy(args.obec, sit=sit, max_vysledku=6)
            print(f"1. Pozemkové a gruntovní knihy (MZA ARON, fond C 17 a velkostatky):")
            if knihy:
                for k in knihy[:5]:
                    print(f"   • {k['name']}")
                    print(f"     Odkaz: {k['permalink']}")
            else:
                print(f"   (Pro přesný název panství zkuste `python3 -I tools/pozemky.py knihy \"{args.obec}\"`)")

            # 2. Lánové rejstříky
            print(f"\n2. Lánové rejstříky (MZA fond D 1, 1669–1679):")
            rejstriky = hledat_lanove_rejstriky(args.obec, sit=sit)
            if rejstriky:
                for r in rejstriky[:3]:
                    print(f"   • {r['name']}")
                    print(f"     Odkaz: {r['permalink']}")
            else:
                print(f"   • Prověřte panství obce v inventáři MZA D 1 na https://www.mza.cz/aron/")

            # 3. Stabilní katastr
            kat = katastr_odkazy(args.obec, dum_cp=args.dum)
            print(f"\n3. Stabilní katastr (1824–1843) a indikační skici se jmény držitelů:")
            print(f"   • ČÚZK Archiv (císařské otisky): {kat['cuzk_mapa_url']}")
            print(f"   • MZA Indikační skici Moravy:    {kat['mza_indikační_skici_url']}")
            for u in kat["mza_skici"]:
                print(f"       {u}")
            print(f"   Tip: V indikačních skicách jsou u čísel parcel a domů zapsána celá jména hospodářů!\n")

    finally:
        sit.zavri()


if __name__ == "__main__":
    main()
