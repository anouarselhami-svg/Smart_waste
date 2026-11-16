#include <Servo.h>
// ==================== SERVOMOTEURS ====================
Servo rampe;
Servo trappe;

const int PIN_RAMPE = 9;
const int PIN_TRAPPE = 10;

const int ANGLE_RAMPE[4] = {20, 70, 120, 170};
// PLASTIC, PAPER, METAL, REJECT

const int RAMPE_INITIALE = 0;
const int TRAPPE_FERMEE = 0;
const int TRAPPE_OUVERTE = 90;

// ==================== CAPTEURS ULTRASONIQUES ====================
const int NB_BACS = 4;

const int TRIG[NB_BACS] = {2, 4, 6, 8};
const int ECHO[NB_BACS] = {3, 5, 7, 11};

const char* NOMS_BACS[NB_BACS] = {
  "PLASTIC", "PAPER", "METAL", "REJECT"
};

const float PROFONDEUR_BAC = 30.0;

const int SEUIL_AVERTISSEMENT = 75;
const int SEUIL_PLEIN = 90;

// ==================== BOUTONS ET LED ====================
const int BTN_DECHET = A0;
const int BTN_SECURITE = A1;

const int LED_VERTE = 12;
const int LED_ROUGE = 13;

bool dechetPresent = false;
bool ancienEtatDechet = HIGH;

// ==================== CONFIGURATION ====================
const float CONFIANCE_MIN = 0.60;

const unsigned long INTERVALLE_NIVEAUX = 5000;
unsigned long dernierControleNiveaux = 0;

bool triEnCours = false;

// ==================== INITIALISATION ====================
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);

  pinMode(BTN_DECHET, INPUT_PULLUP);
  pinMode(BTN_SECURITE, INPUT_PULLUP);

  pinMode(LED_VERTE, OUTPUT);
  pinMode(LED_ROUGE, OUTPUT);

  for (int i = 0; i < NB_BACS; i++) {
    pinMode(TRIG[i], OUTPUT);
    pinMode(ECHO[i], INPUT);
    digitalWrite(TRIG[i], LOW);
  }

  rampe.attach(PIN_RAMPE);
  trappe.attach(PIN_TRAPPE);

  rampe.write(RAMPE_INITIALE);
  trappe.write(TRAPPE_FERMEE);

  digitalWrite(LED_VERTE, HIGH);
  digitalWrite(LED_ROUGE, LOW);

  Serial.println("SYSTEME_PRET");
  Serial.println("COMMANDES: PLASTIC, PAPER, METAL, UNKNOWN, RESET, PING, STATUS, NIVEAUX");
}

// ==================== BOUTON DE DETECTION ====================
void verifierDetectionDechet() {
  bool etatActuel = digitalRead(BTN_DECHET);

  if (ancienEtatDechet == HIGH && etatActuel == LOW) {
    dechetPresent = true;
    Serial.println("DECHET_DETECTE");
  }

  ancienEtatDechet = etatActuel;
}

// ==================== MESURE ULTRASONIQUE ====================
float mesurerDistance(int index) {
  digitalWrite(TRIG[index], LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG[index], HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG[index], LOW);

  unsigned long duree = pulseIn(ECHO[index], HIGH, 30000);

  if (duree == 0) {
    return -1;
  }

  return duree * 0.0343 / 2.0;
}

int calculerRemplissage(float distance) {
  if (distance < 0) {
    return -1;
  }

  float remplissage =
    ((PROFONDEUR_BAC - distance) / PROFONDEUR_BAC) * 100.0;

  return constrain((int)remplissage, 0, 100);
}

// ==================== CONTROLE DES BACS ====================
void afficherNiveaux() {
  bool bacPlein = false;

  Serial.print("NIVEAUX:");

  for (int i = 0; i < NB_BACS; i++) {
    float distance = mesurerDistance(i);
    int niveau = calculerRemplissage(distance);

    if (i > 0) Serial.print(",");

    Serial.print(NOMS_BACS[i]);
    Serial.print("=");

    if (niveau < 0) {
      Serial.print("ERREUR");
    } else {
      Serial.print(niveau);

      if (niveau >= SEUIL_PLEIN) {
        bacPlein = true;
        Serial.print("%:PLEIN");
      } else if (niveau >= SEUIL_AVERTISSEMENT) {
        Serial.print("%:PRESQUE_PLEIN");
      } else {
        Serial.print("%:OK");
      }
    }
  }

  Serial.println();

  digitalWrite(LED_ROUGE, bacPlein ? HIGH : LOW);
  digitalWrite(LED_VERTE, bacPlein ? LOW : HIGH);
}

// ==================== SECURITE DE LA TRAPPE ====================
void fermerTrappeEnSecurite() {
  // Tant que le bouton de securite est appuye,
  // la trappe reste ouverte.
  while (digitalRead(BTN_SECURITE) == LOW) {
    trappe.write(TRAPPE_OUVERTE);
    delay(100);
  }

  trappe.write(TRAPPE_FERMEE);
  delay(400);

  // Si un obstacle est detecte pendant la fermeture,
  // on rouvre la trappe et on recommence.
  while (digitalRead(BTN_SECURITE) == LOW) {
    trappe.write(TRAPPE_OUVERTE);
    delay(100);
  }

  trappe.write(TRAPPE_FERMEE);
  Serial.println("TRAPPE:FERMEE");
}

// ==================== CYCLE DE TRI ====================
void effectuerTri(int indexBac, const char* categorie) {
  if (!dechetPresent) {
    Serial.println("ERR:ABSENCE_DECHET");
    return;
  }

  if (triEnCours) {
    Serial.println("ERR:TRI_EN_COURS");
    return;
  }

  triEnCours = true;

  Serial.print("OK:");
  Serial.println(categorie);

  Serial.println("TRI:DEBUT");

  // 1. Fermer la trappe avant de positionner la rampe.
  trappe.write(TRAPPE_FERMEE);
  delay(500);
  Serial.println("TRAPPE:FERMEE");

  // 2. Orienter la rampe vers le bac cible.
  rampe.write(ANGLE_RAMPE[indexBac]);
  Serial.print("RAMPE:POSITION:");
  Serial.println(categorie);

  delay(1000);
  Serial.println("RAMPE:POSITION_ATTEINTE");

  // 3. Ouvrir la trappe pour deposer le dechet.
  trappe.write(TRAPPE_OUVERTE);
  Serial.println("TRAPPE:OUVERTE");

  delay(1500);
  Serial.println("TRI:DECHET_DEPOSE");

  // 4. Attendre que le passage soit libre.
  while (digitalRead(BTN_SECURITE) == LOW) {
    trappe.write(TRAPPE_OUVERTE);
    delay(100);
  }

  Serial.println("SECURITE:PASSAGE_LIBRE");

  // 5. Fermer la trappe en securite.
  fermerTrappeEnSecurite();

  Serial.println("SECURITE:TRAPPE_FERMEE");

  // 6. Remettre la rampe en position initiale.
  rampe.write(RAMPE_INITIALE);
  delay(700);

  Serial.println("RAMPE:POSITION_INITIALE");

  // 7. Terminer le cycle.
  dechetPresent = false;
  triEnCours = false;

  Serial.println("TRI:TERMINE");
  Serial.println("OK:CYCLE_TERMINE");
}

// ==================== REINITIALISATION ====================
void reinitialiserSysteme() {
  rampe.write(RAMPE_INITIALE);
  trappe.write(TRAPPE_FERMEE);

  dechetPresent = false;
  triEnCours = false;

  digitalWrite(LED_VERTE, HIGH);
  digitalWrite(LED_ROUGE, LOW);

  Serial.println("OK:RESET");
}

// ==================== TRAITEMENT DES COMMANDES ====================
void traiterCommande(String commande) {
  commande.trim();
  commande.toUpperCase();

  if (commande.length() == 0) {
    return;
  }

  if (commande == "PING") {
    Serial.println("PONG");
    return;
  }

  if (commande == "STATUS") {
    Serial.print("STATUS:");
    Serial.print(dechetPresent ? "DECHET_PRESENT" : "AUCUN_DECHET");
    Serial.print(",");
    Serial.println(triEnCours ? "TRI_EN_COURS" : "DISPONIBLE");
    return;
  }

  if (commande == "NIVEAUX") {
    afficherNiveaux();
    return;
  }

  if (commande == "RESET") {
    reinitialiserSysteme();
    return;
  }
    if (commande == "DETECT") {
    dechetPresent = true;
    Serial.println("DECHET_DETECTE");
    return;
  }

  // UNKNOWN est dirige vers le compartiment REJECT.
  if (commande == "UNKNOWN") {
    effectuerTri(3, "UNKNOWN");
    return;
  }

  // Compatibilite avec les anciennes commandes :
  // PLASTIQUE:0.95, PAPIER:0.95, METAL:0.95
  int separateur = commande.indexOf(':');

  String categorie = commande;
  float confiance = 1.0;

  if (separateur >= 0) {
    categorie = commande.substring(0, separateur);
    String valeur = commande.substring(separateur + 1);

    if (valeur.length() == 0) {
      Serial.println("ERR:CONFIANCE_INVALIDE");
      return;
    }

    confiance = valeur.toFloat();

    if (confiance < 0.0 || confiance > 1.0) {
      Serial.println("ERR:CONFIANCE_INVALIDE");
      return;
    }

    if (confiance < CONFIANCE_MIN) {
      Serial.println("ERR:CONFIANCE_FAIBLE");
      return;
    }
  }

  if (categorie == "PLASTIC" || categorie == "PLASTIQUE") {
    effectuerTri(0, "PLASTIC");
  }
  else if (categorie == "PAPER" || categorie == "PAPIER") {
    effectuerTri(1, "PAPER");
  }
  else if (categorie == "METAL") {
    effectuerTri(2, "METAL");
  }
  else if (categorie == "REJECT" || categorie == "REJET" ||
           categorie == "ORGANIQUE") {
    // ORGANIQUE est conserve uniquement pour compatibilite
    // avec les anciens tests Wokwi.
    effectuerTri(3, "UNKNOWN");
  }
  else {
    Serial.println("ERR:COMMANDE_INCONNUE");
  }
}

// ==================== BOUCLE PRINCIPALE ====================
void loop() {
  verifierDetectionDechet();

  // Reception des commandes Python / Serial Monitor.
  if (Serial.available()) {
    String commande = Serial.readStringUntil('\n');
    traiterCommande(commande);
  }

  // Mise a jour periodique des niveaux des bacs.
  if (millis() - dernierControleNiveaux >= INTERVALLE_NIVEAUX) {
    dernierControleNiveaux = millis();
    afficherNiveaux();
  }
}
