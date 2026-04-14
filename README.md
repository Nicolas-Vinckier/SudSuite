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

---

## 🎨 Crédits

Développé avec ❤️ pour simplifier la vie numérique.
