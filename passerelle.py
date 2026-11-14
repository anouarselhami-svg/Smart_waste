import os
import sys
import time
import traceback
import threading
from pathlib import Path

import requests
from wokwi_client import WokwiClientSync

BASE_DIR = Path(__file__).resolve().parent
DIAGRAM = BASE_DIR / "diagram.json"
FIRMWARE = BASE_DIR / "build" / "smartWaste.ino.hex"
API_URL = "http://127.0.0.1:8000/predict"

TOKEN = os.getenv("WOKWI_CLI_TOKEN")
if not TOKEN:
    raise RuntimeError("Token Wokwi introuvable.")

client = WokwiClientSync(TOKEN)
messages = []
lock = threading.Lock()


tampon = ""

def recevoir_ligne(data):
    """Reconstitue les lignes complètes, même si le texte arrive en morceaux."""
    global tampon
    tampon += data.decode("utf-8", errors="replace")
    while "\n" in tampon:
        ligne, tampon = tampon.split("\n", 1)
        ligne = ligne.strip()
        if ligne:
            print(f"   [ARDUINO] {ligne}")
            with lock:
                messages.append(ligne)

def attendre(texte, timeout=15):
    debut = time.time()
    while time.time() - debut < timeout:
        with lock:
            if any(texte in m for m in messages):
                return True
        time.sleep(0.1)
    return False


def effacer():
    with lock:
        messages.clear()


def appuyer_bouton(nom, duree=0.5):
    client.set_control(nom, "pressed", True)
    time.sleep(duree)
    client.set_control(nom, "pressed", False)


def classifier(chemin_image):
    """Envoie l'image à l'API, renvoie le JSON de réponse."""
    with open(chemin_image, "rb") as f:
        r = requests.post(API_URL, files={"image": (Path(chemin_image).name, f, "image/jpeg")}, timeout=30)
    r.raise_for_status()
    return r.json()


def traiter_dechet(chemin_image):
    print(f"\n===== {Path(chemin_image).name} =====")

    # 1) Classification par l'IA
    res = classifier(chemin_image)
    print(f"   [IA] {res['categorie']} (confiance {res['confiance']:.2f}) -> commande {res['commande']}")

    # 2) Détection du déchet (bouton IR 1)
    effacer()
    appuyer_bouton("btnDechet")
    if not attendre("DECHET_DETECTE", 8):
        print("   [ECHEC] Détection non confirmée.")
        return False

    # 3) Envoi de la commande à l'Arduino
    effacer()
    client.serial_write(res["commande"] + "\n")

    # 4) Le résultat : tri, refus (confiance faible) ou erreur
    debut = time.time()
    while time.time() - debut < 8:
        with lock:
            if any(m.startswith("OK:") and m != "OK:CYCLE_TERMINE" for m in messages):
                break
            if any(m.startswith("ERR:") for m in messages):
                print("   [REFUSE] L'Arduino a refusé la commande.")
                return False
        time.sleep(0.1)
    else:
        print("   [ECHEC] Pas de réponse de l'Arduino.")
        return False

    if not attendre("OK:CYCLE_TERMINE", 25):
        print("   [ECHEC] Cycle non terminé.")
        return False

    print("   [SUCCES] Déchet trié.")
    return True


if len(sys.argv) < 2:
    print("Usage : python passerelle.py photo1.jpg [photo2.jpg ...]")
    sys.exit(1)

try:
    print("1. Connexion à Wokwi...")
    client.connect()
    client.upload_file("diagram.json", DIAGRAM)
    client.upload_file("smartWaste.ino.hex", FIRMWARE)
    client.start_simulation(firmware="smartWaste.ino.hex")
    client.serial_monitor(recevoir_ligne)
    time.sleep(2)

    bilan = {}
    for photo in sys.argv[1:]:
        bilan[Path(photo).name] = traiter_dechet(photo)
        time.sleep(1)

    print("\n===== BILAN =====")
    for nom, ok in bilan.items():
        print(f"{nom} : {'TRIE' if ok else 'NON TRIE'}")

except Exception as e:
    print("\nERREUR :", repr(e))
    traceback.print_exc()
finally:
    client.disconnect()
    print("\nDéconnexion terminée.")