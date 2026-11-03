# Projekt rodokmenu

Tohle je projekt rodokmenu vedený skillem **rodokmen**. Na začátku každé konverzace:
1. Načti skill `rodokmen` (pokud ještě není načtený).
2. Přečti `data/STAV.md` – stav, pravidla a co je rozpracované – a konec `data/research_log.md`.
3. Pokračuj tam, kde se skončilo. Komunikuj česky, stručně a srozumitelně pro člověka bez zkušeností s genealogií a programováním.
4. Pro pomocníky (subagenty) na **hledání** ve svazcích (který snímek, oddíl, rok, řádek, folio) smíš použít levnější Gemini model na low (`Model: "flash_lite"` nebo `"flash"`). **Přepis zápisu levný pomocník nedělá** – jen napíše, kde zápis je, a co na řádku jistě vidí (jméno, datum, dům). Přepis, ověření a zápisy dělá hlavní model. (Levný pomocník má tendenci domýšlet kněze, kmotry, příčiny smrti, rodiče i dvojčata, která v zápisech nejsou.)
5. Co by šlo ve skillu zlepšit (chyby nástrojů, nové archivy, nápady), zapisuj do `poznamky_pro_skill.md` – viz skill, sekce „Poznámky pro správce skillu“.

## Pravidla, která chrání kvalitu (platí vždy)
- **Přepis jen toho, co vidíš na výřezu v plném rozlišení.** Co nepřečteš, je „[…]“, nejisté „(?)“. Nikdy nedoplňuj
  kněze, kmotry, bábu, ohledače, příčinu smrti, rodiče rodičů ani dům z jiného zápisu, z rodokmenu nebo „jak to bývá“.
  Ve výsledcích pomocníka má každý úkol řádek `nečteno: …` (co na výřezu přečteno nebylo; „nečteno: nic“ jen když
  opravdu nic). Z náhledu (`…_nahled.jpg`, `--nahled`, šířka pod ~1600 px) se nic neopisuje ani necituje – slouží jen
  k nalezení roku, oddílu, řádku nebo folia. Výřez musí obsahovat hledané jméno.
- **Čísla osob `#N` jen ověřená** (`grep -n "^    N:" data/osoby.py`). Osoba, která v rodokmenu není, se píše jménem
  bez čísla. `kontrola.py` vymyšlené číslo v deníku, STAV.md a textech webu hlásí jako CHYBU.
- **Nález v gruntovní knize, sčítání nebo kronice patří předkovi jen při shodě jména, domu a let** s jeho fakty
  (`tools/pozemky.py predci "Obec"` vypíše, kdo z rodokmenu v obci žil a v kterém domě). Jinak je to „stopa“, ne doklad,
  a nepíše se „doložena kontinuita rodu“.
- **Skripty nesmějí obsahovat genealogická tvrzení.** Zpráva ze skriptu obsahuje jen to, co skript skutečně vyčetl
  (z dat nebo ze stažené stránky). Natvrdo napsané „ověřené rodové větve“ jsou vymýšlení.
- **Před předáním výsledků spusť `python3 -I tools/kontrola_vysledku.py <vysledky.md>`** a oprav CHYBY (neexistující
  osoby a obrázky, výřez nepatřící ke stránce); body „pozor“ vysvětli ve výsledcích.
- **Cizí pracovní složky v `pracovni/` nemaž**, když na ně odkazuje deník; zastaralé označ v deníku.
- **Do faktů `f` osoby se stavem `doc` patří jen to, co je přečteno na snímku některého z jejích zápisů.**
  Údaje z rodinného GEDCOMu (MyHeritage), od rodiny nebo z cizího stromu dej do `note` s uvedením zdroje
  („podle rodinného stromu MyHeritage, neověřeno“). Nikdy v deníku nepiš, že zápis dokládá něco, co v něm není.
  Když GEDCOM odporuje matrice (věk v zápisu ≠ rok narození ve stromu), platí matrika a rozpor jde do `ISSUES`.
- **`datum` v `zaznamy.json` česky**: `4. 6. 1822`, ne `1822-06-04` (web jinak prohodí den a měsíc při řazení).
- **Rámečky jen přes `tools/ramecek.py`** – klíč v `zvyrazneni.json` je `boxes`. Výřez dělej velkoryse
  (zápis + hlavička sloupců + okrajové přípisky), rámeček pak vymezí čtený zápis; rámeček přes celý obrázek je k ničemu.
- **Překlad `cs` a `shrnuti` jsou pro rodinu**: překlad zápisu v 1–3 odstavcích s vysvětlením pojmů, shrnutí 1–3 věty.
  Žádné oddíly „Genealogický význam…“, žádné vykřičníky, žádná čísla Kekulé v textu. Objevy patří do deníku
  a do `zajimavosti.md`.
- **Nejisté místo (?) porovnej s mapou okolí farnosti**, než ho zapíšeš.
- **Deník zapisuj i při neúspěchu** (svazek, snímky od–do, co na nich bylo). Deník se samými úspěchy je podezřelý.
- **Ukládej do gitu po každém dokončeném zápisu**, nejpozději po třech. Neuložená práce za celý den je riziko.
  Při práci v dávkách (`pracovni/overovani*/`) se do `data/` nic nepíše a necommituje, dokud výsledky neprojdou kontrolou.
- **Jména a sňatky** (jako GEDCOM: osoba má jedno rodné jméno, každý sňatek je samostatná rodina). Hlídá `kontrola.py`
  (`SŇATEK`, `PŘÍJMENÍ`); GEDCOM i web z toho skládají rodiny, jména po svatbě a pořadí partnerů.
  - `n` = **rodné příjmení** („Marie Nováková“), nikdy „Marie Dvořáková (roz. Nováková)“.
  - **Příjmení po svatbě se nezahazuje:** fakt `"provdaná Dvořáková"`, u více sňatků v pořadí
    `"provdaná Černá, později Dvořáková"` – tvar opiš z matriky, neodvozuj.
  - **Každý sňatek je vlastní fakt `×`**, při více sňatcích s pořadím: `"× 1. 29. 2. 1848 František Král († 1855)"`,
    `"× 2. 22. 1. 1856 Josef Starý"`. Za datem celé jméno partnera (ženy rodným příjmením).
  - **Každý partner, který není předek, je osoba** v `SIDE`: `id`, `sex`, `partner=<číslo předka>`, stačí jméno;
    `st` a `r` podle zápisu, ze kterého o něm víme.
  - **Děti z dalších sňatků** dostanou `otec`/`matka` (číslo předka nebo id) a vlastní `n` podle křtu. Legitimaci
    pozdějším sňatkem zapiš faktem a do `note`.
- **Přepis `orig` je doslovný opis snímku, ne rekonstrukce.** Co nejde přečíst, označ `[?]` nebo „(čtení nejisté)“;
  nic nedoplňuj podle toho, „jak to v zápisech bývá“. Postup:
  - Čti výřez v plném rozlišení (`zdroje/`), u každého sloupce zvlášť; poznámky pod zápisem a přípisky na okraji patří do přepisu.
  - **Jméno převeď do 1. pádu podle tvaru na snímku.** Velká písmena porovnej s tvary týchž písmen na stejném řádku.
  - **Číslice v přípiscích** (7 × 4 × 1, 3 × 5) porovnej s ostatními prameny. Nejasný rozpor jde do `ISSUES`.
  - Teprve z hotového přepisu piš fakta `f`, `cs` a `shrnuti` – ne z paměti nebo z překladu.
- **Data a věky hlídá `python3 -I tools/kontrola_dat.py`** (spouští ho i `kontrola.py` a hlásí počet). Najde nemožná a podezřelá
  data – věk při sňatku z data narození, věk uvedený v zápisu proti narození, různé roky narození z různých zápisů,
  rodiče a děti (věk matky/otce, dítě po smrti rodiče, dítě před sňatkem rodičů), sňatek po smrti, pohřeb dlouho po úmrtí,
  neplatná data (31. 2.) a datum zápisu ≠ fakt osoby. Postup: **přečti uvedené zápisy znovu ze snímku zvětšené**
  a oprav podle snímku. Když matrika opravdu uvádí jinak (spletl se písař), nic „nepřizpůsobuj“: rozpor zapiš do `ISSUES`
  a do `data/kontrola_dat_ok.txt` řádek „začátek hlášení | snímek přečten znovu <datum>, v zápisu opravdu …“.
- **Rodinný strom (GEDCOM z MyHeritage…) porovnávej nástrojem**: `python3 -I tools/ged_import.py <strom.ged> "Jméno Předka" --porovnej`
  vypíše rozpory, údaje navíc (stopy) a předky navíc. Strom není pramen: stopy ověř v matrice, do dat jen se značkou {{strom: …}}.
- **Web se nasazuje jen `./deploy.sh` nebo `npm run nasadit`** (veřejný export – u žijících jen rok).
  Nasazuje uživatel, ne agent. Přesná data žijících v `data/` nevadí, na web nejdou.

## Nezávislé prameny mimo matriky – nástroje
Cíl: každý důležitý údaj mít doložený z více nezávislých pramenů; co je jen z rodinného stromu, má být vidět jako
„neověřeno“. FamilySearch a GenTeam se **neautomatizují** (ochrana proti robotům, podmínky použití) – jen ručně
v uživatelově prohlížeči. Automatizovat jde:

| nástroj | co dělá |
|---|---|
| `python3 -I tools/prameny.py hledat kramerius "Jan Novák" --od 1880 --do 1960 --misto "Holice\|Chrudim"` | fulltext všech digitálních knihoven (ČDK, NK ČR, Digitální studovna MO): noviny, parte, sborníky, vojenské úmrtní matriky. U běžných jmen vždy s `--misto`. |
| `python3 -I tools/prameny.py hledat kramerius Novák --seznamy-ztrat` | rakousko-uherské seznamy ztrát 1914–1919 (jména často německy: Ladislaus, Wenzel). |
| `python3 -I tools/prameny.py hledat vua Novák --jmeno Jan [--misto Holice]` | databáze padlých v 1. sv. válce VÚA (narození, útvar, úmrtí, příčina, bojiště, hrob). |
| `python3 -I tools/prameny.py hledat cevh Novák --jmeno Jan` | Centrální evidence válečných hrobů: padlí + jména na pomnících a hrobech. |
| `python3 -I tools/prameny.py fronta navrhni` → `fronta spustit` → ráno `fronta vysledky` → `fronta vycisti` | noční dávka: navrhne dotazy ze všech osob v `osoby.py`, běží na pozadí, ráno přehled nálezů. |
| `python3 -I tools/arolsen.py hledat "Novák Josef 1905" [--podrobne] [--misto-narozeni Holice]`, `karta <id> pracovni/x.jpg` | Arolsen Archives: vězni koncentračních táborů, oběti, **nuceně nasazení**, vysídlení (DP). |
| `python3 -I tools/matricula.py fary oesterreich/wien [slovo]` → `knihy <fara>` → `snimky <kniha>` | Matricula (Vídeň, Rakousko, Německo, Polsko): fara, kniha a číslo snímku bez prohlížeče; snímek čti v prohlížeči. |
| `python3 -I tools/smoke_test.py [nástroj…]` | ověří všechny síťové nástroje jedním dotazem (NEDOSTUPNÉ = portál neodpovídá, CHYBA = portál se změnil). |
| `python3 -I tools/pozemky.py hledat "Obec" [--dum CP]` | pozemkové a majetkové prameny: pozemkové/gruntovní knihy v MZA ARON (fond C 17 a velkostatky), lánové rejstříky 1669–1679, stabilní katastr a indikační skici se jmény hospodářů. |
| `python3 -I tools/pieta.py vets hrdina "Novák"` / `misto "Holice"` | hroby, pomníky a vojenská pietní místa (VETS.cz): padlí, pamětní desky, pomníky a fotky. Volba `hrbitovy` dává přímé odkazy na hřbitovní správy (Brno, Jihlava, Třebíč, Praha, BillionGraves, Find a Grave). |
| `python3 -I tools/kroniky.py hledat "Holice"` / `info <id>` | školní a obecní kroniky a archivní fondy obcí v MZA ARON: zápisy o požárech, výstavbě, epidemiích, sporech a škole; stažení snímků digitalizovaných kronik (`snimek <id> <n> out.jpg`). |
| `python3 -I tools/scitani.py plan [--rok 1900] [--obec "Dolní Roveň"]` | sčítání lidu 1857–1921 (MZA Sčítací operáty, Morava): kdo byl při kterém sčítání naživu a v kterém domě → `pracovni/scitani/plan.md`. |
| `python3 -I tools/scitani.py najdi "Dolní Roveň" 1900 7` → `hlavicky <sada> <od> <do> out.jpg` → `snimek <sada> <n> out.jpg` | najde sadu a snímek domu, stáhne arch popisný. `svazek <sada>` = vstup pro `svazky.json`. |
| `python3 -I tools/dum.py "Holice" 112 [--zapis]`, `tools/dum.py --vsechny --zapis` | souřadnice konkrétního domu (čp.) pro mapu webu; obec musí být nejdřív v `mista.json`. |
| `python3 -I tools/kontrola_vysledku.py pracovni/<složka>/vysledky.md` | kontrola výsledků pomocníka před předáním: neexistující `#N`, chybějící obrázky, citace z náhledů, výřez nepatřící ke stránce. |
| `python3 -I tools/pozemky.py predci "Obec"` | kdo z rodokmenu žil v obci (domy, roky, fakta) – koho hledat v rejstříku gruntovní knihy; bez sítě. |
| `python3 -I tools/najdi_vyrez.py <stranka.jpg> <vyrez.jpg>` | bleskové nalezení polohy výřezu ve velké stránce (OpenCV FFT, 0.5 s; dává souřadnice 0..1 pro vyrez.py a ramecek.py). |

**Jak zapracovat nález z těchto pramenů** (jsou to stopy, ne matriční doklady):
1. Otevři odkaz a přečti si ho sám. Shoda jména nestačí – musí sedět i rok, obec nebo rodina.
2. Do deníku `research_log.md` řádek se zdrojem (např. „Kramerius NK, Verlustliste 18. 8. 1916, s. 54“) a odkazem.
3. K osobě do `note`: „Stopa: … (zdroj, odkaz)“. Do `f` jen to, co pramen skutečně říká, s uvedením pramene v `note`.
   Do `r` patří jen matriční zápisy. Stav `doc` se nemění kvůli novinám – `doc` = přečteno v matrice.
4. Je-li to obrazový doklad hodný webu (parte, seznam ztrát, pomník), stáhni stránku do `pracovni/`, udělej výřez
   (`tools/vyrez.py`) a zápis druhu `J` (jiný pramen) do `zaznamy.json` s odkazem – pak smí být i v `r`.
5. Rozpor s matrikou → `ISSUES`, nic nepřepisuj.

**Pozemkové knihy a gruntovnice** – postup v pozemkových knihách:
0. **Koho hledám:** `tools/pozemky.py predci "Obec"` – kdo z rodokmenu v obci žil, v kterém domě a kdy. Bez předka
   v obci gruntovní kniha rodokmenu nic nedá.
1. Knihy pro obec (`tools/pozemky.py knihy "Obec"`) – zjistit časový rozsah a zda má digitalizované snímky.
2. Rejstřík na začátku knihy (`tools/pozemky.py rejstrik <apu_id> [--od 2] [--do 8]`) – projít náhledy indexu, najít ves a jméno hospodáře a číslo listu (**folia**).
3. Nalézt folio v knize (číslo snímku $\approx$ číslo folia + počet listů předsádky/rejstříku). Gruntu obvykle patří blok 8–10 listů.
4. Trhová smlouva / Zápis (`Nowý Zápis` / `Kaufvertrag`): stáhnout plné rozlišení (`snimek <apu_id> <číslo>`), přepsat datum, rychtáře a konšely, kupní cenu (v rýnských zlatých fl.), závdavek, roční splátky a věřitele, výminek (*Wýminek*) a inventář usedlosti.
5. Následující listy s ročními kvitancemi (rathunky) ukazují, jak dlouho předek splácel a kdy přesně grunt předal dalšímu hospodáři. Vše srovnat se sňatky a úmrtími v matrice.
6. **Ztotožnění a zápis:** předek jen při shodě jména, domu a let; pak zápis druhu `J` (`j_<rok>_<jméno>_grunt`) s výřezem z plného rozlišení a přepisem.

**Sčítání lidu** – celý postup ve skillu `.agents/skills/scitani/SKILL.md`: arch popisný domu = zápis druhu `S`, klíč
`s_<rok>_<obec>_cp<čp>`, `misto` „Obec čp. N“, `datum` = rozhodný den (31. 12. daného roku; 1857: 31. 10. 1857; 1921: 15. 2. 1921), výřez + rámeček
kolem řádků domácnosti, přepis všech řádků po sloupcích (jméno, vztah, narození, rodiště, náboženství, stav, povolání).

## Širší rodina a příběhy
Jeden zdroj dat (`data/osoby.py`), web z něj dělá obě zobrazení: **Přímá linie** (jen předci) a **Celá rodina**
(přepínač na stránce Rodokmen; strom jde shora dolů, nejstarší nahoře, výchozí osoba dole).

**Příbuzný mimo přímou linii** (sourozenec předka, jeho potomci, druhý partner...) je položka `SIDE`
s rodiči – pak má vlastní stránku, místo ve stromu i v GEDCOMu:
```python
dict(k=16, id="frantisek_novak_1833", n="František Novák", y="1833–1894", sex="M", st="doc",
     otec=16, matka=17,                      # číslo předka, nebo id jiného příbuzného
     partner="marie_kralova_1840",           # volitelné; i seznam
     f=["* 4. 11. 1833 Holice čp. 112", "kovář v Holicích", "† 1894 Holice"], r=["n_1833_frantisek_novak"],
     t="Bratr Václava Nováka.",
     note="…", pribeh="Druhorozený syn neměl zdědit dílnu…"),
```
- `k` = předek, u kterého se příbuzný ukazuje jako karta. `id` jen malá písmena, číslice a podtržítko. `sex` uveď vždy.
- Pořadí sourozenců ve stromu určuje rok narození (`y` nebo fakt `*`).

**Příběh** (`pribeh`) může mít každá osoba v `P` i v `SIDE`. Zobrazuje se na stránce osoby nahoře, před fakty,
a ve stromu má taková osoba značku ✎. Piš ho při čtení zápisu – tehdy víš, co zápis o člověku říká:
- Délka podle materiálu: obvykle 5–15 vět, klidně dva tři odstavce.
- Co zápis prozrazuje: vdovství, sňatek v mladém věku, epidemie v rodině, svědkové a kmotři, přípisky.
- Co nevíš, nedomýšlej; nejistotu přiznej („pravděpodobně“, „podle rodinné paměti“).

## Nefantazírovat: značky neověřených údajů
Co není přečtené v matričním zápisu, nesmí na webu vypadat jako fakt. Platí pro fakta `f`, poznámky, `pribeh`,
`zajimavosti.md` i `pribeh.md`. Označ to značkou, web ji převede na štítek a všechna taková tvrzení sepíše na stránce
„Co hledáme“ (sekce „Zatím neověřené údaje“); `kontrola.py` je počítá a u faktů `doc` osob je vyžaduje.
```
"† 25. 11. 1849 Dolní Roveň čp. 7 {{strom}}"             # fakt z cizího rodokmenu (MyHeritage, Geni…)
"padl 4. 7. 1916 u Monfalcone {{rodina: rodinná kronika}}"   # od rodiny / z rodinného dokumentu
"{{hypotéza: Matěj Novák z čp. 112 je týž, kdo r. 1760 koupil kovárnu}}"
"{{neověřeno: Františka Nováková se provdala za Josefa Krále}}"   # tvrzení bez pramene
```
- V próze obal celé tvrzení: `{{neověřeno: … }}`; u krátkého faktu stačí značka na konci: `… {{strom}}`.
- Když tvrzení ověříš v zápisu, značku odstraň a do `r` dej klíč zápisu.

## Příběh rodu a Zajímavosti
- **Příběh pro každý rod**: `data/pribehy/<slug rodu>.md` (slug = adresa `/rod/<slug>/`: novakovi, dvorakovi, kralove…),
  s hlavičkou `title`/`lead` jako `pribeh.md`. Ukáže se nahoře na stránce rodu a v seznamu na `/pribehy/`.
- **Zajímavosti** doplní web sám o „Příběhy lidí“ a „Rodokmen v číslech“ (spočítané z dat). Ručně psaná část
  (`zajimavosti.md`) je nad tím.
- Do `zajimavosti.md` po každém kole výzkumu 1–3 nové odstavce `## Nadpis` z toho, co kolo přineslo (`python3 -I tools/napady.py`).

## Roky života `y` – vždy aktuální, nejistota viditelná
Roky z `y` jsou ve stromu, na webu a v GEDCOMu. Uprav je po každém zápisu (`python3 -I tools/roky.py --zapis`).

| zápis | kdy | GEDCOM |
|---|---|---|
| `1835` | přesné datum z matriky (sčítání s celým datem) | `1835` |
| `kol. 1790` | vypočteno z věku: „72 let při úmrtí“, „28 let při sňatku“, sčítání jen s rokem | `ABT 1790` |
| `asi 1790` | odhad: nejstarší známé dítě − 25 (matka) / − 30 (otec) | `EST 1790` |
| `před 1860`, `po 1910` | jen mez („† před 1860“, „žil 1910“) | `BEF` / `AFT` |
| fakt `† mezi 1911 a 1921` | interval (sčítání: žil – vdova); v `y` jako `před 1921` | `BET 1911 AND 1921` |
| `?` | nevíme | – |

Celek: `1835–1890` (obě přesná), jinak s mezerami `kol. 1790 – před 1857`, `asi 1800 – ?`.

## Rytmus aktualizace
1. **Po každém zápisu**: výřez, rámeček, přepis, osoba (i roky `y` – `tools/roky.py`), deník; `pribeh` hlavní osobě zápisu; co není z matriky → značka `{{…}}`; `kontrola.py`.
2. **Po každém kole** (3–5 zápisů, nebo konec sezení): `python3 -I tools/napady.py` → 1–3 odstavce do `zajimavosti.md` a posunout razítko `<!-- aktualizováno při N zápisech -->`; ve `web/` `npm run data && npm run build`; `git add -A && git commit`.
3. **Před každým `git commit` spusť `python3 -I tools/kontrola.py`** a neukládej s CHYBOU.
