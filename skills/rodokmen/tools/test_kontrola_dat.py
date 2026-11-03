#!/usr/bin/env python3
"""Test nástroje kontrola_dat.py: do kopie dat vloží náhodné „špatně přečtené číslice“ a změří, kolik jich nástroj najde.

Použití (z kořene projektu):
  test_kontrola_dat.py [počet] [--seed N] [--vsude]
      počet    kolik náhodných chyb vyzkoušet (výchozí 150; každá se zkouší zvlášť)
      --vsude  chyba se zapíše všude, kde to datum je (osoba, datum i text zápisu) – jako když se číslice špatně přečte
               už na snímku; bez přepínače se změní jen fakt u osoby (nesoulad mezi soubory)
Data projektu se nemění – pracuje se v dočasné kopii.
"""
import json, os, random, re, shutil, subprocess, sys, tempfile
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("RODOKMEN_DATA") or os.path.join(ROOT, "data")
# číslice, které se v rukopisu pletou (kurent i latinka)
ZAMENY = {"0": "68", "1": "74", "2": "37", "3": "852", "4": "971", "5": "638", "6": "508", "7": "142", "8": "350", "9": "47"}


def spust(slozka):
    out = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "kontrola_dat.py")], capture_output=True, text=True,
                         env=dict(os.environ, RODOKMEN_DATA=slozka)).stdout
    return {l for l in out.splitlines() if l.startswith(("CHYBA", "PODEZŘELÉ"))}


def main():
    if not os.path.isdir(DATA):
        sys.exit(f"Složka s daty nenalezena: {DATA} (spusť z kořene projektu s data/, nebo nastav RODOKMEN_DATA)")
    args = sys.argv[1:]
    n = int(next((a for a in args if a.isdigit()), 150))
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 1
    vsude = "--vsude" in args
    rnd = random.Random(seed)
    tmp = tempfile.mkdtemp(prefix="kontrola_dat_test_")
    for f in os.listdir(DATA):
        if f.endswith((".json", ".py", ".txt")):
            shutil.copy(os.path.join(DATA, f), tmp)
    puvodni = {f: open(os.path.join(tmp, f), encoding="utf-8").read() for f in ("osoby.py", "zaznamy.json", "prepisy.json")}
    zaklad = spust(tmp)
    # kandidáti: plná data ve faktech narození / sňatku / úmrtí (ne u neověřených {{…}} údajů)
    txt = puvodni["osoby.py"]
    kand = [m for m in re.finditer(r'["\'](\*|†|×(?: \d\.)?) (\d{1,2})\. (\d{1,2})\. (\d{4})', txt)
            if not txt[txt.rfind("\n", 0, m.start()) + 1:m.start()].lstrip().startswith("#")]   # ne ukázky v komentářích
    if not kand:
        sys.exit("V data/osoby.py nejsou fakta s plným datem (* / † / × d. m. rrrr) – test nemá co zkoušet.")
    vysl = {}   # (událost, místo) → [nalezeno, celkem]
    nenalezene = []
    for i in range(n):
        m = rnd.choice(kand)
        udalost = {"*": "narození", "†": "úmrtí"}.get(m.group(1), "sňatek")
        d, mo, y = m.group(2), m.group(3), m.group(4)
        misto = rnd.choice(["rok-jednotky", "rok-desítky", "den", "měsíc"])
        if misto.startswith("rok"):
            idx = 3 if misto == "rok-jednotky" else 2
            novy_y = y[:idx] + rnd.choice(ZAMENY[y[idx]]) + y[idx + 1:]
            nove = (d, mo, novy_y)
        elif misto == "den":
            c = d[-1]
            nd = d[:-1] + rnd.choice(ZAMENY[c])
            nove = (nd if 1 <= int(nd) <= 28 else d, mo, y)
        else:
            nm = rnd.choice([x for x in ("1", "4", "7", "3", "8", "9") if x != mo]) if len(mo) == 1 else mo
            nove = (d, nm, y)
        if nove == (d, mo, y):
            continue
        stare_t, nove_t = f"{d}. {mo}. {y}", f"{nove[0]}. {nove[1]}. {nove[2]}"
        texty = dict(puvodni)
        s, e = m.start(), m.end()
        texty["osoby.py"] = puvodni["osoby.py"][:s] + puvodni["osoby.py"][s:e].replace(stare_t, nove_t) + puvodni["osoby.py"][e:]
        if vsude:   # stejné datum i v zápisech té osoby (shrnutí, datum, překlad) – „špatně přečteno ze snímku“
            radek = puvodni["osoby.py"][puvodni["osoby.py"].rfind("\n", 0, s):puvodni["osoby.py"].find("\n", e)]
            klice = set(re.findall(r'"([noz]_\d{4}_[a-z_0-9]+)"', radek))
            zaz = json.loads(puvodni["zaznamy.json"])
            pre = json.loads(puvodni["prepisy.json"])
            for z in zaz:
                if z["klic"] in klice:
                    z["datum"] = str(z.get("datum", "")).replace(stare_t, nove_t)
                    z["shrnuti"] = z.get("shrnuti", "").replace(stare_t, nove_t)
            for k in klice & set(pre):
                pre[k]["cs"] = pre[k].get("cs", "").replace(stare_t, nove_t)
            texty["zaznamy.json"] = json.dumps(zaz, ensure_ascii=False, indent=1)
            texty["prepisy.json"] = json.dumps(pre, ensure_ascii=False, indent=1)
        for f, t in texty.items():
            open(os.path.join(tmp, f), "w", encoding="utf-8").write(t)
        nove_hl = spust(tmp) - zaklad
        klic = (udalost, misto)
        vysl.setdefault(klic, [0, 0])
        vysl[klic][1] += 1
        if nove_hl:
            vysl[klic][0] += 1
        else:
            jm = re.search(r'n="([^"]+)"', puvodni["osoby.py"][puvodni["osoby.py"].rfind("dict(", 0, s):s])
            nenalezene.append(f"{udalost} {stare_t} → {nove_t} ({jm.group(1) if jm else '?'})")
    for f, t in puvodni.items():
        open(os.path.join(tmp, f), "w", encoding="utf-8").write(t)
    shutil.rmtree(tmp)
    celkem = sum(v[1] for v in vysl.values())
    nalez = sum(v[0] for v in vysl.values())
    print(f"Režim: {'chyba všude (osoba i zápis)' if vsude else 'chyba jen ve faktu osoby'}; vyzkoušeno {celkem} chyb, nalezeno {nalez} "
          f"({100 * nalez // max(celkem, 1)} %).")
    for (u, mi), (a, b) in sorted(vysl.items()):
        print(f"  {u:9} {mi:13} {a:3}/{b:<3} ({100 * a // b} %)")
    print("Příklady nenalezených:", *nenalezene[:15], sep="\n  ")


if __name__ == "__main__":
    main()
