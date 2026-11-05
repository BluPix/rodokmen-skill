# Začátek projektu: příprava (Fáze 0) a rozhovor s rodinou (Fáze 1)

Přesunuto ze `SKILL.md`, aby se nenačítalo v každé konverzaci. Čti jen u nového projektu nebo před rozhovorem s rodinou.

## Fáze 0 – Příprava (jednou)
1. Zkontroluj nástroje: `python3 --version` (≥ 3.9), `node --version` (≥ 20), `magick -version` (ImageMagick 7; je-li jen
   verze 6 s příkazem `convert`, nástroje ji mimo Windows použijí samy), `git --version`.
   Co chybí, pomoz nainstalovat (macOS: Homebrew `brew install python node imagemagick git`; Windows: winget / instalátory
   z python.org, nodejs.org, imagemagick.org). **winget na Windows vždy s plnými přepínači**, jinak spadne na otázce
   ke zdroji msstore („Error reading input in prompt“): `winget install --id <balík> --source winget
   --accept-source-agreements --accept-package-agreements` (balíky `Python.Python.3.12` + `--scope user`,
   `OpenJS.NodeJS.LTS`, `ImageMagick.ImageMagick`, `Git.Git`). Instalace systémových věcí nech uživatele potvrdit;
   interaktivní příkazy mu dej s předponou `!`, ať je spustí sám.
   **Windows:** `python3` tam bývá jen nefunkční alias z Microsoft Store („Python nebyl nalezen“) – zkontroluj
   `python --version` (případně `py -3 --version`) a ve všech příkazech tohoto skillu místo `python3 -I` používej
   `python -I -X utf8` (funguje-li jen launcher, tak `py -3 -I -X utf8`). Zkontroluj **který** Python to je
   (`which -a python`) – může být přibalený k jinému programu (Inkscape, GIMP…) a nemít certifikáty. Ověř https:
   `python -I -c "import urllib.request; urllib.request.urlopen('https://aron.vychodoceskearchivy.cz')"`. Když spadne
   na `CERTIFICATE_VERIFY_FAILED`, nainstaluj běžný Python (winget výše) a volej ho plnou cestou
   `"$LOCALAPPDATA/Programs/Python/Python312/python.exe"` (do PATH se dostane až po restartu terminálu / prostředí). `-I` ignoruje proměnnou `PYTHONUTF8`;
   bez `-X utf8` je výstup do roury nebo souboru v kódování Windows (cp1250) – čeština se rozbije a některé nástroje
   spadnou na znacích jako „→“. ImageMagick: `winget install --id ImageMagick.ImageMagick --source winget --accept-source-agreements --accept-package-agreements`; do PATH se dostane až po
   restartu terminálu / prostředí (do té doby před příkazy `export PATH="/c/Program Files/ImageMagick-7…:$PATH"` s přesnou složkou
   z `C:\Program Files`). **Nikdy `convert`** (to je systémový nástroj Windows), vždy `magick`. Skripty `.sh` spouštěj
   přes Git Bash (`bash tools/…`). Delší jednorázové skripty v Pythonu nepiš jako heredoc (`python - <<EOF`), v Git Bash
   občas spadnou na „unexpected EOF“ – zapiš je do souboru v `pracovni/` a spusť. Tato pravidla zapiš hned po založení projektu do jeho `GEMINI.md` a `CLAUDE.md`, ať platí i příště
   (a dej je do zadání i pomocníkům, viz `reference/matriky.md`).
2. Zeptej se, kde má projekt být (navrhni `~/Rodokmen`), a založ ho:
   `python3 -I SKILL_DIR/tools/novy_projekt.py <složka>`
   Chce-li uživatel nejdřív vidět, jak web vypadá, založ vedle ukázku: `… novy_projekt.py ~/Rodokmen-ukazka --ukazka`,
   pak `cd web && npm install && npm run nahled` a pošli mu odkaz http://localhost:4321.
3. V projektu `git init` a první uložení (git = historie změn, kdyby se něco pokazilo). Doporuč pokračovat
   **z této složky** (soubor `GEMINI.md` / `CLAUDE.md` v ní zajistí, že příště navážeš).
4. Vyplň v `data/STAV.md` sekci „Pro koho“ a v `data/web.json` název webu („Rodokmen Novákových“),
   jakmile znáš příjmení výchozí osoby (šablona je prázdná).

## Fáze 1 – Rozhovor s rodinou (nejcennější hodina celého projektu)
Cíl: znát co nejvíc o 3–4 generacích nazpět, než sáhneš do matrik.
- Ptej se postupně (ne dotazníkem naráz): výchozí osoba (pro koho rodokmen je – on sám, partner, dítě?), rodiče,
  prarodiče, pradědečci: **jména, rodná příjmení žen, roky a místa narození, sňatky, úmrtí (a kde jsou pohřbeni), řemesla, domy (čísla popisná!)**.
- Požádej o dokumenty: rodné a oddací listy, domovské listy, parte, fotky (i náhrobků), rodinné kroniky, paměti, staré dopisy,
  výpisy z MyHeritage/Geni od příbuzných. Ať je dá do `dokumenty/`. Přečti je celé (PDF/fotky) a vytěž.
- Doporuč zeptat se nejstarších žijících příbuzných – teď, dokud to jde. Nabídni seznam otázek.
- **Příbuzenství ber doslova, jak ho rodina řekla** („pradědeček babičky“ ≠ „otec babičky“) – nikdy ho neopravuj podle
  toho, co se ti hodí do dat. Při nejasnosti se zeptej. Ztotožnění jen podle křestního jména veď jako `prob` s poznámkou.
- Vše zapiš: `data/udaje_od_rodiny.md` (kdo co řekl), osoby do `data/osoby.py` se stavem `fam`
  (formát v hlavičce souboru a v `reference/data.md`). Žijící lidé jen jméno a rok narození.
- **Rodinný strom jako soubor GEDCOM** (`.ged`, export z MyHeritage/Geni/FamilySearch): `python3 -I tools/ged_import.py
  dokumenty/strom.ged "Jméno Příjmení"` vypíše předky s čísly, všechny události a poznámky a **frontu zápisů**
  (nejmladší známá událost u každého předka, a jestli už je v archivu). `--osoby` dá kostru pro `osoby.py`.
  Poznámky ve stromu bývají plné rodinných historek. Přečti je a vytěž do `udaje_od_rodiny.md`.
  Starší strom z **Brother's Keeper** (kódování ANSI a česká data „SRPEN 1945“ nástroj převede sám): místa tam bývají
  v 6. pádě („Táboře“) – do `osoby.py` je přepiš do 1. pádu. Kořenem takového stromu často nejsou uživatel, ale jeho děti
  (oba rody) – výchozí osobu proto vyber jménem.
- **Záloha stromu z MyHeritage** (ZIP se souborem `<strom>.ftb` a složkou `Photos/` – to není GEDCOM, ale databáze):
  rozbal do vlastní složky v `dokumenty/` (bývá velká – dej ji do `.gitignore`), pak
  `python3 -I tools/ftb_export.py <strom.ftb> dokumenty/strom.ged "Jméno Příjmení" <rok narození> pracovni/prima_linie.md <složka Photos>`.
  Vznikne GEDCOM pro `ged_import.py` (bez adres, e-mailů a telefonů) a přehled přímé linie s **původem údajů** – u každé
  osoby, ze kterých cizích stromů (Smart Match) či zdrojů její údaje přišly. Do `osoby.py`: osoba bez cizí citace = `fam`,
  doložená jen cizími stromy = `mh`. Údaje ze stromů (i Smart Match) jsou jen vodítko k zápisu – datum a číslo domu tě
  dovedou na stránku, ale **jména vždy ověř v zápisu** (skutečná chyba: „sňatek“ ze Smart Match byl jiný pár ze stejného domu). V přehledu jsou i připojené skeny (opisy matrik, parte, domovské listy) – přečti je,
  bývají to nejcennější rodinné doklady.
- Strom, který si rodina vede sama, má stav `fam`. Cizí stromy z internetu (stromy jiných lidí na MyHeritage, Geni,
  FamilySearch) jsou **jen vodítko**, stav `mh`, nikdy `doc`.
