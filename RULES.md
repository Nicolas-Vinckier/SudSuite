# 🛠️ SudSuite - Charte de Développement

Ce document définit les règles de conception pour les outils de **SudSuite**.

## 🎨 Principes Fondamentaux

1. **Esthétique Terminal** : Chaque script DOIT commencer par un en-tête ASCII Art stylisé. Les messages importants utilisent des emojis (📂, ✅, ❌, ⚠️, 🚀). [ASCII Art](https://www.asciiart.eu/text-to-ascii-art)
2. **Interactivité Prioritaire** : Favoriser les menus interactifs (`input()`) et les guides étape par étape plutôt que les flags complexes en ligne de commande.
3. **Simplicité d'Installation** : Dépendances minimales. Si une bibliothèque est nécessaire (ex: `Pillow`), inclure un check d'import avec instruction d'installation.
4. **Langue** : Développement et message en français.

## 🏗️ Structure de Code Type

- **En-tête** : ASCII Art et imports.
- **Configuration** : Constantes et filtres d'exclusion en haut de fichier.
- **Utilitaires** : Fonctions partagées comme `format_size()`.
- **Fonction Principale** : `main()` propre avec gestion des interruptions (`KeyboardInterrupt`).

## 🧹 Règles de Gestion de Fichiers

- **Smart Filtering** : Toujours ignorer `.git`, `node_modules`, `__pycache__`, etc.
- **Sécurité** : Ne jamais supprimer de fichiers sans une confirmation explicite (MAJUSCULES de préférence pour les actions critiques).
- **Rapports** : Toujours afficher un bilan (taille traitée, gain d'espace, fichiers restants).

## 🚀 Workflow Additionnel

- Maintenir le `README.md` à jour pour chaque nouvel outil.
- Utiliser l'auto-naming avec horodatage (`YYYYMMDD_HHMMSS`) pour les nouveaux fichiers générés.
- Vérifier l'intégrité des données après chaque opération lourde.
