import sys
import time
from pathlib import Path

import requests
import serial

API_URL = "http://127.0.0.1:8000/predict"
PORT = "rfc2217://localhost:4000"
BAUD = 115200


def classifier(chemin):
    with open(chemin, "rb") as f:
        r = requests.post(API_URL, files={"image": (Path(chemin).name, f, "image/jpeg")}, timeout=30)
    r.raise_for_status()
    return r.json()


def lire_jusqua(ser, test, timeout):
    """Lit les lignes complètes jusqu'à ce que test(ligne) soit vrai. Renvoie la ligne ou None."""
    fin = time.time() + timeout
    while time.time() < fin:
        ligne = ser.readline().decode("utf-8", errors="replace").strip()
        if not ligne:
            continue
        if not ligne.startswith("NIVEAUX:"):
            print(f"   [ARDUINO] {ligne}")
        if test(ligne):
            return ligne
    return None


def traiter(ser, chemin):
    print(f"\n===== {Path(chemin).name} =====")
    res = classifier(chemin)
    print(f"   [IA] {res['categorie']} (confiance {res['confiance']:.2f}) -> {res['commande']}")

    ser.reset_input_buffer()
    print("   >>> Cliquez sur le BOUTON VERT dans la simulation (déchet détecté)...")
    if not lire_jusqua(ser, lambda l: "DECHET_DETECTE" in l, 60):
        print("   [ECHEC] Aucun déchet détecté.")
        return False

    ser.write((res["commande"] + "\n").encode())
    rep = lire_jusqua(ser, lambda l: l.startswith("OK:") or l.startswith("ERR:"), 8)
    if rep is None or rep.startswith("ERR:"):
        print("   [REFUSE] Commande refusée ou sans réponse.")
        return False

    if not lire_jusqua(ser, lambda l: l == "OK:CYCLE_TERMINE", 30):
        print("   [ECHEC] Cycle non terminé.")
        return False

    print("   [SUCCES] Déchet trié.")
    return True


if len(sys.argv) < 2:
    print('Usage : python passerelle_visuelle.py "photo1.jpg" "photo2.jpg"')
    sys.exit(1)

try:
    ser = serial.serial_for_url(PORT, baudrate=BAUD, timeout=0.3)
except Exception as e:
    print("Connexion impossible :", repr(e))
    print("La simulation VS Code est-elle lancée (après modification de wokwi.toml) ?")
    sys.exit(1)

bilan = {}
try:
    for photo in sys.argv[1:]:
        bilan[Path(photo).name] = traiter(ser, photo)
finally:
    ser.close()

print("\n===== BILAN =====")
for nom, ok in bilan.items():
    print(f"{nom} : {'TRIE' if ok else 'NON TRIE'}")
    