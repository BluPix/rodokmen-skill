# Projekt rodokmenu

Tohle je projekt rodokmenu vedený skillem **rodokmen**. Na začátku každé konverzace:
1. Načti skill `rodokmen` (pokud ještě není načtený).
2. Přečti `data/STAV.md` – stav, pravidla a co je rozpracované – a posledních 5 řádků `data/research_log.md` (`tail -n 5`, deník má dlouhé řádky).
3. Pokračuj tam, kde se skončilo. Komunikuj česky, stručně a srozumitelně pro člověka bez zkušeností s genealogií a programováním.
4. Pro pomocníky (subagenty) na **hledání** ve svazcích (který snímek, oddíl, rok, řádek, folio) smíš použít levnější Gemini model na low (`Model: "flash_lite"` nebo `"flash"`). **Přepis zápisu levný pomocník nedělá** – jen napíše, kde zápis je, a co na řádku jistě vidí (jméno, datum, dům). Přepis, ověření a zápisy dělá hlavní model.
5. Co by šlo ve skillu zlepšit (chyby nástrojů, nové archivy, nápady), zapisuj do `poznamky_pro_skill.md` – viz skill, sekce „Poznámky pro správce skillu“.
6. Vždy dodržuj metodiku a pravidla uvedená v `AGENTS.md`.
