import io
import torch
import torch.nn as nn
from fastapi import FastAPI, File, UploadFile, HTTPException
from PIL import Image
from torchvision import models, transforms

CHEMIN_MODELE = "smart_waste_model.pth"

# --- Chargement du modèle (une seule fois au démarrage) ---
ckpt = torch.load(CHEMIN_MODELE, map_location="cpu")
CLASSES = ckpt["classes"]            # ["PLASTIQUE","PAPIER","METAL","ORGANIQUE","INCONNU"]

model = models.mobilenet_v3_small(weights=None)
model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(CLASSES))
model.load_state_dict(ckpt["state_dict"])
model.eval()

# Mêmes transformations que l'évaluation sur Kaggle
prep = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

app = FastAPI(title="SMART BIN - API de classification")


@app.get("/health")
def health():
    return {"statut": "ok", "classes": CLASSES}


@app.post("/predict")
async def predict(image: UploadFile = File(...)):
    try:
        contenu = await image.read()
        img = Image.open(io.BytesIO(contenu)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Image invalide")

    with torch.no_grad():
        proba = torch.softmax(model(prep(img).unsqueeze(0)), dim=1)[0]

    conf, idx = proba.max(0)
    categorie = CLASSES[int(idx)]
    confiance = round(float(conf), 3)

    # Commande prête à envoyer à l'Arduino ("METAL:0.92" ou "INCONNU")
    commande = "INCONNU" if categorie == "INCONNU" else f"{categorie}:{confiance:.2f}"

    return {
        "categorie": categorie,
        "confiance": confiance,
        "commande": commande,
        "probabilites": {c: round(float(p), 3) for c, p in zip(CLASSES, proba)},
    }