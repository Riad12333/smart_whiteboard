# Justification Technique de la Détection (Étape 4quinquies)

> **Projet Vision par Ordinateur — Master Informatique (USTHB 2026-2027)**  
> Document d'analyse comparative, choix algorithmiques et justification pour la soutenance orale.

---

## 1. Pourquoi passer à un modèle appris (Deep Learning) ?

L'approche initiale par **segmentation couleur de peau en espace $YCrCb$** (ITU-R BT.601) avec seuillage et étiquetage en composantes connexes (CCL) constituait la première étape du projet. Cependant, les mesures expérimentales réelles en conditions de projection en classe ont révélé des limites structurelles rédhibitoires :

1. **Échec de l'invariance aux ombres et lumières projetées** :
   - Sous un éclairage ambiant diffus, le taux de détection de la peau atteint environ **$84.2\%$**.
   - Dès que le vidéoprojecteur projette des images dynamiques (notamment des textes ou diaporamas colorés), la lumière projetée directement sur la main de l'utilisateur altère les composantes chromatiques ($Cr, Cb$). Le taux de détection s'effondre à **$< 32\%$**, avec une dispersion spatiale incontrôlée du centroïde.
2. **Sensibilité aux arrière-plans et visages** :
   - La segmentation chromatique est incapable de distinguer la main du visage du professeur ou des vêtements présentant des teintes proches (beige, rose, marron clair). La composante connexe maximale bascule alors vers le visage, faussant la position du pointeur.
3. **Imprécision du bout du doigt (Farthest pixel)** :
   - L'heuristique du pixel le plus éloigné du centroïde ($\max d^2$) fonctionne tant que l'index est tendu et isolé. Dès que la main pivote ou que le poignet entre dans le champ de la caméra, le point le plus éloigné se déplace vers l'avant-bras plutôt que l'index.

**Conclusion expérimentale :** Pour garantir une détection robuste en salle de cours, un modèle basé sur des caractéristiques géométriques et sémantiques apprises (réseau de neurones convolutif) s'avère indispensable, tout en conservant la segmentation couleur (`MARKER` et `SKIN`) en mode de secours (*fallback*).

---

## 2. Rôle des Deux Modèles OpenCV Zoo (MediaPipe ONNX)

### A. Modèle 1 : Palm Detection (`palm_detection_mediapipe_2023feb.onnx`)
> **Ce qu'il fait :**  
> Ce réseau monocoup (Single Shot Detector - SSD) prend une image redimensionnée en $192 \times 192$ pixels et applique une grille d'ancres denses pour détecter la présence et l'orientation de la paume de la main. Il retourne la boîte englobante de la paume, son angle de rotation ainsi que 7 points clés structurels (poignet et bases des doigts), même en présence d'occultations partielles des doigts.

### B. Modèle 2 : Hand Pose Estimation (`handpose_estimation_mediapipe_2023feb.onnx`)
> **Ce qu'il fait :**  
> Ce réseau régresseur prend en entrée la vignette recadrée, normalisée et alignée de la main ($224 \times 224$ pixels) issue de la détection de paume. Il prédit avec une grande précision les coordonnées spatiales 3D $(x, y, z)$ des **21 articulations du squelette de la main** ainsi qu'un indice de confiance global et un score de latéralité (main gauche ou droite).

---

## 3. Limites Connues des Modèles

1. **Occultation complète de la paume** :
   - Si l'utilisateur tourne le dos à la caméra ou présente sa main par la tranche (profil pur avec paume invisible), le détecteur SSD de paume peut ne pas s'activer ($s < 0.6$). Ce cas est compensé par notre politique de tolérance aux pertes de tracking (`MAX_LOST_FRAMES = 5`).
2. **Échelle et résolution minimale** :
   - La main doit occuper une zone minimale d'environ $32 \times 32$ pixels dans le champ de la caméra pour que les ancres SSD l'isolent efficacement.
3. **Proximité de la surface du tableau** :
   - Lorsque la main touche physiquement le tableau blanc éclairé par le faisceau lumineux du projecteur, une forte surexposition (saturation à 255) peut dégrader la prédiction de la profondeur $z$. Cependant, la coordonnée $(x, y)$ de l'index (Landmark 8) reste stable.

---

## 4. Tableau Récapitulatif : Fonctions Prédéfinies vs Code Maison

Conformément aux consignes de travail (`AGENTS.md`), toute utilisation d'une bibliothèque externe est strictement justifiée, et l'ensemble de la logique métier, du traitement du signal et des transformations géométriques est développé à la main :

| Composant / Fonction | Nature (Prédéfini vs Maison) | Justification / Pourquoi ce choix | Ce que j'ai implémenté moi-même |
| :--- | :--- | :--- | :--- |
| **Capture vidéo & I/O** | `cv2.VideoCapture`, `cv2.imshow` | Prédéfini (OpenCV) imposé pour l'accès aux flux vidéo matériels multiplateformes. | Gestionnaire `CameraManager`, calcul du FPS réel par fenêtre glissante, sauvegarde de clips de test. |
| **Inférence Réseaux ONNX** | `cv2.dnn.readNet`, `net.forward` | Prédéfini (OpenCV Zoo) pour l'exécution vectorisée SIMD (AVX2) des tenseurs des deux modèles MediaPipe sans installer le paquet lourd `mediapipe`. | Wrappers d'entrée/sortie, script de téléchargement automatique et vérification SHA-256 (`tools/download_models.py`). |
| **Conversions de couleur** | **Codé maison (NumPy)** | Requis par le sujet : maîtriser les formules de changement d'espace colorimétrique. | $BGR \to YCrCb$ (ITU-R BT.601) et $BGR \to HSV$ vectorisés de zéro en pur NumPy. |
| **Morphologie mathématique** | **Codé maison (NumPy)** | Requis par le sujet : comprendre l'impact des opérateurs sur le bruit. | Érosion, dilatation et ouverture $3 \times 3$ écrites à la main avec parcours de voisinage. |
| **Étiquetage (CCL)** | **Codé maison (NumPy)** | Requis par le sujet : extraction des régions sans `cv2.connectedComponents`. | Algorithme BFS (Breadth-First Search) avec décimation et isolation du plus grand blob. |
| **Arbitrage multi-mains** | **Codé maison (Python)** | Absence d'arbitrage dans OpenCV Zoo : le modèle renvoie une liste brute de candidats. | Sélection spatiale par continuité euclidienne ($\min d(L_8, L_{\text{last}})$) avec repli sur le score de confiance. |
| **Posture de pointage** | **Codé maison (Géométrie)** | Déterminer si l'utilisateur pointe ou manipule un objet sans dépendre d'un classifieur externe. | Ratios euclidiens $d(\text{tip}, \text{wrist})$ vs $d(\text{pip}, \text{wrist})$ invariants par rotation et échelle pour les 5 doigts. |
| **Confinement zone tableau** | **Codé maison / Algorithmique** | Éliminer les détections hors du plan utile (ex: spectateur au premier plan). | Test d'inclusion dans le polygone de calibration avec marge de tolérance (`HAND_ML_BOARD_MARGIN`). |
| **Filtrage temporel (1€ Filter & EMA)** | **Codé maison (NumPy/Math)** | Supprimer le tremblement physiologique sans introduire de latence lors des mouvements rapides. | Implémentation intégrale de l'algorithme 1€ (Casiez et al., 2012) avec fréquence de coupure adaptative $f_c(v)$ et zone morte (*deadzone*). |
| **Calibration géométrique (DLT)** | **Codé maison (Algèbre linéaire)** | Estimer la transformation projective $3 \times 3$ sans utiliser `cv2.findHomography`. | Formulation du système linéaire $8 \times 8$ (Direct Linear Transform) et résolution par `np.linalg.solve`. |
| **Mapping de coordonnées** | **Codé maison (NumPy)** | Reprojection des coordonnées caméra vers l'écran projeté. | Produit matriciel homogène, normalisation par la composante projective $w$, et clampage aux bornes. |
| **Moteur de dessin (Rasterization)** | **Codé maison (NumPy/Pygame)** | Rendu fluide des traits sans interpolation fermée d'OpenCV. | Algorithme de tracé de segments de **Bresenham** avec tampon circulaire (*round brush stamp*), gestion Undo/Redo. |
