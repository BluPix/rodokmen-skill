# Jak správně bádat v pozemkových knihách a gruntovnicích

Přesunuto ze `SKILL.md`. Čti, než otevřeš pozemkovou nebo gruntovní knihu.
Pozemkové knihy obsahují trhové smlouvy (Kaufvertrag / Nowý Zápis), předání usedlostí, vyplacení sourozenců a výminky.
**Nikdy nestahuj snímek 1 jako „doklad“!** Snímky 1–3 jsou moderní archivní desky nebo úvodní dekrety.
Správný postup:
0. **Koho hledám:** `python3 -I tools/pozemky.py predci "Obec"` vypíše, kdo z rodokmenu v obci žil, v kterém domě a kdy. Bez předka v obci kniha rodokmenu nic nedá. Knihu vyber podle obce **domu** předka (ne podle farnosti) a podle let, kdy tam hospodařil.
1. **Kniha:** Vyhledej knihy pro danou obec (`python3 -I tools/pozemky.py knihy "Obec"`). Zkontroluj časový rozsah a zda má digitalizované snímky online.
2. **Rejstřík (index):** Stáhni náhledy úvodních snímků knihy (`python3 -I tools/pozemky.py rejstrik <apu_id> [--od 2] [--do 8]`). Staré knihy jsou indexovány podle vsí a uvádějí jména hospodářů a čísla **listů (folií)**, např. *fol. 111*.
3. **Nalezení folia:** Číslo snímku odpovídá přibližně: *číslo folia + počet listů předsádky/rejstříku*. Většina gruntovnic má gruntu vyhrazen blok 8–10 listů.
4. **Trhová smlouva / Zápis:** Vyhledej smlouvu, kde předek usedlost kupuje nebo přejímá (`Nowý Zápis`). Stáhni plné rozlišení (`snimek <apu_id> <číslo>`). Přečti a přepiš:
   - datum a rychtáře / konšely obce,
   - kupní cenu v rýnských zlatých (fl.), hotovost (závdavek na ruku),
   - roční splátky a komu se vyplácely (sirotčí podíly předchozího hospodáře, sourozenci),
   - výminek (*Wýminek*): kolik měřic pole ve kterých tratích, kopy naddělkem, část zahrady, loučka u potoka, naturální dávky,
   - inventář živnosti: železný vůz, rádlo s železem, brány, nářadí, dobytek.
5. **Roční splátky (rathunky / kvitance):** Na následujících listech sleduj roční zápisy o splátkách. Ukazují, jak dlouho předek hospodařil a v kterém roce usedlost postoupil další generaci. Srovnej se sňatky a úmrtími v matrice.
6. **Ztotožnění a zápis:** nález patří předkovi jen při shodě jména, domu a let s fakty z kroku 0 – jinak je to stopa do deníku, ne „doložená kontinuita rodu“. Číslo osoby `#N` piš jen ověřené v `osoby.py`. Zápis druhu `J` s výřezem z plného rozlišení; z náhledů rejstříku (`…_nahled.jpg`) se nic necituje. Kurent 18. století je těžký: nejistá slova „(?)“, nečitelné „[…]“, nic nedoplňovat.
