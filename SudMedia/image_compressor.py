import os
import io
import sys

try:
    from .sudmedia_utils import (
        analyze_quality,
        analyze_size_change,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        format_size,
        get_original_image_quality,
        image_save_options,
        prepare_image_for_format,
        prepare_image_for_quality,
        print_quality_analysis,
    )
except ImportError:
    from sudmedia_utils import (
        analyze_quality,
        analyze_size_change,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        format_size,
        get_original_image_quality,
        image_save_options,
        prepare_image_for_format,
        prepare_image_for_quality,
        print_quality_analysis,
    )

configure_console_output()

try:
    from PIL import Image
    configure_pillow(Image)
except ImportError:
    print("[Erreur] La bibliotheque 'Pillow' n'est pas installee.")
    print("Veuillez l'installer avec la commande suivante :")
    print("   pip install Pillow")
    sys.exit(1)


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
        with Image.open(input_path) as source_image:
            fmt = source_image.format.lower() if source_image.format else "inconnu"
            original_quality = get_original_image_quality(source_image)
            img = source_image.copy()
    except Exception as e:
        print(f"[Erreur] lors de l'ouverture de l'image : {e}")
        return None

    if fmt not in ["png", "jpeg", "jpg", "webp", "mpo", "gif"]:
        print(
            f"[Attention] Format {fmt} non standard. L'image sera convertie automatiquement."
        )

    save_format = (
        "JPEG"
        if fmt in ["jpg", "jpeg", "mpo"]
        else ("WEBP" if fmt == "webp" else "PNG")
    )

    img = prepare_image_for_format(img, save_format)

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
        
        save_params = image_save_options(
            save_format,
            compression_mode="lossless",
            original_quality=original_quality,
        )
        img.save(buffer, format=save_format, **save_params)

        new_size = buffer.tell()
        if not settings:
            print(f"✓ Optimisation terminée.")

    elif choix == "2":
        if not settings:
            print("\n--- Compression AVEC PERTE ---")
            quality_analysis = analyze_quality(
                input("Niveau de qualite souhaite (1-100, ex: 70) : ").strip(),
                default=70,
            )
            quality = quality_analysis.quality

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
            quality_analysis = analyze_quality(settings.get("quality"), default=70)
            quality = quality_analysis.quality
            use_webp = settings.get("use_webp", True)

        if use_webp:
            save_format = "WEBP"

        img = prepare_image_for_quality(
            img,
            save_format,
            compression_mode="lossy",
            quality=quality,
        )

        if not settings:
            print("\n[Analyse] Calcul des risques et BENEFICES en cours...")

        save_params = image_save_options(
            save_format,
            compression_mode="lossy",
            quality=quality,
        )
        img.save(buffer, format=save_format, **save_params)

        new_size = buffer.tell()

        if not settings:
            size_analysis = analyze_size_change(original_size, new_size)

            print("\n" + "= " * 15)
            print("ANALYSE DES RISQUES ET BENEFICES")
            print("= " * 15)

            print(
                "BENEFICE : Reduction du poids de "
                f"{size_analysis.reduction_percent:.2f}%"
            )
            print(f"   (De {format_size(original_size)} à {format_size(new_size)})")

            if size_analysis.variation > 0:
                print(
                    "\n[Attention] La compression a AUGMENTE la taille de l'image (l'image d'origine est deja trop compressee)."
                )

            print()
            print_quality_analysis(quality_analysis)

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

    size_analysis = analyze_size_change(original_size, new_size)
    print(f"✓ Succès ! Fichier sauvegardé : {os.path.basename(output_path)}")
    if not settings:
        print(f"Gain d'espace total : {size_analysis.reduction_percent:.2f}%")
        print(f"Nouvelle taille : {format_size(new_size)}")
    
    return {
        "choix": choix,
        "quality": quality if choix == "2" else None,
        "use_webp": (save_format == "WEBP") if choix == "2" else None,
    }


def print_banner():
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


def get_target_files(paths):
    """Collecte récursivement les formats acceptés par le compresseur."""
    return collect_target_files(
        paths,
        (".png", ".jpeg", ".jpg", ".webp", ".mpo", ".gif"),
        item_label="une image supportée",
    )


def main():
    print_banner()
    if len(sys.argv) < 2:
        print(
            "🖼️  Utilisation : python image_compressor.py <image_ou_dossier_1> [image_ou_dossier_2] ..."
        )
        print("\nExemples :")
        print("  python image_compressor.py mon_image.jpg")
        print("  python image_compressor.py ./mon_dossier_images")
        sys.exit(0)

    target_files = get_target_files(sys.argv[1:])

    if not target_files:
        print("[Erreur] Aucun fichier à traiter.")
        sys.exit(1)

    # Si on a plusieurs images, on propose d'appliquer les mêmes réglages
    batch_settings = None
    if len(target_files) > 1:
        rep = (
            input(
                f"\n📦 {len(target_files)} images détectées. "
                "Voulez-vous appliquer les mêmes réglages à toutes ? (o/n) : "
            )
            .strip()
            .lower()
        )
        if rep == "o":
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


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption par l'utilisateur. Arrêt du traitement...")
