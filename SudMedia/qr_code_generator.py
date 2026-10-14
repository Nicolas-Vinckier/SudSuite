"""Generateur de QR codes personnalisables pour SudSuite."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .sudmedia_utils import configure_console_output, configure_pillow, unique_available_path
except ImportError:
    from sudmedia_utils import configure_console_output, configure_pillow, unique_available_path


ERROR_CORRECTION_LEVELS = {
    "L": "Environ 7% de correction d'erreur, QR plus leger",
    "M": "Environ 15% de correction d'erreur, equilibre par defaut",
    "Q": "Environ 25% de correction d'erreur, recommande avec un logo",
    "H": "Environ 30% de correction d'erreur, personnalisation maximale",
}

IMAGE_FORMATS = {
    "png": "PNG",
    "webp": "WEBP",
    "jpeg": "JPEG",
    "jpg": "JPEG",
}

PRESETS = ("simple", "standard", "advanced")
BOX_SIZE_LIMITS = (2, 40)
BORDER_LIMITS = (0, 20)


@dataclass(frozen=True)
class QRCodeConfig:
    data: str
    output: Path
    version: int | None = None
    error_correction: str = "M"
    box_size: int = 10
    border: int = 4
    fill_color: str = "#000000"
    back_color: str = "#ffffff"
    transparent: bool = False
    output_format: str = "png"
    logo: Path | None = None
    logo_ratio: float = 0.22
    rounded: bool = False
    allow_overwrite: bool = False


def print_banner() -> None:
    banner = r"""
 ____            _  ___  ____  
/ ___| _   _  __| |/ _ \|  _ \ 
\___ \| | | |/ _` | | | | |_) |
 ___) | |_| | (_| | |_| |  _ < 
|____/ \__,_|\__,_|\__\_\_| \_\
    """
    print(banner)


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("La valeur doit etre superieure a 0.")
    return number


def _version(value: str) -> int:
    number = _positive_int(value)
    if number > 40:
        raise argparse.ArgumentTypeError("La version QR doit etre comprise entre 1 et 40.")
    return number


def _logo_ratio(value: str) -> float:
    ratio = float(value)
    if ratio <= 0 or ratio > 0.35:
        raise argparse.ArgumentTypeError("Le ratio logo doit etre entre 0 et 0.35.")
    return ratio


def _yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "O/n" if default else "o/N"
    while True:
        answer = input(f"{prompt} ({suffix}) : ").strip().lower()
        if not answer:
            return default
        if answer in {"o", "oui", "y", "yes", "1"}:
            return True
        if answer in {"n", "non", "no", "0", "2"}:
            return False
        print("Repondez par o/oui ou n/non.")


def _choice(prompt: str, choices: tuple[str, ...], default: str) -> str:
    normalized_choices = {choice.lower(): choice for choice in choices}
    default_index = choices.index(default) + 1
    for index, choice in enumerate(choices, 1):
        print(f"{index}. {choice}")
    while True:
        answer = input(f"{prompt} [{default_index}] : ").strip().lower()
        if not answer:
            return default
        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(choices):
                return choices[index - 1]
        if answer in normalized_choices:
            return normalized_choices[answer]
        print(f"Choix invalide. Tapez un nombre entre 1 et {len(choices)}.")


def _described_choice(
    prompt: str,
    choices: tuple[tuple[str, str], ...],
    default: str,
) -> str:
    values = tuple(value for value, _description in choices)
    default_index = values.index(default) + 1
    for index, (value, description) in enumerate(choices, 1):
        print(f"{index}. {value} - {description}")
    while True:
        answer = input(f"{prompt} [{default_index}] : ").strip().lower()
        if not answer:
            return default
        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(values):
                return values[index - 1]
        for value in values:
            if answer == value.lower():
                return value
        print(f"Choix invalide. Tapez un nombre entre 1 et {len(values)}.")


def _ask_int(prompt: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    while True:
        answer = input(f"{prompt} [{default}] : ").strip()
        if not answer:
            return default
        try:
            value = int(answer)
        except ValueError:
            print("Veuillez saisir un nombre entier.")
            continue
        if value < minimum or (maximum is not None and value > maximum):
            limit = f" entre {minimum} et {maximum}" if maximum is not None else f" >= {minimum}"
            print(f"Valeur attendue{limit}.")
            continue
        return value


def _ask_float(prompt: str, default: float, minimum: float, maximum: float) -> float:
    while True:
        answer = input(f"{prompt} [{default}] : ").strip().replace(",", ".")
        if not answer:
            return default
        try:
            value = float(answer)
        except ValueError:
            print("Veuillez saisir un nombre.")
            continue
        if value < minimum or value > maximum:
            print(f"Valeur attendue entre {minimum} et {maximum}.")
            continue
        return value


def _ask_optional_path(prompt: str) -> Path | None:
    answer = input(f"{prompt} : ").strip().strip('"')
    return Path(answer) if answer else None


def _minimum_version_for_data(data: str, error_correction: str) -> int | None:
    qrcode, correction_levels = _load_qrcode_modules()
    qr = qrcode.QRCode(
        version=None,
        error_correction=correction_levels[error_correction],
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.version


def _ask_qr_version(data: str, error_correction: str) -> int:
    try:
        minimum_version = _minimum_version_for_data(data, error_correction)
    except RuntimeError:
        minimum_version = None

    if minimum_version:
        print(f"Version minimale pour ce contenu : {minimum_version}")
        return _ask_int(
            "Version QR",
            minimum_version,
            minimum=minimum_version,
            maximum=40,
        )
    return _ask_int("Version QR", 10, minimum=1, maximum=40)


def validate_config(config: QRCodeConfig) -> None:
    if config.box_size < BOX_SIZE_LIMITS[0] or config.box_size > BOX_SIZE_LIMITS[1]:
        raise ValueError(
            f"La taille des modules doit etre entre {BOX_SIZE_LIMITS[0]} et {BOX_SIZE_LIMITS[1]}."
        )
    if config.border < BORDER_LIMITS[0] or config.border > BORDER_LIMITS[1]:
        raise ValueError(
            f"La marge doit etre entre {BORDER_LIMITS[0]} et {BORDER_LIMITS[1]}."
        )
    if config.version is not None and (config.version < 1 or config.version > 40):
        raise ValueError("La version QR doit etre comprise entre 1 et 40.")
    if config.logo_ratio <= 0 or config.logo_ratio > 0.35:
        raise ValueError("Le ratio logo doit etre entre 0 et 0.35.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cree un QR code fonctionnel et hautement personnalisable.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("data", nargs="?", help="Texte, URL ou payload a encoder.")
    parser.add_argument("-o", "--output", help="Fichier de sortie.")
    parser.add_argument(
        "--preset",
        choices=PRESETS,
        default="standard",
        help="Niveau de complexite initial.",
    )
    parser.add_argument("--version", type=_version, help="Version QR fixe de 1 a 40.")
    parser.add_argument(
        "--error-correction",
        choices=tuple(ERROR_CORRECTION_LEVELS),
        default=None,
        help="Niveau de correction d'erreur.",
    )
    parser.add_argument("--box-size", type=_positive_int, help="Taille d'un module en pixels.")
    parser.add_argument("--border", type=int, help="Marge en modules autour du QR.")
    parser.add_argument("--fill-color", help="Couleur des modules, nom Pillow ou hex.")
    parser.add_argument("--back-color", help="Couleur du fond, nom Pillow ou hex.")
    parser.add_argument("--transparent", action="store_true", help="Fond transparent en PNG/WebP.")
    parser.add_argument(
        "--format",
        choices=tuple(IMAGE_FORMATS),
        default=None,
        help="Format de sortie.",
    )
    parser.add_argument("--logo", help="Image a inserer au centre.")
    parser.add_argument("--logo-ratio", type=_logo_ratio, help="Largeur du logo par rapport au QR.")
    parser.add_argument("--rounded", action="store_true", help="Modules arrondis si qrcode[pil] le supporte.")
    parser.add_argument("--overwrite", action="store_true", help="Remplace le fichier de sortie s'il existe.")
    return parser


def default_config_for_preset(preset: str) -> dict[str, object]:
    if preset == "simple":
        return {
            "error_correction": "M",
            "box_size": 10,
            "border": 4,
            "fill_color": "#000000",
            "back_color": "#ffffff",
            "output_format": "png",
            "logo_ratio": 0.20,
        }
    if preset == "advanced":
        return {
            "error_correction": "H",
            "box_size": 14,
            "border": 4,
            "fill_color": "#111111",
            "back_color": "#ffffff",
            "output_format": "png",
            "logo_ratio": 0.22,
        }
    return {
        "error_correction": "Q",
        "box_size": 12,
        "border": 4,
        "fill_color": "#000000",
        "back_color": "#ffffff",
        "output_format": "png",
        "logo_ratio": 0.22,
    }


def default_output_path(output_format: str, name: str = "qr_code") -> Path:
    return Path.cwd() / "QR_Codes" / f"{name}.{output_format}"


def interactive_config() -> QRCodeConfig:
    data = input("Contenu du QR code (URL, texte, Wi-Fi, vCard...) : ").strip()
    if not data:
        raise ValueError("Aucun contenu a encoder.")

    print("\n--- Niveau de personnalisation ---")
    preset = _described_choice(
        "Niveau",
        (
            ("simple", "QR classique, juste le contenu et la sortie"),
            ("standard", "couleurs, taille, format et correction d'erreur"),
            ("advanced", "version QR, logo, transparence, modules arrondis"),
        ),
        "standard",
    )
    defaults = default_config_for_preset(preset)

    output_format = str(defaults["output_format"])
    error_correction = str(defaults["error_correction"])
    box_size = int(defaults["box_size"])
    border = int(defaults["border"])
    fill_color = str(defaults["fill_color"])
    back_color = str(defaults["back_color"])
    transparent = False
    rounded = False
    version = None
    logo = None
    logo_ratio = float(defaults["logo_ratio"])

    if preset in {"standard", "advanced"}:
        print("\n--- Rendu ---")
        output_format = _choice("Format", ("png", "webp", "jpeg"), output_format)
        fill_color = input(f"Couleur du QR [{fill_color}] : ").strip() or fill_color
        back_color = input(f"Couleur du fond [{back_color}] : ").strip() or back_color
        if output_format in {"png", "webp"}:
            transparent = _yes_no("Fond transparent", False)
        box_size = _ask_int(
            "Taille des modules en pixels",
            box_size,
            minimum=BOX_SIZE_LIMITS[0],
            maximum=BOX_SIZE_LIMITS[1],
        )
        border = _ask_int(
            "Marge autour du QR",
            border,
            minimum=BORDER_LIMITS[0],
            maximum=BORDER_LIMITS[1],
        )

        print("\n--- Fiabilite ---")
        error_correction = _described_choice(
            "Correction d'erreur",
            tuple(ERROR_CORRECTION_LEVELS.items()),
            error_correction,
        )

    if preset == "advanced":
        print("\n--- Options avancees ---")
        if _yes_no("Forcer une version QR precise", False):
            version = _ask_qr_version(data, error_correction)
        rounded = _yes_no("Modules arrondis", False)
        logo = _ask_optional_path("Logo central (laisser vide pour aucun)")
        if logo:
            logo_ratio = _ask_float("Taille du logo, ratio du QR", logo_ratio, 0.01, 0.35)
            if error_correction in {"L", "M"}:
                print("Conseil : avec un logo, Q ou H est plus fiable.")
                if _yes_no("Passer automatiquement en correction H", True):
                    error_correction = "H"

    print("\n--- Sortie ---")
    default_folder = Path.cwd() / "QR_Codes"
    folder_input = input(f"Dossier de sortie [{default_folder}] : ").strip().strip('"')
    output_folder = Path(folder_input) if folder_input else default_folder
    name_input = input("Nom du fichier sans extension [qr_code] : ").strip()
    output_name = name_input or "qr_code"
    output = output_folder / f"{output_name}.{output_format}"
    overwrite = _yes_no("Remplacer le fichier s'il existe", False)

    return QRCodeConfig(
        data=data,
        output=output,
        version=version,
        error_correction=error_correction,
        box_size=box_size,
        border=border,
        fill_color=fill_color,
        back_color=back_color,
        transparent=transparent,
        output_format=output_format,
        logo=logo,
        logo_ratio=logo_ratio,
        rounded=rounded,
        allow_overwrite=overwrite,
    )


def config_from_args(args: argparse.Namespace) -> QRCodeConfig:
    data = args.data or input("Contenu du QR code (URL, texte, Wi-Fi, vCard...) : ").strip()
    if not data:
        raise ValueError("Aucun contenu a encoder.")

    defaults = default_config_for_preset(args.preset)
    output_format = (args.format or defaults["output_format"]).lower()
    output = Path(args.output) if args.output else default_output_path(output_format)
    if output.suffix:
        suffix_format = output.suffix.lstrip(".").lower()
        if args.format is None and suffix_format in IMAGE_FORMATS:
            output_format = suffix_format
    else:
        output = output.with_suffix(f".{output_format}")

    border = args.border if args.border is not None else int(defaults["border"])
    if border < 0:
        raise ValueError("La marge ne peut pas etre negative.")

    return QRCodeConfig(
        data=data,
        output=output,
        version=args.version,
        error_correction=args.error_correction or str(defaults["error_correction"]),
        box_size=args.box_size or int(defaults["box_size"]),
        border=border,
        fill_color=args.fill_color or str(defaults["fill_color"]),
        back_color=args.back_color or str(defaults["back_color"]),
        transparent=args.transparent,
        output_format=output_format,
        logo=Path(args.logo) if args.logo else None,
        logo_ratio=args.logo_ratio or float(defaults["logo_ratio"]),
        rounded=args.rounded,
        allow_overwrite=args.overwrite,
    )


def _load_qrcode_modules():
    try:
        import qrcode
        from qrcode.constants import (
            ERROR_CORRECT_H,
            ERROR_CORRECT_L,
            ERROR_CORRECT_M,
            ERROR_CORRECT_Q,
        )
    except ImportError as exc:
        raise RuntimeError(
            "La bibliotheque 'qrcode' n'est pas installee. "
            'Installez-la avec : pip install "qrcode[pil]"'
        ) from exc

    return qrcode, {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }


def _make_image(qr, config: QRCodeConfig):
    if not config.rounded:
        image = qr.make_image(
            fill_color=config.fill_color,
            back_color=config.back_color,
        ).convert("RGBA" if config.transparent else "RGB")
        return _make_background_transparent(image, config) if config.transparent else image

    try:
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
    except ImportError:
        image = qr.make_image(
            fill_color=config.fill_color,
            back_color=config.back_color,
        ).convert("RGBA" if config.transparent else "RGB")
        return _make_background_transparent(image, config) if config.transparent else image

    image = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        fill_color=config.fill_color,
        back_color=config.back_color,
    ).convert("RGBA" if config.transparent else "RGB")
    return _make_background_transparent(image, config) if config.transparent else image


def _make_background_transparent(image, config: QRCodeConfig):
    from PIL import ImageColor

    background = ImageColor.getrgb(config.back_color)
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y][:3] == background:
                pixels[x, y] = (background[0], background[1], background[2], 0)
    return image


def _paste_logo(image, config: QRCodeConfig):
    if not config.logo:
        return image
    if not config.logo.is_file():
        raise FileNotFoundError(f"Logo introuvable : {config.logo}")

    from PIL import Image

    with Image.open(config.logo) as logo_source:
        logo = logo_source.convert("RGBA")

    logo_size = max(1, int(min(image.size) * config.logo_ratio))
    logo.thumbnail((logo_size, logo_size))
    x = (image.width - logo.width) // 2
    y = (image.height - logo.height) // 2
    image = image.convert("RGBA")
    image.alpha_composite(logo, (x, y))
    return image


def generate_qr_code(config: QRCodeConfig) -> Path:
    validate_config(config)
    qrcode, correction_levels = _load_qrcode_modules()

    if config.output_format not in IMAGE_FORMATS:
        raise ValueError(f"Format non supporte : {config.output_format}")
    if config.transparent and IMAGE_FORMATS[config.output_format] == "JPEG":
        raise ValueError("Le JPEG ne supporte pas la transparence.")

    try:
        from PIL import Image

        configure_pillow(Image)
    except ImportError as exc:
        raise RuntimeError(
            "La bibliotheque 'Pillow' est requise. "
            'Installez-la avec : pip install "qrcode[pil]"'
        ) from exc

    qr = qrcode.QRCode(
        version=config.version,
        error_correction=correction_levels[config.error_correction],
        box_size=config.box_size,
        border=config.border,
    )
    qr.add_data(config.data)
    try:
        qr.make(fit=config.version is None)
    except Exception as exc:
        if "Code length overflow" not in str(exc):
            raise
        minimum_version = _minimum_version_for_data(config.data, config.error_correction)
        raise ValueError(
            "La version QR choisie est trop petite pour ce contenu. "
            f"Utilisez la version {minimum_version} minimum, ou ne forcez pas la version."
        ) from exc

    image = _make_image(qr, config)
    image = _paste_logo(image, config)

    output = config.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if not config.allow_overwrite:
        output = Path(unique_available_path(output))

    image_format = IMAGE_FORMATS[config.output_format]
    if image_format == "JPEG":
        image = image.convert("RGB")
    image.save(output, format=image_format)
    return output


def main(argv: list[str] | None = None) -> int:
    configure_console_output()
    print_banner()
    parser = build_parser()
    effective_argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(effective_argv)

    try:
        config = interactive_config() if not effective_argv else config_from_args(args)
        output = generate_qr_code(config)
    except Exception as exc:
        print(f"Erreur : {exc}")
        return 2

    print(f"QR code cree : {output}")
    print(f"Correction d'erreur : {config.error_correction} - {ERROR_CORRECTION_LEVELS[config.error_correction]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
