# 🛠️ Tools - Sud Suite

Bienvenue dans la suite d'outils **Sud**, une collection de scripts Python conçus pour simplifier la gestion de vos médias (images et vidéos).

## 🚀 Outils Inclus

### 1. 📉 Sud Compressor (`image_compressor.py`)

Un compresseur d'images intelligent capable de réduire drastiquement la taille de vos fichiers tout en vous informant des risques de perte de qualité.

- **Formats supportés** : JPEG, PNG, WebP.
- **Mode Sans Perte (Lossless)** : Optimise l'image sans aucune dégradation visuelle (idéal pour l'archivage).
- **Mode Avec Perte (Lossy)** : Permet de choisir un niveau de qualité (1-100) et simule le gain d'espace avant de sauvegarder.
- **Conversion WebP** : Option pour convertir automatiquement vos images en format WebP pour un gain d'espace maximal.
- **Analyse de Risque** : Le script affiche une analyse textuelle (Risque faible, modéré ou élevé) selon la qualité choisie.

### 2. 📂 Sud Sorting (`image_sorting.py`)

Un outil d'organisation automatisé pour vos photos et vidéos. Il trie vos fichiers en vrac dans une structure de dossiers propre et chronologique.

- **Structure de sortie** : `Destination / Année / Mois / Fichier` (ex: `2023 / Janvier / photo.jpg`).
- **3 Modes de Détection de Date** :
  1.  **Date de modification** : Basé sur le système de fichiers.
  2.  **Date de création** : Basé sur les métadonnées de création.
  3.  **Nom du fichier** : Détecte les dates dans les noms.
- **Auto-détection intelligente** : Analyse un échantillon de 10% de vos fichiers pour deviner le format de date (`AAAAMMDD`, `DDMMAAAA` ou `MMDDAAAA`).
- **Mode "Lazy"** : Si vous configurez un dossier vide, le script ne vous posera de questions sur le format que lors du premier tri effectif.
- **Trie inversé (Restauration)** : Option pour annuler un tri et renvoyer tous les fichiers de la destination vers la source (avec gestion des doublons).
- **Full Cleaning** : Option pour tout réinitialiser (suppression de la config et de TOUTES les photos dans source/destination après confirmation du nombre d'éléments).

### 3. 📦 Sud Archive (`folder_compressor.py`)

Un outil de compression de dossiers intelligent pour archiver vos projets tout en ignorant les fichiers inutiles.

- **3 Modes de Compression** :
  1. **Classique** : Vitesse maximale (ZIP).
  2. **Medium** : Équilibre poids/vitesse (ZIP optimisé).
  3. **Ultra** : Compression maximale (Format `.tar.xz` via LZMA).
- **Filtres Smart** : Ignore automatiquement les dossiers comme `.git`, `node_modules`, `__pycache__`, etc.
- **Auto-Naming** : Génère automatiquement un nom avec horodatage (ex: `Projet_Archive_20240414_2125.zip`).
- **Estimation & Vérification** : Calcule le gain d'espace et vérifie l'intégrité de l'archive après création.

### 4. 🏷️ Sud Rename (`image_renamer.py`)

Un outil de renommage en masse puissant basé sur la date de modification des fichiers. Idéal pour uniformiser les noms de fichiers provenant de différentes sources.

- **Sécurité maximale** : Crée automatiquement un nouveau dossier `[Nom]_renamed` pour ne pas écraser vos fichiers originaux.
- **Basé sur la date** : Utilise la date de dernière modification pour générer le nouveau nom.
- **Format flexible** : Supporte les tokens `YYYY`, `MM`, `DD`, `HH`, `mm`, `SS`.
- **Gestion des collisions** : Utilise le token `#` pour ajouter un index si plusieurs fichiers ont le même horodatage.
- **Support Multi-Média** : Fonctionne avec les images et les vidéos.
- **Sécurité** : Prévisualisation des 5 premiers fichiers avant confirmation du renommage.
- **Prévisualisation** : Affiche un échantillon des changements avant confirmation.

### 5. 🔄 Sud Convert (`image_convertissor.py`)

Un outil de conversion d'images polyvalent qui permet de changer le format de vos fichiers tout en préservant la qualité maximale.

- **Formats de sortie supportés** : PNG, JPEG, WebP, BMP, TIFF, GIF.
- **Conversion Sans Perte** : Utilise les réglages optimaux pour chaque format (ex: `lossless=True` pour le WebP).
- **Idempotence** : Détecte les fichiers déjà convertis dans le dossier de destination et les ignore pour éviter les doublons et gagner du temps.
- **Organisation de sortie** : Crée automatiquement un dossier `[Nom]_convert` ou `converted` pour isoler les fichiers transformés.
- **Double Barre de Progression** : Rendu fluide affichant l'avancement global du lot ainsi que l'état de traitement de l'image actuelle sur une seule ligne.
- **Auto-Gestion du canal Alpha** : Convertit intelligemment la transparence (RGBA vers RGB) vers un fond blanc lors du passage vers des formats comme le JPEG.

### 6. 📏 Sud Resize (`image_resizer.py`)

Un outil puissant pour redimensionner vos images tout en gérant intelligemment le rapport d'aspect. Parfait pour adapter des photos haute résolution à des formats spécifiques (ex: passage du paysage au portrait) sans déformation.

- **Modes de Redimensionnement** :
  1. **Remplissage (Fill)** : Redimensionne et recadre automatiquement l'image au centre pour remplir les dimensions cibles. Idéal pour transformer une photo paysage en portrait.
  2. **Adaptation (Fit)** : Redimensionne l'image pour qu'elle tienne entièrement dans le cadre (ajoute des bandes si nécessaire).
  3. **Étirage (Stretch)** : Redimensionne sans conserver le ratio (déformation).
- **Auto-Naming** : Sauvegarde les fichiers avec les dimensions et un horodatage (`YYYYMMDD_HHMMSS`) pour éviter les écrasements.
- **En masse** : Supporte le traitement de fichiers uniques ou de dossiers entiers.
- **Qualité** : Utilise le rééchantillonnage Lanczos pour une netteté maximale.

### 7. 🚀 Sud Master (`image_master.py`)

L'outil ultime de la suite qui permet de combiner le redimensionnement, la conversion et la compression en une seule opération fluide.

- **Workflow tout-en-un** : Sélectionnez les étapes à la carte (Resize, Convert, Compress) selon vos besoins.
- **Intelligent & Adaptatif** :
  - **Fichier seul** : Sauvegarde le résultat au même endroit avec un suffixe descriptif (ex: `image_800x600_min.webp`).
  - **Dossier complet** : Regroupe tout le traitement dans un dossier de sortie dédié (`_MASTER`).
- **Optimisation séquentielle** : Applique toutes les transformations en une seule fois pour une rapidité maximale et une usure minimale du disque.
- **Bilan Complet** : Affiche un résumé détaillé du gain d'espace total après le traitement combiné.

---

## 🛠️ Installation

1.  Assurez-vous d'avoir [Python](https://www.python.org/) installé.
2.  Installez la bibliothèque obligatoire **Pillow** :
    ```bash
    pip install Pillow
    ```

---

## 📖 Utilisation

### Compresser une image

Lancez le script en passant le chemin d'une ou plusieurs images en argument :

```bash
python image_compressor.py photo.jpg
```

Suivez ensuite les instructions interactives dans le terminal.

### Trier ses photos

Lancez simplement le script et suivez le guide de configuration initial :

```bash
python image_sorting.py
```

Le menu interactif vous propose 4 options :

1.  **Utiliser la config actuelle** : Lance le tri configuré.
2.  **Recommencer la config** : Change les dossiers source/destination ou le mode.
3.  **Trie inversé** : Ramène les fichiers triés vers la source.
4.  **Full cleaning** : Supprime la config et vide les dossiers source/dest.

### Compresser un dossier (Archivage)

```bash
python folder_compressor.py
```

Laissez-vous guider par le menu pour choisir le dossier et le niveau de compression.

### Renommer ses fichiers en masse

```bash
python image_renamer.py
```

1.  Indiquez le dossier contenant les médias.
2.  Choisissez votre format de renommage (ex: `YYYYMMDD_HHmmSS_#`).
3.  Vérifiez la prévisualisation et confirmez.

### Convertir ses images

```bash
# Unitairement
python image_convertissor.py photo.jpg

# Par dossier complet
python image_convertissor.py ./mes_images
```

1.  Passez le chemin du fichier ou dossier en argument.
2.  Choisissez le format cible via le menu interactif.
3.  Vérifiez le bilan final affiché dans le terminal.

### Redimensionner ses images

```bash
# Lancez le script
python image_resizer.py

# Ou passez un chemin en argument
python image_resizer.py ./vacances
```

1.  Indiquez le fichier ou dossier à traiter.
2.  Entrez les dimensions cibles (Largeur et Hauteur).
3.  Sélectionnez la méthode de redimensionnement (le mode "Remplissage" est idéal pour le portrait/paysage).

### Utiliser le Master Tool (Tout-en-un)

```bash
# Pour un dossier complet
python image_master.py ./mon_dossier

# Pour un fichier unique (sauvegarde locale avec suffixe)
python image_master.py photo.jpg
```

1.  Lancez le script avec un chemin en argument (ou glissez-déposez).
2.  Cochez les étapes souhaitées (`📏`, `🔄`, `🗜️`).
3.  Configurez vos réglages et admirez le gain de place final.

---

## 🎨 Crédits

Développé avec ❤️ pour simplifier la vie numérique.
