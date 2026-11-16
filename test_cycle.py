import serial, time

ser = serial.serial_for_url("rfc2217://localhost:4000", baudrate=115200, timeout=0.3)

def lire(duree):
    fin = time.time() + duree
    lignes = []
    while time.time() < fin:
        l = ser.readline().decode(errors="replace").strip()
        if l and not l.startswith("NIVEAUX:"):
            print("   [ARDUINO]", l)
            lignes.append(l)
    return lignes

ser.reset_input_buffer()
print(">>> Cliquez MAINTENANT sur le bouton vert (30 s)...")
lignes = lire(30)

if not any("DECHET_DETECTE" in l for l in lignes):
    print("\nRESULTAT : le clic n'a PAS ete recu (mauvais bouton ou clic non pris en compte).")
else:
    print("\nClic recu. Envoi de PLASTIC:0.95")
    ser.write(b"PLASTIC:0.95\n")
    lire(10)

ser.close()