#!/usr/bin/env python3
"""Bleskové nalezení výřezu ve velké stránce pomocí OpenCV (FFT matchTemplate).

Použití:
  tools/najdi_vyrez.py <stranka.jpg> <vyrez.jpg> [--vyrez-ven <cesta.jpg>]

Vypíše:
  - Pixely: x, y, šířka, výška
  - Relativní souřadnice (0..1) pro tools/vyrez.py a tools/ramecek.py: x0,y0,x1,y1
  - Procento shody (100 % = identický vzor; výřez musí mít stejné měřítko jako stránka)
"""
import os
import sys

# Přednostně spustit ve virtuálním prostředí .venv, kde je nainstalované opencv
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_py = os.path.join(root, ".venv", "bin", "python3")
if os.path.exists(venv_py) and os.path.abspath(sys.executable) != os.path.abspath(venv_py):
    os.execv(venv_py, [venv_py, os.path.abspath(__file__)] + sys.argv[1:])

try:
    import cv2
except ImportError:
    sys.exit("Chybí balíček opencv. Nainstalujte ho do projektu: python3 -m venv .venv && .venv/bin/pip install opencv-python-headless")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    page_path = sys.argv[1]
    tpl_path = sys.argv[2]

    out_crop = None
    if "--vyrez-ven" in sys.argv:
        idx = sys.argv.index("--vyrez-ven")
        if idx + 1 < len(sys.argv):
            out_crop = sys.argv[idx + 1]

    if not os.path.exists(page_path):
        sys.exit(f"Chyba: Soubor stránky neexistuje: {page_path}")
    if not os.path.exists(tpl_path):
        sys.exit(f"Chyba: Soubor výřezu neexistuje: {tpl_path}")

    # Načtení v odstínech šedi pro maximální rychlost
    page = cv2.imread(page_path, cv2.IMREAD_GRAYSCALE)
    tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)

    if page is None:
        sys.exit(f"Nelze načíst obrázek: {page_path}")
    if tpl is None:
        sys.exit(f"Nelze načíst výřez: {tpl_path}")

    H, W = page.shape[:2]
    h, w = tpl.shape[:2]

    if w > W or h > H:
        sys.exit(f"Výřez ({w}x{h}) je větší než prohledávaná stránka ({W}x{H})!")

    # FFT křížová korelace
    res = cv2.matchTemplate(page, tpl, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, (x0, y0) = cv2.minMaxLoc(res)

    x1 = x0 + w
    y1 = y0 + h

    rel_x0 = x0 / W
    rel_y0 = y0 / H
    rel_x1 = x1 / W
    rel_y1 = y1 / H

    print(f"Shoda: {max_val * 100:.1f} %")
    print(f"Pozice (pixely): x={x0}, y={y0}, w={w}, h={h}")
    print(f"Rozsah (pixely): x0={x0}, y0={y0}, x1={x1}, y1={y1}")
    print(f"Pro tools/vyrez.py a tools/ramecek.py (0..1):")
    print(f"{rel_x0:.4f},{rel_y0:.4f},{rel_x1:.4f},{rel_y1:.4f}")

    if out_crop:
        # Pokud uživatel chtěl uložit výřez pro vizuální kontrolu
        crop = page[y0:y1, x0:x1]
        cv2.imwrite(out_crop, crop)
        print(f"Kontrolní výřez uložen do: {out_crop}")


if __name__ == "__main__":
    main()
