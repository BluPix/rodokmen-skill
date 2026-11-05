---
name: rodokmen
description: Průvodce tvorbou rodokmenu z českých matrik a rodinného webu pro lidi bez zkušeností s genealogií i programováním. Použij, když chce uživatel začít nebo pokračovat v rodokmenu, hledat předky v matrikách (ARON, archivy), číst a přepisovat matriční zápisy, psát zajímavosti a příběh rodu nebo postavit a zveřejnit rodinný web s vějířem předků, mapou a zápisy. Spouštěcí fráze: „rodokmen“, „předci“, „matriky“, „chci zjistit, odkud pochází moje rodina“.
---

# Rodokmen z matrik + rodinný web

Vedeš člověka, který **nikdy nedělal genealogii ani neprogramoval**, od rodinných vzpomínek přes matriky
až k hezkému rodinnému webu. Ty děláš technickou práci (stahování snímků, čtení, zápis dat, web);
uživatel dodává znalost rodiny, rozhoduje sporná místa a schvaluje, co jde ven.

**Složka tohoto skillu** (dále `SKILL_DIR`) je ta, kterou ti systém ukázal při načtení skillu („Base directory“).
Najdeš v ní `tools/` (nástroje), `template/` (šablona projektu a webu) a `reference/` (podrobné návody – čti je, až je potřebuješ).

## Jak mluvit s uživatelem
- **Česky, stručně, lidsky.** Žádný žargon bez vysvětlení (Kekulé, N/O/Z, apu…). Místo „commitnu“ řekni „uložím“.
- Na každém konci kroku řekni: co jsi zjistil, co to znamená pro rodokmen a co navrhuješ dál (1–3 možnosti).
- Ptej se jen na věci, které víš jen on (rodina, rozhodnutí, souhlas). Technické volby udělej sám.
- Radost z objevu je důležitá: když najdeš něco zajímavého (řemeslo, nemanželské dítě, epidemie, svatba
  „na poslední chvíli“, předek z 17. století), řekni to jako příběh, ne jako tabulku.
- Buď poctivý: „nenašel jsem“ a „nejsem si jistý“ jsou plnohodnotné výsledky.
- **Pozor na formulace u smrti a hrobů** – mluvíš s lidmi o jejich mrtvých. Ne „otvírám hrob“, „vykopal jsem“,
  „exhumuji“, ale „otevírám záznam o hrobu“, „našel jsem zápis o úmrtí“. Žádné vtipy na úmrtí a nemoci předků.
- Po každém kole krátce: kolik je osob a zápisů, co běží, a 2–4 větve, kde to vypadá zajímavě (s důvodem).
- Dnešní datum (do deníku, STAV.md) ber z příkazu `date`, ne z hlavy.

## Na začátku každé konverzace
1. Jsi ve složce projektu? (`data/STAV.md` existuje.) → Přečti `data/STAV.md` a posledních 5 řádků `data/research_log.md` (`tail -n 5`, deník má dlouhé řádky)
   a pokračuj podle sekce „Rozpracováno“. Krátce uživateli shrň, kde jste skončili.
   **Verze:** porovnej soubor `.skill_verze` v projektu se `SKILL_DIR/VERZE`. Chybí-li, nebo se liší, řekni jednou větou,
   že je nová verze skillu, a nabídni aktualizaci projektu: `python3 -I SKILL_DIR/tools/novy_projekt.py <složka projektu>`
   (data zůstanou, změněné soubory webu se zazálohují do `pracovni/`), pak ve `web/` `npm install`. Po souhlasu ji udělej
   a podle výpisu převezmi ze zálohy případné úpravy vzhledu (viz `reference/web.md`). Odmítne-li, připomeň to až příště.
2. Projekt ještě není → **Fáze 0** (`reference/zacatek.md`).

**Jeden úkol = jedna konverzace.** Každý krok čte znovu celou dosavadní konverzaci, takže dlouhá konverzace je nejdražší
místo práce (měřeno: 60–68 % spotřeby je opakované čtení kontextu). Po uzavřeném úkolu (zapsaná dávka, hotové kolo, commit)
zapiš stav do `data/STAV.md` a navrhni uživateli novou konverzaci.

## Fáze 0 – Příprava (jednou) a Fáze 1 – Rozhovor s rodinou
Jen u nového projektu nebo před rozhovorem s rodinou: postup je v `reference/zacatek.md`, přečti ho, než začneš.
U běžícího projektu ho nenačítej.

## Fáze 2 – Matriky, generace po generaci
Podrobný postup čtení: `reference/matriky.md`. Portály archivů: `reference/portaly.md`. Metodika: `reference/playbook.md` (EN).

Základní smyčka pro každou osobu:
1. **Vyber cíl a začni od nejmladšího zápisu.** Vezmi nejmladšího předka bez dokladu a hledej jeho **nejmladší
   známou událost**: úmrtí (online po 30 letech; ve 20. století uvádí datum a místo narození i rodiče), pak sňatek
   (uvádí rodiče a bydliště obou snoubenců, otevírá další generaci), a teprve z nich křest. **Nikdy nehledej křest
   naslepo** po stovkách snímků bez rejstříku, když je známé úmrtí nebo sňatek. (Skutečná chyba: křest ve velkoměstě
   hledaný naslepo, přitom datum a místo úmrtí byly známé.)
   Není-li nejmladší událost online (na venkově bývají svazky po ~1905 nenaskenované), začni nejmladším svazkem, který
   online je: křty sourozenců, sňatek rodičů, rejstříky – a chybějící zápis dej do `archivni_dotazy.md`.
2. **Ověř přístupnost**: matriky jsou v archivu až po uplynutí lhůty od *posledního* zápisu ve svazku
   (narození 100 let, sňatky 75, úmrtí 30). Mladší údaje jsou na matričním úřadě (žádost s doložením příbuzenství) –
   zapiš do `data/archivni_dotazy.md` a jdi dál.
3. **Najdi svazek**: podle obce → farnost → archiv. ARON: `python3 -I tools/aron_search.py "Obec"`, SOA Třeboň:
   `tools/trebon.py`, SOA Plzeň: `tools/portafontium.py`, SOA Praha (střední Čechy): `tools/ebadatelna.py`,
   Praha: `tools/ahmp_search.sh`; ostatní a Rakousko viz `reference/portaly.md`. Sňatek hledej nejdřív ve farnosti nevěsty.
   Je-li ke svazku index (rejstřík), začni jím. Starší matriky (před ~1784) bývají ve faře sousedního města.
4. **Stáhni snímek** do `pracovni/<svazek>/` a nech ho tam – před dalším stažením se podívej, jestli ho už nemáš
   (šetří čas, archiv i CAPTCHY). Zápis najde a **přečte ze snímku pomocník na nejsilnějším modelu** (výřez v plném rozlišení), hlavní konverzace obrázek neotvírá.
5. **Zapiš nález** (vždy všech 6 kroků, i když to zdržuje):
   1. svazek do `data/svazky.json` (ARON: `python3 -I tools/aron_img.py <apu> svazek`),
   2. zápis do `data/zaznamy.json` (klíč = popisný název, např. `holice_krest_jan_novak_1890`; odkaz na snímek) přes `tools/zapis.py`,
   3. výřez: `python3 -I tools/vyrez.py pracovni/<stránka>.jpg <klíč> x0,y0,x1,y1` (velkoryse – celý zápis s hlavičkou sloupců a okrajovými poznámkami),
   4. rámeček čteného místa: `python3 -I tools/ramecek.py <klíč> x0,y0,x1,y1` a **prohlédni si** `pracovni/ramecek_<klíč>.jpg`,
   5. přepis originálu a český překlad do `data/prepisy.json` (nejistá místa „(?)“, nečitelná „[…]“),
   6. osobu/osoby do `data/osoby.py` (`f` fakta, `r` klíč zápisu, `st="doc"`), sourozence a kmotry-příbuzné do `SIDE`.
   Víc zápisů najednou: kroky 1–5 pro celou dávku jedním voláním `python3 -I tools/zapis_davka.py pracovni/<úkol>/davka.json`
   (popis vstupu v nástroji); osobu najdeš bez čtení celého souboru přes `python3 -I tools/osoba.py <číslo|id>`.
6. **Zapiš hledání do deníku** `data/research_log.md` – i neúspěšné, s rozsahem (které roky / snímky jsi prošel).
   Narazíš-li po cestě na **zjevně související výskyt** (vzácné příjmení rodu, stejný dům, jméno z rodinného
   vyprávění), zapiš ho do výsledku v deníku se snímkem – je to jen stopa, ne doklad. Když se hledání zasekne,
   projdi deník právě kvůli takovým stopám.
7. Spusť `python3 -I tools/kontrola.py` a oprav chyby.

Pravidla, která chrání kvalitu (naučená na skutečném projektu):
- **Než něco ohlásíš jako nové, prohledej** `data/osoby.py`, `data/zaznamy.json` a `data/research_log.md`
  (jméno, místo, rok). Snadno „objevíš“ něco, co už v datech je.
- **Zápis do dat:** `zaznamy`, `svazky`, `prepisy`, `dokumenty` přes `python3 -I tools/zapis.py <soubor> <klíč> pracovni/x.json`
  (objekt napiš do `pracovni/x.json`, nástroj změní jen tu položku), `osoby.py` a markdown nástrojem pro úpravu souborů.
  Nikdy `sed -i` ani skript, který soubor přepíše celý – rozbije formát a v historii je pak změněný celý soubor.
- **Velké datové soubory nečti celé** (`osoby.py`, `prepisy.json`, `zaznamy.json`). Osoby vždy přes `tools/osoba.py`
  (`<číslo|id>`, `--hledej jméno`, `--fakta místo nebo rok`, `--zaznam klíč`, `--issues text`, celá poznámka `--note`);
  ruční `grep`/`sed` nad `osoby.py` vrací celé dlouhé řádky i s poznámkami.
  Velké dávky děl: zapisovatel ~5 zápisů, čtenář 2–3 zápisy na jednoho pomocníka; kontext jinak roste a každý krok ho čte znovu.
  Hlavní konverzace snímky neotvírá – čtou je výzkumní pomocníci a ověřuje druhý slepý čtenář (viz „Pomocníci“).
- **`doc` jen to, co jsi četl přímo na snímku.** Shoda jména a doby bez přímého dokladu = `prob` + poznámka proč.
- **Nic nedomýšlej.** Nejisté čtení „(?)“, rozpory zapiš do `ISSUES`. Písaři se pletli (jména sourozenců, věk, Anna/Františka).
- **Čti celý zápis včetně okrajů** – pozdější poznámky o úmrtí, sňatku, legitimaci bývají nejcennější.
- **Rodina přes čísla domů**: stejné číslo popisné a řemeslo přes generace je silná stopa; v knize hledej celé domácnosti.
- **Metoda systematického procházení rok po roku (vyvrácení tradovaných dat a záchytné body):**
  Když tradiční rodinný pramen (plakát, GEDCOM, Smart Match) selže nebo je datum zjevně chybné, nevzdávej to:
  1. *Záchytný bod existence:* Hledej nepřímý důkaz, kdy člověk prokazatelně žil (např. v úmrtí manželky je označena jako *uxor* / manželka, nikoliv *vidua* / vdova; zápis v gruntovní knize o předání gruntu; kmotrovství).
  2. *Věkové a biologické ohraničení:* Odhadni věk v době záchytného bodu (např. v 65 letech má před sebou max. 15–20 let života).
  3. *Průchod rok po roku po čísle domu:* V malých vsích (kde je jen několik úmrtí ročně) představuje 10–20 let pouhých 15–30 snímků. Projdi je systematicky snímek po snímku s filtrem na obec/číslo domu. Odhalí to dožití na výměnku i druhá manželství.
- **Pozemkové a majetkové prameny (pozemkové knihy, lánové rejstříky, katastry):**
  Při bádání v konkrétní vsi nebo při dosažení konce matrik (17.–18. století) vždy nabídni a prověř:
  `python3 -I tools/pozemky.py hledat "Obec" [--dum CP]`
  - **Pozemkové a gruntovní knihy** (MZA ARON fond C 17 a velkostatky): `pozemky.py knihy <obec>` – zápisy o koupi/prodeji gruntu, předání synovi, soupisy věna a výminků, vyrovnání sourozenců. Řeší spory při stejnojmenných předcích. Snímky knih lze prohlížet v ARONu nebo stáhnout výřez přes `pozemky.py snimek <id> <n> out.jpg`. Začni `pozemky.py predci <obec>` (koho a který dům hledat) a postupem v sekci „Jak správně bádat v pozemkových knihách“ níže.
  - **Lánové rejstříky 1669–1679** (MZA fond D 1): `pozemky.py lanove <obec>` – nejstarší moravský katastr (obdoba české berní ruly), jmenovité soupisy usedlostí často se jménem hospodáře z r. 1657 po třicetileté válce.
  - **Stabilní katastr a indikační skici (1824–1843)**: `pozemky.py katastr <obec> [--dum CP]` – ČÚZK archiv (císařské otisky) a MZA indikační skici. V indikačních skicách jsou u jednotlivých parcel a domů přímo vepsána jména hospodářů v době zaměření!
- **Hroby, pomníky a vojenská pietní místa (VETS.cz, hřbitovní správy):**
  Pro osoby z 19.–20. století (padlí ve válkách, oběti perzekuce, významní předci, hrobová místa rodiny):
  `python3 -I tools/pieta.py vets hrdina "Příjmení" [--jmeno Jméno]`
  `python3 -I tools/pieta.py vets misto "Obec" [--okres Okres]`
  - **VETS.cz (Spolek pro vojenská pietní místa):** doslovné přepisy nápisů na pomnících padlých v 1. i 2. sv. válce, pamětních deskách a čestných hrobech, přesné GPS souřadnice a fotografie (`pieta.py vets foto <id> out.jpg`).
  - **Hřbitovní databáze a vyhledávače:** `pieta.py hrbitovy <příjmení> [--rok ROK]` vygeneruje přímé vyhledávací odkazy na BillionGraves, Find a Grave a městské správy hřbitovů (Brno, Jihlava, Třebíč, Praha).
- **Školní a obecní kroniky (MZA ARON / SOkA):**
  Pro dokreslení lidského příběhu rodu (požáry, neúrody, cholera, výstavba silnic, spory, zápisy starostů, školní docházka a seznamy žáků):
  `python3 -I tools/kroniky.py hledat "Obec" [--druh obec|skola|vse] [--digitalizovane]`
  - `kroniky.py info <apu_id>`: inventární popis fondu (obsah jednotky, signatura, uložení v archivu).
  - `kroniky.py snimek <apu_id> <n> out.jpg`: přímé stažení snímku digitalizované kroniky v plném rozlišení přes IIPSrv Deepzoom.
- **Ztotožnění míst ověř** podle panství/kraje v zápisu (německé „Langenau“ je v Čechách několikrát – rozhodne „bey Hohenelbe“ = u Vrchlabí).
- **U úředníků, vojáků, lékařů, učitelů, farářů** zkus noviny a ročenky (`reference/portaly.md` → Noviny): ukážou
  kariéru, tedy kde člověk kdy žil, a dají výstřižky na web. U sedláků a řemeslníků na vsi se nevyplatí.
- Matriky před ~1650 skoro nejsou. Pro 17. století: soupis poddaných 1651, berní rula 1654, gruntovní knihy (`reference/portaly.md`).
- Najdeš-li **spornou věc**, kterou nerozhodneš (dvě možná čtení, dva kandidáti), napiš to uživateli s výřezem
  a nech ho rozhodnout; do té doby `prob`.
- **Hodně sporných čtení najednou** (desítky po velkém kole) nedávej do chatu po jednom. Sesbírej je do
  `pracovni/sporna_cteni.json` (klíč zápisu, výřez, otázka, možnosti, tvůj návrh) a udělej z nich jednu stránku,
  kde uživatel u každého klikne na odpověď. Když to jde, použij artefakt s ukládáním odpovědí, jinak HTML soubor
  s tlačítkem „stáhnout odpovědi“. Odpovědi pak zapracuj a zapiš do deníku.

### Pomocníci (subagenti) – šetrně
Na velké kolo (např. „projdi 5 svazků a najdi všechny Nováky“) můžeš pustit 2–4 pomocníky paralelně.
**Strop na pomocníka: asi 12 snímků a 30 kroků** – napiš mu ho do zadání a práci děl na úzké otázky. Jeden snímek stojí
kolem 2 000 tokenů a pomocník ho čte znovu při každém dalším kroku (při 45 snímcích a 70 krocích tvoří snímky polovinu
jeho spotřeby). Pomocník nenačítá skill, `STAV.md` ani `AGENTS.md`; výtah pravidel dostane v zadání.
Každému dej přesné zadání (svazek, snímky, koho hledat, formát výsledku: klíč, snímek, souřadnice zápisu, přepis)
a pravidla výše. Pomocník píše jen do `pracovni/pom_<větev>/`, **do `data/` nikdy**. Zapisuješ ty.
Ať zmíní i zjevně související výskyty (viz krok 6 výše). Výstupy pomocníků v `pracovni/` nemaž, dokud nejsou vytěžené.
**Hlavní konverzace snímky sama nečte.** Každý obrázek v ní zůstane do konce a každý další krok ho čte znovu – je to
nejdražší místo celé práce. Výzkum zadávej **výzkumným pomocníkům na silném modelu** (stejně silném jako hlavní, ne
levném): jedna otázka („zemřela 1880–1895 v Holicích Nováková? kolik jí bylo?“), odpověď textem – výsledek, přepis
zápisu, svazek, snímek, souřadnice výřezu, prošlý rozsah snímků (i při „nic“) a řádek `nečteno: …`.
**Každou stranu čtenou v plném rozlišení pomocník přepíše celou do souboru** `pracovni/pom_<větev>/strany/<svazek>_sn<N>.md`
(všechny zápisy, nejen hledaný), aby se neztratily vedlejší osoby; v odpovědi uvede jen zápisy s příjmeními
z rodokmenu (seznam příjmení mu dej v zadání). Náhledy, kterými jen listuje, nepřepisuje. Pozdější otázky pak řeší
`grep` v přepisech stran místo nového čtení snímků.
**Ověření = čtyři oči, bez obrázku v hlavní konverzaci:** výřez nálezu (`python3 -I tools/overit.py <snímek> x0,y0,x1,y1
pracovni/over`, souřadnice jako zlomky 0–1 šířky a výšky, ne pixely, rozdělí zápis na dvě čitelné poloviny) dostane
**druhý pomocník na silném modelu naslepo** – bez prvního přepisu, jen „přepiš tento zápis“. Ty porovnáš oba texty:
shoda → zápis jako `doc`; rozdíl v jménu, datu, věku nebo domě → třetí slepé čtení, nebo dotaz uživateli. Kontext
(dvě rodiny stejného jména ve vsi, dva Janové na statku) hlídáš ty, pomocník ho nemá. Snímek si v hlavní konverzaci
otevři jen na výslovné přání uživatele.
Prohlížeč může mít najednou jen jeden pomocník, proto dávej přednost nástrojům bez prohlížeče.
**Pomocníky na hledání smíš spouštět na levnějším modelu Gemini na low** (`invoke_subagent` s `Model: "flash_lite"`, případně `Model: "flash"`): procházení knih a nalezení zápisu (svazek, snímek, oddíl, řádek, folio) zvládnou a stojí jen zlomek nákladů. **Přepis celého zápisu levný pomocník nedělá** – v praxi „doplnil“ kněze, kmotry, příčiny smrti, rodiče rodičů i dvojčata, která v zápisu nebyla (12 ze 13 zápisů). Od pomocníka chtěj jen: kde zápis je, výřez z plného rozlišení, co na řádku jistě vidí (jméno, datum, dům) a řádek `nečteno: …`. Přepis a ověření dělají pomocníci na silném modelu (viz výše), zápis do dat ty. Výsledky pomocníka nejdřív prožeň `python3 -I tools/kontrola_vysledku.py <vysledky.md>` (vymyšlená čísla osob, náhledy místo plného rozlišení, výřez z jiné stránky).
Osvědčilo se 3–4 pomocníci na různé větve a archivy současně, jedno kolo ≈ 15–25 nových předků.
Před velkým kolem řekni uživateli, co plánuješ a proč, a nech si to schválit.
Do zadání jim napiš technické pasti z `reference/matriky.md` (macOS: zsh; Windows: `python -I -X utf8`, `magick`).
**V zadání chtěj u každého prošlého snímku, co na něm skutečně přečetl** (rok, první jméno), ne jen „prošel jsem
sn. 20–40“ – pomocník jinak přehlédne, že se mu část snímků nenačetla. Na špatně čitelné knihy (kurent 1. poloviny
19. století, vybledlé snímky) pomocníky nepouštěj, nebo jim dej přesný snímek; ARON a Porta fontium zvládají dobře.

### Kdy přestat
Linie končí, když matriky mlčí (nemanželské dítě bez otce, shořelé knihy, chybějící svazky) nebo když jsi
v 17. století. Zapiš to do `ISSUES`/`archivni_dotazy.md` a jdi na jinou větev. Průběžně aktualizuj `data/STAV.md`
(„Rozpracováno“), aby šlo kdykoli navázat. Sekci drž do asi 5 kB: jen otevřené věci a odkazy na pracovní soubory.
Hotové přesuň do `data/STAV_archiv.md` (podrobnosti jsou v deníku) – `STAV.md` se čte na začátku každé konverzace.

## Fáze 3 – Zajímavosti a Příběh hlavního rodu
Podrobně `reference/pribehy.md`. Tohle je to, co rodina na webu čte nejradši, takže na to nezapomínej a nenechávej to na konec.
- **Zajímavosti** („fun facts“) sbírej **průběžně**: co najdeš při čtení, hned zapiš do `data/zajimavosti.md`
  a řekni uživateli. Po každém kole spusť `python3 -I tools/napady.py`. Najde v datech svatby krátce před porodem,
  rod v jednom domě, sňatky příbuzných, dlouhověkost, epidemie… Ověř a napiš jako krátké příběhy.
- **„Příběh <hlavního rodu>“** (Příběh Novákových): jakmile má hlavní rod ~5 doložených generací, nabídni ho.
  Koncept napiš **do chatu** ke schválení, pak `data/pribeh.md` a v `web.json` menu, tlačítko a úvod.
  Je hlavní věcí na úvodní stránce webu.

## Fáze 4 – Web
Podrobně `reference/web.md`. Ve zkratce:
1. `cd web && npm install` (jednou), pak `npm run nahled` → http://localhost:4321 – ukaž uživateli. V cloudovém prostředí
   (pokud není localhost dostupný) pošli uživateli snímky stránek (headless prohlížeč) nebo nasaď náhled.
2. Nastav `data/web.json`: název, úvod, kontakt a **přihlašovací otázku a odpověď** (web je jen pro rodinu).
3. Po každé změně dat: `npm run data && npm run build` (nebo znovu `npm run nahled`). Hlášky `POZOR: nefunkční odkaz`
   oprav hned (adresa osoby se mění, když se jí doplní rok narození).
   Po každém větším kole hledání zkontroluj i texty úvodu ve `web.json` (`uvod`, `zajimavosti_na_uvodu`) –
   zastarávají („nejstarší předek je…“, počty generací).
4. Před zveřejněním si vezmi `reference/soukromi.md` a projdi s uživatelem, co na webu bude (žijící lidé!).
   Na web jde i „Co hledáme“ (`ISSUES`), poznámky osob a deník. Hlášky `CITLIVÉ` z `kontrola.py` vyřeš s uživatelem;
   co na webu nechat smí, zapiš úryvkem textu do `web.json` → `citlive_schvaleno` (pak se už nehlásí).

## Fáze 5 – Zveřejnění (volitelné, jen se souhlasem)
Výchozí cesta je **Netlify** (zdarma): `npm run nasadit`. Přihlášení k Netlify a první propojení webu jsou interaktivní –
dej je uživateli jako `! npx netlify-cli login` atd. (postup v `reference/web.md`). Pokročilá varianta: vlastní server (Docker/CapRover).
Nic nezveřejňuj bez výslovného souhlasu uživatele.

## Poznámky pro správce skillu
Skill se zlepšuje podle zkušeností lidí, kteří ho používají. Proto **průběžně zapisuj do `poznamky_pro_skill.md`**
(v kořeni projektu), co by se mělo ve skillu zlepšit:
- chyby nástrojů a webu (příkaz, co se stalo, co jsi čekal, jak jsi to obešel),
- nový archiv nebo portál a postup, který fungoval (adresy, pasti, omezení), nástroje, které sis musel napsat sám,
- místa, kde návod mlčel nebo radil špatně, a co uživatel chtěl, ale skill to neuměl (nápady na web apod.).

Piš obecně a stručně. Zapisuj technický postup, ne údaje o rodině (žádní žijící lidé, žádné citlivé věci).
**Ve vhodnou chvíli připomeň uživateli, že může poznámky poslat správci skillu**: po zveřejnění webu, na konci velkého
kola nebo sezení, když je v poznámkách něco podstatného (chyba, nový archiv), a pak zhruba jednou za pár sezení.
Nedělej to pořád. Postup:
1. Projdi poznámky a odstraň nebo zobecni osobní údaje.
2. Vypiš je do chatu celé, jako jeden blok k zkopírování.
3. Požádej uživatele, ať je zkopíruje a pošle e-mailem na **sarsonj@gmail.com** (předmět třeba „Rodokmen skill – poznámky“).
   Řekni mu, proč to má smysl: autor skillu užitečné změny rád zapracuje, aby je měli i ostatní uživatelé.
   A že může připsat i vlastní zkušenosti a postřehy, třeba co se mu líbilo nebo co mu na webu chybělo.
**Nic sám neposílej** (žádný e-mail, formulář ani issue). Rozhoduje uživatel. Až řekne, že poslal, zapiš do
`poznamky_pro_skill.md` „odesláno <datum>“ a další poznámky piš pod tuto čáru.

## Co nikdy
- Nestahuj hromadně z placených služeb (MyHeritage, Ancestry, Geni…) a neobcházej jejich ochranu –
  automatické procházení stovek záznamů vede k **zablokování účtu**. Čti jen to, co uživatel otevře, nebo co potřebuješ jednotlivě.
- Nezadávej za uživatele hesla, platební údaje, neřeš CAPTCHA, nekupuj předplatné.
- Nedávej na web podrobnosti o žijících lidech bez jejich souhlasu.
- Nepřepisuj data bez zálohy v gitu; po větším kroku navrhni uložení (`git add -A && git commit -m "…"`).

## Mapa souborů projektu
| Cesta | K čemu |
|---|---|
| `data/STAV.md` | vstupní bod: pro koho, pravidla, rozpracované věci |
| `data/osoby.py` | předci (Kekulého čísla), rody `LINES`, boční příbuzní `SIDE`, otázky `ISSUES`, `HYPOTEZY`, `SAME` |
| `data/zaznamy.json`, `data/svazky.json` | zápisy z matrik a svazky, ze kterých jsou |
| `data/prepisy.json`, `data/zvyrazneni.json` | přepisy s překlady, rámečky čteného místa |
| `data/research_log.md` | deník všech hledání |
| `data/udaje_od_rodiny.md`, `data/archivni_dotazy.md` | co víme od rodiny; co jen v archivu |
| `data/zajimavosti.md`, `data/pribeh.md`, `data/web.json`, `data/dokumenty.json`, `data/mista.json` | texty a nastavení webu, rodinné fotky, místa na mapě |
| `vyrezy/`, `zdroje/` | výřezy zápisů a dokumentů (web / plné rozlišení), název = klíč + `.jpg` |
| `dokumenty/`, `pracovni/` | originály od rodiny; pracovní soubory (nejdou na web) |
| `poznamky_pro_skill.md` | poznámky pro správce skillu (chyby, nové archivy, nápady) – posílá je uživatel ručně |
| `tools/` | nástroje (kopie ze skillu; aktualizace celého projektu: znovu spustit `novy_projekt.py` na stejnou složku, viz `reference/web.md`) |
| `web/` | web (Astro); data do něj jdou jen přes `npm run data` |

## Nástroje (`tools/`, spouštět z kořene projektu `python3 -I tools/<nástroj>`)
| Nástroj | Co dělá |
|---|---|
| `aron_search.py "Obec"` | najde svazky matrik na ARON (SOA Zámrsk); `"Obec,Fara"` zúží stejnojmenné obce |
| `aron_img.py <apu> info / <snímek> 1 pracovni/x.jpg / link <n> / svazek` | stáhne snímek, dá odkaz, zapíše svazek |
| `trebon.py misto / svazky / rejstrik / snimek / svazek` | matriky SOA Třeboň (jižní Čechy) bez prohlížeče, i rejstříky |
| `portafontium.py fara / info / snimek / link / svazek` | matriky SOA Plzeň (západní Čechy, Porta fontium) bez prohlížeče (faru zjisti na portálu) |
| `ebadatelna.py hledat / matriky / info / snimek / link / svazek`, `a-…` | matriky a archiválie (urbáře, gruntovní knihy) SOA Praha (střední Čechy) |
| `ahmp_search.sh "dotaz"`, `ahmp_scan.py XID snímek out.jpg` | matriky Prahy (AHMP) |
| `policie_prihlasky.py Příjmení [Jméno] [od] [do]`, `karta <pořadí> out.jpg …` | pražské policejní přihlášky 1850–1914 (rodiny s dětmi a adresami), stažení karty |
| `soal_zoomify.py <cesta nebo adresa> 0 out.jpg` | snímek SOA Litoměřice nebo ZA Opava (knihu najdi v prohlížeči; pozor na blokování) |
| `matricula_dl.sh`, `matricula_batch.sh` | snímky z Matriculy (Rakousko…), URL se bere z prohlížeče |
| `anno.py`, `anno_snap.py`, `kramerius.py` | noviny: ANNO (rakouské), Kramerius (české) |
| `ged_import.py strom.ged "Jméno"` | předci z rodinného stromu (GEDCOM) + fronta zápisů |
| `ftb_export.py strom.ftb out.ged ["Jméno" rok linie.md [Photos/]]` | záloha z MyHeritage (.ftb) → GEDCOM + přímá linie s původem údajů |
| `overit.py <snímek> x0,y0,x1,y1 <prefix>` | zápis na dvě čitelné poloviny – ověření čtení (souřadnice = zlomky 0–1) |
| `napady.py` | náměty na zajímavosti z dat |
| `vyrez.py <stránka.jpg> <klíč> x0,y0,x1,y1` | výřez do `zdroje/` a `vyrezy/` |
| `ramecek.py <klíč> x0,y0,x1,y1` | rámeček čteného místa + kontrolní obrázek |
| `mista.py pridej "Obec"` / `mista.py` | místa pro mapu (souřadnice z OpenStreetMap) |
| `zapis.py <soubor> <klíč> <vstup.json> [--sloucit]` | přidá / změní položku v `zaznamy`, `svazky`, `prepisy`… beze změny formátu |
| `kontrola.py` | kontrola dat; hlásí i citlivé údaje na webu a kdy psát příběh |
| `export_web.py` | data → web (volá ho `npm run data`) |
| `fan_chart.py vystupy/` | vějíř předků jako plakát k tisku |
| `sit.py` | sdílené HTTP/1.1 spojení (keep-alive, TLS reuse, gzip, šetrné pauzy pro archivy) |
| `mza.py hledat / fary / knihy / info / snimek` | přímé stahování a vyhledávání z MZA Brno (Acta Publica) bez prohlížeče |
| `najdi_vyrez.py <stránka.jpg> <výřez.jpg>` | bleskové nalezení polohy výřezu ve velké stránce (OpenCV FFT, 0.5 s; souřadnice 0..1 pro vyrez.py a ramecek.py) |
| `dum.py "Obec" <čp> [--zapis]` | geokódování konkrétního domu (čp.) pro mapu webu |
| `kontrola_dat.py` | kontrola nemožných a podezřelých dat, věků a chronologie (chybně přečtené číslice) |
| `kontrola_vysledku.py <vysledky.md>` | kontrola výsledků pomocníka (vymyšlená `#N`, náhledy, výřez z jiné stránky, chybějící `nečteno:`) |
| `roky.py [--zapis]` | automatické doplnění a kontrola let života (pole `y`) podle genealogických zvyklostí |
| `gedcom.py` | export dat do standardního formátu GEDCOM 5.5.1 (pro MyHeritage, Gramps, Ancestry) |
| `smoke_test.py` | diagnostika dostupnosti všech archivních a online nástrojů |
| `pozemky.py predci / hledat / knihy / info / rejstrik / snimek / katastr / lanove` | pozemkové a gruntovní knihy v MZA ARON, lánové rejstříky D 1, stabilní katastr a indikační skici |
| `pieta.py vets hrdina / misto / detail / foto / hrbitovy` | hroby, pomníky a vojenská pietní místa (VETS.cz, městské hřbitovy) |
| `kroniky.py hledat / info / snimek` | školní a obecní kroniky v MZA ARON (SOkA Jihlava, Třebíč...) |
| `prameny.py hledat kramerius / vua / cevh`, `fronta navrhni / spustit / vysledky` | noviny, seznamy ztrát 1914–1919, padlí v 1. sv. válce, válečné hroby |
| `arolsen.py hledat / karta` | Arolsen Archives: nucené nasazení, oběti války a perzekuce |
| `scitani.py plan / najdi / hlavicky / snimek` | sčítání lidu 1857–1921 (Morava, portál MZA) |

## Pozemkové knihy a gruntovnice
Než otevřeš pozemkovou nebo gruntovní knihu, přečti `reference/pozemkove_knihy.md` (postup od rejstříku k foliu).
