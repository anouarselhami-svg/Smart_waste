import cv2

for indice in range(5):
    for nom, backend in [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW)]:
        cap = cv2.VideoCapture(indice, backend)
        if not cap.isOpened():
            continue
        lum = 0
        for _ in range(40):
            ok, img = cap.read()
            if ok:
                lum = img.mean()
        print(f"indice {indice} | {nom} | luminosité {lum:.1f}")
        cap.release()