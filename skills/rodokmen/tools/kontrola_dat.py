#!/usr/bin/env python3
"""Kontrola věrohodnosti dat a věků – hledá pravděpodobně špatně přečtená nebo zapsaná data.

Použití (z kořene projektu):
  kontrola_dat.py              vypíše CHYBY (nemožné) a PODEZŘELÉ údaje, u každého zápisy k novému přečtení
  kontrola_dat.py --vse        navíc INFO (dítě před svatbou, velký věkový rozdíl manželů, pozdní křest…)
  kontrola_dat.py --souhrn     jen jeden řádek s počty (volá ho kontrola.py)
  kontrola_dat.py --md soubor  zapíše výsledek i jako Markdown (např. pracovni/kontrola_dat.md)
  kontrola_dat.py --pokryti    kolik údajů jde vůbec porovnat (osoby s narozením, věky ze zápisů, páry rodič–dítě)

Ověřené výjimky: když zápis přečteš znovu ze snímku a údaj v matrice opravdu je (písař se spletl), přidej do
data/kontrola_dat_ok.txt řádek „začátek hlášení | proč je to v pořádku“ – např.
  #24 Jan Holubář: věk při úmrtí 3. 3. 1908 | sn. 102 přečten znovu 29. 10. 2026, v zápisu opravdu 49 let
Hlášení začínající tímto textem se pak už nevypisuje (jen se sečte).

Co hlídá (vše z data/osoby.py, data/zaznamy.json a data/prepisy.json):
  - neplatná data (31. 2., měsíc 13) ve faktech i v datech zápisů,
  - pořadí událostí: narození ≤ křest ≤ sňatek ≤ úmrtí ≤ pohřeb; křest do 7 dní po narození a pohřeb 1–5 dní po úmrtí
    (v 18.–19. století se křtilo do 3 dnů a pohřbívalo za 2–3 dny – posun dne o pár čísel tak bývá vidět),
  - „žil(a) v únoru 1879“ nebo „† před 1887“ proti datu úmrtí, druhý sňatek za života prvního manžela,
  - sourozence (stejná matka) narozené méně než 9 měsíců po sobě,
  - rodiče ve vlastním zápisu osoby (křest, sňatek): „zemřelého Josefa“, „† Františka“ × „žijící Marie“, „oba rodiče žijí /
    nežili“, „otec zemřel, matka žije“ proti datům úmrtí rodičů,
  - věk při sňatku (muž pod 18 nebo nad 75, žena pod 15 nebo nad 60) a délku života nad 100 let,
  - věk uvedený ve faktu („78 let při úmrtí“) nebo v zápisu („ve věku 64 let“, „(31 let)“) proti věku spočtenému
    z data narození, a věky uvedené v různých zápisech proti sobě (různé roky narození),
  - rodiče a děti: věk otce a matky při narození dítěte, dítě narozené po smrti matky nebo dlouho po smrti otce,
    dítě narozené dřív než rodič, dítě před sňatkem rodičů,
  - manžele: sňatek po smrti jednoho z nich, velký věkový rozdíl,
  - zápis vlastní osoby (klíč n_/o_/z_ + rok + jméno) proti faktu osoby: datum zápisu ≠ datum narození / sňatku / úmrtí,
  - rok úmrtí v „y“ proti faktu úmrtí.
Údaje se značkou {{strom}}, {{rodina}}, {{neověřeno}} se kontrolují také, hlášení u nich je označené „(neověřený údaj)“.
Hlášení není rozsudek: znamená „přečti ten zápis znovu, zvětšený“. Opravuj jen podle snímku.
"""
import datetime, json, os, re, sys, unicodedata
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("RODOKMEN_DATA") or os.path.join(ROOT, "data")   # jiná složka dat jen pro testy

DATUM = r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})"
ZNACKA = re.compile(r"\{\{\s*(strom|rodina|neověřeno|neovereno|hypotéza|hypoteza)\s*:?\s*|\s*\}\}")


def jload(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def ascii_(text):
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", ascii_(re.sub(r"\s*\(.*?\)", "", text or ""))).strip("_")


class D:
    """Datum s přesností: přesné (den, měsíc, rok), jen rok, „kol.“ (přibližný rok) nebo horní mez („před …“)."""

    def __init__(self, y, m=None, d=None, kol=False, pred=False, text=""):
        self.y, self.m, self.d, self.kol, self.pred, self.text = y, m, d, kol, pred, text

    @property
    def presne(self):
        return self.d is not None and not self.kol and not self.pred

    def ord(self):   # přibližné číslo dne (pro rozdíly); neznámý měsíc/den = střed roku
        return self.y * 365.25 + ((self.m or 7) - 1) * 30.44 + (self.d or 1)

    def tol(self):   # nejistota v letech
        return 0 if self.presne else (3 if self.kol else 1)

    def __str__(self):
        if self.d:
            return f"{self.d}. {self.m}. {self.y}"
        return ("kol. " if self.kol else "před " if self.pred else "") + str(self.y)


def let(a, b):
    """Celé roky mezi daty a ≤ b (u nepřesných dat přibližně)."""
    if a.presne and b.presne:
        return b.y - a.y - ((b.m, b.d) < (a.m, a.d))
    return int((b.ord() - a.ord()) // 365.25)


def datum(text, kol_ok=True):
    """První datum v textu: „12. 3. 1850“, „kol. 1784“, „před 1925“, „1849“."""
    m = re.search(DATUM, text)
    if m:
        d, mo, y = map(int, m.groups())
        pred = bool(re.search(r"před\s*$", text[:m.start()]))
        return D(y, mo, d, pred=pred, text=m.group(0))
    m = re.search(r"(kol\.|asi|před|po)?\s*(?:[a-záčďéěíňóřšťúůýž]+\s+)?(?:\d{1,2}/)?(\d{4})", text)
    if m:
        w = m.group(1) or ""
        return D(int(m.group(2)), kol=w in ("kol.", "asi") or not kol_ok, pred=w == "před", text=m.group(0))
    return None


def platne(d, mo, y):
    try:
        datetime.date(y, mo, d)
        return True
    except ValueError:
        return False


def main():
    args = sys.argv[1:]
    vse, souhrn = "--vse" in args, "--souhrn" in args
    md = args[args.index("--md") + 1] if "--md" in args else None
    ns = {}
    exec(open(os.path.join(DATA, "osoby.py"), encoding="utf-8").read(), ns)
    P, SIDE = ns.get("P", {}), ns.get("SIDE", [])
    zaz = {z.get("klic"): z for z in jload("zaznamy.json", [])}
    prep = jload("prepisy.json", {})
    hlaseni = []   # (úroveň, klíč osoby, text, zápisy k přečtení)

    def hlas(uroven, kdo, text, zapisy=()):
        hlaseni.append((uroven, kdo, text, [z for z in zapisy if z]))

    # --- osoby: předci podle Kekulého čísla + strukturovaní příbuzní ---------------------------------------------
    osoby = {}
    for k, p in P.items():
        osoby[k] = dict(p, _k=k, _otec=2 * k if 2 * k in P else None, _matka=2 * k + 1 if 2 * k + 1 in P else None,
                        _sex="M" if k % 2 == 0 else "F" if k > 1 else p.get("sex"))
    for s in SIDE:
        if s.get("id"):
            osoby[s["id"]] = dict(s, _k=s["id"], _otec=s.get("otec"), _matka=s.get("matka"), _sex=s.get("sex"))

    partneri = {k: set() for k in osoby}   # kdo je s kým sezdán podle struktury dat (Kekulé pár, „partner“ u příbuzných)
    for k in P:
        if isinstance(k, int) and k >= 2 and (k ^ 1) in P:
            partneri[k].add(k ^ 1)
    for s in SIDE:
        pa = s.get("partner")
        for x in (pa if isinstance(pa, list) else [pa] if pa is not None else []):
            if s.get("id") in osoby and x in osoby:
                partneri[s["id"]].add(x)
                partneri[x].add(s["id"])

    def jmeno(k):
        p = osoby[k]
        return f"#{k} {p.get('n')}" if isinstance(k, int) else f"{p.get('n')} ({k})"

    # --- události z faktů ---------------------------------------------------------------------------------------
    for k, p in osoby.items():
        ev = p["_ev"] = {"nar": None, "krest": None, "umrti": None, "umrti_pred": None, "pohreb": None, "snatky": [], "veky": []}
        p["_neover"] = set()
        for f0 in p.get("f", []):
            neover = bool(ZNACKA.search(f0)) and "hypot" not in f0
            f = ZNACKA.sub("", f0).strip()
            for m in re.finditer(DATUM, f):
                d, mo, y = map(int, m.groups())
                if not platne(d, mo, y):
                    hlas("CHYBA", k, f"neplatné datum „{m.group(0)}“ ve faktu „{f0}“", p.get("r", []))
            if f.startswith("*"):
                ev["nar"] = ev["nar"] or datum(f[1:])
                if neover:
                    p["_neover"].add("nar")
            elif f.startswith("křest"):
                ev["krest"] = datum(f)
            elif f.startswith("†"):
                d = datum(f[1:])
                if d and d.pred:
                    ev["umrti_pred"] = d
                elif d:
                    ev["umrti"] = d
                    if neover:
                        p["_neover"].add("umrti")
            elif f.startswith("×"):
                t = re.sub(r"^×\s*\d\.\s+(?=\d{1,2}\.\s*\d{1,2}\.\s*\d{4})", "", f)
                t = re.sub(r"^×\s*", "", t)
                d = datum(t) if re.match(r"(kol\.\s*)?(\d{1,2}\.\s*\d{1,2}\.\s*)?\d{4}", t) else None
                ev["snatky"].append({"d": d, "kdo": t, "neover": neover})
            m = re.search(r"\bžil[a]?\s+(?:ještě\s+)?(?:v\s+)?(?:(\w+)\s+)?(\d{4})", f)
            if m:
                mes = ("ledn únor břez dub květn červn červenc srpn září říjn listopad prosin").split()
                mi = next((i + 1 for i, x in enumerate(mes) if m.group(1) and ascii_(m.group(1)).startswith(ascii_(x)[:4])), None)
                ev.setdefault("zil", []).append((D(int(m.group(2)), mi, 28 if mi else None), f0))
            m = re.search(r"pohřben[a]?\s+" + DATUM, f)
            if m:
                ev["pohreb"] = D(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            # věk uvedený ve faktu: „78 let při úmrtí 1849“, „věk 23 při sňatku 1822“
            for m in re.finditer(r"(?:věk\s+)?(\d{1,3})(?:\s*(?:let|roky|rok))?(?:\s+\d+\s*měs\w*)?(?:,\s*možná\s+\d+)?\s+při\s+(úmrtí|sňatku)(?:\s+(\d{4}))?", f):
                ev["veky"].append({"vek": int(m.group(1)), "udalost": m.group(2), "rok": int(m.group(3)) if m.group(3) else None,
                                   "zdroj": "fakt", "text": f0})
        if not ev["nar"]:   # rok narození z „y“, když chybí fakt
            m = re.match(r"\s*(kol\.|asi)?\s*(\d{4})", p.get("y", "") or "")
            if m:
                ev["nar"] = D(int(m.group(2)), kol=True, text="y")
        m = re.search(r"[–-]\s*(\d{4})\s*$", p.get("y", "") or "")
        if m and ev["umrti"] and abs(int(m.group(1)) - ev["umrti"].y) > 0:
            hlas("PODEZŘELÉ", k, f"rok úmrtí v „y“ ({p.get('y')}) ≠ fakt úmrtí ({ev['umrti']})", p.get("r", []))

    # --- věky uvedené v zápisech (shrnutí + překlad) ------------------------------------------------------------
    MES = "ledna února března dubna května června července srpna září října listopadu prosince".split()

    def tvary(d):
        if not (d and d.d and d.m and 1 <= d.m <= 12):   # nemožné datum (např. „1. 24. 1826“) hlásí kontrola jinde
            return set()
        return {f"{d.d}. {d.m}. {d.y}", f"{d.d}/{d.m} {d.y}", f"{d.d}.{d.m}.{d.y}", f"{d.d}. {MES[d.m - 1]} {d.y}"}

    def kmeny(p):
        n = re.sub(r"\s*\(.*?\)", "", p.get("n", "")).replace("P. ", "").split()
        return {ascii_(w)[:4] for w in n if len(w) > 2}

    def jmena(p):
        """(křestní kmen, {kmeny příjmení}) – příjmení rodné i po svatbě („provdaná Saláková, později Mašková“)."""
        n = re.sub(r"\s*\(.*?\)", "", p.get("n", "")).replace("P. ", "").split()
        if not n:
            return None, set()
        prij = {ascii_(n[-1])[:4]}
        for f in p.get("f", []):
            m = re.match(r"provdaná\s+(.*)", ZNACKA.sub("", f))
            if m:
                prij |= {ascii_(w)[:4] for w in re.findall(r"[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]\w+", m.group(1))}
        return ascii_(n[0])[:4], prij

    def sedi_jmeno(k, text):
        kr, prij = jmena(osoby[k])
        a = ascii_(text)
        return bool(kr) and a.find(kr) >= 0 and any(x in a for x in prij)

    def je_manzel(k, q, snatek):
        """Sňatek osoby q („× … Josef Novák“) je sňatek s osobou k – jméno sedí a q nemá jiného známého partnera téhož jména."""
        if not sedi_jmeno(k, snatek["kdo"]):
            return False
        if k in partneri.get(q, ()):
            return True
        return not any(sedi_jmeno(x, snatek["kdo"]) for x in partneri.get(q, ()))

    VEK = re.compile(r"(?:ve\s+věku\s+|věk\s+)?(\d{1,3})\s+(?:let|roky|rok)\b(?!\s*\d)")

    zap_osoby = {}
    for k, p in osoby.items():
        for r in p.get("r", []):
            zap_osoby.setdefault(r, []).append(k)
    for r, kdo in zap_osoby.items():
        z = zaz.get(r)
        if not z or z.get("druh") not in ("O", "Z"):
            continue
        text = (z.get("shrnuti", "") + " \n " + prep.get(r, {}).get("cs", ""))
        ta = ascii_(text)
        kandidati = []
        for k in kdo:
            ev = osoby[k]["_ev"]
            if z["druh"] == "Z" and ev["umrti"] and any(t in text for t in tvary(ev["umrti"])):
                kandidati.append((k, "úmrtí", ev["umrti"]))
            if z["druh"] == "O":
                for s in ev["snatky"]:
                    if s["d"] and any(t in text for t in tvary(s["d"])):
                        kandidati.append((k, "sňatku", s["d"]))
        if not kandidati:
            continue
        nalez = []   # (osoba, věk, pozice)
        if z["druh"] == "Z":
            # úmrtní zápis: věk patří tomu, jehož datum úmrtí je v textu nejblíž před ním (do dalšího data)
            data_pos = sorted((m.start(), m.end()) for m in re.finditer(DATUM + "|" + r"\d{1,2}\.\s*(?:" + "|".join(MES) + r")\s*\d{4}", text))
            for k, ud, d in kandidati:
                for tv in tvary(d):
                    for mm in re.finditer(re.escape(tv), text):
                        konec = next((s for s, e in data_pos if s > mm.end()), len(text))
                        v = VEK.search(text, mm.end(), konec)
                        if v and not re.search(r"měsíc|dn[íy]", text[v.end():v.end() + 3]):
                            nalez.append((k, int(v.group(1)), v.start()))
        else:
            # oddací zápis: věk do 80 znaků za celým jménem (křestní + příjmení) a bez jiné osoby / role mezi nimi
            for k, ud, d in kandidati:
                kr, prij = jmena(osoby[k])
                if not kr:
                    continue
                for mm in re.finditer(r"\b" + re.escape(kr) + r"\w*\s+(?:\w+\s+){0,2}?(" + "|".join(map(re.escape, prij)) + r")\w*", ta):
                    v = VEK.search(text, mm.end(), mm.end() + 80)
                    if not v:
                        continue
                    mezi = ta[mm.end():v.start()]
                    if re.search(r"zenich|nevest|svedk|syn |dcer|otec|matk|[a-z]+ [A-Z]", mezi) or re.search(r"[(,]\s*\w+ \w+ \(", text[mm.end():v.start()]):
                        continue
                    nalez.append((k, int(v.group(1)), v.start()))
        videno = set()
        for k, vek, pos in nalez:
            ud, d = next((u, dd) for kk, u, dd in kandidati if kk == k)
            if vek > 110 or (k, vek) in videno or re.search(r"(pod|nad|do|od|než)\s*$", text[max(0, pos - 5):pos]):
                continue
            videno.add((k, vek))
            osoby[k]["_ev"]["veky"].append({"vek": vek, "udalost": ud, "rok": d.y, "d": d, "zdroj": r,
                                            "text": text[max(0, pos - 60):pos + 12].replace("\n", " ")})

    # --- kontroly jedné osoby -----------------------------------------------------------------------------------
    for k, p in osoby.items():
        ev, r = p["_ev"], p.get("r", [])
        nar, umr = ev["nar"], ev["umrti"]
        pozn = " (neověřený údaj)" if p["_neover"] else ""
        if nar and umr:
            v = let(nar, umr)
            if v < 0:
                hlas("CHYBA", k, f"úmrtí {umr} před narozením {nar}{pozn}", r)
            elif v > 100:
                hlas("PODEZŘELÉ", k, f"dožil(a) se {v} let ({nar} – {umr}){pozn}", r)
        if nar and ev["krest"] and nar.presne and ev["krest"].presne:
            dn = ev["krest"].ord() - nar.ord()
            if dn < 0:
                hlas("CHYBA", k, f"křest {ev['krest']} před narozením {nar}", r)
            elif dn > 7:
                hlas("PODEZŘELÉ" if nar.y < 1920 else "INFO", k, f"křest {ev['krest']} až {int(dn)} dní po narození {nar} (obvykle 0–3 dny)", r)
        if umr and ev["pohreb"] and umr.presne:
            dn = ev["pohreb"].ord() - umr.ord()
            if dn < 0:
                hlas("CHYBA", k, f"pohřeb {ev['pohreb']} před úmrtím {umr}", r)
            elif dn < 1 or dn > 5:
                hlas("PODEZŘELÉ", k, f"pohřeb {ev['pohreb']} {int(dn)} dní po úmrtí {umr} (obvykle 2–3 dny)", r)
        for zd, txt in ev.get("zil", []):
            if umr and zd.ord() > umr.ord() + 31:
                hlas("CHYBA", k, f"podle údaje „{txt}“ žil(a) ještě {zd.y}, ale úmrtí je {umr}", r)
        if umr and ev["umrti_pred"] and umr.ord() > ev["umrti_pred"].ord():
            hlas("CHYBA", k, f"úmrtí {umr}, ale jiný fakt říká „† {ev['umrti_pred']}“", r)
        for s in ev["snatky"]:
            d = s["d"]
            if not d:
                continue
            if nar:
                v = let(nar, d)
                lim = (18, 75) if p["_sex"] == "M" else (15, 60)
                if v < 12:
                    hlas("CHYBA", k, f"sňatek {d} ve věku {v} let (narození {nar}) – „{s['kdo']}“", r)
                elif v + nar.tol() < lim[0] or v - nar.tol() > lim[1]:
                    hlas("PODEZŘELÉ", k, f"sňatek {d} ve věku {v} let (narození {nar}) – „{s['kdo']}“", r)
            if umr and d.ord() > umr.ord() + 1:
                hlas("CHYBA", k, f"sňatek {d} po vlastním úmrtí {umr}{pozn}", r)
        # uvedené věky proti narození a proti sobě
        odhady = []
        for v in ev["veky"]:
            d = v.get("d")
            if not d:
                if v["udalost"] == "úmrtí" and umr and (v["rok"] in (None, umr.y)):
                    d = umr
                elif v["udalost"] == "sňatku":
                    d = next((s["d"] for s in ev["snatky"] if s["d"] and (v["rok"] in (None, s["d"].y))), None)
                if not d and v["rok"]:
                    d = D(v["rok"])
            if not d:
                continue
            odhady.append((d.y - v["vek"], v, d))
            if nar and nar.text != "y" and not (v["zdroj"] == "fakt" and nar.kol):
                spoct = let(nar, d)
                rozdil = abs(spoct - v["vek"])
                if rozdil > 1 + nar.tol() + d.tol():
                    kde = "ve faktu" if v["zdroj"] == "fakt" else f"v zápisu {v['zdroj']}"
                    hlas("PODEZŘELÉ", k, f"věk při {v['udalost']} {d}: {kde} {v['vek']} let, z narození {nar} vychází {spoct} "
                                         f"(rozdíl {rozdil}) – „{v['text'].strip()}“",
                         [v["zdroj"]] if v["zdroj"] != "fakt" else r)
        if len(odhady) >= 2:
            roky = [o[0] for o in odhady]
            if max(roky) - min(roky) > 3:
                popis = "; ".join(f"{o[1]['vek']} let při {o[1]['udalost']} {o[2]} → * kol. {o[0]}"
                                  + ("" if o[1]["zdroj"] == "fakt" else f" ({o[1]['zdroj']})") for o in sorted(odhady, key=lambda o: o[2].ord()))
                hlas("PODEZŘELÉ", k, f"uvedené věky si odporují: {popis}", r)

    # --- rodiče a děti --------------------------------------------------------------------------------------------
    for k, p in osoby.items():
        nar = p["_ev"]["nar"]
        if not nar:
            continue
        for role, rk in (("otec", p["_otec"]), ("matka", p["_matka"])):
            if rk is None or rk not in osoby:
                continue
            rp = osoby[rk]
            rnar, rumr = rp["_ev"]["nar"], rp["_ev"]["umrti"]
            zap = list(dict.fromkeys(p.get("r", [])[:2] + rp.get("r", [])[:2]))
            if rnar:
                v = let(rnar, nar)
                lim = (16, 70) if role == "otec" else (14, 50)
                if v < 0:
                    hlas("CHYBA", k, f"{role} {jmeno(rk)} se narodil(a) {rnar}, až po dítěti ({nar})", zap)
                elif v + rnar.tol() + nar.tol() < lim[0] or v - rnar.tol() - nar.tol() > lim[1]:
                    hlas("PODEZŘELÉ", k, f"{role} {jmeno(rk)} měl(a) při narození dítěte {v} let ({rnar} → {nar})", zap)
            if rumr and rumr.presne and nar.presne:
                dn = nar.ord() - rumr.ord()
                if (role == "matka" and dn > 1) or (role == "otec" and dn > 300):
                    hlas("CHYBA", k, f"narozen(a) {nar}, ale {role} {jmeno(rk)} zemřel(a) už {rumr}", zap)
        # sňatek rodičů
        o, m = p["_otec"], p["_matka"]
        if o in osoby and m in osoby:
            for s in osoby[o]["_ev"]["snatky"]:
                if s["d"] and s["d"].presne and nar.presne and kmeny(osoby[m]) & {ascii_(w)[:4] for w in s["kdo"].split()}:
                    dn = s["d"].ord() - nar.ord()
                    if dn > 0:
                        hlas("PODEZŘELÉ" if dn > 400 else "INFO", k,
                             f"narozen(a) {nar}, {int(dn // 30)} měsíců před sňatkem rodičů {s['d']} (nemanželské dítě, nebo špatný rok?)",
                             list(dict.fromkeys(p.get("r", [])[:1] + osoby[o].get("r", [])[:3])))

    # --- rodiče v zápisu: „zemřelého Josefa…“ / „žijící Marie…“ / „oba rodiče žijí“ × data úmrtí rodičů -------------
    MRTVY = r"(?:†|\+|zemrel\w*|zesnul\w*|nebozt\w*|nezijici\w*)"
    ZIVY = r"(?:zijici\w*|na zivu)"
    for k, p in osoby.items():
        ev = p["_ev"]
        for r in p.get("r", []):
            z = zaz.get(r)
            if not z or z.get("druh") not in ("N", "O"):
                continue
            # událost osoby v tomto zápisu: vlastní křest, nebo sňatek s datem zápisu
            zd = datum(str(z.get("datum", "")))
            if not zd or not zd.presne:
                continue
            if z["druh"] == "N":
                if not (ev["nar"] and ev["nar"].presne and r.endswith(slug(p.get("n"))) and abs(ev["nar"].ord() - zd.ord()) < 5):
                    continue
            elif not any(s["d"] and s["d"].presne and abs(s["d"].ord() - zd.ord()) < 2 for s in ev["snatky"]):
                continue
            text = ascii_(prep.get(r, {}).get("cs", "") + " \n " + z.get("shrnuti", ""))
            rodice = [(role, rk) for role, rk in (("otec", p["_otec"]), ("matka", p["_matka"])) if rk in osoby]
            for role, rk in rodice:
                kr, prij = jmena(osoby[rk])
                if not kr:
                    continue
                vzor_jm = kr + r"\w*\s+(?:\w+\s+){0,2}?(?:" + "|".join(map(re.escape, prij)) + ")"
                umr_r = osoby[rk]["_ev"]["umrti"] or osoby[rk]["_ev"]["umrti_pred"]
                zil = [zd2 for zd2, _ in osoby[rk]["_ev"].get("zil", [])]
                for mm in re.finditer(MRTVY + r"\s+(?:\w+\s+){0,1}?" + vzor_jm, text):
                    if umr_r and not umr_r.pred and umr_r.ord() > zd.ord() + 31 + (0 if umr_r.presne else 365):
                        hlas("CHYBA", k, f"zápis {r} ({zd}) uvádí {role} jako zemřelého („{mm.group(0)}“), ale {jmeno(rk)} zemřel(a) až {umr_r}",
                             [r] + osoby[rk].get("r", [])[-1:])
                for mm in re.finditer(ZIVY + r"\s+(?:\w+\s+){0,1}?" + vzor_jm, text):
                    if umr_r and umr_r.ord() < zd.ord() - 31 - (0 if umr_r.presne else 365):
                        hlas("CHYBA", k, f"zápis {r} ({zd}) uvádí {role} jako žijící(ho) („{mm.group(0)}“), ale {jmeno(rk)} zemřel(a) už {umr_r}",
                             [r] + osoby[rk].get("r", [])[-1:])
            # obecné věty o obou rodičích – přiřadí se k osobě, jejíž celé jméno je v textu nejblíž před nimi
            kr, prij = jmena(p)
            if not kr or len(rodice) < 2:
                continue
            vety = []   # (kdo: oba/otec/matka, mrtví?, shoda)
            for mm in re.finditer(r"(?:oba\s+)?rodice\W+(?:\w+\W+){0,4}?(nezil\w*|nezij\w*|zemrel\w*|zil\w*|zij\w*|na zivu|na zive)", text):
                if not re.search(r"\b(otec|matka|jen|pouze)\b", mm.group(0)):
                    vety.append(("oba", mm.group(1).startswith(("nez", "zemr")), mm))
            for mm in re.finditer(r"\b(otec|matka)\s+(?:\w+\s+){0,2}?(nezil\w*|nezij\w*|zemrel\w*|zil\w*|zij\w*|na zivu|na zive)", text):
                vety.append((mm.group(1), mm.group(2).startswith(("nez", "zemr")), mm))
            for kdo_v, mrtvi, mm in vety:
                pred = text[max(0, mm.start() - 400):mm.start()]
                moje = [x.end() for x in re.finditer(kr + r"\w*\s+(?:\w+\s+){0,2}?(?:" + "|".join(map(re.escape, prij)) + ")", pred)]
                cizi = [x.end() for x in re.finditer(r"(zenich\w*|nevest\w*)", pred)]   # i „rodiče nevěsty“
                if not moje or (cizi and max(cizi) > max(moje)):
                    continue
                for role, rk in rodice:
                    if kdo_v not in ("oba", role):
                        continue
                    u = osoby[rk]["_ev"]["umrti"]
                    if not u:
                        continue
                    if mrtvi and u.ord() > zd.ord() + 31 + (0 if u.presne else 365):
                        hlas("CHYBA", k, f"zápis {r} ({zd}): „{mm.group(0)}“, ale {role} {jmeno(rk)} zemřel(a) až {u}", [r] + osoby[rk].get("r", [])[-1:])
                    if not mrtvi and u.ord() < zd.ord() - 31 - (0 if u.presne else 365):
                        hlas("CHYBA", k, f"zápis {r} ({zd}): „{mm.group(0)}“, ale {role} {jmeno(rk)} zemřel(a) už {u}", [r] + osoby[rk].get("r", [])[-1:])

    # --- sourozenci se stejnou matkou: méně než 9 měsíců od sebe ---------------------------------------------------
    deti = {}
    for k, p in osoby.items():
        if p["_matka"] in osoby and p["_ev"]["nar"] and p["_ev"]["nar"].presne:
            deti.setdefault(p["_matka"], []).append(k)
    for m_, ks in deti.items():
        ks.sort(key=lambda x: osoby[x]["_ev"]["nar"].ord())
        for a, b in zip(ks, ks[1:]):
            dn = osoby[b]["_ev"]["nar"].ord() - osoby[a]["_ev"]["nar"].ord()
            if 2 < dn < 270:
                hlas("PODEZŘELÉ", b, f"narozen(a) {osoby[b]['_ev']['nar']}, jen {int(dn)} dní po sourozenci {jmeno(a)} ({osoby[a]['_ev']['nar']}) – stejná matka {jmeno(m_)}",
                     list(dict.fromkeys(osoby[a].get("r", [])[:1] + osoby[b].get("r", [])[:1])))

    # --- manželé (podle jména ve sňatku) --------------------------------------------------------------------------
    podle_jmena = {}
    for k, p in osoby.items():
        podle_jmena.setdefault(slug(p.get("n")), []).append(k)
    for k, p in osoby.items():
        for s in p["_ev"]["snatky"]:
            d = s["d"]
            jm = re.split(r"\s*[,(]|\s+z\s+|\s+\(", re.sub(r"^(kol\.\s*)?(\d{1,2}\.\s*\d{1,2}\.\s*)?\d{4}\s*", "", s["kdo"]))[0]
            jm = re.sub(r"\b(Rudíkov|Vladislav|Benetice|Chlum|Brtnice|Tasov|Okřešice)\b\s*", "", jm).strip()
            for k2 in podle_jmena.get(slug(jm), []):
                if k2 == k:
                    continue
                if not any(je_manzel(k, k2, x) for x in osoby[k2]["_ev"]["snatky"]):   # vzájemnost, ne stejnojmenný
                    continue
                q = osoby[k2]["_ev"]
                if d and q["umrti"] and q["umrti"].presne and d.presne and d.ord() > q["umrti"].ord() + 1:
                    hlas("CHYBA", k, f"sňatek {d} s {jmeno(k2)}, který(á) zemřel(a) už {q['umrti']}", p.get("r", [])[:3])
                if p["_ev"]["nar"] and q["nar"] and str(k) < str(k2):
                    rozdil = abs(p["_ev"]["nar"].y - q["nar"].y)
                    if rozdil > 25:
                        hlas("INFO", k, f"věkový rozdíl manželů {rozdil} let ({p['_ev']['nar']} × {jmeno(k2)} {q['nar']})", p.get("r", [])[:3])

    # --- druhý sňatek za života prvního manžela (z textu „× 1. … († 1855)“ nebo z osoby manžela) -------------------
    for k, p in osoby.items():
        sn = [s for s in p["_ev"]["snatky"] if s["d"]]
        sn.sort(key=lambda s: s["d"].ord())
        for prev, nxt in zip(sn, sn[1:]):
            smrt = None
            m = re.search(r"†\s*([^)]*)", prev["kdo"])
            if m:
                smrt = datum(m.group(1))
            if smrt and not smrt.pred and nxt["d"].ord() < smrt.ord() - (0 if smrt.presne else 365):
                hlas("PODEZŘELÉ", k, f"další sňatek {nxt['d']} („{nxt['kdo']}“), ale předchozí manžel(ka) zemřel(a) až {smrt} („{prev['kdo']}“)",
                     p.get("r", [])[:4])
        # vdova/vdovec podle textu sňatku, ale manžel z dřívějšího sňatku žil déle (osoba v datech)
    for k, p in osoby.items():
        for s in p["_ev"]["snatky"]:
            if not s["d"]:
                continue
            for k2, q in osoby.items():
                if k2 == k or not q["_ev"]["umrti"]:
                    continue
                # k2 je dřívější manžel(ka) osoby k: k2 má sňatek s k dřív než s
                for s2 in q["_ev"]["snatky"]:
                    if (s2["d"] and s2["d"].ord() < s["d"].ord() - 30 and je_manzel(k, k2, s2)
                            and not sedi_jmeno(k2, s["kdo"])
                            and q["_ev"]["umrti"].ord() > s["d"].ord() + 1):
                        hlas("PODEZŘELÉ", k, f"sňatek {s['d']} („{s['kdo']}“), ale dřívější manžel(ka) {jmeno(k2)} (× {s2['d']}) žil(a) do {q['_ev']['umrti']}",
                             (p.get("r", [])[:2] + q.get("r", [])[:2]))

    # --- vlastní zápis osoby proti faktům ---------------------------------------------------------------------------
    for k, p in osoby.items():
        s = slug(p.get("n"))
        ev = p["_ev"]
        for r in p.get("r", []):
            z = zaz.get(r)
            if not z or not s or s not in r:
                continue
            zd = datum(str(z.get("datum", "")))
            if not zd or not zd.presne:
                continue
            rok_klice = re.match(r"[noz]_(\d{4})_", r)
            rok_klice = int(rok_klice.group(1)) if rok_klice else None
            if r.startswith("n_") and r.endswith(s) and ev["nar"] and ev["nar"].presne and rok_klice in (ev["nar"].y, ev["krest"] and ev["krest"].y):
                if (zd.d, zd.m, zd.y) != (ev["nar"].d, ev["nar"].m, ev["nar"].y) and not (ev["krest"] and (zd.d, zd.m, zd.y) == (ev["krest"].d, ev["krest"].m, ev["krest"].y)):
                    hlas("CHYBA", k, f"zápis {r} má datum {zd}, osoba má narození {ev['nar']}", [r])
            if r.startswith("z_") and r.endswith(s) and ev["umrti"] and ev["umrti"].presne and rok_klice == ev["umrti"].y:
                if (zd.d, zd.m, zd.y) != (ev["umrti"].d, ev["umrti"].m, ev["umrti"].y):
                    hlas("CHYBA", k, f"zápis {r} má datum {zd}, osoba má úmrtí {ev['umrti']}", [r])
            manzele = [x for x in ev["snatky"] if slug(re.split(r"\s*[,(]", re.sub(r"^(kol\.\s*)?(\d{1,2}\.\s*\d{1,2}\.\s*)?\d{4}\s*(\w+\s+(?=[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]\w+\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]))?", "", x["kdo"]))[0]) in r]
            if r.startswith("o_") and manzele:
                if not any(x["d"] and x["d"].presne and (x["d"].d, x["d"].m, x["d"].y) == (zd.d, zd.m, zd.y) for x in manzele):
                    hlas("PODEZŘELÉ", k, f"oddací zápis {r} má datum {zd}, mezi sňatky osoby takové datum není", [r])
    for r, z in zaz.items():
        for m in re.finditer(DATUM, str(z.get("datum", ""))):
            d, mo, y = map(int, m.groups())
            if not platne(d, mo, y):
                hlas("CHYBA", r, f"zápis {r}: neplatné datum „{z.get('datum')}“", [r])

    if "--pokryti" in args:
        nar_p = sum(1 for p in osoby.values() if p["_ev"]["nar"] and p["_ev"]["nar"].presne)
        nar_a = sum(1 for p in osoby.values() if p["_ev"]["nar"])
        veky_z = sum(1 for p in osoby.values() for v in p["_ev"]["veky"] if v["zdroj"] != "fakt")
        veky_f = sum(1 for p in osoby.values() for v in p["_ev"]["veky"] if v["zdroj"] == "fakt")
        s_vek = sum(1 for p in osoby.values() for s in p["_ev"]["snatky"] if s["d"] and p["_ev"]["nar"])
        u_vek = sum(1 for p in osoby.values() if p["_ev"]["umrti"] and p["_ev"]["nar"])
        rd = sum(1 for p in osoby.values() for rk in (p["_otec"], p["_matka"])
                 if p["_ev"]["nar"] and rk in osoby and osoby[rk]["_ev"]["nar"])
        oz = sum(1 for p in osoby.values() for r in p.get("r", []) if zaz.get(r, {}).get("druh") in ("O", "Z"))
        print(f"osob: {len(osoby)}, s narozením: {nar_a} (přesným {nar_p}); sňatků s věkem: {s_vek}; úmrtí s věkem: {u_vek}; "
              f"páry rodič–dítě s oběma narozeními: {rd}; věků ze zápisů: {veky_z} (z {oz} vazeb osoba–zápis O/Z), z faktů: {veky_f}")
        return
    # --- výstup ---------------------------------------------------------------------------------------------------
    poradi = {"CHYBA": 0, "PODEZŘELÉ": 1, "INFO": 2}
    ok_path = os.path.join(DATA, "kontrola_dat_ok.txt")
    ok = [l.split("|")[0].strip() for l in open(ok_path, encoding="utf-8")
          if l.strip() and not l.lstrip().startswith("#!")] if os.path.exists(ok_path) else []
    def cil_text(h):
        return f"{jmeno(h[1]) if h[1] in osoby else h[1]}: {h[2]}"
    potlaceno = [h for h in hlaseni if any(o and cil_text(h).startswith(o) for o in ok)]
    hlaseni = [h for h in hlaseni if h not in potlaceno and (vse or h[0] != "INFO")]
    hlaseni.sort(key=lambda h: (poradi[h[0]], str(h[1])))
    pocty = {u: sum(1 for h in hlaseni if h[0] == u) for u in poradi}
    if souhrn:
        if pocty["CHYBA"] or pocty["PODEZŘELÉ"]:
            print(f"kontrola_dat: {pocty['CHYBA']} nemožných a {pocty['PODEZŘELÉ']} podezřelých dat/věků – "
                  "spusť python3 -I tools/kontrola_dat.py a sporné zápisy přečti znovu zvětšené")
        return
    radky = []
    for u, kdo, text, zapisy in hlaseni:
        snimky = []
        for zk in zapisy[:4]:
            z = zaz.get(zk, {})
            snimky.append(f"{zk} (sn. {z.get('snimek')})" if z.get("snimek") else zk)
        cil = jmeno(kdo) if kdo in osoby else str(kdo)
        radky.append(f"{u}: {cil}: {text}" + (f"\n    přečíst znovu: {', '.join(snimky)}" if snimky else ""))
    print("\n".join(radky) if radky else "Žádné podezřelé údaje.")
    print(f"\nCelkem: {pocty['CHYBA']} CHYBA, {pocty['PODEZŘELÉ']} PODEZŘELÉ" + (f", {pocty['INFO']} INFO" if vse else " (INFO: --vse)")
          + (f"; {len(potlaceno)} již ověřených výjimek (data/kontrola_dat_ok.txt)" if potlaceno else ""))
    if md:
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("# Kontrola dat a věků\n\nKaždé hlášení = přečti uvedené zápisy znovu ze snímku (zvětšené). Opravuj jen podle snímku.\n\n")
            for line in radky:
                fh.write("- " + line.replace("\n    ", "\n  - ") + "\n")
    sys.exit(1 if pocty["CHYBA"] else 0)


if __name__ == "__main__":
    main()
