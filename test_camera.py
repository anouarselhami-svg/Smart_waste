import cv2, sys

indice = int(sys.argv[1]) if len(sys.argv) > 1 else 0
cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise SystemExit(f"Camera {indice} introuvable")

for _ in range(30):          # laisse l'exposition se stabiliser
    cap.read()

print(f"Camera {indice} - ESPACE: photo, Q: quitter")
n = 0
while True:
    ok, img = cap.read()
    if not ok:
        print("Lecture impossible")
        break
    cv2.imshow("Webcam", img)
    k = cv2.waitKey(1) & 0xFF
    if k == ord(" "):
        n += 1
        cv2.imwrite(f"capture{n}.jpg", img)
        print(f"Photo enregistrée : capture{n}.jpg  (moyenne luminosité : {img.mean():.1f})")
    elif k == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()