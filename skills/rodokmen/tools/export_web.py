#!/usr/bin/env python3
"""Export dat rodokmenu (data/*) do webu ve složce web/.

Čte data/osoby.py, data/zaznamy.json, data/svazky.json, data/prepisy.json, data/zvyrazneni.json,
data/mista.json, data/web.json, data/dokumenty.json a markdownové poznámky. Zapisuje
web/src/data/site.json, web/src/generated/*, web/public/{img,zdroje}, web/public/prihlaseni.html,
web/nginx.conf a web/netlify/edge-functions/brana.js.

Spouští se z web/ příkazem `npm run data` (nebo přímo `python3 -I tools/export_web.py`, na Windows `python -I -X utf8 …`).
`npm run data -- --verejny` (a vždy při nasazení, `--nasazeni`) je veřejný export: u žijících jen rok, ne přesné datum.
"""
import datetime, hashlib, html, json, os, re, shutil, subprocess, sys, unicodedata
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
DATA = os.environ.get("RODOKMEN_DATA") or os.path.join(ROOT, "data")   # jiná složka dat jen pro testy nástrojů
WEB = os.path.join(ROOT, "web")
VYREZY = os.path.join(ROOT, "vyrezy")      # výřezy zápisů a dokumentů (asi 1800 px) – zobrazují se na webu
ZDROJE = os.path.join(ROOT, "zdroje")      # tytéž výřezy v plném rozlišení (proklik)

LINE_COLORS = {8: "#EFB45F", 9: "#F09A78", 10: "#E58AA6", 11: "#B99AE0",
               12: "#86B8E8", 13: "#6FCBB9", 14: "#9CD17A", 15: "#D3D46A"}
STATUS = {"doc": "doloženo matrikou", "prob": "pravděpodobné", "fam": "údaj od rodiny",
          "mh": "jen z cizího rodokmenu", "unk": "neznámé"}
KINDS = {"N": "křest / narození", "O": "sňatek", "Z": "úmrtí", "I": "rejstřík", "S": "sčítání lidu", "J": "jiný pramen"}


def jload(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_people():
    ns = {}
    exec(open(os.path.join(DATA, "osoby.py"), encoding="utf-8").read(), ns)
    for name, default in (("P", {}), ("SIDE", []), ("LINES", {}), ("ISSUES", []), ("HYPOTEZY", []), ("SAME", {})):
        ns.setdefault(name, default)
    return ns


def record_rows():
    svazky = jload("svazky.json", {})
    rows = []
    for z in jload("zaznamy.json", []):
        sv = svazky.get(z.get("svazek", ""), {})
        key = z["klic"]
        rows.append(dict(
            key=key, kind=z.get("druh", "J"), date=z.get("datum", ""), title=z.get("nazev", key),
            summary=z.get("shrnuti", ""), scan=z.get("snimek", ""),
            archive=sv.get("archiv", ""), volume=sv.get("svazek", ""), vdesc=sv.get("popis", ""),
            portal=sv.get("portal", "archivu"), url=z.get("odkaz") or sv.get("url", ""),
            img=os.path.exists(os.path.join(VYREZY, key + ".jpg")),
            full=os.path.exists(os.path.join(ZDROJE, key + ".jpg")),
        ))
    return rows


def strip_comments(md):
    """Poznámky <!-- … --> v markdownu jsou pro Clauda, ne pro web."""
    return re.sub(r"<!--.*?-->\n?", "", md, flags=re.S)


def slugify(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def norm_answer(text):
    """Stejná normalizace jako v prihlaseni.html: bez diakritiky, malá písmena, jen a-z0-9."""
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]", "", t)


def years(y):
    y = (y or "").strip()
    ys = re.findall(r"\d{4}", y)
    if not ys:
        return ""
    approx = "≈" if re.match(r"^(asi|kol\.|cca|≈)", y) else ""   # odhad i výpočet z věku
    head, dash, tail = y.partition("–")
    if y.startswith(("?", "†")) or (dash and not re.search(r"\d{4}", head)) or re.match(r"po\b", y):
        # neznámý rok narození (i „18. stol. – před 1818“): ukázat jen úmrtí
        # („? – před 1743“ → „† před 1743“, „– po 1921“ → „žil 1921“)
        if re.search(r"\bpo\b", tail or y):
            return "žil " + ys[-1]
        return "† " + ("před " if "před" in y else "") + ys[-1]
    if y.startswith("*"):
        return "* " + ys[0]
    if len(ys) == 1:
        return approx + ys[0] + ("–?" if dash else "")   # „1818 – ?“ → „1818–?“ (jako ve vějíři)
    # horní mez úmrtí ukázat („1835–před 1921“), ne jen otazník
    second = ("před " if "před" in tail else "po " if re.search(r"\bpo\b", tail) else "") + \
        ("≈" if re.search(r"(asi|kol\.|cca|≈)", tail) else "") + ys[-1]
    return f"{approx}{ys[0]}–{second}"


def gen(k):
    return k.bit_length() - 1


def relation(k):
    g, male = gen(k), (k % 2 == 0)
    if g == 0:
        return "výchozí osoba rodokmenu"
    if g == 1:
        return "otec" if male else "matka"
    base = "dědeček" if male else "babička"
    if g <= 5:
        return "pra" * (g - 2) + base
    return f"{'předek' if male else 'předkyně'} v {g}. generaci ({'pra' * (g - 2)}{base})"


def sex_of(s):
    """Pohlaví příbuzného: 'sex', jinak podle jména (příjmení -ová/-á, křestní jméno na -a/-e)."""
    if s.get("sex") in ("M", "F"):
        return s["sex"]
    jm = re.sub(r"\(.*?\)", "", s.get("n", "")).replace("P. ", "").replace("roz. ", "").split()
    if not jm:
        return "M"
    if jm[-1].endswith(("ová", "ská", "cká", "ná", "ká")) or jm[0].endswith(("a", "e")) and jm[0] not in ("Jiří",):
        return "F"
    return "M"


def side_years(s):
    """Roky příbuzného z 'y', jinak ze závorky ve jméně „(1902–1950)“, „(* 1869)“."""
    if s.get("y"):
        return s["y"], re.sub(r"\s*\(.*?\)\s*", " ", s["n"]).strip()
    m = re.search(r"\(([^()]*\d{4}[^()]*)\)", s.get("n", ""))
    return (m.group(1).strip() if m else ""), re.sub(r"\s*\(.*?\)\s*", " ", s["n"]).strip()


def structured(s):
    return any(x in s for x in ("otec", "matka", "partner", "id"))


def manzel(fact):
    """Jméno ze sňatku: „× 2. 3. 5. 1887 Karel Dvořák († 1910) z Holic“ → „Karel Dvořák“ (jako v gedcom.py)."""
    t = bez_znacek(fact).lstrip("× ").strip()
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


ZIVOT = (("*", "Narození"), ("křest", "Křest"), ("×", "Sňatek"), ("provd", "Po svatbě"), ("†", "Úmrtí"), ("pohřb", "Pohřeb"))


def zivotni_udaje(facts, htmls):
    """Základní údaje pod jménem osoby s popisky (narození, křest, sňatky, úmrtí, pohřeb) – z faktů „*“, „křest“, „×“, „†“,
    „pohřben(a)“; ostatní fakta (povolání, rodiče, bydliště) zůstanou v seznamu pod příběhem."""
    life, other, videno = [], [], set()
    for f, h in zip(facts, htmls):
        label = next((lab for pre, lab in ZIVOT if f.startswith(pre)), None)
        if not label or "vyvráceno" in f:   # vyvrácené tvrzení (např. datum z rodinného rodokmenu) není životní údaj
            other.append(h)
            continue
        if label in videno and label != "Sňatek":   # druhé narození/úmrtí = jiný pramen (odhad z věku, rodinný rodokmen)
            label += " (jiný údaj)"
        videno.add(label)
        h = re.sub(r"^\s*(\*|×|†|křest|pohřben[ao]?|provdaná|provd\.)\s*", "", h)
        m = re.match(r"(\d)\.\s+(?=\d{1,2}\.\s*\d{1,2}\.\s*\d{4}|\d{4}|\D)", h) if label == "Sňatek" else None
        if m:
            label, h = f"{m.group(1)}. sňatek", h[m.end():]
        life.append(dict(label=label, html=h))
    return life, other


# --- značky neověřených tvrzení: {{neověřeno: text}} / {{rodina: …}} / {{strom: …}} / {{hypotéza: …}} nebo jen {{strom}} ------
ZNACKY = {"neověřeno": ("neověřeno", "Zatím neověřeno v pramenech – jen tvrzení"),
          "rodina": ("podle rodiny", "Z rodinné paměti nebo rodinných dokumentů, ne z matriky"),
          "strom": ("z cizího stromu", "Převzato z rodokmenu na internetu (MyHeritage, Geni…), neověřeno v matrice"),
          "hypotéza": ("hypotéza", "Náš odhad – čeká na doklad")}
ZN_RX = re.compile(r"\{\{\s*(neověřeno|neovereno|rodina|strom|hypotéza|hypoteza)\s*(?::\s*(.*?))?\s*\}\}", re.S)


def _zn_klic(k):
    return {"neovereno": "neověřeno", "hypoteza": "hypotéza"}.get(k, k)


def oznac(text, kde=None, sber=None):
    """{{značka: text}} → <span class="zn zn-…">text<sup>štítek</sup></span>; samotná {{značka}} → jen štítek.
    Když je dán seznam `sber`, přidá do něj každé tvrzení (druh, text, kde) – pro stránku „Co hledáme“ a kontrolu."""
    if not text:
        return text

    def sub(m):
        k = _zn_klic(m.group(1))
        stitek, titul = ZNACKY[k]
        obsah = (m.group(2) or "").strip()
        if sber is not None:
            # samotná značka {{strom}} označuje text před sebou (celý fakt, nebo poslední větu)
            pred = text[:m.start()].strip()
            veta = re.split(r"(?<=[.!?])\s+", pred)[-1] if pred else ""
            sber.append(dict(kind=k, label=stitek, text=re.sub(r"<[^>]+>|\*\*|\{\{.*?\}\}", "", obsah or veta).strip() or "(označený údaj)", where=kde))
        badge = f'<sup class="zn-badge" title="{titul}">{stitek}</sup>'
        return f'<span class="zn zn-{slugify(k)}">{obsah}{badge}</span>' if obsah else badge

    return ZN_RX.sub(sub, text)


def bez_znacek(text):
    """Pro místa, kde značky nemají co dělat (karty stromu, GEDCOM, regulární výrazy míst)."""
    return ZN_RX.sub(lambda m: (m.group(2) or "").strip(), text or "").strip()


# --- propojení jmen v textech s osobami (ikonka za jménem → stránka osoby) ------------------------------------
OLINK_SVG = ('<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><circle cx="8" cy="4" r="2.4" fill="currentColor"/>'
             '<path d="M3.5 14.5v-3a4.5 4.5 0 0 1 9 0v3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')


def _stem_krestni(word):
    r"""Kmen křestního jména pro skloňování: Josef→Josef\w{0,3} (Josefa, Josefem, Josefovi), Marie→Mari\w{1,2}
    (Marii, Marií), Anna→Ann\w{1,2} (Anny, Annou). Mariana se tak nechytí na Marii."""
    w = re.escape(word)
    if word[-1] in "aeyáéíý" and len(word) > 3:
        return re.escape(word[:-1]) + "\\w{1,2}"
    return w + "\\w{0,3}"


def _stem_prijmeni(word, zena):
    r"""Kmen příjmení: Nováková→Novákov\w{0,3}; Novák→Novák(?!ov)\w{0,3} (ne Nováková); Dvořák→Dvořák\w{0,3};
    Krejčí→Krejč\w{0,3}."""
    w = re.escape(word)
    if zena and word.endswith("ová"):
        return re.escape(word[:-3]) + "ov\\w{0,3}"
    if word.endswith(("ec", "ek", "el")) and len(word) > 3:
        return "(?:" + w + "|" + re.escape(word[:-2] + word[-1]) + "(?!ov)\\w{0,3})"
    if word[-1] in "aeyáéíý" and len(word) > 3:
        return re.escape(word[:-1]) + "\\w{0,3}"
    return w + ("" if zena else "(?!ov)") + "\\w{0,3}"


def propojovac(people):
    """Vrátí funkci text → text s ikonkou-odkazem za každým jménem osoby z rodokmenu.
    Jméno = křestní jméno + příjmení (i skloněné: „Jana Nováka“, „Marii Novákové“). Stejnojmenné osoby rozliší
    rok v závorce do 40 znaků za jménem („Jan Novák (* 1890)“) nebo titul „P.“; jinak odkaz nedá (raději nic než
    špatně). Rok u jména, který nesedí na žádnou osobu, odkaz zruší. Jméno ve <span class="nolink">…</span> se vynechá."""
    skupiny = {}
    for sl, p in people.items():
        casti = [c for c in re.sub(r"\(.*?\)", "", p["name"]).replace("roz. ", "").split() if c not in ("P.",)]
        if len(casti) < 2 or casti[-1][0].islower():
            continue
        skupiny.setdefault((casti[0], casti[-1], p["sex"]), []).append(p)
    vzory = []
    for (jm, pr, sex), lidi in skupiny.items():
        rx = re.compile(r"(?<![\w/-])(P\.\s+)?(" + _stem_krestni(jm) + r"\s+(?:[A-ZÁ-Ž]\w+\s+)?" + _stem_prijmeni(pr, sex == "F") + r")(?![\w-])")
        vzory.append((rx, lidi))

    def nahrad(text, krome=None):
        if not text:
            return text
        vlozene = []   # vložené odkazy schovat za zástupný znak, ať se do nich další jména nepropisují

        def sub_factory(lidi):
            def sub(m):
                cele = m.group(0)
                pred = text_akt[max(0, m.start() - 200):m.start()]
                za = text_akt[m.end():m.end() + 40]
                if za.startswith("](") or pred.endswith("[") or za.startswith("\x00"):
                    return cele                      # už je to odkaz
                i = pred.rfind('<span class="nolink">')
                if i >= 0 and "</span>" not in pred[i:]:
                    return cele                      # autor odkaz zakázal
                kand = [p for p in lidi if p["slug"] != krome]
                usek = za[:za.index(")") + 1] if ")" in za else za.split(".")[0]
                roky = re.findall(r"\b(1[6-9]\d\d|20\d\d)\b", usek)
                if roky:
                    kand = [p for p in kand if any(y in (p["y"] or "") for y in roky)]
                if len(kand) > 1 and m.group(1):
                    kand = [p for p in kand if p["name"].startswith("P.")] or kand
                if len(kand) > 1 and sum(p["direct"] for p in kand) == 1:
                    kand = [p for p in kand if p["direct"]]
                if len(kand) != 1:
                    return cele
                p = kand[0]
                vlozene.append(f'<a class="olink" href="/osoba/{p["slug"]}/" title="{html.escape(p["name"])} {p["years"]} – v rodokmenu">{OLINK_SVG}</a>')
                return f"{cele}\x00{len(vlozene) - 1}\x00"
            return sub

        def propoj_cast(cast):
            nonlocal text_akt
            text_akt = cast
            for rx, lidi in vzory:
                text_akt = rx.sub(sub_factory(lidi), text_akt)
            return text_akt

        text_akt = text
        text_akt = mimo_kod(text, propoj_cast)   # do schémat v ```…``` by se HTML odkazu vypsalo jako text
        return re.sub(r"\x00(\d+)\x00", lambda m: vlozene[int(m.group(1))], text_akt)
    return nahrad


KOD_RX = re.compile(r"(^```.*?^```[^\n]*$)", re.M | re.S)


def mimo_kod(text, fn):
    """Použije fn jen na části markdownu mimo bloky ```…```."""
    return "".join(c if i % 2 else fn(c) for i, c in enumerate(KOD_RX.split(text)))


def md_hvezdicky(text):
    """„**Jan Novák (* 1890)**“ – hvězdička za závorkou by v markdownu zavřela tučné písmo jako kurzíva."""
    return mimo_kod(text, lambda c: c.replace("(* ", "(\\* "))


def vlastni_zapis(p, rec):
    """Je zápis o této osobě (její křest, sňatek, úmrtí), nebo ji jen zmiňuje (křest dítěte – je tam jako otec)?
    Rozhoduje jméno osoby v názvu zápisu; žena i pod příjmením manžela. Sčítání a jiné prameny jsou vždy „o ní“."""
    if rec["kind"] not in ("N", "O", "Z"):
        return True
    casti = [c for c in re.sub(r"\(.*?\)|\?", "", p["name"]).replace("roz. ", "").split() if c != "P."]
    if len(casti) < 2:
        return True
    zena = p.get("sex") == "F"
    prijmeni = {casti[-1]}
    if zena:   # „Úmrtí Anny Novákové“ – rodné jméno v názvu chybí
        for f in p["facts"]:
            m = re.match(r"×[^A-ZÁ-Ž]*(?:[A-ZÁ-Ž]\w+ )+([A-ZÁ-Ž]\w+)", f)
            if m:
                s = m.group(1)
                prijmeni.add(s if s.endswith(("ová", "á", "í")) else (s[:-2] + s[-1] if s.endswith(("ec", "ek")) else s.rstrip("aeo")) + "ová")
    def norm(t):   # bez diakritiky, s = z (Rosalie × Rozálie), malá písmena
        t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
        return t.lower().replace("s", "z")
    slova = re.findall(r"\w+", norm(rec["title"]))
    k = norm(casti[0])[:4]
    if not any(w.startswith(k) for w in slova):
        return False
    return any(any(w.startswith(norm(x)[:max(3, len(x) - 2)]) for w in slova) for x in prijmeni)


def historie_a_otazky(people, slugs, issues):
    """K osobě: řádky deníku, které se jí týkají (#číslo, id, klíč jejího vlastního zápisu) = historie nálezů a oprav,
    a otázky z ISSUES, které ji zmiňují. Otázkám (stránka Co hledáme) naopak přidá odkazy na osoby."""
    def osoby_v(text):
        out = set()
        for m in re.finditer(r"#(\d+)\b", text):
            if int(m.group(1)) in slugs:
                out.add(slugs[int(m.group(1))])
        for k, sl in slugs.items():
            if isinstance(k, str) and re.search(r"(?<![\w])" + re.escape(k) + r"(?![\w])", text):
                out.add(sl)
        return out

    def md(t):   # tučné písmo z deníku, jinak holý text
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(t))

    zapisy_osob = {}
    for sl, p in people.items():
        for r in p.get("ownRecords", []):
            zapisy_osob.setdefault(r, set()).add(sl)
    for p in people.values():
        p["history"], p["questions"] = [], []
    denik = os.path.join(DATA, "research_log.md")
    radky = open(denik, encoding="utf-8").read().splitlines() if os.path.exists(denik) else []
    for r in radky:
        if not re.match(r"^\|\s*\d+\s*\|", r):
            continue
        b = [c.strip() for c in r.strip().strip("|").split(" | ")]
        if len(b) < 6:
            continue
        cislo, datum, zdroj, hledano, vysledek = b[0], b[1], b[2], b[4], b[5]
        komu = osoby_v(r) | {sl for klic, sls in zapisy_osob.items() if re.search(r"(?<![\w])" + re.escape(klic) + r"(?![\w])", r) for sl in sls}
        if not komu:
            continue
        druh = ("oprava" if re.search(r"oprav|chybn|vyvrác|omyl|mylně|nesouhlas", vysledek, re.I)
                else "nenalezeno" if re.search(r"nenalez|bez výsledku|negativní|nebyl[ao]? nalez", vysledek, re.I) else "nález")
        polozka = dict(n=int(cislo), date=datum, source=html.escape(zdroj), searched=md(hledano),
                       result=md(vysledek if len(vysledek) <= 700 else vysledek[:700].rsplit(" ", 1)[0] + " …"), kind=druh)
        for sl in komu:
            people[sl]["history"].append(polozka)
    for p in people.values():
        p["history"].sort(key=lambda h: h["n"])
    for i, it in enumerate(issues):
        title, text = (it, "") if isinstance(it, str) else it[:2]
        vyreseno = title.startswith("[Vyřešeno") or text.startswith("Vyřešeno")
        komu = osoby_v(title + " " + text)
        if not komu:   # otázka bez čísla osoby – aspoň celé jméno přímého předka v nadpisu
            komu = {sl for sl, p in people.items() if p.get("direct") and len(p["name"].split()) > 1 and p["name"] in title}
        komu = sorted(komu)
        for sl in komu:
            people[sl]["questions"].append(dict(title=re.sub(r"^\[Vyřešeno[^\]]*\]\s*", "", title), text=text, solved=vyreseno))
        info = dict(people=[dict(slug=sl, name=people[sl]["name"]) for sl in komu], solved=vyreseno)
        issues[i] = (title, text, info)
    for p in people.values():
        p["questions"].sort(key=lambda q: q["solved"])


def cisla(people, records):
    """„Rodokmen v číslech“ – mechanické, ověřitelné údaje z dat pro stránku Zajímavosti (nic se nedomýšlí)."""
    def yr(t):
        m = re.search(r"\b1[4-9]\d\d|20\d\d\b", t or "")
        return int(m.group(0)) if m else None

    def fdate(p, sym):
        for f in p["facts"]:
            if f.startswith(sym):
                m = re.search(r"(\d{1,2})\. (\d{1,2})\. (\d{4})", f)
                if m:
                    return int(m.group(3)) + (int(m.group(2)) - 1) / 12 + (int(m.group(1)) - 1) / 365
                y = yr(f)
                return y + 0.5 if y else None
        return None
    doc = [p for p in people.values() if p["st"] == "doc"]
    out = []
    nejst = min((p for p in people.values() if p["direct"] and yr(p["y"])), key=lambda p: yr(p["y"]), default=None)
    if nejst:
        out.append(dict(label="Nejstarší doložený předek", value=f"{nejst['name']} ({nejst['years']})", slug=nejst["slug"]))
    vek = [(fdate(p, "†") - fdate(p, "*"), p) for p in people.values() if fdate(p, "†") and fdate(p, "*")]
    vek = [(v, p) for v, p in vek if 0 < v < 110]
    if vek:
        v, p = max(vek, key=lambda x: x[0])
        out.append(dict(label="Nejdelší doložený život", value=f"{p['name']} – {int(v)} let", slug=p["slug"]))
        out.append(dict(label="Průměrný věk dožití (u koho známe narození i úmrtí)", value=f"{sum(v for v, _ in vek) / len(vek):.0f} let ({len(vek)} osob)"))
    sn = []
    for p in people.values():
        b = fdate(p, "*")
        for f in p["facts"]:
            if f.startswith("×") and b:
                m = re.search(r"(\d{1,2})\. (\d{1,2})\. (\d{4})", f)
                if m:
                    w = int(m.group(3)) + (int(m.group(2)) - 1) / 12 - b
                    if 12 < w < 80:
                        sn.append((w, p))
                    break
    if sn:
        zeny = [(w, p) for w, p in sn if p["sex"] == "F"]
        muzi = [(w, p) for w, p in sn if p["sex"] == "M"]
        if zeny:
            w, p = min(zeny, key=lambda x: x[0])
            out.append(dict(label="Nejmladší nevěsta", value=f"{p['name']} – {int(w)} let", slug=p["slug"]))
            out.append(dict(label="Průměrný věk nevěst při první svatbě", value=f"{sum(w for w, _ in zeny) / len(zeny):.0f} let ({len(zeny)} nevěst)"))
        if muzi:
            out.append(dict(label="Průměrný věk ženichů při první svatbě", value=f"{sum(w for w, _ in muzi) / len(muzi):.0f} let ({len(muzi)} ženichů)"))
    vdovy = [p for p in people.values() if any(re.search(r"× 2\.|vdov", f) for f in p["facts"])]
    if vdovy:
        out.append(dict(label="Kolik předků se ženilo či vdávalo podruhé", value=f"{len(vdovy)}"))
    jmena = {}
    for p in people.values():
        j = p["name"].replace("P. ", "").split()[0]
        jmena[j] = jmena.get(j, 0) + 1
    top = sorted(jmena.items(), key=lambda x: -x[1])[:5]
    if top:
        out.append(dict(label="Nejčastější křestní jména", value=", ".join(f"{j} ({n}×)" for j, n in top)))
    remesla = {}
    rx = re.compile(r"\b(kovář|tesař|obuvník|zedník|krejčí|mlynář|hostinsk|povozník|kněz|kněž|farář|kapucín|učitel|pacholek|čeledín|služk|dělník|voják|dělostřel|záložník|rychtář|starost|hajn|šenkýř|řezník|pekař|truhlář|kolář|švec|tkadl|sklenář|zahradník)\w*", re.I)
    lemma = {"hostinsk": "hostinský", "služk": "služka", "dělostřel": "dělostřelec", "starost": "starosta", "kněž": "kněz", "hajn": "hajný", "tkadl": "tkadlec"}
    for p in people.values():
        for f in p["facts"]:
            if f[:1] in "*×†":
                continue
            for m in rx.finditer(f):
                k = m.group(1).lower()
                remesla.setdefault(lemma.get(k, k), set()).add(p["slug"])
    if remesla:
        out.append(dict(label="Řemesla zmíněná u předků (počet osob)", value=", ".join(f"{k} ({len(v)})" for k, v in sorted(remesla.items(), key=lambda x: -len(x[1]))[:10])))
    domy = {}
    for p in people.values():
        for f in p["facts"]:
            if f.startswith("*"):
                m = re.search(r"([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][\w'-]*(?: [A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][\w'-]*)?) čp\. (\d+)", f)
                if m:
                    domy.setdefault(f"{m.group(1)} čp. {m.group(2)}", []).append(p)
    nej = sorted(domy.items(), key=lambda x: -len(x[1]))[:3]
    for d, lidi in nej:
        if len(lidi) >= 3:
            roky = [yr(p["y"]) for p in lidi if yr(p["y"])]
            out.append(dict(label=f"Narozeni v domě {d}", value=f"{len(lidi)} lidí z rodokmenu" + (f" ({min(roky)}–{max(roky)})" if roky else "")))
    out.append(dict(label="Doloženo matrikou", value=f"{len(doc)} z {len(people)} osob; {len(records)} přečtených zápisů"))
    return out


def placeholder(p):
    return p["n"].startswith(("otec neuveden", "matka neuvedena")) or p["n"] in ("", "?")


def magick_bin():   # ImageMagick 7 (magick), jinak 6 (convert) – ten ale ne na Windows, tam je convert.exe jiný program
    return shutil.which("magick") or (os.name != "nt" and shutil.which("convert")) or None


def size(path):
    w, h = subprocess.run([magick_bin(), path + "[0]", "-format", "%w %h", "info:"],
                          capture_output=True, text=True, check=True).stdout.split()
    return int(w), int(h)


def draw_boxes(src, dst, boxes, small):
    """Kopie výřezu v plném rozlišení s nakreslenými rámečky (pokud má stejný poměr stran jako webový výřez,
    na kterém se rámečky měřily). Vrací False, pak se kopíruje bez rámečků."""
    if not os.path.exists(small) or not magick_bin():
        return False
    (W, H), (w, h) = size(src), size(small)
    if abs(W / H - w / h) > 0.015 * (w / h):
        return False
    sw = max(4, round(W / 450))
    cmd = [magick_bin(), src, "-fill", "none", "-stroke", "#d7302a", "-strokewidth", str(sw)]
    for x0, y0, x1, y1 in boxes:
        cmd += ["-draw", f"rectangle {x0 * W:.0f},{y0 * H:.0f},{x1 * W:.0f},{y1 * H:.0f}"]
    subprocess.run(cmd + ["-quality", "90", dst], check=True)
    return True


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# --- veřejný export: u žijících jen rok, ne přesné datum (narození ani jiné) ---------------------------------------
ZIJE_LET = 110   # narozen před méně než tolika lety a bez údaje o úmrtí → bereme jako žijícího (stejně v gedcom.py)
MESICE = ("ledna", "února", "března", "dubna", "května", "června", "července", "srpna", "září", "října", "listopadu", "prosince")
GED_MESICE = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
DATUM_RX = re.compile(r"\b(\d{1,2})\.\s*(?:(\d{1,2})\.|(" + "|".join(MESICE) + r"))\s*(\d{4})\b")


def zije(y, facts, *texty):
    """Žijící: u osoby stojí „žijící“, nebo se narodila před méně než ZIJE_LET lety a nemá úmrtí (rozsah let, †)."""
    if any("žijící" in (t or "").lower() for t in [*facts, *texty]):
        return True
    y = y or ""
    if "†" in y or re.search(r"–\D*\d{4}", y) or any(f.lstrip().startswith("†") for f in facts):
        return False
    m = re.search(r"\d{4}", y) or re.search(r"\d{4}", " ".join(f for f in facts if f.lstrip().startswith("*")))
    return bool(m) and int(m.group(0)) > datetime.date.today().year - ZIJE_LET


def zijici(P, SIDE):
    """Jména žijících a přesná data (den, měsíc, rok), která se u nich v datech píšou."""
    osoby = [(p["n"], p.get("y"), p.get("f", []), [p.get("note"), p.get("pribeh")]) for p in P.values() if not placeholder(p)]
    osoby += [(side_years(s)[1], side_years(s)[0], s.get("f", []), [s.get("t"), s.get("note"), s.get("pribeh")]) for s in SIDE]
    jmena, data = [], set()
    for jmeno, y, facts, texty in osoby:
        if not zije(y, facts, *texty):
            continue
        jmena.append(jmeno)
        for m in DATUM_RX.finditer(" ".join([*facts, *(t or "" for t in texty)])):
            mes = int(m.group(2)) if m.group(2) else MESICE.index(m.group(3)) + 1
            if 1 <= int(m.group(1)) <= 31 and 1 <= mes <= 12:
                data.add((int(m.group(1)), mes, m.group(4)))
    return jmena, data


def skryj_data(paths, data):
    """Přesná data žijících ve vygenerovaných souborech nahradí rokem – kdekoli se objeví (údaje, deník, příběhy, GEDCOM):
    14. 5. 1990, 14.5.1990, 14. května 1990, 14 MAY 1990, 1990-05-14 → 1990."""
    vzory = []
    for d, m, y in sorted(data):
        vzory += [rf"0?{d}\.\s*0?{m}\.\s*{y}", rf"0?{d}\.\s*{MESICE[m - 1]}\s*{y}", rf"0?{d} {GED_MESICE[m - 1]} {y}", rf"{y}-{m:02d}-{d:02d}"]
    if not vzory:
        return
    rx = re.compile(r"\b(?:" + "|".join(vzory) + r")\b")
    for path in paths:
        text = open(path, encoding="utf-8").read()
        novy = rx.sub(lambda m: re.search(r"\d{4}", m.group(0)).group(0), text)
        if novy != text:
            write(path, novy)


def login_files(cfg):
    """Přihlašovací brána: otázka na webu, na serveru (nginx i Netlify) jen otisk odpovědi (SHA-256).
    Stejný otisk spočítá přihlašovací stránka a uloží ho do cookie – samotná odpověď se nikam neukládá."""
    login = cfg.get("prihlaseni") or {}
    answer = norm_answer(login.get("odpoved", ""))
    tpl = open(os.path.join(WEB, "prihlaseni.sablona.html"), encoding="utf-8").read()
    if "rodokmen:" not in tpl:   # stará šablona (do 0.4.0) ukládá do cookie odpověď – s novou bránou by se nikdo nepřihlásil
        sys.exit("CHYBA: web/ má starou šablonu přihlášení. Aktualizujte projekt: python3 -I <skill>/tools/novy_projekt.py <složka projektu>")
    contact = cfg.get("kontakt") or {}
    hint = ""
    if contact.get("email"):
        hint = (f'Neznáte odpověď? Napište {html.escape(contact.get("jmeno", ""))} na '
                f'<a href="mailto:{html.escape(contact["email"])}">{html.escape(contact["email"])}</a>.')
    page = (tpl.replace("{{NAZEV}}", html.escape(cfg.get("nazev", "Rodokmen")))
               .replace("{{UVOD}}", html.escape(login.get("uvod", "Tenhle web je jen pro rodinu a příbuzné.")))
               .replace("{{OTAZKA}}", html.escape(login.get("otazka", "Odpověď na rodinnou otázku")))
               .replace("{{NAPOVEDA}}", hint))
    write(os.path.join(WEB, "public", "prihlaseni.html"), page)

    edge = os.path.join(WEB, "netlify", "edge-functions", "brana.js")
    if answer:
        digest = hashlib.sha256(("rodokmen:" + answer).encode()).hexdigest()
        nginx_map = f'  "{digest}" 1;'
        write(edge, open(os.path.join(WEB, "netlify", "brana.sablona.js"), encoding="utf-8").read().replace("{{HASH}}", digest))
    else:   # bez přihlášení – web je otevřený
        nginx_map = "  default 1;"
        if os.path.exists(edge):
            os.remove(edge)
    nginx = open(os.path.join(WEB, "nginx.sablona.conf"), encoding="utf-8").read().replace("{{ODPOVED}}", nginx_map)
    write(os.path.join(WEB, "nginx.conf"), nginx)
    return bool(answer)


def main():
    ns = load_people()
    P, LINES, SIDE, ISSUES = ns["P"], ns["LINES"], ns["SIDE"], ns["ISSUES"]
    if 1 not in P:
        sys.exit("V data/osoby.py chybí výchozí osoba (číslo 1).")
    SAME = ns["SAME"]                       # alias Kekulé → kanonické Kekulé (předek v rodokmenu vícekrát)
    cfg = jload("web.json", {})
    login = cfg.get("prihlaseni") or {}
    verejny = "--verejny" in sys.argv or "--nasazeni" in sys.argv
    if "--nasazeni" in sys.argv and not norm_answer(login.get("odpoved", "")) and not login.get("otevreny"):
        sys.exit("CHYBA: v data/web.json není odpověď na přihlašovací otázku – web by byl otevřený komukoli.\n"
                 "Nastavte prihlaseni.odpoved, nebo (jen když to opravdu chcete) prihlaseni.otevreny: true.")
    docs_cfg = jload("dokumenty.json", [])
    recs = {r["key"]: r for r in record_rows()}

    slugs, used = {}, set()
    for k in sorted(P):
        p = P[k]
        if placeholder(p) or k in SAME:
            continue
        yv = (p.get("y") or "").strip()
        ys = [] if yv.startswith(("?", "†")) else re.findall(r"\d{4}", yv)   # rok úmrtí do adresy nedávat
        s = slugify(p["n"] + (" " + ys[0] if ys else ""))
        if s in used or not s:
            s = f"{s}-{k}"
        used.add(s)
        slugs[k] = s
    for a, c in SAME.items():
        slugs[a] = slugs[c]
    aliases_of = {}
    for a, c in SAME.items():
        aliases_of.setdefault(c, []).append(a)

    def line_of(k):
        g = gen(k)
        return k >> (g - 3) if g >= 3 else None

    people = {}
    for k, p in sorted(P.items()):
        if k not in slugs or k in SAME:
            continue
        path, c = [], k
        while c >= 1:
            path.append(slugs.get(c))
            c //= 2
        people[slugs[k]] = dict(
            k=k, slug=slugs[k], name=p["n"], y=p.get("y", ""), years=years(p.get("y")), st=p.get("st", "unk"),
            status=STATUS.get(p.get("st"), ""), gen=gen(k), sex="M" if k == 1 and p.get("sex", "M") == "M" or k > 1 and k % 2 == 0 else "F",
            rel=relation(k), line=line_of(k), facts=p.get("f", []), note=p.get("note", ""), story=p.get("pribeh", ""), direct=True,
            records=[r for r in p.get("r", []) if r in recs],
            father=slugs.get(2 * k), mother=slugs.get(2 * k + 1),
            fatherUnknown=(2 * k in P and placeholder(P[2 * k])), motherUnknown=(2 * k + 1 in P and placeholder(P[2 * k + 1])),
            child=slugs.get(k // 2) if k > 1 else None, spouse=slugs.get(k ^ 1) if k > 1 else None,
            family=None, ownFamily=None, path=path,
            side=[dict(name=s["n"], text=s.get("t", ""), records=[r for r in s.get("r", []) if r in recs], slug=None, sid=s.get("id") or (slugify(s["n"]) if structured(s) else None))
                  for s in SIDE if s.get("k") == k],
            docs=[dict(img=d["img"], caption=d["popis"]) for d in docs_cfg if k in d.get("osoby", [])],
            children=[slugs[c] for c in [k // 2] + [a // 2 for a in aliases_of.get(k, [])] if k > 1 and c in slugs],
            also=[dict(k=a, rel=relation(a), line=line_of(a), child=slugs.get(a // 2)) for a in aliases_of.get(k, [])],
        )
        if aliases_of.get(k):
            for a in aliases_of[k]:
                people[slugs[k]]["records"] = list(dict.fromkeys(people[slugs[k]]["records"] + [r for r in P[a].get("r", []) if r in recs]))
            people[slugs[k]]["facts"] = [f for f in people[slugs[k]]["facts"] if not f.startswith("TÁŽ OSOBA")]

    def snatky(a, b):
        """Sňatek páru: údaje „×“ jednoho, které jmenují druhého (vdova má i sňatky s jinými); přednost mají údaje otce."""
        for x, y in ((a, b), (b, a)):
            hit = [f for f in (people[x]["facts"] if x else []) if f.startswith("×") and y and jmeno_sedi(manzel(f), people[y]["name"])]
            if hit:
                return hit
        return []

    families = {}
    for k in sorted(P):
        f, m = 2 * k, 2 * k + 1
        if k not in slugs or k in SAME or (f not in slugs and m not in slugs):
            continue
        fs, ms = slugs.get(f), slugs.get(m)
        fid = "-a-".join(x for x in (fs, ms) if x) if fs and ms else (fs or ms) + "-rodina"
        marriage = snatky(fs, ms)
        frec = P.get(f, {}).get("r", []) + P.get(m, {}).get("r", [])
        child_rec = [r for r in P[k].get("r", []) if r in recs and recs[r]["kind"] == "N"]
        rlist = [r for r in dict.fromkeys(frec) if r in recs and recs[r]["kind"] == "O"] + child_rec
        if fid in families:   # stejný pár potkán dvakrát (předek v rodokmenu vícekrát) – jedna rodina, víc dětí
            fam = families[fid]
            fam["children"].append(slugs[k])
            fam["records"] = list(dict.fromkeys(fam["records"] + rlist))
            fam["side"] += people[slugs[k]]["side"]
        else:
            families[fid] = dict(id=fid, father=fs, mother=ms, fatherUnknown=f in P and placeholder(P[f]),
                                 child=slugs[k], children=[slugs[k]], marriage=marriage, records=rlist,
                                 line=line_of(f) if f in P else line_of(m), gen=gen(f), side=list(people[slugs[k]]["side"]))
        people[slugs[k]]["family"] = fid
        for x in (fs, ms):
            if x:
                people[x]["ownFamily"] = fid

    # --- širší rodina: strukturované položky SIDE (otec/matka/partner) jsou plnohodnotné osoby se stránkou a místem ve stromu
    rel_by_id = {}
    for s in SIDE:
        if not structured(s):
            continue
        sid = s.get("id") or slugify(s["n"])
        if sid in rel_by_id:
            print(f"POZOR: boční příbuzný '{s['n']}' má stejné id '{sid}' jako jiný – doplň 'id'")
            continue
        rel_by_id[sid] = s

    def ref_slug(x):
        """odkaz na rodiče/partnera: číslo předka (Kekulé) nebo id příbuzného → slug"""
        if isinstance(x, int):
            return slugs.get(SAME.get(x, x))
        if isinstance(x, str):
            return rel_slugs.get(x)
        return None

    rel_slugs = {}
    for sid, s in rel_by_id.items():
        yv, nm = side_years(s)
        ys = [] if yv.startswith(("?", "†")) else re.findall(r"\d{4}", yv)
        sl = slugify(nm + (" " + ys[0] if ys else ""))
        if sl in used or not sl:
            sl = f"{sl}-{slugify(sid)}" if sl else slugify(sid)
        used.add(sl)
        rel_slugs[sid] = sl

    def gen_of_rel(sid, seen=()):
        s = rel_by_id[sid]
        for key in ("otec", "matka"):
            x = s.get(key)
            if isinstance(x, int) and SAME.get(x, x) in P:
                return gen(SAME.get(x, x)) - 1
            if isinstance(x, str) and x in rel_by_id and x not in seen:
                g = gen_of_rel(x, seen + (sid,))
                if g is not None:
                    return g - 1
        for x in (s.get("partner") if isinstance(s.get("partner"), list) else [s.get("partner")]):
            if isinstance(x, int) and SAME.get(x, x) in P:
                return gen(SAME.get(x, x))
            if isinstance(x, str) and x in rel_by_id and x not in seen:
                return gen_of_rel(x, seen + (sid,))
        return gen(s["k"]) if isinstance(s.get("k"), int) and s["k"] in P else 0

    def rel_text(sid):
        """„bratr · Jan Novák (prapradědeček)“ / „vnuk · Václav Novák (praprapradědeček)“"""
        s = rel_by_id[sid]
        male = sex_of(s) == "M"
        o, m = s.get("otec"), s.get("matka")
        if isinstance(o, int) and isinstance(m, int) and o % 2 == 0 and m == o + 1 and (o // 2) in P:
            k = o // 2
            return f"{'bratr' if male else 'sestra'} · {P[k]['n']} ({relation(k)})"
        d, cur, seen = 0, sid, set()
        while cur in rel_by_id and cur not in seen:
            seen.add(cur)
            s2 = rel_by_id[cur]
            o2, m2 = s2.get("otec"), s2.get("matka")   # dítě z druhého sňatku: přednost má rodič, který je předek
            par = next((x for x in (o2, m2) if isinstance(x, int) and SAME.get(x, x) in P), o2 if o2 is not None else m2)
            d += 1
            if isinstance(par, int) and SAME.get(par, par) in P:
                k = SAME.get(par, par)
                slovo = {1: "syn" if male else "dcera", 2: "vnuk" if male else "vnučka", 3: "pravnuk" if male else "pravnučka"}.get(
                    d, f"{'potomek' if male else 'potomkyně'} ({d}. generace)")
                return f"{slovo} · {P[k]['n']} ({relation(k)})"
            if isinstance(par, str):
                cur = par
                continue
            break
        pa = s.get("partner")
        pa = pa[0] if isinstance(pa, list) and pa else pa
        if isinstance(pa, int) and SAME.get(pa, pa) in P:
            k = SAME.get(pa, pa)
            return f"{'manžel' if male else 'manželka'} · {P[k]['n']} ({relation(k)})"
        return "širší rodina" + (f" · {P[s['k']]['n']}" if isinstance(s.get("k"), int) and s["k"] in P else "")

    for sid, s in rel_by_id.items():
        yv, nm = side_years(s)
        sl = rel_slugs[sid]
        partners = s.get("partner") if isinstance(s.get("partner"), list) else ([s.get("partner")] if s.get("partner") else [])
        g = gen_of_rel(sid)
        anc = s.get("k") if isinstance(s.get("k"), int) and s["k"] in P else None
        people[sl] = dict(
            k=None, slug=sl, name=nm, y=yv, years=years(yv), st=s.get("st", "fam"), status=STATUS.get(s.get("st", "fam"), ""),
            gen=g, sex=sex_of(s), rel=rel_text(sid), line=line_of(anc) if anc and anc >= 8 else None,
            facts=s.get("f", []) or ([s["t"]] if s.get("t") and not s.get("f") else []), note=s.get("note", ""), story=s.get("pribeh", ""),
            direct=False, records=[r for r in s.get("r", []) if r in recs],
            father=ref_slug(s.get("otec")), mother=ref_slug(s.get("matka")), fatherUnknown=False, motherUnknown=False,
            child=None, spouse=None, partners=[x for x in (ref_slug(x) for x in partners) if x], family=None, ownFamily=None,
            path=[], side=[], docs=[dict(img=d["img"], caption=d["popis"]) for d in docs_cfg if sid in d.get("osoby", [])],
            children=[], also=[], sid=sid, anchor=slugs.get(anc) if anc else None,
        )
    for sl, p in list(people.items()):
        if p["direct"]:
            continue
        for ps in (p["father"], p["mother"]):
            if ps and sl not in people[ps]["children"]:
                people[ps]["children"].append(sl)
        for ps in p["partners"]:
            if ps and sl not in people[ps].setdefault("partners", []):
                people[ps].setdefault("partners", []).append(sl)
        # drobečková cesta: nahoru přes rodiče až k předkovi
        chain, cur, seen = [], sl, set()
        while cur and cur not in seen and not people[cur]["direct"]:
            seen.add(cur); chain.append(cur)
            cur = people[cur]["father"] or people[cur]["mother"]
        p["path"] = chain + (people[cur]["path"] if cur else [])   # od osoby nahoru k výchozí osobě (jako u předků)
    for p in people.values():
        p.setdefault("partners", [])
        if p["direct"] and p["spouse"] and p["spouse"] not in p["partners"]:
            p["partners"].insert(0, p["spouse"])
        sn = [f for f in p["facts"] if f.startswith("×")]   # partneři v pořadí sňatků („× 1.“, „× 2.“)
        p["partners"].sort(key=lambda x: next((i for i, f in enumerate(sn) if jmeno_sedi(manzel(f), people[x]["name"])), len(sn)))
    # seřadit děti podle roku narození
    def birth_year(sl):
        q = people[sl]
        m = re.search(r"\d{4}", " ".join(f for f in q["facts"] if f.startswith("*")) or q["y"] or "")
        return int(m.group(0)) if m else 9999
    for p in people.values():
        p["children"] = sorted(dict.fromkeys(p["children"]), key=birth_year)
    # odkazy z textových karet na stránky strukturovaných příbuzných
    for p in people.values():
        for e in p["side"]:
            if e.get("sid") in rel_slugs:
                e["slug"] = rel_slugs[e["sid"]]
            e.pop("sid", None)
    # rodiny: příbuzní jako další děti rodin předků; páry příbuzných jako nové rodiny
    for sl, p in people.items():
        if p["direct"]:
            continue
        fs, ms = p["father"], p["mother"]
        if not (fs or ms):
            continue
        fid = next((f for f in families.values() if f["father"] == fs and f["mother"] == ms), None)
        if fid is None:
            fid_key = "-a-".join(x for x in (fs, ms) if x) if fs and ms else (fs or ms) + "-rodina"
            if fid_key not in families:
                families[fid_key] = dict(id=fid_key, father=fs, mother=ms, fatherUnknown=False, child=sl, children=[],
                                         marriage=snatky(fs, ms), records=[], line=people[fs or ms]["line"], gen=people[fs or ms]["gen"], side=[])
            fid = families[fid_key]
        if sl not in fid["children"]:
            fid["children"].append(sl)
        fid["records"] = list(dict.fromkeys(fid["records"] + [r for r in p["records"] if recs[r]["kind"] == "N"]))
        p["family"] = fid["id"]
        for x in (fs, ms):
            if x and not people[x].get("ownFamily"):
                people[x]["ownFamily"] = fid["id"]
    for f in families.values():
        f["children"] = sorted(dict.fromkeys(f["children"]), key=birth_year)

    # strom pro stránku rodokmenu (přímá linie i širší rodina)
    def place_of(p):
        for f in p["facts"]:
            if f.startswith("*") and re.search(r"\d{4}\s+(.+)", f):
                return re.sub(r"^\*\s*(kol\.|asi)?\s*[\d. ]*\d{4}\s*", "", f).strip()
        return ""
    tree = [dict(slug=sl, name=p["name"], years=p["years"], sex=p["sex"], k=p["k"], direct=p["direct"], st=p["st"], line=p["line"],
                 gen=p["gen"], rel=p["rel"], father=p["father"], mother=p["mother"], partners=p["partners"], children=p["children"],
                 place=place_of(p), story=bool(p["story"])) for sl, p in people.items()]

    propoj_jmena = propojovac(people)
    klic_rx = re.compile(r"(?<![\w/\"'])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?![\w/\"'])")

    def propoj(text, krome=None):
        """Jména → odkazy na osoby; klíče zápisů v textu („(s_1857_hodov_cp50)“) → odkaz na zápis s čitelným názvem."""
        def zapis(m):
            r = recs.get(m.group(1))
            return f'<a href="/zdroj/{r["key"]}/">{html.escape(r["title"])}</a>' if r else m.group(0)
        return mimo_kod(propoj_jmena(text, krome=krome), lambda cast: klic_rx.sub(zapis, cast)) if text else text
    claims = []
    for sl, p in people.items():
        kde = dict(type="osoba", slug=sl, name=p["name"])
        p["note"], p["story"] = (re.sub(r"\s*\([^()]*\b(?:dokumenty|pracovni|zdroje)/[^()]*\)", "", t or "") for t in (p["note"], p["story"]))   # cesty k souborům čtenáři nic neřeknou (jako bez_cest v gedcom.py)
        raw = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", bez_znacek(p["story"]))
        raw = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", raw)).strip()
        p["storyExcerpt"] = (raw[:220].rsplit(" ", 1)[0] + "…") if len(raw) > 220 else raw
        p["story"] = oznac(propoj(p["story"], krome=sl), kde, claims)
        p["factsHtml"] = [oznac(f, kde, claims) for f in p["facts"]]
        p["noteHtml"] = oznac(propoj(p["note"], krome=sl), kde, claims)
        p["facts"] = [bez_znacek(f) for f in p["facts"]]     # holý text pro logiku (mapa, strom, sňatky)
        p["life"], p["otherHtml"] = zivotni_udaje(p["facts"], p["factsHtml"])

    for p in people.values():
        p["ownRecords"] = [r for r in p["records"] if r in recs and vlastni_zapis(p, recs[r])]
    historie_a_otazky(people, {**slugs, **{sid: sl for sid, sl in rel_slugs.items() if sl in people}}, ISSUES)
    refs = {}
    for s, p in people.items():
        for r in p["records"] + [r for e in p["side"] for r in e["records"]]:
            refs.setdefault(r, []).append(s)
    hl = jload("zvyrazneni.json", {})
    prep = jload("prepisy.json", {})
    records = []
    for key, r in recs.items():
        r = dict(r)
        r["boxes"] = hl.get(key, {}).get("boxes", [])
        tr = prep.get(key, {})
        r["orig"], r["cs"] = tr.get("orig", ""), tr.get("cs") or tr.get("cz", "")
        r["kindName"] = KINDS.get(r["kind"], r["kind"])
        r["people"] = list(dict.fromkeys(refs.get(key, [])))
        records.append(r)

    lines = {}
    for k, (name, desc) in sorted(LINES.items()):
        if k not in LINE_COLORS:
            continue
        members = [(p["k"], p) for p in people.values() if p["line"] == k and p["direct"]]
        members += [(a["k"], p) for p in people.values() for a in p["also"] if a["line"] == k]
        members.sort(key=lambda x: x[0])
        lines[slugify(name)] = dict(k=k, slug=slugify(name), name=name, desc=desc, color=LINE_COLORS[k],
                                    root=slugs.get(k), people=[p["slug"] for _, p in members],
                                    gens={p["slug"]: gen(kk) for kk, p in members})
    lines = {s: l for s, l in lines.items() if l["root"]}
    for p in people.values():
        p["lineSlug"] = next((l["slug"] for l in lines.values() if l["k"] == p["line"]), None)

    places = []
    for name, e in jload("mista.json", {}).items():
        if "lat" not in e:
            continue
        rx = re.compile(e.get("re") or re.escape(name))
        hits = [p for p in people.values() if rx.search(" ".join(p["facts"]))]
        byline = {}
        for p in sorted(hits, key=lambda p: p["k"] or 10 ** 9):
            byline.setdefault(p["line"] or 0, []).append(p["slug"])
        if e.get("hypoteza"):
            byline = {e.get("rod", 0): []}
        if not byline:
            continue
        yrs = [int(y) for p in hits for y in re.findall(r"\b1[4-9]\d\d\b", p["y"] or "")]
        places.append(dict(name=name, lat=e["lat"], lon=e["lon"], lines=[dict(k=k, people=v) for k, v in sorted(byline.items())],
                           years=[min(yrs), max(yrs)] if yrs else None, hypothesis=bool(e.get("hypoteza"))))

    known = [p for p in people.values() if p["direct"] and p["k"] > 1]
    stats = dict(ancestors=len(known), documented=sum(p["st"] == "doc" for p in known), records=len(records),
                 generations=max(p["gen"] for p in people.values() if p["direct"]) + 1,
                 relatives=sum(1 for p in people.values() if not p["direct"]),
                 stories=sum(1 for p in people.values() if p["story"]), claims=0)
    hypotheses = [dict(line=h.get("rod"), title=h.get("nadpis", "Hypotéza"), text=h.get("text", ""),
                       items=[dict(name=a, text=b) for a, b in h.get("polozky", [])],
                       records=[r for r in h.get("zaznamy", []) if r in recs]) for h in ns["HYPOTEZY"]]

    has_story = os.path.exists(os.path.join(DATA, "pribeh.md"))
    public_cfg = {k: v for k, v in cfg.items() if k != "prihlaseni"}
    public_cfg["maPribeh"] = has_story
    site = dict(config=public_cfg, places=places, root=slugs[1], aliases={a: slugs[a] for a in SAME}, people=people,
                families=families, records=records, lines=lines, tree=tree, claims=claims,
                issues=[dict(title=i, text="") if isinstance(i, str) else dict(title=i[0], text=i[1], **(i[2] if len(i) > 2 else {})) for i in ISSUES], stats=stats, hypotheses=hypotheses,
                docs=[dict(img=d["img"], caption=d["popis"], people=[slugs[k] for k in d.get("osoby", []) if k in slugs])
                      for d in docs_cfg if os.path.exists(os.path.join(VYREZY, d["img"] + ".jpg"))])

    gen_dir = os.path.join(WEB, "src", "generated")
    for src, dst in (("archivni_dotazy.md", "dotazy.md"), ("research_log.md", "denik.md"), ("zajimavosti.md", "zajimavosti.md")):
        path = os.path.join(DATA, src)
        text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        text = strip_comments(re.sub(r"^# .*\n", "", text, count=1))
        write(os.path.join(gen_dir, dst), md_hvezdicky(oznac(propoj(text), dict(type="text", slug="/zajimavosti/", name="Zajímavosti"), claims)) if dst == "zajimavosti.md" else text)
    story = os.path.join(DATA, "pribeh.md")
    if has_story:
        md = strip_comments(open(story, encoding="utf-8").read())
        hlava, _, telo = md.partition("\n---\n") if md.startswith("---") else ("", "", md)
        telo = md_hvezdicky(oznac(propoj(telo), dict(type="text", slug="/pribehy/", name="Příběh rodu"), claims))
        md = (hlava + "\n---\n" + telo) if hlava else telo
    write(os.path.join(gen_dir, "pribeh.md"), md if has_story else "---\ntitle: Příběh\nlead: ''\n---\n")

    # příběhy jednotlivých rodů: data/pribehy/<slug rodu>.md (slug = jako /rod/<slug>/), s frontmatter title/lead
    prib_dir = os.path.join(DATA, "pribehy")
    gen_prib = os.path.join(gen_dir, "pribehy")
    os.makedirs(gen_prib, exist_ok=True)
    for f in os.listdir(gen_prib):
        os.remove(os.path.join(gen_prib, f))
    line_stories = {}
    if os.path.isdir(prib_dir):
        for f in sorted(os.listdir(prib_dir)):
            if not f.endswith(".md"):
                continue
            slug = f[:-3]
            md = strip_comments(open(os.path.join(prib_dir, f), encoding="utf-8").read())
            hlava, _, telo = md.partition("\n---\n") if md.startswith("---") else ("", "", md)
            nazev = lines[slug]["name"] if slug in lines else slug
            telo = md_hvezdicky(oznac(propoj(telo), dict(type="text", slug=f"/rod/{slug}/", name=f"Příběh rodu {nazev}"), claims))
            write(os.path.join(gen_prib, f), (hlava + "\n---\n" + telo) if hlava else telo)
            line_stories[slug] = True
            if slug not in lines:
                print(f"POZOR: data/pribehy/{f} – žádný rod s adresou /rod/{slug}/ (rody: {', '.join(lines)})")
    for sl, l in lines.items():
        l["story"] = sl in line_stories

    stats["claims"] = len(claims)
    site["figures"] = cisla(people, records)
    write(os.path.join(WEB, "src", "data", "site.json"), json.dumps(site, ensure_ascii=False, indent=1))
    hrefs = os.path.join(gen_dir, "fan_hrefs.json")
    json.dump({k: f"/osoba/{s}/" for k, s in slugs.items()}, open(hrefs, "w", encoding="utf-8", newline="\n"))
    subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(TOOLS, "fan_chart.py"),
                    os.path.join(gen_dir, "fan.svg"), "--web", hrefs], check=True, capture_output=True)
    subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "gedcom.py")], check=True, capture_output=True)
    if verejny:   # data/rodokmen.ged zůstává úplný, zkracuje se jen to, co jde na web
        vystupy = [os.path.join(WEB, "src", "data", "site.json"), os.path.join(WEB, "public", "rodokmen.ged")]
        vystupy += [os.path.join(d, f) for d, _, fs in os.walk(gen_dir) for f in fs if f.endswith((".md", ".svg", ".json"))]
        jmena, data = zijici(P, SIDE)
        skryj_data(vystupy, data)
        print(f"Veřejný export – u žijících jen rok (zkrácená data: {len(data)}); žijící: {', '.join(jmena) or 'nikdo'}")

    gated = login_files(cfg)

    # rámečky v plném rozlišení se překreslují jen u obrázků, kterým se rámečky změnily (jaké jsou nakreslené, pamatuje .ramecky.json)
    zv = os.path.join(DATA, "zvyrazneni.json")
    hl_mtime = os.path.getmtime(zv) if os.path.exists(zv) else 0
    ramecky_json = os.path.join(WEB, ".ramecky.json")   # mimo public/, ať se nenahrává na web
    try:
        ramecky = json.load(open(ramecky_json, encoding="utf-8"))
    except (OSError, ValueError):
        ramecky = {}
    prace = []
    for sub, src_dir in (("img", VYREZY), ("zdroje", ZDROJE)):
        dst_dir = os.path.join(WEB, "public", sub)
        os.makedirs(dst_dir, exist_ok=True)
        for key in list(recs) + [d["img"] for d in docs_cfg] + ([cfg["uvod"]["foto"]] if cfg.get("uvod", {}).get("foto") else []):
            src = os.path.join(src_dir, key + ".jpg")
            dst = os.path.join(dst_dir, key + ".jpg")
            if not os.path.exists(src):
                continue
            boxes = hl.get(key, {}).get("boxes", []) if sub == "zdroje" else []
            stale = not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)
            if sub == "zdroje" and not stale:
                if key in ramecky:
                    stale = ramecky[key] != boxes
                else:   # obrázek z doby před .ramecky.json – platí staré pravidlo podle data změny
                    stale = bool(boxes) and hl_mtime > os.path.getmtime(dst)
                    if not stale:
                        ramecky[key] = boxes
            if stale:
                prace.append((sub, key, src, dst, boxes))
    if len(prace) > 20:
        print(f"Kopíruji {len(prace)} obrázků (s rámečky: {sum(1 for p in prace if p[4])}) – může to trvat pár minut…", flush=True)
    copied = 0
    try:
        for sub, key, src, dst, boxes in prace:
            if not (boxes and draw_boxes(src, dst, boxes, os.path.join(VYREZY, key + ".jpg"))):
                shutil.copy2(src, dst)
            if sub == "zdroje":
                ramecky[key] = boxes
            copied += 1
            if len(prace) > 20 and copied % 25 == 0:
                print(f"  … {copied}/{len(prace)}", flush=True)
    finally:   # i po přerušení (Ctrl+C) si zapamatovat, co už je hotové
        write(ramecky_json, json.dumps(ramecky, ensure_ascii=False))
    print(f"{len(people)} osob (z toho {stats['relatives']} širší rodina, {stats['stories']} s příběhem), {len(claims)} označených neověřených tvrzení, {len(families)} rodin, {len(records)} zápisů, {len(lines)} rodů, {len(places)} míst; "
          f"zkopírováno {copied} obrázků; přihlášení {'zapnuté' if gated else 'VYPNUTÉ (web je otevřený)'}")

    # odkazy v textech, které nikam nevedou (adresa osoby se změní třeba doplněním roku narození: jan-novak → jan-novak-1798)
    targets = dict(osoba=people, zdroj=recs, rod=lines, rodina=families)
    texts = {f: open(os.path.join(gen_dir, f), encoding="utf-8").read() for f in ("pribeh.md", "zajimavosti.md")}
    texts["web.json"] = json.dumps(cfg, ensure_ascii=False)
    texts["osoby.py (hypotézy)"] = json.dumps(hypotheses, ensure_ascii=False)
    broken = [(f, m.group(0)) for f, t in texts.items()
              for m in re.finditer(r"/(osoba|zdroj|rod|rodina)/([^/\s)\"'#?<>\]]+)", t) if m.group(2) not in targets[m.group(1)]]
    for f, link in dict.fromkeys(broken):
        print(f"POZOR: nefunkční odkaz {link}/ v {f} – oprav ho (adresy stránek jsou ve web/src/data/site.json)")


if __name__ == "__main__":
    main()
