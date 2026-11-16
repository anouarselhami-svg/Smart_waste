import sys
import time
import threading
from pathlib import Path

import cv2
import requests
import serial

ADRESSE = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.25:8080/video"  # votre adresse + /video
API_URL = "http://127.0.0.1:8000/predict"
PORT = "rfc2217://localhost:4000"
BAUD = 115200

SEUIL_CHANGEMENT = 0.03   # 3 % de l'image modifiée = objet présent
DUREE_STABLE = 1.0        # secondes d'objet immobile avant capture
DUREE_RETRAIT = 2.0       # secondes sans objet avant de se réarmer


class Camera:
    """Lit le flux en continu pour toujours avoir l'image la plus récente."""
    def __init__(self, source):
        self.cap = cv2.VideoCapture(source)
        self.frame = None
        self.lock = threading.Lock()
        self.actif = True
        threading.Thread(target=self._boucle, daemon=True).start()

    def _boucle(self):
        while self.actif:
            ok, img = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = img
            else:
                time.sleep(0.05)

    def get(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.actif = False
        self.cap.release()


def preparer(img):
    petit = cv2.resize(img, (320, 240))
    return cv2.GaussianBlur(cv2.cvtColor(petit, cv2.COLOR_BGR2GRAY), (7, 7), 0)


def fraction_changee(fond, courant):
    diff = cv2.absdiff(fond, courant)
    _, masque = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(masque) / masque.size


def classifier(img):
    h, w = img.shape[:2]
    if w > 640:
        img = cv2.resize(img, (640, int(h * 640 / w)))
    ok, buf = cv2.imencode(".jpg", img)
    r = requests.post(API_URL, files={"image": ("objet.jpg", buf.tobytes(), "image/jpeg")}, timeout=30)
    r.raise_for_status()
    return r.json()


def attendre(ser, test, timeout):
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


def traiter(ser, img):
    cv2.imwrite("dernier_objet.jpg", img)
    res = classifier(img)
    print(f"   [IA] {res['categorie']} (confiance {res['confiance']:.2f}) -> {res['commande']}")

    ser.reset_input_buffer()
    ser.write(b"DETECT\n")
    rep = attendre(ser, lambda l: "DECHET_DETECTE" in l or l.startswith("ERR:"), 5)
    if rep is None or rep.startswith("ERR:"):
        print("   [ECHEC] DETECT non reconnu : la commande est-elle dans smartWaste.ino ?")
        return False

    ser.write((res["commande"] + "\n").encode())
    rep = attendre(ser, lambda l: l.startswith("OK:") or l.startswith("ERR:"), 8)
    if rep is None or rep.startswith("ERR:"):
        print("   [REFUSE] Commande refusee ou sans reponse.")
        ser.write(b"RESET\n")
        return False

    if not attendre(ser, lambda l: l == "OK:CYCLE_TERMINE", 30):
        print("   [ECHEC] Cycle non termine.")
        return False

    print("   [SUCCES] Dechet trie.")
    return True


def texte(img, msg, couleur):
    cv2.putText(img, msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, couleur, 2)


try:
    ser = serial.serial_for_url(PORT, baudrate=BAUD, timeout=0.1)
except Exception as e:
    sys.exit(f"Connexion Arduino impossible : {e!r}\nLa simulation VS Code est-elle lancee ?")

cam = Camera(ADRESSE)
print("Attente de la camera...")
while cam.get() is None:
    time.sleep(0.1)

print("Ne mettez AUCUN objet : memorisation du fond dans 2 s...")
time.sleep(2)
fond = preparer(cam.get())
print("Fond memorise. Posez un objet. (B = refaire le fond, Q = quitter)")

etat = "ARMEE"
debut = None
sans_objet_depuis = None
dernier_msg = ("", (255, 255, 255))

try:
    while True:
        img = cam.get()
        frac = fraction_changee(fond, preparer(img))
        maintenant = time.time()

        if etat == "ARMEE":
            if frac > SEUIL_CHANGEMENT:
                if debut is None:
                    debut = maintenant
                elif maintenant - debut >= DUREE_STABLE:
                    print("\n>>> Objet detecte")
                    etat = "TRAITEMENT"
                    texte_aff = ("TRAITEMENT...", (0, 165, 255))
                    cv2.imshow("SMART BIN - camera", img)
                    cv2.waitKey(1)
                    try:
                        traiter(ser, cam.get())
                    except Exception as e:
                        print("   [ERREUR]", repr(e))
                    print("   Retirez l'objet...")
                    etat = "RETRAIT"
                    sans_objet_depuis = None
                    debut = None
            else:
                debut = None
            dernier_msg = ("PRET - posez un objet", (0, 200, 0)) if debut is None else ("OBJET DETECTE...", (0, 165, 255))

        elif etat == "RETRAIT":
            if frac < SEUIL_CHANGEMENT:
                if sans_objet_depuis is None:
                    sans_objet_depuis = maintenant
                elif maintenant - sans_objet_depuis >= DUREE_RETRAIT:
                    print("Pret pour un nouvel objet.")
                    etat = "ARMEE"
            else:
                sans_objet_depuis = None
            dernier_msg = ("RETIREZ L'OBJET", (0, 0, 255))

        texte(img, f"{dernier_msg[0]}  ({frac*100:.1f} %)", dernier_msg[1])
        cv2.imshow("SMART BIN - camera", img)
        k = cv2.waitKey(30) & 0xFF
        if k == ord("q"):
            break
        if k == ord("b"):
            fond = preparer(cam.get())
            print("Fond memorise de nouveau.")
finally:
    cam.stop()
    ser.close()
    cv2.destroyAllWindows()