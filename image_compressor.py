import os
import io
import sys

try:
    from PIL import Image
except ImportError:
    print("[Erreur] La bibliotheque 'Pillow' n'est pas installee.")
    print("Veuillez l'installer avec la commande suivante :")
    print("   pip install Pillow")
    sys.exit(1)


def format_size(size_in_bytes):
    """Formate une taille en octets vers une unité lisible."""
    for unit in ["O", "Ko", "Mo", "Go"]:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} To"


def get_original_quality(img):
    """Tente de récupérer la qualité d'origine d'un JPEG."""
    return img.info.get("quality", 100)
def compress_image(input_path, settings=None):
    quality = None
    use_webp = False
    if not os.path.exists(input_path):
        print(f"[Erreur] Le fichier {input_path} n'existe pas.")
        return None

    original_size = os.path.getsize(input_path)
    print(f"\n[Info] Fichier en cours : {os.path.basename(input_path)}")
    print(f"[Poids] Taille originale  : {format_size(original_size)}")

    try:
        img = Image.open(input_path)
    except Exception as e:
        print(f"[Erreur] lors de l'ouverture de l'image : {e}")
        return None

    # Identifier le format d'origine
    fmt = img.format.lower() if img.format else "inconnu"

    if fmt not in ["png", "jpeg", "jpg", "webp", "mpo", "gif"]:
        print(
            f"[Attention] Format {fmt} non standard. L'image sera convertie automatiquement."
        )

    save_format = (
        "JPEG"
        if fmt in ["jpg", "jpeg", "mpo"]
        else ("WEBP" if fmt == "webp" else "PNG")
    )

    # Pour le support JPEG sans canal alpha (Les JPEG ne supportent pas la transparence RGBA)
    if save_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    if not settings:
        print("\n" + "=" * 55)
        print("🎨 SÉLECTION DU MODE DE COMPRESSION")
        print("=" * 55)
        print(
            "1. SANS PERTE (Lossless) : Optimisation sans degradation (Meilleur pour garder la qualite 100%)"
        )
        print(
            "2. AVEC PERTE (Lossy)    : Reduction de la qualite pour un fichier beaucoup plus leger"
        )
        choix = input("\nVotre choix (1 ou 2) : ").strip()
    else:
        choix = settings.get("choix")

    buffer = io.BytesIO()

    if choix == "1":
        if not settings:
            print("\n[Traitement] Compression SANS PERTE en cours...")
        
        if save_format == "JPEG":
            # Meilleure conservation possible pour le JPEG via PIL
            q = get_original_quality(img)
            kwargs = (
                {"quality": "keep"} if q != 100 else {"quality": 100, "subsampling": 0}
            )
            try:
                img.save(buffer, format="JPEG", optimize=True, **kwargs)
            except:
                img.save(
                    buffer, format="JPEG", optimize=True, quality=100, subsampling=0
                )
        elif save_format == "PNG":
            # L'optimisation PNG est nativement lossless.
            img.save(buffer, format="PNG", optimize=True)
        elif save_format == "WEBP":
            # Vrai lossless pour WebP
            img.save(buffer, format="WEBP", lossless=True, quality=100, method=6)

        new_size = buffer.tell()
        if not settings:
            print(f"✓ Optimisation terminée.")

    elif choix == "2":
        if not settings:
            print("\n--- Compression AVEC PERTE ---")
            try:
                quality = int(
                    input("Niveau de qualite souhaite (1-100, ex: 70) : ").strip()
                )
            except ValueError:
                print("Entrée invalide. Utilisation de la qualité par défaut (70).")
                quality = 70
            
            quality = max(1, min(100, quality))

            # Proposition de conversion WebP : excellent compromis poids/qualité
            format_choisi = (
                input(
                    "Voulez-vous convertir en WebP pour un gain maximum ? (o/n, defaut: o) : "
                )
                .strip()
                .lower()
            )
            use_webp = format_choisi != "n"
        else:
            quality = settings.get("quality", 70)
            use_webp = settings.get("use_webp", True)

        if use_webp:
            save_format = "WEBP"

        if save_format == "WEBP" and img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")

        if not settings:
            print("\n[Analyse] Calcul des risques et BENEFICES en cours...")

        if save_format == "JPEG":
            img.save(buffer, format="JPEG", optimize=True, quality=quality)
        elif save_format == "WEBP":
            img.save(buffer, format="WEBP", quality=quality, method=4)
        elif save_format == "PNG":
            # Simulation de perte sur PNG : réduction drastique de la palette de couleurs
            colors = max(2, int((quality / 100) * 256))
            lossy_img = img.convert("P", palette=Image.ADAPTIVE, colors=colors)
            lossy_img.save(buffer, format="PNG", optimize=True)

        new_size = buffer.tell()

        if not settings:
            loss_percentage = 100 - quality
            size_reduction = (
                (original_size - new_size) / original_size * 100 if original_size > 0 else 0
            )

            print("\n" + "= " * 15)
            print("ANALYSE DES RISQUES ET BENEFICES")
            print("= " * 15)

            print(f"BENEFICE : Reduction du poids de {size_reduction:.2f}%")
            print(f"   (De {format_size(original_size)} à {format_size(new_size)})")

            if size_reduction < 0:
                print(
                    "\n[Attention] La compression a AUGMENTE la taille de l'image (l'image d'origine est deja trop compressee)."
                )

            print(f"\n[Risque] Degradaion de la qualite estimee a {loss_percentage}%.")
            if quality < 50:
                print(
                    "   -> RISQUE ELEVE  : Artefacts tres visibles, image potentiellement floue, couleurs baveuses."
                )
            elif quality < 80:
                print(
                    "   -> RISQUE MODERE : Legere perte de nettete ou petits artefacts (acceptable pour le web)."
                )
            else:
                print(
                    "   -> RISQUE FAIBLE : Perte de qualite quasi imperceptible a l'oeil nu."
                )

            confirmer = (
                input("\nProceder a la sauvegarde avec cette qualite ? (o/n) : ")
                .strip()
                .lower()
            )
            if confirmer != "o":
                print("Operation annulee par l'utilisateur.")
                return None
        else:
            # En mode batch auto, on vérifie quand même si on veut sauvegarder si la taille a augmenté
            if new_size > original_size and settings.get("skip_if_larger", True):
                print("ℹ️ Taille augmentée, passage à l'image suivante (réglages auto).")
                return None

    else:
        print("[Erreur] Choix invalide.")
        return None

    print("\n" + "-" * 55)

    # Si la taille est plus grande après compression sans perte -> aucun intérêt de la sauvegarder
    if new_size >= original_size and choix == "1":
        if not settings:
            print(
                "ℹ️ L'optimisation sans perte n'a pas permis de réduire la taille du fichier."
            )
            print(
                "   L'image originale étant déjà optimale, aucune modification n'a été appliquée."
            )
        return None

    # Construire le chemin de sortie
    filename, ext = os.path.splitext(input_path)
    output_ext = f".{save_format.lower()}"
    if save_format == "JPEG":
        output_ext = ".jpg"

    # Éviter d'écraser l'original en ajoutant "_min"
    output_path = f"{filename}_min{output_ext}"

    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

    print(f"✓ Succès ! Fichier sauvegardé : {os.path.basename(output_path)}")
    if not settings:
        print(
            f"Gain d'espace total : {((original_size - new_size) / original_size) * 100:.2f}%"
        )
        print(f"Nouvelle taille : {format_size(new_size)}")
    
    return {"choix": choix, "quality": quality if choix == "2" else None, "use_webp": (save_format == "WEBP") if choix == "2" else None}


if __name__ == "__main__":
    print(
        r"""
 ____            _  ____                                                   
/ ___| _   _  __| |/ ___|___  _ __ ___  _ __  _ __ ___  ___ ___  ___  _ __ 
\___ \| | | |/ _` | |   / _ \| '_ ` _ \| '_ \| '__/ _ \/ __/ __|/ _ \| '__|
 ___) | |_| | (_| | |__| (_) | | | | | | |_) | | |  __/\__ \__ \ (_) | |   
|____/ \__,_|\__,_|\____\___/|_| |_| |_| .__/|_|  \___||___/___/\___/|_|   
                                       |_|                                 
    """
    )
    if len(sys.argv) < 2:
        print(
            "🖼️  Utilisation : python image_compressor.py <image_ou_dossier_1> [image_ou_dossier_2] ..."
        )
        print("\nExemples :")
        print("  python image_compressor.py mon_image.jpg")
        print("  python image_compressor.py ./mon_dossier_images")
        sys.exit(0)

    # Collecte de tous les fichiers à traiter
    target_files = []
    valid_extensions = (".png", ".jpeg", ".jpg", ".webp", ".mpo", ".gif")

    for path in sys.argv[1:]:
        if os.path.isdir(path):
            files = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(valid_extensions)]
            if not files:
                print(f"[Alerte] Aucun fichier image valide trouvé dans le dossier : {path}")
            target_files.extend(files)
        elif os.path.isfile(path):
            if path.lower().endswith(valid_extensions):
                target_files.append(path)
            else:
                print(f"[Alerte] Le fichier {path} n'est pas une image supportée.")
        else:
            print(f"[Erreur] {path} n'est ni un fichier ni un dossier valide.")

    if not target_files:
        print("[Erreur] Aucun fichier à traiter.")
        sys.exit(1)

    # Si on a plusieurs images, on propose d'appliquer les mêmes réglages
    batch_settings = None
    if len(target_files) > 1:
        rep = input(f"\n📦 {len(target_files)} images détectées. Voulez-vous appliquer les mêmes réglages à toutes ? (o/n) : ").strip().lower()
        if rep == 'o':
            # On exécute la première image pour récupérer les réglages
            print("\n--- Configuration des réglages groupés ---")
            res = compress_image(target_files[0])
            if res:
                batch_settings = res
                batch_settings["skip_if_larger"] = True
                # Traiter le reste avec ces réglages
                for path in target_files[1:]:
                    compress_image(path, settings=batch_settings)
            else:
                print("Abandon du traitement groupé ou erreur sur la première image.")
            sys.exit(0)

    # Traitement individuel (par défaut ou si 'n' a été répondu)
    for path in target_files:
        compress_image(path)
