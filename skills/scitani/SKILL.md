---
name: scitani
description: Ověření rodokmenu ze sčítání lidu 1857–1921 (Morava, portál MZA Sčítací operáty) – kontrola dat narození, domácností a nejistých čtení z matrik a přidání archu jako pramene k osobám. Použij, když má agent „projít sčítání“, ověřit údaje osob ze sčítání, zpracovat nález z MyHeritage „Sčítání lidu v Česku“, nebo pokračovat v plánu pracovni/scitani/plan.md.
---

# Sčítání lidu jako druhý zdroj pravdy

Arch popisný (Aufnahmsbogen) = jeden dům k rozhodnému dni: všichni obyvatelé s narozením, rodištěm, vztahem k hlavě
domácnosti, náboženstvím, stavem a povoláním. Je to **úřední pramen se snímkem** – smí do `r` osoby jako matrika.
Ale data narození v něm **hlásili sami obyvatelé**: rok bývá o 1–2 vedle, den/měsíc přehozený. Proto:

- **shoda** s matrikou = údaj má druhý nezávislý doklad,
- **nový údaj** (v rodokmenu chybí) = doplnit s uvedením „(sčítání 1900)“; přesné datum narození pak dohledat v matrice,
- **rozpor** = nic nepřepisovat → `ISSUES` + znovu přečíst matriční zápis (nejisté čtení, záměna osob). Tohle je hlavní
  přínos: sčítání nás donutí zkontrolovat nečitelná místa v matrikách.

## Ročníky a co na archu najdeš

| sčítání | rozhodný den (`datum` zápisu) | narození na archu (obvykle) | poznámka |
|---|---|---|---|
| 1857 | 31. 10. 1857 | rok narození | obec bývá zapsaná jako část jiné (1857 „Holice / Dolní Roveň“) |
| 1869 | 31. 12. 1869 | rok narození | |
| 1880 | 31. 12. 1880 | rok (někdy celé datum) | |
| 1890 | 31. 12. 1890 | rok (někdy celé datum) | |
| 1900 | 31. 12. 1900 | den, měsíc, rok | arch = 2 snímky (přední strana lidé, zadní zvířata a podpis) |
| 1910 | 31. 12. 1910 | den, měsíc, rok | |
| 1921 | 15. 2. 1921 | den, měsíc, rok | |

Vždy se řiď hlavičkou sloupců na konkrétním archu – formuláře se liší i v rámci ročníku. Co na archu není, nevymýšlej.
Měsíce bývají česky zkráceně („list.“ = listopad, „čer.“ / „červ.“ – rozliš červen × červenec, „září“, „říj.“, „srp.“).
Ženy bývají psané příjmením muže v mužském tvaru („Dokulil Anna“), sourozenci „ “ (= totéž příjmení).

Nedochované ročníky ukáže plán (např. Panská Lhota, Malé, Komárovice, Zhoř jen 1921; Arnolec 1910 a 1921).
Okres na portálu je dobový: Hodov, Přeckov, Čikov → SOkA Žďár n. S.; Třebenice u Valče → okres Mor. Krumlov (SOkA Znojmo).

## Postup (jedna domácnost)

1. **Kde**: `python3 -I tools/scitani.py plan` → `pracovni/scitani/plan.md` (obec × rok, čp., kdo tam má být, sada,
   odhad snímku; ✓ = hotovo). Bez čp. → projdi celou obec (hlavičky). Z MyHeritage stačí obec + čp.
2. **Najdi snímek**: `scitani.py najdi "Obec" ROK ČP` → `scitani.py hlavicky <sada> <od> <do> pracovni/scitani/hlavicky.jpg`
   (číslo snímku vlevo, číslo domu vpravo nahoře; zadní strany mají pruh prázdný). Číslo domu ověř na hlavičce.
3. **Stáhni** přední stranu: `scitani.py snimek <sada> <n> pracovni/scitani/<klíč>.jpg` (plné rozlišení ~6700 px,
   ~460 dlaždic – sekvenčně, ne paralelně). Má-li domácnost víc lidí, pokračuje na dalším snímku – stáhni i ten.
4. **Přečti VŠECHNY řádky** (výřezy `magick … -crop`, čti sám, ne pomocník – pravidlo 2 z AGENTS.md). Nejisté „(?)“.
5. **Přepis** do `pracovni/scitani/prepis/<klíč>.json` (klíč `s_<rok>_<obec bez diakritiky>_cp<čp>`):
   ```json
   {"sada": 12345, "snimek": 58, "rok": 1900, "obec": "Dolní Roveň", "cp": 7,
    "radky": [{"jmeno": "Jan Novák", "vztah": "majitel bytu", "nar": "14. 2. 1890",
               "rodiste": "Holice, okr. Pardubice", "nab": "řím. kat.", "stav": "ženatý", "povolani": "…", "pozn": ""}],
    "cs": "Srozumitelný český popis domácnosti pro rodinu (kdo byl hlava, vztahy, povolání, staré pojmy vysvětlit)."}
   ```
   `jmeno` piš „Křestní Příjmení“ v tom tvaru, jak je na archu.
   `nar` česky „14. 2. 1890“, jen rok „1890“.
6. **Porovnej**: `scitani.py porovnej pracovni/scitani/prepis/<klíč>.json`
   - `✓` shoda · `≈` sedí jen část (hlášené datum – zapiš, matriku znovu zkontroluj) · `✗` ROZPOR → `ISSUES`
   - `+ NOVÉ` → doplnit fakt „* 10. 10. 1875 Dolní Roveň (podle sčítání 1900)“; `!` víc kandidátů → rozhodni sám
   - `?` člověk mimo rodokmen (+ „možná jde o …“ – jiné příjmení po sňatku?) → stopa do `note` příbuzného + deník
   - `–` měl v domě být a není → zkontroluj fakta o bydlišti (stěhování, úmrtí)
   Výstup ber jako návrh – posuzuješ ty (stejné jméno ≠ stejný člověk; rozhodují rodiče, dům, rodiště).
7. **Zápis** (jen jeden zapisující agent najednou – viz AGENTS.md „Bezpečnost souběhu“):
   - `scitani.py zapis pracovni/scitani/prepis/<klíč>.json` → vypíše tři příkazy `zapis.py` (svazek, zápis, přepis);
     zkontroluj `shrnuti` a `cs`, pak je spusť,
   - `tools/vyrez.py pracovni/scitani/<klíč>.jpg <klíč> x0,y0,x1,y1` (celý arch s hlavičkou obce a čp.),
     `tools/ramecek.py <klíč> …` kolem řádků domácnosti, prohlédni `pracovni/ramecek_<klíč>.jpg`,
   - `data/osoby.py` (Edit): `<klíč>` do `r` každé nalezené osoby; nové údaje do `f` s „(sčítání ROK)“; rozpory do
     `ISSUES`; povolání/výměnek/bydliště jako fakt („1900 výměnkář v Dolní Rovni čp. 7 (sčítání)“),
   - deník `data/research_log.md`: řádek i pro neúspěch („čp. 12 v sadě není, arch chybí“).
8. `python3 -I tools/kontrola.py` a `tools/kontrola_dat.py`; plán znovu (`scitani.py plan`) – dům má ✓.

## Dávková práce (víc domácností)

- Postupuj po obcích (jedna obec = jeden výlet na portál, sady jsou v mezipaměti). Pořadí: přímí předci před širší
  rodinou, rozpory a „bez data narození“ napřed.
- Pomocníci smějí **najít snímek a navrhnout přepis**; čtení zapisovaných údajů a zápis dělá hlavní agent (pravidlo 2).
  Do zadání pomocníkům: tento soubor + konkrétní řádky z plánu + „nic nezapisuj do data/, výstup = prepis JSON“.
- Portál šetři: stahuj sekvenčně, náhledy (`--nahled`, `hlavicky`) před plnými snímky, žádné paralelní stahování.
- Po dávce: commit (jen hlavní agent), `cd web && npm run data`, zmínka v `data/STAV.md` (kolik domů hotovo).
