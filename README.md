# 🛠️ Tools - Sud Suite

Bienvenue dans la suite d'outils **Sud**, une collection de scripts Python conçus pour simplifier la gestion de vos médias (images et vidéos).

## 🚀 Outils Inclus

### 1. 📉 Sud Compressor (`image_compressor.py`)
Un compresseur d'images intelligent capable de réduire drastiquement la taille de vos fichiers tout en vous informant des risques de perte de qualité.

*   **Formats supportés** : JPEG, PNG, WebP.
*   **Mode Sans Perte (Lossless)** : Optimise l'image sans aucune dégradation visuelle (idéal pour l'archivage).
*   **Mode Avec Perte (Lossy)** : Permet de choisir un niveau de qualité (1-100) et simule le gain d'espace avant de sauvegarder.
*   **Conversion WebP** : Option pour convertir automatiquement vos images en format WebP pour un gain d'espace maximal.
*   **Analyse de Risque** : Le script affiche une analyse textuelle (Risque faible, modéré ou élevé) selon la qualité choisie.

### 2. 📂 Sud Sorting (`image_sorting.py`)
Un outil d'organisation automatisé pour vos photos et vidéos. Il trie vos fichiers en vrac dans une structure de dossiers propre et chronologique.

*   **Structure de sortie** : `Destination / Année / Mois / Fichier` (ex: `2023 / Janvier / photo.jpg`).
*   **3 Modes de Détection de Date** :
    1.  **Date de modification** : Basé sur le système de fichiers.
    2.  **Date de création** : Utile pour les fichiers originaux.
    3.  **Nom du fichier** : Détecte les dates dans les noms (ex: `IMG_20230101_...`).
*   **Gestion des Doublons** : Détecte automatiquement les fichiers déjà existants et les déplace dans un dossier spécifique `doublon`.
*   **Configuration Persistante** : Sauvegarde vos dossiers sources et destinations préférés dans un fichier `image_sorting_config.json`.

---

## 🛠️ Installation

1.  Assurez-vous d'avoir [Python](https://www.python.org/) installé sur votre système.
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
Le script vous demandera vos dossiers source et destination lors de la première utilisation.

---

## 🎨 Crédits
Développé avec ❤️ pour simplifier la vie numérique.
