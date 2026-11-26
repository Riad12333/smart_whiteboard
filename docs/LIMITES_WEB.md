# Limites Techniques et Architecture de la Version Web

> **Smart Interactive Whiteboard — USTHB (2026-2027)**  
> Note technique sur la version Web statique (`web/`), les choix de portage et les divergences d'exécution par rapport au projet de référence Python.

---

## 1. Pourquoi MediaPipe Tasks Vision sur le Web (et non OpenCV Zoo ONNX) ?

Dans l'application Python officielle (qui reste le **projet noté de référence**), nous exécutons directement les modèles ONNX nus issus d'OpenCV Zoo (`palm_detection_mediapipe_2023feb.onnx` et `handpose_estimation_mediapipe_2023feb.onnx`) via le moteur natif C++ d'OpenCV (`cv2.dnn.readNet`).

Dans la version Web statique (`web/`), nous utilisons le runtime officiel **MediaPipe Tasks Vision** (`@mediapipe/tasks-vision` via WebAssembly et modèle `hand_landmarker.task`) hébergé localement dans `web/models/`. Voici les justifications techniques fondamentales :

1. **Poids et complexité du runtime WebAssembly** :
   - Exécuter des modèles ONNX avec le module OpenCV DNN en JavaScript nécessiterait de compiler l'intégralité d'OpenCV C++ en WebAssembly (`opencv.js`). Une telle compilation avec support DNN, SIMD et threads pèse entre **$30\text{ Mo}$ et $50\text{ Mo}$**, ce qui est inacceptable pour un chargement Web fluide.
   - À l'inverse, le runtime WebAssembly de MediaPipe Tasks (`vision_wasm_internal.wasm`) est hautement épuré ($\approx 14\text{ Mo}$), optimisé avec les instructions vectorielles WebAssembly SIMD et le moteur XNNPACK, permettant une inférence temps réel à **60 FPS** directement sur CPU ou via le GPU de n'importe quel ordinateur ou smartphone.
2. **Gestion du pipeline et des tenseurs dans le navigateur** :
   - Dans le navigateur, extraire les tenseurs d'un flux vidéo `HTMLVideoElement` vers OpenCV WebAssembly nécessite des copies mémoire répétées et coûteuses (`ImageData` $\to$ Matrice C++ $\to$ Tenseur $\to$ Matrice).
   - MediaPipe Tasks Vision gère en interne la capture directe depuis les textures WebGL matérielles du navigateur sans passage par le pont JavaScript, éliminant ainsi tout goulet d'étranglement de copie mémoire.
3. **Autonomie locale et absence totale de CDN à l'exécution** :
   - Conformément aux consignes du projet, tous les fichiers (`vision_wasm_internal.wasm`, `vision_wasm_internal.js`, et `hand_landmarker.task`) sont stockés localement dans `web/models/`. Le site fonctionne **à 100% hors-ligne**, sans aucune dépendance vers un CDN externe à l'exécution.

---

## 2. Ce qui reste 100% Identique et Partagé (Le Cœur Algorithmique)

La version Web ne réinvente aucun calcul. Elle réutilise fidèlement l'algorithmique et les contrats définis pour Python :
- **DLT Homography** : Résolution du système linéaire $8 \times 8$ par élimination de Gauss-Jordan écrite à la main dans [web/js/core_logic.js](file:///c:/Users/pc/Downloads/smart_whiteboard-main/smart_whiteboard-main/web/js/core_logic.js), validée par test unitaire contre `tests/fixtures/homography_cases.json`.
- **Projection de coordonnées** : Formules projectives homogènes identiques ($H \cdot [x, y, 1]^T$).
- **Filtrage temporel** : Implémentation exacte du **filtre $1€$** (Casiez et al., 2012) et de la **zone morte circulaire** avec les mêmes paramètres (`one_euro_min_cutoff = 1.0`, `one_euro_beta = 0.007`, `deadzone_radius = 3.5 px`).
- **Moteur de tracé** : Algorithme de lignes de **Bresenham** pur entier et gestion de pile Undo / Redo sans état.
- **Format d'échange** : Structure de données strictement conforme à [docs/PROTOCOL.md](file:///c:/Users/pc/Downloads/smart_whiteboard-main/smart_whiteboard-main/docs/PROTOCOL.md) (point de pointage au Landmark 8, posture d'index, score de confiance, bounding box).

---

## 3. Limites Spécifiques à la Version Web

1. **Exigence de contexte sécurisé (HTTPS)** :
   - Les navigateurs (Chrome, Firefox, Safari) interdisent formellement l'accès à la webcam via `getUserMedia` sur une connexion `http://` non locale. Le site doit être consulté sur `localhost` ou déployé sur un hébergeur HTTPS (ex : GitHub Pages, Netlify, Vercel).
   - En cas d'accès non sécurisé ou de refus de l'utilisateur, le système bascule gracieusement en **Mode Souris** pour garantir la continuité de la détection.
2. **Absence de portage du mode peau ($YCrCb$) en pur Web** :
   - Alors que le mode `MARKER` (HSV) est implémenté via l'API Canvas 2D (`web/js/detection_marker.js`), la segmentation couleur de peau adaptative $YCrCb$ avec calibration de variance n'est pas portée en JavaScript pour préserver la clarté pédagogique : le Web privilégie le mode Machine Learning haute fidélité (`HAND_ML`) et le mode Marqueur (`MARKER`).
3. **Statut académique du projet** :
   - Cette version Web est un **bonus technique de présentation** facilitant la démonstration interactive sur n'importe quel ordinateur ou tablette sans installer Python. Le projet officiel évalué à l'oral pour le Master reste le logiciel Python / Pygame / OpenCV Zoo documenté dans `AGENTS.md`.
