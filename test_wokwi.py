
import os
from wokwi_client import WokwiClientSync

token = os.getenv("WOKWI_CLI_TOKEN")

if not token:
    raise SystemExit("ERREUR : token Wokwi introuvable.")

client = WokwiClientSync(token)

try:
    result = client.connect()
    print("Connexion Wokwi réussie !")
    print("Informations du serveur :", result)
finally:
    client.disconnect()
