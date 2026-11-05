#!/usr/bin/env python3
"""Zapíše celou dávku nových zápisů jedním voláním: výřez, rámeček, přepis, záznam (a případně svazek) pro každý.
Šetří kroky i kontext pomocníka – místo ~6 volání na zápis jedno na dávku a jeden souhrnný kontrolní obrázek.

Použití (z kořene projektu):
  zapis_davka.py <davka.json> [--prepsat] [--nanecisto]
    davka.json   seznam objektů (napiš nástrojem Write do pracovni/<úkol>/), každý:
      {"klic": "z_1890_anna_novakova",
       "snimek": "pracovni/…/stranka.jpg",        plný snímek stránky (plné rozlišení)
       "vyrez": [x0, y0, x1, y1],                  oblast zápisu na snímku (zlomky 0..1), velkoryse i s hlavičkou
       "ramecek": [[x0, y0, x1, y1], …],           čtené místo jako zlomky VÝŘEZU (vyrezy/<klic>.jpg)
       "ramecek_pozn": "",                         nepovinné
       "prepis": {"orig": "…", "cs": "…"},         doslovné čtení + český překlad pro rodinu
       "zaznam": {"druh": "Z", "datum": "…", "nazev": "…", "misto": "…", "svazek": "mza_1234",
                  "snimek": 42, "odkaz": "…?strana=42", "shrnuti": "…"},
       "svazek": {"id": "mza_1234", …}}           nepovinné – jen když svazek v data/svazky.json ještě není
    --prepsat    dovolí přepsat zápis, který už v datech je (jinak dávka skončí dřív, než cokoli zapíše)
    --nanecisto  jen zkontroluje vstup, nic nezapíše
Nejdřív zkontroluje celou dávku (povinná pole, existence snímků, souřadnice, existující klíče), teprve pak zapisuje.
Na konci vytvoří pracovni/ramecky_davka.jpg – všechny rámečky na jednom obrázku; prohlédni si ho.
Osoby (data/osoby.py), deník a ISSUES dál upravuj nástrojem Edit; najdi je přes tools/osoba.py.
"""
import json, os, re, shutil, subprocess, sys
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
POVINNE_ZAZNAM = ("druh", "datum", "nazev", "misto", "svazek", "odkaz", "shrnuti")


def oblast(b):
    return (isinstance(b, (list, tuple)) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)
            and 0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1)


def zkontroluj(davka, prepsat):
    chyby = []
    zaznamy = {x.get("klic") for x in json.load(open(os.path.join(ROOT, "data", "zaznamy.json"), encoding="utf-8"))}
    svazky = json.load(open(os.path.join(ROOT, "data", "svazky.json"), encoding="utf-8"))
    videne = set()
    for i, r in enumerate(davka):
        k = r.get("klic") if isinstance(r, dict) else None
        kde = f"položka {i + 1} ({k or 'bez klíče'})"
        if not isinstance(k, str) or not re.fullmatch(r"[a-z0-9_]+", k):
            chyby.append(f"{kde}: „klic“ musí být text z malých písmen bez diakritiky, číslic a _")
            continue
        if k in videne:
            chyby.append(f"{kde}: klíč je v dávce dvakrát")
        videne.add(k)
        obrazek = any(os.path.exists(os.path.join(ROOT, d, k + ".jpg")) for d in ("zdroje", "vyrezy"))
        if (k in zaznamy or obrazek) and not prepsat:
            chyby.append(f"{kde}: zápis nebo obrázek zdroje/vyrezy/{k}.jpg už existuje (přepsat jen s --prepsat)")
        if "ramecek_pozn" in r and not isinstance(r["ramecek_pozn"], str):
            chyby.append(f"{kde}: „ramecek_pozn“ musí být text")
        if not os.path.isfile(os.path.join(ROOT, r.get("snimek", ""))):
            chyby.append(f"{kde}: snímek „{r.get('snimek')}“ neexistuje")
        if not oblast(r.get("vyrez")):
            chyby.append(f"{kde}: „vyrez“ musí být [x0, y0, x1, y1] ve zlomcích 0..1")
        if not r.get("ramecek") or not all(oblast(b) for b in r["ramecek"]):
            chyby.append(f"{kde}: „ramecek“ musí být seznam [[x0, y0, x1, y1], …] ve zlomcích 0..1")
        p = r.get("prepis") or {}
        if not (p.get("orig") and p.get("cs")):
            chyby.append(f"{kde}: „prepis“ potřebuje „orig“ i „cs“")
        z = r.get("zaznam") or {}
        chybi = [f for f in POVINNE_ZAZNAM if not z.get(f)]
        if chybi:
            chyby.append(f"{kde}: v „zaznam“ chybí {', '.join(chybi)}")
        if z.get("klic", k) != k:
            chyby.append(f"{kde}: „zaznam.klic“ ({z['klic']}) nesedí s „klic“")
        sv = r.get("svazek")
        if z.get("svazek") and z["svazek"] not in svazky and not (sv and sv.get("id") == z["svazek"]):
            chyby.append(f"{kde}: svazek „{z['svazek']}“ není v data/svazky.json – přidej „svazek“ s „id“")
        if sv is not None:
            if not isinstance(sv, dict) or sv.get("id") != z.get("svazek"):
                chyby.append(f"{kde}: „svazek“ potřebuje „id“ shodné se „zaznam.svazek“")
            elif sv["id"] in svazky and not prepsat:
                chyby.append(f"{kde}: svazek „{sv['id']}“ už v data/svazky.json je – „svazek“ vynech (nebo --prepsat)")
    return chyby


HOTOVO = []   # klíče zapsané v tomto běhu – pro hlášení při chybě uprostřed dávky


def spust(*args, vstup=None):
    out = subprocess.run([sys.executable, "-I", *args], input=vstup, capture_output=True, text=True, cwd=ROOT)
    if out.returncode:
        sys.exit(f"CHYBA při {' '.join(os.path.basename(a) for a in args[:2])}:\n{out.stderr or out.stdout}\n"
                 f"Celé zapsané: {', '.join(HOTOVO) or 'nic'}. Rozepsaný zápis i zbytek dávky zapiš znovu s --prepsat "
                 "(zapsané položky z dávky vyřaď).")


def main():
    neznamy = [a for a in sys.argv[1:] if a.startswith("--") and a not in ("--prepsat", "--nanecisto")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if neznamy or len(args) != 1:
        sys.exit((f"Neznámý přepínač {', '.join(neznamy)} – nic nezapsáno.\n" if neznamy else "") + __doc__)
    try:
        davka = json.load(open(args[0], encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        sys.exit(f"Vstup {args[0]} není platný JSON: {e}")
    if not isinstance(davka, list) or not davka:
        sys.exit("Vstup musí být neprázdný seznam [ {…}, … ].")
    chyby = zkontroluj(davka, "--prepsat" in sys.argv)
    if chyby:
        sys.exit("Dávka nezapsána, oprav vstup:\n- " + "\n- ".join(chyby))
    if "--nanecisto" in sys.argv:
        print(f"Vstup v pořádku: {len(davka)} zápisů (nic nezapsáno).")
        return
    nahledy = []
    for r in davka:
        k = r["klic"]
        spust(os.path.join(TOOLS, "vyrez.py"), r["snimek"], k, ",".join(str(v) for v in r["vyrez"]))
        pozn = ["--pozn", r["ramecek_pozn"]] if r.get("ramecek_pozn") else []
        spust(os.path.join(TOOLS, "ramecek.py"), k, *[",".join(str(v) for v in b) for b in r["ramecek"]], *pozn)
        if r.get("svazek"):   # svazek před záznamem – záznam nikdy neodkazuje na chybějící svazek
            sv = {x: y for x, y in r["svazek"].items() if x != "id"}
            spust(os.path.join(TOOLS, "zapis.py"), "svazky", r["svazek"]["id"], "-", vstup=json.dumps(sv, ensure_ascii=False))
        spust(os.path.join(TOOLS, "zapis.py"), "prepisy", k, "-", vstup=json.dumps(r["prepis"], ensure_ascii=False))
        spust(os.path.join(TOOLS, "zapis.py"), "zaznamy", k, "-", vstup=json.dumps({"klic": k, **r["zaznam"]}, ensure_ascii=False))   # klic první jako v ostatních záznamech
        nahledy.append(os.path.join(ROOT, "pracovni", f"ramecek_{k}.jpg"))
        HOTOVO.append(k)
        print(f"zapsáno: {k}")
    # jeden souhrnný obrázek místo N náhledů – pomocník si prohlédne jen ten
    souhrn = os.path.join(ROOT, "pracovni", "ramecky_davka.jpg")
    m = shutil.which("magick")
    montage = [m, "montage"] if m else [shutil.which("montage") or "montage"]   # ImageMagick 7 / 6
    if os.path.exists(souhrn):
        os.remove(souhrn)
    # bez popisků: ImageMagick bez nastaveného písma popisky neumí; pořadí vypíšeme
    try:
        subprocess.run(montage + [*nahledy, "-geometry", "700x700>+6+6", "-tile", "3x", souhrn], capture_output=True)
    except OSError:   # montage není na PATH (např. Windows) – zápis je hotový, jen bez souhrnu
        pass
    if os.path.exists(souhrn):
        print(f"Hotovo: {len(davka)} zápisů. Prohlédni si rámečky v {souhrn} "
              f"(po řádcích zleva, 3 vedle sebe): {', '.join(r['klic'] for r in davka)}")
    else:
        print(f"Hotovo: {len(davka)} zápisů. Souhrn se nepodařil – prohlédni pracovni/ramecek_<klic>.jpg jednotlivě.")


if __name__ == "__main__":
    main()
