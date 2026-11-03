#!/usr/bin/env python3
"""
pieta.py – hroby, pomníky a vojenská pietní místa (VETS.cz, hřbitovní vyhledávače).

Zdroje:
  vets        Spolek pro vojenská pietní místa (VETS.cz) – databáze pomníků, pamětních desek,
              válečných hrobů, čestných pohřebišť, padlých a obětí válek i totalitních režimů.
              Obsahuje GPS souřadnice, doslovné přepisy nápisů a fotografie.
  hrbitovy    Generátor přímých odkazů a dotazů do hřbitovních správ a databází náhrobků:
              - BillionGraves (fotografie náhrobků s GPS)
              - Find a Grave
              - Brno (gis.brno.cz/-/hrbitovy/ – Ústřední hřbitov, Židenice, Královo Pole...)
              - Jihlava (smj.cz vyhledávání hrobů)
              - Třebíč (trebic.cz vyhledávání hrobů)
              - Praha (hrbitovy.cz Správa pražských hřbitovů)

Použití (z kořene projektu):
  python3 -I tools/pieta.py vets hrdina "Novák" [--jmeno Jan]
  python3 -I tools/pieta.py vets misto "Holice" [--okres Pardubice]
  python3 -I tools/pieta.py vets detail "12345-pomnik-padlym"
  python3 -I tools/pieta.py vets foto "12345-pomnik-padlym" pracovni/pomnik.jpg
  python3 -I tools/pieta.py hrbitovy "Novák" [--jmeno Jan] [--rok 1890]
"""

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.parse
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_TOOLS = os.path.join(_ROOT, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

try:
    import sit
except ImportError:
    sit = None

VETS_BASE = "https://www.vets.cz"


def _strip_tags(html_text: str) -> str:
    """Odstraní HTML tagy a dekóduje entity."""
    if not html_text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def _odstran_diakritiku(text: str) -> str:
    """Převede text na ASCII bez diakritiky."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    ).lower()


# ==============================================================================
# VETS.CZ - Hrdinové a oběti
# ==============================================================================

def hledat_vets_hrdina(prijmeni: str, jmeno: Optional[str] = None) -> List[Dict[str, Any]]:
    """Vyhledá osoby v abecedním rejstříku VETS.cz."""
    s = sit.ziskej_klienta() if sit else None
    prijmeni_clean = prijmeni.strip()
    if not prijmeni_clean:
        return []

    prvni_pismeno = prijmeni_clean[0].lower()
    # Písmena v URL na VETS:
    url_pismeno = urllib.parse.quote(prvni_pismeno)
    url = f"{VETS_BASE}/vpm/hrdina/{url_pismeno}/"

    try:
        resp = s.get(url) if s else None
        if not resp or not resp.ok:
            return []
        html_text = resp.text()
    except Exception as e:
        sys.stderr.write(f"Chyba při dotazu na VETS hrdiny: {e}\n")
        return []

    # Odkazy na hrdiny: <li><a href="/vpm/vaclav-abraham-235/">Abraham Václav</a></li>
    matches = re.findall(r'<li><a href=[\"\'](/vpm/[^\"\']+)[\"\']>([^<]+)</a></li>', html_text)
    norm_prijmeni = _odstran_diakritiku(prijmeni_clean)
    norm_jmeno = _odstran_diakritiku(jmeno.strip()) if jmeno else None

    vysledky = []
    for href, full_name in matches:
        full_norm = _odstran_diakritiku(full_name)
        if norm_prijmeni in full_norm:
            if norm_jmeno and norm_jmeno not in full_norm:
                continue
            vysledky.append({
                "jmeno": full_name.strip(),
                "url": urllib.parse.urljoin(VETS_BASE, href),
                "path": href
            })

    # Pro nalezené stáhneme detail (max 10)
    for polozka in vysledky[:10]:
        detail = detail_vets_hrdina(polozka["url"])
        if detail:
            polozka.update(detail)

    return vysledky


def detail_vets_hrdina(url_nebo_path: str) -> Dict[str, Any]:
    """Získá podrobnosti o hrdinovi/oběti z VETS.cz."""
    s = sit.ziskej_klienta() if sit else None
    url = urllib.parse.urljoin(VETS_BASE, url_nebo_path)
    try:
        resp = s.get(url) if s else None
        if not resp or not resp.ok:
            return {}
        html = resp.text()
    except Exception as e:
        sys.stderr.write(f"Chyba při čtení detailu hrdiny {url}: {e}\n")
        return {}

    hero_match = re.search(r'<div id=\"hero\">(.*?)</div>', html, re.DOTALL)
    if not hero_match:
        return {}
    content = hero_match.group(1)

    name_m = re.search(r'<h3>\s*<a[^>]*>([^<]+)</a>\s*</h3>', content)
    jmeno = name_m.group(1).strip() if name_m else ""

    narozeni_m = re.search(r'\*\s*([^\n<]+)', content)
    narozeni = narozeni_m.group(1).strip() if narozeni_m else ""

    umrti_m = re.search(r'†\s*([^\n<]+)', content)
    umrti = umrti_m.group(1).strip() if umrti_m else ""

    # Seznam VPM památníků spojených s touto osobou
    # <a href="/vpm/12345-pomnik-padlym/#...">pomník</a> - Obec, okres Pardubice
    vpm_links = []
    for vm in re.finditer(r'<a href=[\"\'](/vpm/[^\"\']+)[\"\']>([^<]+)</a>\s*-\s*([^<\n]+)', content):
        vpm_url = urllib.parse.urljoin(VETS_BASE, vm.group(1))
        typ_pamatniku = vm.group(2).strip()
        misto = vm.group(3).strip()
        vpm_links.append({
            "url": vpm_url,
            "typ": typ_pamatniku,
            "misto": misto
        })

    # Text životopisu
    bio_text = _strip_tags(content)
    lines = bio_text.split("\n")
    clean_lines = []
    for l in lines:
        if l.startswith("VPM:") or "okres" in l and any(k in l for k in ["hrob", "deska", "pomník"]):
            continue
        clean_lines.append(l)

    return {
        "jmeno": jmeno,
        "narozeni": narozeni,
        "umrti": umrti,
        "pamatniky": vpm_links,
        "text": "\n".join(clean_lines).strip()
    }


# ==============================================================================
# VETS.CZ - Místa a památníky
# ==============================================================================

def hledat_vets_misto(obec: str, okres: Optional[str] = None) -> List[Dict[str, Any]]:
    """Vyhledá památníky a vojenské hroby v dané obci."""
    s = sit.ziskej_klienta() if sit else None
    obec_clean = obec.strip()

    if not okres:
        # Zkusíme dohledat okres z data/mista.json pro bleskové zacílení
        mista_file = os.path.join(_ROOT, "data", "mista.json")
        if os.path.exists(mista_file):
            try:
                with open(mista_file, "r", encoding="utf-8") as mf:
                    mista_data = json.load(mf)
                    minfo = mista_data.get(obec_clean)
                    if minfo and "osm" in minfo:
                        m_okr = re.search(r"okres\s+([^,]+)", minfo["osm"])
                        if m_okr:
                            okres = m_okr.group(1).strip()
            except Exception:
                pass

    norm_obec = _odstran_diakritiku(obec_clean)
    norm_okres = _odstran_diakritiku(okres.strip()) if okres else None


    # Seznam okresů
    kraje = [
        "1-jihocesky", "2-jihomoravsky", "3-karlovarsky", "4-kralovehradecky",
        "5-liberecky", "6-moravskoslezsky", "7-olomoucky", "8-pardubicky",
        "9-plzensky", "10-praha", "11-stredocesky", "12-ustecky",
        "13-vysocina", "14-zlinsky"
    ]

    cilove_obce = []

    for kraj_slug in kraje:
        if norm_okres and not any(k in kraj_slug for k in ["vysocina", "jihomoravsky"]):
            # drobná optimalizace pro Moravu
            pass
        url = f"{VETS_BASE}/vpm/mista/kraj/{kraj_slug}/"
        try:
            resp = s.get(url) if s else None
            if not resp or not resp.ok:
                continue
            html = resp.text()
            districts = re.findall(r'<a\s+href=[\"\'](/vpm/mista/okres/[^\"\']+)[\"\']>([^<]+)</a>', html)
            for dist_url, dist_name in districts:
                if norm_okres and norm_okres not in _odstran_diakritiku(dist_name):
                    continue
                # Prohledáme obce v okrese
                d_resp = s.get(urllib.parse.urljoin(VETS_BASE, dist_url)) if s else None
                if not d_resp or not d_resp.ok:
                    continue
                m_obce = re.findall(r'<a\s+href=[\"\'](/vpm/mista/obec/[^\"\']+)[\"\']>([^<]+)</a>', d_resp.text())
                for o_url, o_name in m_obce:
                    if norm_obec in _odstran_diakritiku(o_name):
                        cilove_obce.append((o_name, dist_name, urllib.parse.urljoin(VETS_BASE, o_url)))
        except Exception:
            continue

        if cilove_obce and not norm_okres:
            break

    pametni_mista = []
    for o_name, dist_name, o_url in cilove_obce:
        try:
            resp = s.get(o_url) if s else None
            if not resp or not resp.ok:
                continue
            html = resp.text()
            # Každé VPM má blok <div class="vpmone" id="...">
            items = re.findall(r'<div class=\"vpmone\"\s+id=\"([^\"]+)\">(.*?)<br style=\"clear:both;\">', html, re.DOTALL)
            for vpm_id, block in items:
                title_m = re.search(r'<h4[^>]*>\s*<a href=\"([^\"]+)\">([^<]+)</a>', block)
                url_detail = urllib.parse.urljoin(VETS_BASE, title_m.group(1)) if title_m else ""
                nazev = title_m.group(2).strip() if title_m else vpm_id

                loc_m = re.search(r'Umístění:\s*([^<]+)<br>', block)
                umisteni = loc_m.group(1).strip() if loc_m else ""

                napis_m = re.search(r'<div class=\"vpmonenapis\">Nápis:<br>(.*?)</div>', block, re.DOTALL)
                napis = _strip_tags(napis_m.group(1)) if napis_m else ""

                gps_m = re.search(r'lat=([0-9.]+)&amp;lon=([0-9.]+)', block)
                gps = (float(gps_m.group(1)), float(gps_m.group(2))) if gps_m else None

                foto_m = re.search(r'<div class=\"misto_main_photo\">.*?<a href=\"([^\"]+)\"', block, re.DOTALL)
                foto_url = urllib.parse.urljoin(VETS_BASE, foto_m.group(1)) if foto_m else ""

                pametni_mista.append({
                    "id": vpm_id,
                    "nazev": nazev,
                    "obec": o_name,
                    "okres": dist_name,
                    "umisteni": umisteni,
                    "napis": napis,
                    "gps": gps,
                    "url": url_detail,
                    "foto_url": foto_url
                })
        except Exception as e:
            sys.stderr.write(f"Chyba při čtení obce {o_name}: {e}\n")

    return pametni_mista


def detail_vets_pamatnik(identifikator_nebo_url: str) -> Dict[str, Any]:
    """Získá úplný detail památníku nebo válečného hrobu z VETS.cz."""
    s = sit.ziskej_klienta() if sit else None
    if identifikator_nebo_url.startswith("http"):
        url = identifikator_nebo_url
    else:
        ident = identifikator_nebo_url.strip("/# ")
        url = f"{VETS_BASE}/vpm/{ident}/"

    try:
        resp = s.get(url) if s else None
        if not resp or not resp.ok:
            return {}
        html = resp.text()
    except Exception as e:
        sys.stderr.write(f"Chyba při čtení VPM {url}: {e}\n")
        return {}

    title_m = re.search(r'<h4>\s*<a[^>]*>([^<]+)</a>\s*</h4>', html)
    nazev = title_m.group(1).strip() if title_m else ""

    loc_m = re.search(r'Umístění:\s*([^<]+)<br>', html)
    umisteni = loc_m.group(1).strip() if loc_m else ""

    napis_m = re.search(r'<div class=\"vpmonenapis\">Nápis:<br>(.*?)</div>', html, re.DOTALL)
    napis = _strip_tags(napis_m.group(1)) if napis_m else ""

    poznamka_m = re.search(r'Poznámka:\s*<br>\s*<p[^>]*>(.*?)</p>', html, re.DOTALL)
    poznamka = _strip_tags(poznamka_m.group(1)) if poznamka_m else ""

    gps_m = re.search(r'lat=([0-9.]+)&amp;lon=([0-9.]+)', html)
    gps = f"{gps_m.group(1)}, {gps_m.group(2)}" if gps_m else ""

    # Fotografie
    fotky = []
    for fm in re.finditer(r'<a href=[\"\'](/vpm/foto/mista/normal/[^\"\']+)[\"\']', html):
        f_url = urllib.parse.urljoin(VETS_BASE, fm.group(1))
        if f_url not in fotky:
            fotky.append(f_url)

    return {
        "nazev": nazev,
        "umisteni": umisteni,
        "napis": napis,
        "poznamka": poznamka,
        "gps": gps,
        "url": url,
        "fotky": fotky
    }


def stahni_vets_foto(identifikator_nebo_url: str, vystup_cesta: str) -> bool:
    """Stáhne hlavní fotografii památníku nebo hrobu z VETS.cz."""
    s = sit.ziskej_klienta() if sit else None
    detail = detail_vets_pamatnik(identifikator_nebo_url)
    if not detail or not detail.get("fotky"):
        sys.stderr.write("Nenalezena žádná fotografie pro daný památník.\n")
        return False

    foto_url = detail["fotky"][0]
    return s.stahni_soubor(foto_url, vystup_cesta) if s else False


# ==============================================================================
# Hřbitovní správy a databáze hrobů (odkazy)
# ==============================================================================

def vygeneruj_odkazy_hrbitovy(prijmeni: str, jmeno: Optional[str] = None, rok: Optional[int] = None) -> Dict[str, str]:
    """Vygeneruje přímé vyhledávací odkazy na české i mezinárodní hřbitovní vyhledávače."""
    p = urllib.parse.quote(prijmeni.strip())
    j = urllib.parse.quote(jmeno.strip()) if jmeno else ""
    r = str(rok) if rok else ""

    odkazy = {
        "BillionGraves (foto náhrobků s GPS)": f"https://billiongraves.com/search/results?given_names={j}&family_names={p}&birth_year={r}",
        "Find a Grave (databáze hrobů)": f"https://www.findagrave.com/memorial/search?firstname={j}&lastname={p}&location=Czech+Republic",
        "Brno GIS – Správa hřbitovů města Brna": "https://gis.brno.cz/-/hrbitovy/",
        "Jihlava – vyhledávání hrobových míst": "https://www.smj.cz/sluzby/hrbitovy/vyhledavani-hrobu/",
        "Třebíč – vyhledávání hrobů": "https://trebic.cz/vyhledavani-hrobu/",
        "Praha – Správa pražských hřbitovů": "https://www.hrbitovy.cz/?page_id=89"
    }
    return odkazy


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Hroby, pomníky a vojenská pietní místa (VETS.cz, hřbitovy)")
    sub = parser.add_subparsers(dest="prikaz", required=True)

    # VETS
    p_vets = sub.add_parser("vets", help="Vyhledávání na VETS.cz (Spolek pro vojenská pietní místa)")
    vets_sub = p_vets.add_subparsers(dest="vets_prikaz", required=True)

    # vets hrdina
    p_h = vets_sub.add_parser("hrdina", help="Hledání hrdiny / oběti v abecedním rejstříku VETS")
    p_h.add_argument("prijmeni", help="Příjmení hledané osoby (např. Novák)")
    p_h.add_argument("--jmeno", help="Křestní jméno (např. Jan)")

    # vets misto
    p_m = vets_sub.add_parser("misto", help="Hledání památníků, hrobů a desek v obci")
    p_m.add_argument("obec", help="Název obce (např. Holice, Chrudim)")
    p_m.add_argument("--okres", help="Název okresu pro zúžení (např. Pardubice)")

    # vets detail
    p_d = vets_sub.add_parser("detail", help="Detail památníku z VETS.cz")
    p_d.add_argument("ident", help="Identifikátor nebo URL památníku (např. 12345-pomnik-padlym)")

    # vets foto
    p_f = vets_sub.add_parser("foto", help="Stáhnutí fotografie památníku nebo hrobu z VETS.cz")
    p_f.add_argument("ident", help="Identifikátor nebo URL památníku")
    p_f.add_argument("vystup", help="Cesta k výstupnímu souboru .jpg")

    # hrbitovy
    p_hrb = sub.add_parser("hrbitovy", help="Přímé vyhledávací odkazy na hřbitovní vyhledávače a náhrobky")
    p_hrb.add_argument("prijmeni", help="Příjmení")
    p_hrb.add_argument("--jmeno", help="Křestní jméno")
    p_hrb.add_argument("--rok", type=int, help="Rok narození nebo úmrtí")

    args = parser.parse_args()

    if args.prikaz == "vets":
        if args.vets_prikaz == "hrdina":
            print(f"Hledám na VETS.cz: '{args.prijmeni}' (jméno: {args.jmeno or 'všechna'})...")
            nalezy = hledat_vets_hrdina(args.prijmeni, args.jmeno)
            if not nalezy:
                print("Nebyly nalezeny žádné shody v abecedním rejstříku VETS.cz.")
                return

            print(f"\nNalezeno {len(nalezy)} záznamů na VETS.cz:")
            for it in nalezy:
                print(f"\n👉 {it['jmeno']}")
                if it.get("narozeni") or it.get("umrti"):
                    print(f"   Životní data: * {it.get('narozeni', '?')}  † {it.get('umrti', '?')}")
                print(f"   Odkaz: {it['url']}")
                if it.get("text"):
                    print(f"   Životopis: {it['text'][:250]}...")
                if it.get("pamatniky"):
                    print("   Pietní místa a hroby:")
                    for pam in it["pamatniky"]:
                        print(f"     • {pam['typ']} ({pam['misto']}): {pam['url']}")

        elif args.vets_prikaz == "misto":
            print(f"Hledám památníky a hroby pro obec '{args.obec}' na VETS.cz...")
            mista = hledat_vets_misto(args.obec, args.okres)
            if not mista:
                print(f"Pro obec '{args.obec}' nebyly na VETS.cz nalezeny žádné památníky.")
                return

            print(f"\nNalezeno {len(mista)} pietních míst v obci {args.obec}:")
            for m in mista:
                print(f"\n🏛️  {m['nazev']} [{m['id']}]")
                print(f"    Umístění: {m['umisteni']}")
                if m.get("gps"):
                    print(f"    GPS: {m['gps'][0]}, {m['gps'][1]}")
                print(f"    Odkaz: {m['url']}")
                if m.get("napis"):
                    print(f"    Nápis:\n{m['napis']}")

        elif args.vets_prikaz == "detail":
            d = detail_vets_pamatnik(args.ident)
            if not d:
                print("Památník nebyl nalezen.")
                return
            print(f"\n🏛️  {d['nazev']}")
            print(f"   Umístění: {d['umisteni']}")
            if d.get("gps"):
                print(f"   GPS: {d['gps']}")
            print(f"   Odkaz: {d['url']}")
            if d.get("napis"):
                print(f"\n   Nápis:\n{d['napis']}")
            if d.get("poznamka"):
                print(f"\n   Poznámka:\n{d['poznamka']}")
            if d.get("fotky"):
                print(f"\n   Fotografie ({len(d['fotky'])}):")
                for f in d["fotky"]:
                    print(f"     • {f}")

        elif args.vets_prikaz == "foto":
            uspech = stahni_vets_foto(args.ident, args.vystup)
            if uspech:
                print(f"Fotografie úspěšně uložena do: {args.vystup}")
            else:
                print("Chyba při stahování fotografie.")
                sys.exit(1)

    elif args.prikaz == "hrbitovy":
        odkazy = vygeneruj_odkazy_hrbitovy(args.prijmeni, args.jmeno, args.rok)
        print(f"\nHřbitovní správy a online databáze náhrobků pro '{args.prijmeni}' {args.jmeno or ''}:")
        for zdroj, link in odkazy.items():
            print(f"  • {zdroj}:\n    👉 {link}")


if __name__ == "__main__":
    main()
