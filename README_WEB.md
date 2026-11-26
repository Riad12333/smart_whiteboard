# Smart Interactive Whiteboard — Version Web Statique

> **Bonus de présentation Web (HTML5, CSS3, Modules ES JavaScript natifs — Zéro build, zéro serveur backend)**  
> *Note : Le projet académique principal noté reste l'application Python (`main.py`). Cette version Web sert de démonstrateur universel exécutable depuis n'importe quel navigateur ou smartphone.*

---

## 🚀 1. Lancer en Local

En raison des politiques de sécurité des navigateurs modernes concernant les modules ES (`import/export`) et le chargement WebAssembly (`.wasm`), ouvrez le site via un petit serveur HTTP local :

```powershell
cd smart_whiteboard-main/web
python -m http.server 8000
```

Ouvrez ensuite : **[http://localhost:8000](http://localhost:8000)**

*(Pour tester sur votre téléphone connecté au même Wi-Fi en mode tactile/souris uniquement, utilisez `python -m http.server 8000 --bind 0.0.0.0` et accédez à `http://<VOTRE_IP_LOCALE>:8000`)*.

---

## 🌐 2. Publier Gratuitement en Ligne (HTTPS Obligatoire)

> ⚠️ **Rappel de sécurité critique (`getUserMedia`) :**  
> Tous les navigateurs modernes (Chrome, Edge, Safari iOS, Firefox) **bloquent l'accès à la webcam** si le site n'est pas servi en **HTTPS** (sauf sur `localhost`). Pour activer la caméra sur ordinateur distant ou sur smartphone, un hébergement HTTPS gratuit est indispensable.

### Option A : GitHub Pages (Recommandé — Déjà configuré via branche `gh-pages`)
1. Ce dépôt contient déjà la branche `gh-pages` synchronisée avec le contenu de `web/`.
2. Rendez-vous dans **Settings > Pages** sur votre dépôt GitHub.
3. Sous **Build and deployment** :
   - **Source** : `Deploy from a branch`
   - **Branch** : sélectionnez **`gh-pages`** et **`/ (root)`**, puis cliquez sur **Save**.
4. Votre site est automatiquement en ligne en HTTPS à l'adresse :  
   `https://<VOTRE_PSEUDO>.github.io/smart_whiteboard/`

### Option B : Netlify (Déploiement instantané par glisser-déposer)
1. Créez un compte gratuit sur [netlify.com](https://www.netlify.com).
2. Glissez-déposez simplement le dossier `web/` dans **Sites > Add new site > Deploy manually** (ou liez votre dépôt GitHub en définissant `Publish directory: web`).
3. Netlify génère instantanément une URL HTTPS (`https://nom-aleatoire.netlify.app`).

### Option C : Cloudflare Pages
1. Connectez votre dépôt GitHub sur [pages.cloudflare.com](https://pages.cloudflare.com).
2. Paramètres de build :
   - **Framework preset** : `None`
   - **Build command** : *(laisser vide)*
   - **Build output directory** : `web`
3. Déploiement global ultra-rapide sur le réseau CDN Cloudflare avec certificat SSL/HTTPS automatique.

---

## ✅ 3. Liste de Contrôle de Publication (Checklist Pré-Démo)

Avant de présenter le lien public ou de passer la soutenance, cochez les 5 points suivants :

- [ ] **Caméra autorisée** : Lors de l'ouverture sur l'URL HTTPS, le navigateur demande l'accès caméra et le badge HUD passe au vert (`MAIN (ML)`).
- [ ] **Modèle WASM chargé sans CDN** : Dans l'onglet *Network* (Réseau) des outils développeur (`F12`), `hand_landmarker.task` et `vision_wasm_internal.wasm` sont servis localement (`200 OK`) sans aucune requête vers un CDN externe.
- [ ] **Repli Mode Souris vérifié** : Si la permission caméra est refusée (ou sur un PC sans webcam), l'application bascule proprement en mode `SOURIS` et permet de dessiner, zoomer et naviguer.
- [ ] **Console navigateur sans erreur** : L'onglet *Console* (`F12`) n'affiche aucune erreur bloquante rouge (`Uncaught TypeError` ou `404 Not Found`).
- [ ] **Test sur téléphone (Mobile & Tactile)** : Sur smartphone (en HTTPS), la barre d'outils s'adapte à la largeur de l'écran et le dessin tactile au doigt sur le canvas répond sans défilement parasite de la page (`touch-action: none`).
