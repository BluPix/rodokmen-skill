#!/usr/bin/env python3
"""Kontrola konzistence dat rodokmenu. Spouštějte po každé větší změně a před stavbou webu.

Použití: kontrola.py
Vypíše CHYBY (rozbijí web nebo jsou věcně špatně) a UPOZORNĚNÍ (něco chybí, doplnit).
Návratový kód 1, pokud jsou chyby.
"""
import datetime, json, os, re, sys
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("RODOKMEN_DATA") or os.path.join(ROOT, "data")   # jiná složka dat jen pro testy


def jload(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def manzel(fact):
    """Jméno ze sňatku: „× 2. 16. 6. 1925 Antonín Holubář († 1950) z Okřešic“ → „Antonín Holubář“ (jako v gedcom.py)."""
    t = re.sub(r"\{\{\s*\w+\s*:?\s*|\s*\}\}", "", fact).lstrip("× ").strip()
    t = re.sub(r"^\d\.\s+(?=\d{1,2}\.\s*\d{1,2}\.\s*\d{4}|\d{4}|\D)", "", t)
    t = re.sub(r"^((kol\.|asi|před|po)\s*)?(\d{1,2}\.\s*\d{1,2}\.\s*)?\d{4}", "", t)
    return re.split(r"\s+z\s+|,", re.sub(r"\s*\(.*?\)", "", t))[0].strip()


def jmeno_sedi(spouse, name):
    """Jméno ze sňatku patří osobě: stejné příjmení (první 4 písmena); je-li ve sňatku jen křestní, stejné křestní."""
    s = spouse.replace("roz. ", "").split()
    n = re.sub(r"\s*\(.*?\)", "", name or "").replace("roz. ", "").split()
    if not s or not n:
        return False
    if len(s) == 1 or len(n) == 1 or "…" in s[-1]:   # příjmení neznámé nebo nečitelné → stačí křestní
        return s[0] == n[0]
    return s[-1][:4] == n[-1][:4]


def main():
    err, warn = [], []
    ns = {}
    try:
        exec(open(os.path.join(DATA, "osoby.py"), encoding="utf-8").read(), ns)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"CHYBA: data/osoby.py nejde načíst: {e}")
    P, SIDE, LINES, SAME = ns.get("P", {}), ns.get("SIDE", []), ns.get("LINES", {}), ns.get("SAME", {})
    zaz = jload("zaznamy.json", [])
    svazky, prep, hl = jload("svazky.json", {}), jload("prepisy.json", {}), jload("zvyrazneni.json", {})
    keys = [z.get("klic") for z in zaz]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        err.append(f"zápisy se stejným klíčem: {sorted(dup)}")
    keys = set(keys)

    if 1 not in P:
        err.append("chybí osoba 1 (výchozí osoba rodokmenu)")
    for k, p in P.items():
        if not isinstance(k, int) or k < 1:
            err.append(f"osoba {k!r}: číslo musí být kladné celé číslo")
            continue
        if k > 1 and k // 2 not in P and k not in SAME:
            warn.append(f"osoba {k} ({p.get('n')}): v rodokmenu chybí její dítě {k // 2} – je číslo správně?")
        st = p.get("st", "unk")
        if st not in ("doc", "prob", "fam", "mh", "unk"):
            err.append(f"osoba {k}: neznámý stav '{st}'")
        for r in p.get("r", []):
            if r not in keys:
                err.append(f"osoba {k} ({p.get('n')}) cituje neexistující zápis '{r}'")
        if st == "doc" and not p.get("r"):
            warn.append(f"osoba {k} ({p.get('n')}) je 'doc' (doloženo), ale necituje žádný zápis")
    side_ids = {}
    for s in SIDE:
        if s.get("k") not in P:
            err.append(f"boční příbuzný '{s.get('n')}' patří k neexistující osobě {s.get('k')}")
        for r in s.get("r", []):
            if r not in keys:
                err.append(f"boční příbuzný '{s.get('n')}' cituje neexistující zápis '{r}'")
        if any(x in s for x in ("otec", "matka", "partner", "id")):   # širší rodina (strukturovaná položka)
            sid = s.get("id")
            if not sid or not re.match(r"^[a-z0-9_]+$", sid):
                err.append(f"boční příbuzný '{s.get('n')}': strukturovaná položka potřebuje 'id' (malá písmena, číslice, podtržítko), např. 'josef_novak_1902'")
            elif sid in side_ids:
                err.append(f"boční příbuzný '{s.get('n')}': id '{sid}' už má '{side_ids[sid]}'")
            else:
                side_ids[sid] = s.get("n")
            if s.get("sex") not in (None, "M", "F"):
                err.append(f"boční příbuzný '{s.get('n')}': 'sex' musí být 'M' nebo 'F'")
    for s in SIDE:
        if not any(x in s for x in ("otec", "matka", "partner", "id")):
            continue
        for key in ("otec", "matka", "partner"):
            for x in (s.get(key) if isinstance(s.get(key), list) else [s.get(key)]):
                if x is None:
                    continue
                if isinstance(x, int) and x not in P and x not in SAME:
                    err.append(f"boční příbuzný '{s.get('n')}': '{key}' = {x} není v rodokmenu")
                elif isinstance(x, str) and x not in side_ids:
                    err.append(f"boční příbuzný '{s.get('n')}': '{key}' = '{x}' není id žádného bočního příbuzného")
        if s.get("st") == "doc" and not s.get("r"):
            warn.append(f"boční příbuzný '{s.get('n')}' je 'doc', ale necituje žádný zápis")
    nestrukt = sum(1 for s in SIDE if not any(x in s for x in ("otec", "matka", "partner", "id")))
    if nestrukt:
        warn.append(f"{nestrukt} bočních příbuzných je jen text bez 'otec'/'matka' – nejsou ve stromu ani nemají stránku; "
                    f"doplň 'id', 'otec'/'matka' (číslo předka nebo id), 'sex', 'f', 'y' (viz AGENTS.md „Širší rodina“)")
    # ženy rodným příjmením: „roz. …“ ve jménu nebo jako samostatný fakt znamená, že 'n' je příjmení po svatbě
    for kde, o in [(f"osoba {k}", p) for k, p in P.items()] + [("boční příbuzná", s) for s in SIDE]:
        if re.search(r"\broz\.", o.get("n", "")) or any(f.strip().startswith("roz.") for f in o.get("f", [])):
            warn.append(f"PŘÍJMENÍ – {kde} '{o.get('n')}': do 'n' patří rodné příjmení, příjmení po svatbě jako fakt "
                        f"„provdaná Došková“, u příbuzné jen s textem do závorky „Marie Nováková (provd. Šindelková, * 1925)“")
    # sňatky: každý manžel(ka) z údaje „×“ má být v datech jako osoba – jinak ho GEDCOM ani strom neznají
    jmena = {k: p.get("n", "") for k, p in P.items()}
    jmena.update({s["id"]: s.get("n", "") for s in SIDE if s.get("id")})
    partneri = {}
    def spoj(a, b):
        a, b = (SAME.get(x, x) if isinstance(x, int) else x for x in (a, b))
        if a in jmena and b in jmena:
            partneri.setdefault(a, set()).add(jmena[b])
            partneri.setdefault(b, set()).add(jmena[a])
    for k in P:
        if isinstance(k, int) and k > 1:
            spoj(k, k ^ 1)
    for s in SIDE:
        for x in (s.get("partner") if isinstance(s.get("partner"), list) else [s.get("partner")]):
            if s.get("id") and x is not None:
                spoj(s["id"], x)
        if s.get("otec") is not None and s.get("matka") is not None:
            spoj(s["otec"], s["matka"])
    for x, o in list(P.items()) + [(s["id"], s) for s in SIDE if s.get("id")]:
        sn = [f for f in o.get("f", []) if f.lstrip().startswith("×")]
        for f in sn:
            if not any(jmeno_sedi(manzel(f), n) for n in partneri.get(SAME.get(x, x) if isinstance(x, int) else x, ())):
                warn.append(f"SŇATEK – {x} ({o.get('n')}): „{f}“ – manžel(ka) není v datech jako osoba; doplň do SIDE příbuzného "
                            f"s 'id', 'sex' a 'partner': {x!r} (děti z toho sňatku s 'otec'/'matka'), jinak ho GEDCOM ani strom neznají")
        zena = o.get("sex") == "F" if not isinstance(x, int) or x == 1 else x % 2 == 1
        if zena and len(sn) > 1 and not any(f.strip().startswith("provd") for f in o.get("f", [])):
            warn.append(f"PŘÍJMENÍ – {x} ({o.get('n')}): {len(sn)} sňatky, ale chybí údaj „provdaná …, později …“ s příjmeními po svatbách")
    pribehy = sum(1 for p in P.values() if p.get("pribeh")) + sum(1 for s in SIDE if s.get("pribeh"))
    for a, c in SAME.items():
        if c not in P:
            err.append(f"SAME: {a} -> {c}, ale osoba {c} neexistuje")
    for k in LINES:
        if k not in range(8, 16):
            err.append(f"LINES: rod {k} – rody mají čísla 8 až 15 (pradědečci a prababičky)")

    cited = {r for p in P.values() for r in p.get("r", [])} | {r for s in SIDE for r in s.get("r", [])}
    for z in zaz:
        k = z.get("klic", "?")
        for f in ("klic", "druh", "datum", "nazev", "shrnuti"):
            if not z.get(f):
                err.append(f"zápis {k}: chybí pole '{f}'")
        if z.get("svazek") and z["svazek"] not in svazky:
            err.append(f"zápis {k}: svazek '{z['svazek']}' není v data/svazky.json")
        if z.get("ukazka"):   # vymyšlený zápis ukázkové rodiny – nemá snímek ani přepis
            continue
        if not z.get("odkaz") and not svazky.get(z.get("svazek", ""), {}).get("url"):
            warn.append(f"zápis {k}: chybí odkaz na snímek (pole 'odkaz')")
        if not os.path.exists(os.path.join(ROOT, "vyrezy", k + ".jpg")):
            warn.append(f"zápis {k}: chybí výřez vyrezy/{k}.jpg")
        elif k not in hl:
            warn.append(f"zápis {k}: chybí rámeček (tools/ramecek.py)")
        if k not in prep:
            warn.append(f"zápis {k}: chybí přepis a překlad v data/prepisy.json")
        elif not prep[k].get("cs") and not prep[k].get("cz"):
            warn.append(f"zápis {k}: chybí překlad ('cs' nebo 'cz') v data/prepisy.json")
        if k not in cited:
            warn.append(f"zápis {k}: necituje ho žádná osoba (doplnit do 'r' u osoby nebo bočního příbuzného)")


    # --- formát data zápisu: web řadí funkcí dateKey(), která u ISO tvaru (1822-06-04) prohodí den a měsíc
    datum_ok = re.compile(r"^(\d{1,2}\. \d{1,2}\. \d{4}|\d{1,2}\. \d{4}|\d{1,2}/\d{4}|\d{4}|(před|po|kol\.|asi|cca) \d{4}|\d{4}–\d{4})$")
    for z in zaz:
        if z.get("datum") and not datum_ok.match(str(z["datum"]).strip()):
            err.append(f"zápis {z.get('klic')}: datum '{z['datum']}' musí být česky („4. 6. 1822“, „3/1867“, „1797“), ne ISO – web ho jinak špatně seřadí")
    # --- rámečky: klíč musí být 'boxes' (jiný klíč web ignoruje a rámeček nevykreslí)
    for k, e in hl.items():
        if isinstance(e, dict) and "boxes" not in e:
            err.append(f"rámeček {k}: v zvyrazneni.json chybí klíč 'boxes' (je tam {sorted(e)}) – znovu tools/ramecek.py")
    # --- fakta s plným datem u osoby 'doc' musí mít oporu v jejích zápisech (jinak jsou tiše z GEDCOMu / od rodiny)
    mes = "ledna února března dubna května června července srpna září října listopadu prosince".split()
    zk = {z.get("klic"): z for z in zaz}

    def tvary(d, m, y):
        return {f"{d}. {m}. {y}", f"{d}/{m} {y}", f"{d}/{m}. {y}", f"{d}. {mes[m - 1]} {y}", f"{d}.{m}.{y}", f"{d}/{m}/{y}",
                f"{y}-{m:02d}-{d:02d}", f"{d:02d}.{m:02d}.{y}", f"{d}. {m:02d}. {y}"}
    for k, p in P.items():
        if p.get("st") != "doc":
            continue
        text = " ".join((prep.get(r, {}).get("orig", "") + " " + prep.get(r, {}).get("cs", "") + " " + prep.get(r, {}).get("cz", "")
                         + " " + zk.get(r, {}).get("shrnuti", "") + " " + str(zk.get(r, {}).get("datum", ""))) for r in p.get("r", []))
        text = re.sub(r"\s+", " ", text)
        note = p.get("note", "")
        for f in p.get("f", []):
            if "{{" in f:
                continue   # údaj je označený ({{rodina}}, {{strom}}, {{neověřeno}}, {{hypotéza}}) – to je v pořádku
            for m in re.finditer(r"(\d{1,2})\. (\d{1,2})\. (\d{4})", f):
                d, mo, y = map(int, m.groups())
                if not (1 <= mo <= 12) or any(t in text for t in tvary(d, mo, y)):
                    continue
                if any(t in note for t in tvary(d, mo, y)):
                    continue   # zdroj toho data je vysvětlený v poznámce („podle rodinného stromu MyHeritage † 25. 11. 1849, neověřeno“)
                warn.append(f"osoba {k} ({p.get('n')}): údaj „{f}“ není v žádném z jejích zápisů {p.get('r')} – "
                            f"doplň zdroj do 'note' (rodina, strom MyHeritage…), nebo ho přesuň z faktů; 'doc' = přečteno na snímku")
        # roky života 'y' vs. fakt narození
        yb = re.search(r"\d{4}", p.get("y", "") or "")
        fb = next((re.search(r"\d{4}", f) for f in p.get("f", []) if f.startswith("*") and re.search(r"\d{4}", f)), None)
        if yb and fb and not p.get("y", "").startswith("†") and yb.group(0) != fb.group(0):
            warn.append(f"osoba {k} ({p.get('n')}): roky 'y' ({p.get('y')}) nesedí s faktem narození ({fb.string})")

    for name, e in jload("mista.json", {}).items():
        if "lat" not in e:
            warn.append(f"místo {name}: nemá souřadnice (spusťte tools/mista.py)")
        try:
            re.compile(e.get("re") or "")
        except re.error as ex:
            err.append(f"místo {name}: špatný výraz '{e.get('re')}': {ex}")

    cfg = jload("web.json", {})
    if not (cfg.get("prihlaseni") or {}).get("odpoved") and not (cfg.get("prihlaseni") or {}).get("otevreny"):
        warn.append("web.json: není nastavená odpověď na přihlašovací otázku – nasazení webu skončí chybou")

    if re.search(r"Novák|Petrovi", json.dumps(cfg, ensure_ascii=False)) and "Novák" not in P.get(1, {}).get("n", ""):
        warn.append("web.json: jsou v něm ještě ukázkové texty (Novákovi) – nastav název, příběh a kontakt")

    # Citlivé věci, které jdou na web: ISSUES („Co hledáme“), poznámky a fakta osob, boční příbuzní, texty.
    citlive = re.compile(r"sebevra|vzal[a]? si život|oběsil|zastřelil[a]? se|utopil[a]? se|alkohol|vězen|kriminál|"
                         r"rozvod|rozvedl|psychiatr|léčebn|duševn|rakovin|nemanželsk|cizoložst|dluh|exekuc|interrupc|potrat", re.I)

    hranice = datetime.date.today().year - 100   # posledních ~100 let; staré matriční údaje (nemanželské dítě v 18. stol.) nevadí

    def recent(text):
        return any(int(y) >= hranice for y in re.findall(r"\b(19\d\d|20\d\d)\b", text))
    schvaleno = [s for s in (cfg.get("citlive_schvaleno") if isinstance(cfg.get("citlive_schvaleno"), list) else [])
                 if isinstance(s, str) and len(s.strip()) >= 3]

    def schvalene(text, m):   # uživatel to na web pustil: v web.json „citlive_schvaleno“ je úryvek textu s tímto slovem
        umrti = re.search(r"†[^†]{0,30}?\b(1[5-9]\d\d|20\d\d)\b[^†„“]{0,50}$", text[:m.start()])   # „† 28. 5. 1890 Kouty čp. 2 (rakovina…“
        if umrti and int(umrti.group(1)) < hranice:   # příčina smrti z matriky u úmrtí starého přes 100 let není tajemství
            return True
        for s in schvaleno:
            i = text.find(s)
            while i >= 0:
                if i <= m.start() and m.end() <= i + len(s):
                    return True
                i = text.find(s, i + 1)
        return False
    texty = [("ISSUES", i if isinstance(i, str) else " ".join(i)) for i in ns.get("ISSUES", [])]
    for k, p in P.items():
        text = " ".join(p.get("f", [])) + " " + p.get("note", "")
        roky = [int(y) for y in re.findall(r"\b1[5-9]\d\d|20\d\d\b", p.get("y", "") + " " + text)]
        texty.append((f"osoba {k}", text + (f" {hranice}" if roky and min(roky) >= 1870 or k < 8 else "")))
    texty += [(f"boční příbuzný {s.get('n')}", s.get("n", "") + " " + s.get("t", "")) for s in SIDE]
    for f in ("zajimavosti.md", "pribeh.md"):
        if os.path.exists(os.path.join(DATA, f)):
            texty += [(f, odst) for odst in open(os.path.join(DATA, f), encoding="utf-8").read().split("\n\n")]
    for kde, text in texty:
        if not recent(text):
            continue
        m = next((m for m in citlive.finditer(text) if not schvalene(text, m)), None)
        if m:
            warn.append(f"CITLIVÉ ({kde}): „…{text[max(0, m.start() - 40):m.end() + 40].strip()}…“ – jde na web; "
                        f"zeptej se uživatele, jestli to tam smí být (reference/soukromi.md); když ano, "
                        f"přidej úryvek textu s tím slovem do web.json „citlive_schvaleno“")

    if not os.path.exists(os.path.join(DATA, "pribeh.md")) and LINES:
        hlavni = min(LINES)
        n = max((k.bit_length() for k in P if k >= 8 and k >> (k.bit_length() - 4) == hlavni), default=0)
        if n >= 6:
            warn.append(f"rod {LINES[hlavni][0]} má už {n} generací – je čas napsat příběh rodu "
                        f"(data/pribeh.md, reference/pribehy.md); koncept nejdřív ukaž uživateli v chatu")

    # --- systematická aktualizace: co zastarává, když přibývají zápisy ------------------------------------------
    import unicodedata

    def slugify(text):
        t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    n_zap = len(zaz)
    # příběhy osob: kdo má vlastní zápisy, ale žádný příběh
    bez_pribehu = [f"{k} {p.get('n')}" for k, p in sorted(P.items()) if p.get("st") == "doc" and len(p.get("r", [])) >= 2 and not p.get("pribeh")]
    if bez_pribehu:
        warn.append(f"AKTUALIZACE – {len(bez_pribehu)} osob má 2+ vlastní zápisy, ale žádný 'pribeh' (začni nejbližšími generacemi): "
                    f"{', '.join(bez_pribehu[:6])}" + (" …" if len(bez_pribehu) > 6 else "") + " – viz AGENTS.md „Příběh“, návrhy v PRIBEHY_NAVRH.md")
    # příběhy rodů: rod s 3+ doloženými generacemi bez data/pribehy/<slug>.md
    hlavni_rod = (cfg.get("pribeh") or {}).get("rod", 8) if os.path.exists(os.path.join(DATA, "pribeh.md")) else None
    for lk, (nazev, _popis) in sorted(LINES.items()):
        gens = {k.bit_length() - 1 for k, p in P.items() if k >= 8 and p.get("st") == "doc" and k >> (k.bit_length() - 4) == lk}
        soubor = os.path.join(DATA, "pribehy", slugify(nazev) + ".md")
        if lk == hlavni_rod:
            continue   # hlavní rod má data/pribeh.md
        if len(gens) >= 3 and not os.path.exists(soubor):
            warn.append(f"AKTUALIZACE – rod {nazev} má {len(gens)} doložené generace, ale chybí příběh rodu data/pribehy/{slugify(nazev)}.md")
    # razítka: texty a úvod webu nesou počet zápisů, při kterém byly naposledy aktualizované
    def razitko_md(f):
        path = os.path.join(DATA, f)
        if not os.path.exists(path):
            return None
        m = re.search(r"<!--\s*aktualizováno při (\d+) zápisech\s*-->", open(path, encoding="utf-8").read())
        return int(m.group(1)) if m else -1
    for f, limit in (("zajimavosti.md", 5), ("pribeh.md", 10)):
        r = razitko_md(f)
        if r is None:
            continue
        if r < 0:
            warn.append(f"AKTUALIZACE – {f} nemá razítko: po úpravě přidej řádek <!-- aktualizováno při {n_zap} zápisech --> (kontrola pak hlídá zastarání)")
        elif n_zap - r >= limit:
            warn.append(f"AKTUALIZACE – {f} naposledy aktualizován při {r} zápisech, teď je jich {n_zap}: projdi nové zápisy, doplň text a posuň razítko")
    r = cfg.get("aktualizovano_pri_zapisech")
    if r is None:
        warn.append(f"AKTUALIZACE – web.json nemá \"aktualizovano_pri_zapisech\": po úpravě úvodu a karet zajímavostí nastav {n_zap}")
    elif n_zap - int(r) >= 10:
        warn.append(f"AKTUALIZACE – úvod webu (web.json: uvod, zajimavosti_na_uvodu) naposledy při {r} zápisech, teď {n_zap}: přepiš a posuň číslo")
    # roky života (y) nesedí s fakty – MyHeritage a GEDCOM podle nich párují
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import roky
        zmeny = [x for x in roky.navrhy() if x[2] != x[3]]
        if zmeny:
            warn.append(f"AKTUALIZACE – {len(zmeny)} osob má roky (y) neodpovídající faktům, např. {zmeny[0][1]} „{zmeny[0][2]}“ → „{zmeny[0][3]}“: python3 -I tools/roky.py (--zapis)")
    except Exception as e:  # noqa: BLE001
        warn.append(f"roky.py selhal: {e}")
    # noční fronta pramenů: nezpracované výsledky
    fronta = os.path.join(ROOT, "pracovni", "prameny", "fronta.json")
    if os.path.exists(fronta):
        try:
            fr = json.load(open(fronta, encoding="utf-8"))
            hot = sum(1 for x in fr if x.get("stav") == "hotovo")
            if hot:
                warn.append(f"AKTUALIZACE – {hot} hotových výsledků noční fronty čeká na zpracování: python3 -I tools/prameny.py fronta vysledky, pak fronta vycisti")
        except Exception:  # noqa: BLE001
            pass
    # web: data na webu starší než data projektu
    site = os.path.join(ROOT, "web", "src", "data", "site.json")
    nejnovejsi = max(os.path.getmtime(os.path.join(DATA, f)) for f in os.listdir(DATA) if os.path.isfile(os.path.join(DATA, f)))
    if os.path.exists(site) and os.path.getmtime(site) < nejnovejsi - 60:
        warn.append("AKTUALIZACE – web má starší data než data/: ve web/ spusť npm run data && npm run build")

    log = os.path.join(DATA, "research_log.md")
    rows = sum(1 for l in open(log, encoding="utf-8") if re.match(r"^\| \d+ \|", l)) if os.path.exists(log) else 0
    # „#N“ v textech musí být existující osoba (pomocník si čísla osob vymýšlel: „Jan Svatoň (#156 / #312)“)
    for f in ("research_log.md", "STAV.md", "zajimavosti.md", "pribeh.md"):
        cesta = os.path.join(DATA, f)
        if not os.path.exists(cesta):
            continue
        for i, radek in enumerate(open(cesta, encoding="utf-8"), 1):
            for c in sorted({int(x) for x in re.findall(r"#(\d+)\b", radek)} - set(P)):
                kde = re.match(r"^\| (\d+) \|", radek)
                err.append(f"{f} {'ř. deníku ' + kde.group(1) if kde else 'řádek ' + str(i)}: osoba #{c} v osoby.py neexistuje – číslo ověř grepem, nevymýšlej")
    zn_rx = re.compile(r"\{\{\s*(neověřeno|neovereno|rodina|strom|hypotéza|hypoteza)\b")
    texty_zn = "\n".join(l for l in open(os.path.join(DATA, "osoby.py"), encoding="utf-8") if not l.lstrip().startswith("#"))
    for f in ("zajimavosti.md", "pribeh.md"):
        if os.path.exists(os.path.join(DATA, f)):
            texty_zn += open(os.path.join(DATA, f), encoding="utf-8").read()
    zn = {}
    for m in zn_rx.finditer(texty_zn):
        k = {"neovereno": "neověřeno", "hypoteza": "hypotéza"}.get(m.group(1), m.group(1))
        zn[k] = zn.get(k, 0) + 1
    spatne = re.findall(r"\{\{\s*(?!neověřeno|neovereno|rodina|strom|hypotéza|hypoteza)(\w+)", texty_zn)
    for z in sorted(set(spatne)):
        err.append(f"neznámá značka {{{{{z}…}}}} – povolené: {{{{neověřeno: …}}}}, {{{{rodina: …}}}}, {{{{strom: …}}}}, {{{{hypotéza: …}}}}")
    # věrohodnost dat a věků (věk při sňatku, rodiče a děti, věk v zápisu × narození…) – samostatný nástroj
    try:
        import subprocess
        out = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "kontrola_dat.py"), "--souhrn"],
                             capture_output=True, text=True, timeout=120).stdout.strip()
        if out:
            warn.append(out)
    except Exception as e:  # noqa: BLE001
        warn.append(f"kontrola_dat.py se nepodařilo spustit: {e}")
    print(f"{len(P)} osob, {len(side_ids)} v širší rodině, {pribehy} příběhů, {len(zaz)} zápisů, {len(svazky)} svazků, {rows} řádků deníku; "
          f"označených neověřených tvrzení: {sum(zn.values())} " + (str(zn) if zn else ""))
    for e in err:
        print("CHYBA:", e)
    for w in warn:
        print("upozornění:", w)
    if not err and not warn:
        print("Vše v pořádku.")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
