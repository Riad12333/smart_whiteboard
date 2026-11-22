# ROADMAP — étapes du projet

Dis « Étape N » pour lancer une étape. Chaque étape a un critère de validation.

## Étape 0 : Mise en place
Pose-moi tes questions (OS, version de Python, webcam, résolution, matériel disponible). Crée la structure du projet, requirements.txt, un settings.py de départ et documente les formats d'échange.
Validée quand : le projet se lance et affiche « hello » avec la config chargée.

## Étape 1 : camera.py
Capture, redimensionnement, mesure du FPS, aperçu vidéo. Mode vidéo enregistrée pour tester sans webcam.
Validée quand : l'aperçu tourne à FPS stable et une courte vidéo de test est enregistrée.

## Étape 2 : Détection, partie 1 (couleur et masque)
Conversion BGR -> YCrCb à la main (et HSV pour le mode marqueur). Calibration de la couleur de peau au démarrage (carré affiché, touche, moyenne et écart-type de Cr et Cb). Seuillage. ROI.
Seuils de secours : 133 <= Cr <= 173 et 77 <= Cb <= 127.
Validée quand : la fenêtre de debug montre un masque où la main ressort clairement.

## Étape 3 : Détection, partie 2 (région et bout du doigt)
Érosion et dilatation maison, étiquetage des composantes connexes maison (sur image réduite), plus grande région, centroïde, bout du doigt (pixel le plus éloigné du centroïde ; alternative « point le plus haut » dans la config). Geste imposé : index tendu, poing fermé.
Validée quand : un point suit mon index sur la vidéo à au moins 20 FPS.

## Étape 4 : Détection, partie 3 (stabilité et robustesse)
Lissage exponentiel P = a*P_new + (1-a)*P_prev, zone morte, perte et reprise du tracking, mode marqueur coloré en secours, mesures de stabilité (écart-type immobile, taux de détection, plusieurs lumières), tests unitaires.
Validée quand : la sortie respecte le format d'échange et les mesures sont notées pour le rapport.

## Étape 5 : Calibration et mapping
Homographie par DLT (système 8x8, np.linalg.solve), 4 couples de points, cibles affichées sur la zone projetée, validation avec des points supplémentaires (erreur moyenne en pixels), sauvegarde dans la config. Option : mode clic sur 4 coins pour tester à la maison.
Validée quand : l'erreur de mapping est mesurée et affichée honnêtement.

## Étape 6 : Télécommande
Script pour identifier les codes reçus, table codes -> événements dans la config, anti-répétition, simulation clavier.
Validée quand : les deux événements sont générés correctement et les codes réels sont notés.

## Étape 7 : Interface et interaction
Fenêtre plein écran, curseur visible, menu principal + sous-menus, boutons grands avec survol, retour menu, reset. interaction.py relie événement + position -> action.
Validée quand : je navigue dans les menus avec la souris simulée, puis avec la main.

## Étape 8 : Dessin
Traits (listes de points + couleur + épaisseur), stylo posé/levé par la télécommande (interrupteur), 2 couleurs ou épaisseurs, effacer tout, Undo/Redo, gomme, tracé de lignes type Bresenham.
Validée quand : je dessine une figure et j'annule.

## Étape 9 : Fonctions libres
Image + zoom (avant/arrière/retour), mini-leçon cohérente (menu, pages texte/image, annotation, navigation).
Validée quand : une séquence pédagogique complète se déroule sans intervention sur le code.

## Étape 10 : Intégration et dashboard
main.py, boucle principale, dashboard technique (FPS, état du tracking, position, validité de la calibration, erreur de mapping mesurée), gestion d'erreurs.
Validée quand : tout fonctionne ensemble avec webcam + écran + clavier simulé.

## Étape 11 : Matériel réel et robustesse
Checklist de séance avec le vrai projecteur et la vraie télécommande : calibration physique, seuils de lumière, codes réels, répétition de la démo, plan B.
Validée quand : la démo complète passe 3 fois de suite sans toucher au code.

## Étape 12 : Rapport et livraison
Plan du rapport (~8 pages, en anglais) : système, matériel et logiciel, calibration et repères, détection et limites, télécommande et codes, interface, algorithmes et tests, limites. Archive finale (code commenté, config, rapport PDF). Script de démo et questions du prof.
Validée quand : le rapport est envoyé le 5 déc et la démo répétée.
