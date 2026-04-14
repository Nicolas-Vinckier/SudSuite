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
    for unit in ['O', 'Ko', 'Mo', 'Go']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} To"

def get_original_quality(img):
    """Tente de récupérer la qualité d'origine d'un JPEG."""
    return img.info.get("quality", 100)

def compress_image(input_path):
    if not os.path.exists(input_path):
        print(f"[Erreur] Le fichier {input_path} n'existe pas.")
        return

    original_size = os.path.getsize(input_path)
    print(f"\n[Info] Fichier en cours : {os.path.basename(input_path)}")
    print(f"[Poids] Taille originale  : {format_size(original_size)}")

    try:
        img = Image.open(input_path)
    except Exception as e:
        print(f"[Erreur] lors de l'ouverture de l'image : {e}")
        return

    # Identifier le format d'origine
    fmt = img.format.lower() if img.format else "inconnu"
    
    if fmt not in ['png', 'jpeg', 'jpg', 'webp', 'mpo', 'gif']:
        print(f"[Attention] Format {fmt} non standard. L'image sera convertie automatiquement.")

    save_format = 'JPEG' if fmt in ['jpg', 'jpeg', 'mpo'] else ('WEBP' if fmt == 'webp' else 'PNG')
    
    # Pour le support JPEG sans canal alpha (Les JPEG ne supportent pas la transparence RGBA)
    if save_format == 'JPEG' and img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')

    print("\n" + "="*55)
    print("🎨 SÉLECTION DU MODE DE COMPRESSION")
    print("="*55)
    print("1. SANS PERTE (Lossless) : Optimisation sans degradation (Meilleur pour garder la qualite 100%)")
    print("2. AVEC PERTE (Lossy)    : Reduction de la qualite pour un fichier beaucoup plus leger")
    
    choix = input("\nVotre choix (1 ou 2) : ").strip()

    buffer = io.BytesIO()
    
    if choix == '1':
        print("\n[Traitement] Compression SANS PERTE en cours...")
        if save_format == 'JPEG':
            # Meilleure conservation possible pour le JPEG via PIL
            q = get_original_quality(img)
            kwargs = {"quality": "keep"} if q != 100 else {"quality": 100, "subsampling": 0}
            try:
                 img.save(buffer, format='JPEG', optimize=True, **kwargs)
            except:
                 img.save(buffer, format='JPEG', optimize=True, quality=100, subsampling=0)
        elif save_format == 'PNG':
            # L'optimisation PNG est nativement lossless.
            img.save(buffer, format='PNG', optimize=True)
        elif save_format == 'WEBP':
            # Vrai lossless pour WebP
            img.save(buffer, format='WEBP', lossless=True, quality=100, method=6)
        
        new_size = buffer.tell()
        print(f"✓ Optimisation terminée.")
        
    elif choix == '2':
        print("\n--- Compression AVEC PERTE ---")
        try:
            quality = int(input("Niveau de qualite souhaite (1-100, ex: 70) : ").strip())
        except ValueError:
            print("Entrée invalide. Utilisation de la qualité par défaut (70).")
            quality = 70
            
        quality = max(1, min(100, quality))

        # Proposition de conversion WebP : excellent compromis poids/qualité
        format_choisi = input("Voulez-vous convertir en WebP pour un gain maximum ? (o/n, defaut: o) : ").strip().lower()
        if format_choisi != 'n':
             save_format = 'WEBP'
             
        if save_format == 'WEBP' and img.mode not in ('RGB', 'RGBA'):
             img = img.convert('RGBA' if 'A' in img.mode else 'RGB')
             
        print("\n[Analyse] Calcul des risques et BENEFICES en cours...")

        if save_format == 'JPEG':
            img.save(buffer, format='JPEG', optimize=True, quality=quality)
        elif save_format == 'WEBP':
            img.save(buffer, format='WEBP', quality=quality, method=4)
        elif save_format == 'PNG':
            # Simulation de perte sur PNG : réduction drastique de la palette de couleurs
            colors = max(2, int((quality / 100) * 256))
            lossy_img = img.convert('P', palette=Image.ADAPTIVE, colors=colors)
            lossy_img.save(buffer, format='PNG', optimize=True)
            
        new_size = buffer.tell()
        
        loss_percentage = 100 - quality
        size_reduction = (original_size - new_size) / original_size * 100 if original_size > 0 else 0
        
        print("\n" + "= "*15)
        print("ANALYSE DES RISQUES ET BENEFICES")
        print("= "*15)
        
        print(f"BENEFICE : Reduction du poids de {size_reduction:.2f}%")
        print(f"   (De {format_size(original_size)} à {format_size(new_size)})")
        
        if size_reduction < 0:
            print("\n[Attention] La compression a AUGMENTE la taille de l'image (l'image d'origine est deja trop compressee).")
        
        print(f"\n[Risque] Degradaion de la qualite estimee a {loss_percentage}%.")
        if quality < 50:
            print("   -> RISQUE ELEVE  : Artefacts tres visibles, image potentiellement floue, couleurs baveuses.")
        elif quality < 80:
            print("   -> RISQUE MODERE : Legere perte de nettete ou petits artefacts (acceptable pour le web).")
        else:
            print("   -> RISQUE FAIBLE : Perte de qualite quasi imperceptible a l'oeil nu.")
        
        confirmer = input("\nProceder a la sauvegarde avec cette qualite ? (o/n) : ").strip().lower()
        if confirmer != 'o':
            print("Operation annulee par l'utilisateur.")
            return

    else:
        print("[Erreur] Choix invalide.")
        return
        
    print("\n" + "-"*55)
    
    # Si la taille est plus grande après compression sans perte -> aucun intérêt de la sauvegarder
    if new_size >= original_size and choix == '1':
        print("ℹ️ L'optimisation sans perte n'a pas permis de réduire la taille du fichier.")
        print("   L'image originale étant déjà optimale, aucune modification n'a été appliquée.")
        return

    # Construire le chemin de sortie
    filename, ext = os.path.splitext(input_path)
    output_ext = f".{save_format.lower()}"
    if save_format == 'JPEG': output_ext = '.jpg'
    
    # Éviter d'écraser l'original en ajoutant "_min"
    output_path = f"{filename}_min{output_ext}"

    with open(output_path, 'wb') as f:
        f.write(buffer.getvalue())

    print("Succes ! Fichier sauvegarde avec succes ! ")
    print(f"Chemin : {output_path}")
    print(f"Gain d'espace total : {((original_size - new_size) / original_size) * 100:.2f}%")
    print(f"Nouvelle taille : {format_size(new_size)}")

if __name__ == "__main__":
    print(r'''
   _____           _  _____                                                     
  / ____|         | |/ ____|                                                    
 | (___  _   _  __| | |     ___  _ __ ___  _ __  _ __ ___  ___ ___  ___  _ __   
  \___ \| | | |/ _` | |    / _ \| '_ ` _ \| '_ \| '__/ _ \/ __/ __|/ _ \| '__|  
  ____) | |_| | (_| | |___| (_) | | | | | | |_) | | |  __/\__ \__ \ (_) | |     
 |_____/ \__,_|\__,_|\_____\___/|_| |_| |_| .__/|_|  \___||___/___/\___/|_|     
                                          | |                                   
                                          |_|                                   
    ''')
    if len(sys.argv) < 2:
        print("🖼️  Utilisation : python image_compressor.py <chemin_vers_image_1> [chemin_2] ...")
        print("\nExemple :")
        print("  python image_compressor.py mon_image.jpg")
        sys.exit(0)
        
    for path in sys.argv[1:]:
        compress_image(path)
