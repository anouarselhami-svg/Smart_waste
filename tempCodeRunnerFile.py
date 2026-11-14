
import os
import time
import threading
from pathlib import Path
from wokwi_client import WokwiClientSync

BASE_DIR = Path(__file__).resolve().parent
DIAGRAM = BASE_DIR / "diagram.json"
FIRMWARE = BASE_DIR / "build" / "smartWaste.ino.hex"

TOKEN = os.getenv("WOKWI_CLI_TOKEN")

if not TOKEN:
    raise RuntimeError("Token Wokwi introuvable.")

client = WokwiClientSync(TOKEN)

messages = []
lock = threading.Lock()

def recevoir_ligne(data):
    ligne = data.decode("utf-8", errors="replace").strip()

    if ligne:
        print(f"[ARDUINO] {ligne}")
        with lock:
            messages.append(ligne)

def contient(texte):
    with lock:
        return any(texte in msg for msg in messages)

def attendre(texte, timeout=15):
    debut = time.time()

    while time.time() - debut < timeout:
        if contient(texte):
            return True
        time.sleep(0.1)

    return False

def effacer_messages():
    with lock:
        messages.clear()

def appuyer_bouton(bouton, duree=0.5):
    client.set_control(bouton, "pressed", True)
    time.sleep(duree)
    client.set_control(bouton, "pressed", False)

def tester_categorie(categorie):
    print(f"\n===== TEST {categorie} =====")

    # Attendre une détection réelle du déchet.
    effacer_messages()
    print("[PYTHON] Détection du déchet...")
    appuyer_bouton("btnDechet")

    if not attendre("DECHET_DETECTE", 8):
        print("[ECHEC] Détection non confirmée.")
        return False

    print("[PYTHON] Déchet détecté.")

    # Envoyer la catégorie après confirmation.
    effacer_messages()
    print(f"[PYTHON] Envoi : {categorie}")
    client.serial_write(categorie + "\n")

    if not attendre("OK:" + categorie, 8):
        print("[ECHEC] Accusé de réception absent.")
        return False

    print("[OK] Commande acceptée.")

    # Attendre la fin réelle du cycle mécanique.
    if not attendre("OK:CYCLE_TERMINE", 25):
        print("[ECHEC] Cycle non terminé dans le délai.")
        return False

    print(f"[SUCCES] Cycle {categorie} terminé.")
    time.sleep(2)
    return True

try:
    print("1. Connexion...")
    print(client.connect())

    print("\n2. Chargement...")
    client.upload_file("diagram.json", DIAGRAM)
    client.upload_file("smartWaste.ino.hex", FIRMWARE)

    print("\n3. Démarrage...")
    client.start_simulation(firmware="smartWaste.ino.hex")

    client.serial_monitor(recevoir_ligne)
    time.sleep(2)

    print("\n4. Test PING")
    effacer_messages()
    client.serial_write("PING\n")
    print("PONG :", attendre("PONG", 5))

    resultats = {}

    for categorie in ["PLASTIC", "PAPER", "METAL", "UNKNOWN"]:
        resultats[categorie] = tester_categorie(categorie)

    print("\n===== BILAN FINAL =====")

    for categorie, resultat in resultats.items():
        print(f"{categorie} : {'REUSSI' if resultat else 'ECHEC'}")

    print("\nTest RESET")
    effacer_messages()
    client.serial_write("RESET\n")
    print("RESET :", attendre("OK:RESET", 5))

except Exception as erreur:
    print("\nERREUR :", erreur)

finally:
    client.disconnect()
    print("\nDéconnexion terminée.")
