"""Optimisation sûre de documents DOCX, principalement via leurs médias intégrés."""

from __future__ import annotations

import copy
import io
import os
import posixpath
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import quote, unquote, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from ..filesystem import collect_target_files, unique_path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - dépendance contrôlée au runtime
    Image = None

DOCX_EXTENSIONS = (".docx",)
RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
JPEG_CONTENT_TYPE = "image/jpeg"
PNG_CONTENT_TYPE = "image/png"


class DocxOptimizationError(RuntimeError):
    """Erreur empêchant l'optimisation ou la validation d'un DOCX."""


@dataclass(frozen=True)
class DocxMediaChange:
    """Transformation appliquée à un média interne au DOCX."""

    source_name: str
    output_name: str
    action: str
    original_size: int
    optimized_size: int
    transparent: bool = False
    photographic: bool | None = None

    @property
    def saved_bytes(self) -> int:
        return self.original_size - self.optimized_size


@dataclass
class DocxOptimizationResult:
    """Bilan d'une optimisation de document DOCX."""

    source: Path
    output: Path
    original_size: int
    optimized_size: int
    media_total: int
    changes: list[DocxMediaChange] = field(default_factory=list)

    @property
    def changed_media(self) -> int:
        return len(self.changes)

    @property
    def png_to_jpeg(self) -> int:
        return sum(change.action == "png_to_jpeg" for change in self.changes)

    @property
    def png_lossless(self) -> int:
        return sum(change.action == "png_lossless" for change in self.changes)

    @property
    def jpeg_recompressed(self) -> int:
        return sum(change.action == "jpeg_recompressed" for change in self.changes)

    @property
    def saved_bytes(self) -> int:
        return self.original_size - self.optimized_size

    @property
    def reduction_percent(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return (self.saved_bytes / self.original_size) * 100.0


def collect_docx(paths: Iterable[str | os.PathLike[str]]) -> list[Path]:
    """Collecte les fichiers DOCX depuis des fichiers et dossiers."""
    return [
        Path(path)
        for path in collect_target_files(
            paths,
            DOCX_EXTENSIONS,
            item_label="un document DOCX",
        )
    ]


def _require_pillow() -> None:
    if Image is None:
        raise DocxOptimizationError(
            "Pillow est requis pour optimiser les images DOCX. Installez-le avec : pip install Pillow"
        )


def _normalize_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    aliases = {
        "1": "lossless",
        "2": "smart",
        "3": "aggressive",
        "sans_perte": "lossless",
        "sans-perte": "lossless",
        "intelligent": "smart",
        "agressif": "aggressive",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"lossless", "smart", "aggressive"}:
        raise DocxOptimizationError(
            "Mode invalide. Utilisez lossless, smart ou aggressive."
        )
    return normalized


def _validate_quality(quality: int) -> int:
    try:
        normalized = int(quality)
    except (TypeError, ValueError) as error:
        raise DocxOptimizationError("La qualité JPEG doit être un entier entre 1 et 100.") from error
    if not 1 <= normalized <= 100:
        raise DocxOptimizationError("La qualité JPEG doit être comprise entre 1 et 100.")
    return normalized


def _validate_min_gain(value: float) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as error:
        raise DocxOptimizationError("Le gain minimum doit être un pourcentage valide.") from error
    if not 0 <= normalized <= 100:
        raise DocxOptimizationError("Le gain minimum doit être compris entre 0 et 100.")
    return normalized


def _default_output_path(source: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return unique_path(source.with_name(f"{source.stem}_Optimized_{timestamp}.docx"))


def _has_used_transparency(image) -> bool:
    """Détecte une transparence réellement utilisée, pas seulement un canal alpha opaque."""
    if image.mode in {"RGBA", "LA"}:
        alpha = image.getchannel("A")
        minimum, _maximum = alpha.getextrema()
        return minimum < 255
    if image.mode == "P" and "transparency" in image.info:
        converted = image.convert("RGBA")
        minimum, _maximum = converted.getchannel("A").getextrema()
        return minimum < 255
    return False


def _looks_photographic(image) -> bool:
    """Heuristique prudente : beaucoup de couleurs = photo/illustration riche."""
    if image.width < 96 or image.height < 96:
        return False
    sample = image.convert("RGB")
    sample.thumbnail((256, 256))
    # getcolors renvoie None au-delà de maxcolors : comportement recherché ici.
    colors = sample.getcolors(maxcolors=2048)
    return colors is None


def _png_save_options(image) -> dict:
    options: dict = {"optimize": True, "compress_level": 9}
    if image.info.get("icc_profile"):
        options["icc_profile"] = image.info["icc_profile"]
    if image.info.get("dpi"):
        options["dpi"] = image.info["dpi"]
    if image.info.get("exif"):
        options["exif"] = image.info["exif"]
    return options


def _jpeg_save_options(image, quality: int) -> dict:
    options: dict = {
        "quality": quality,
        "optimize": True,
        "progressive": True,
    }
    if image.info.get("icc_profile"):
        options["icc_profile"] = image.info["icc_profile"]
    if image.info.get("dpi"):
        options["dpi"] = image.info["dpi"]
    if image.info.get("exif"):
        options["exif"] = image.info["exif"]
    return options


def _encode_png_lossless(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", **_png_save_options(image))
    return buffer.getvalue()


def _encode_jpeg(image, quality: int) -> bytes:
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", **_jpeg_save_options(image, quality))
    return buffer.getvalue()


def _gain_percent(original_size: int, new_size: int) -> float:
    if original_size <= 0:
        return 0.0
    return ((original_size - new_size) / original_size) * 100.0


def _candidate_png(
    name: str,
    data: bytes,
    *,
    mode: str,
    jpeg_quality: int,
    min_savings_percent: float,
) -> tuple[bytes, str, bool, bool] | None:
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        if (source.format or "").upper() != "PNG":
            return None
        transparent = _has_used_transparency(source)
        photographic = _looks_photographic(source)
        image = source.copy()
        image.info.update(source.info)

    best_data = data
    best_action: str | None = None

    lossless_data = _encode_png_lossless(image)
    if len(lossless_data) < len(best_data):
        best_data = lossless_data
        best_action = "png_lossless"

    may_convert = mode in {"smart", "aggressive"} and not transparent
    if may_convert and (mode == "aggressive" or photographic):
        jpeg_data = _encode_jpeg(image, jpeg_quality)
        if (
            len(jpeg_data) < len(best_data)
            and _gain_percent(len(data), len(jpeg_data)) >= min_savings_percent
        ):
            best_data = jpeg_data
            best_action = "png_to_jpeg"

    if best_action is None:
        return None
    return best_data, best_action, transparent, photographic


def _candidate_jpeg(
    data: bytes,
    *,
    jpeg_quality: int,
    min_savings_percent: float,
) -> bytes | None:
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        if (source.format or "").upper() not in {"JPEG", "MPO"}:
            return None
        image = source.copy()
        image.info.update(source.info)
    candidate = _encode_jpeg(image, jpeg_quality)
    if (
        len(candidate) < len(data)
        and _gain_percent(len(data), len(candidate)) >= min_savings_percent
    ):
        return candidate
    return None


def _choose_media_name(old_name: str, used_names: set[str]) -> str:
    path = PurePosixPath(old_name)
    candidate = str(path.with_suffix(".jpg"))
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate
    index = 2
    while True:
        candidate = str(path.with_name(f"{path.stem}_optimized_{index}.jpg"))
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        index += 1


def _relationship_source_dir(rels_name: str) -> str:
    path = PurePosixPath(rels_name)
    parts = list(path.parts)
    try:
        rels_index = len(parts) - 1 - parts[::-1].index("_rels")
    except ValueError:
        return str(path.parent)
    return str(PurePosixPath(*parts[:rels_index])) if rels_index else ""


def _resolve_internal_target(rels_name: str, target: str) -> str | None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    raw_path = unquote(parsed.path).replace("\\", "/")
    if not raw_path:
        return None
    if raw_path.startswith("/"):
        normalized = posixpath.normpath(raw_path.lstrip("/"))
    else:
        source_dir = _relationship_source_dir(rels_name)
        normalized = posixpath.normpath(posixpath.join(source_dir, raw_path))
    if normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def _target_for_new_part(rels_name: str, original_target: str, new_part: str) -> str:
    parsed = urlsplit(original_target)
    if parsed.path.startswith("/"):
        new_path = "/" + new_part
    else:
        source_dir = _relationship_source_dir(rels_name)
        new_path = posixpath.relpath(new_part, source_dir or ".")
    encoded_path = quote(new_path, safe="/:@!$&'()*+,;=-._~%")
    return urlunsplit((parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment))


def _update_relationships(
    rels_name: str,
    xml_data: bytes,
    rename_map: dict[str, str],
) -> tuple[bytes, int]:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as error:
        raise DocxOptimizationError(f"Relations XML invalides : {rels_name}") from error

    changed = 0
    for relationship in root.findall(f"{{{RELATIONSHIPS_NS}}}Relationship"):
        if relationship.get("TargetMode", "").lower() == "external":
            continue
        target = relationship.get("Target")
        if not target:
            continue
        resolved = _resolve_internal_target(rels_name, target)
        if resolved in rename_map:
            relationship.set(
                "Target",
                _target_for_new_part(rels_name, target, rename_map[resolved]),
            )
            changed += 1

    if not changed:
        return xml_data, 0
    ET.register_namespace("", RELATIONSHIPS_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), changed


def _update_content_types(
    xml_data: bytes,
    rename_map: dict[str, str],
) -> bytes:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as error:
        raise DocxOptimizationError("[Content_Types].xml est invalide.") from error

    defaults = root.findall(f"{{{CONTENT_TYPES_NS}}}Default")
    has_jpg = any(
        (element.get("Extension") or "").lower() == "jpg"
        and (element.get("ContentType") or "").lower() == JPEG_CONTENT_TYPE
        for element in defaults
    )
    if rename_map and not has_jpg:
        ET.SubElement(
            root,
            f"{{{CONTENT_TYPES_NS}}}Default",
            {"Extension": "jpg", "ContentType": JPEG_CONTENT_TYPE},
        )

    for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        part_name = (override.get("PartName") or "").lstrip("/")
        if part_name in rename_map:
            override.set("PartName", "/" + rename_map[part_name])
            override.set("ContentType", JPEG_CONTENT_TYPE)

    ET.register_namespace("", CONTENT_TYPES_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _clone_zip_info(info: zipfile.ZipInfo, filename: str) -> zipfile.ZipInfo:
    cloned = copy.copy(info)
    cloned.filename = filename
    cloned.orig_filename = filename
    return cloned


def _write_entry(zout: zipfile.ZipFile, info: zipfile.ZipInfo, data: bytes) -> None:
    compress_type = info.compress_type
    if compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
        compress_type = zipfile.ZIP_DEFLATED
    compresslevel = 9 if compress_type == zipfile.ZIP_DEFLATED else None
    zout.writestr(info, data, compress_type=compress_type, compresslevel=compresslevel)


def _validate_docx_structure(archive: zipfile.ZipFile, source: Path) -> None:
    names = set(archive.namelist())
    required = {"[Content_Types].xml", "word/document.xml"}
    missing = sorted(required - names)
    if missing:
        raise DocxOptimizationError(
            f"{source.name} n'est pas un DOCX valide : élément(s) manquant(s) : {', '.join(missing)}"
        )


def verify_docx_package(path: str | os.PathLike[str]) -> None:
    """Vérifie CRC, XML de base et cibles internes des relations OOXML."""
    document = Path(path)
    try:
        with zipfile.ZipFile(document, "r") as archive:
            _validate_docx_structure(archive, document)
            bad_member = archive.testzip()
            if bad_member:
                raise DocxOptimizationError(
                    f"Archive DOCX corrompue : CRC invalide pour {bad_member}."
                )
            names = set(archive.namelist())
            try:
                ET.fromstring(archive.read("[Content_Types].xml"))
                ET.fromstring(archive.read("word/document.xml"))
            except ET.ParseError as error:
                raise DocxOptimizationError("XML principal du DOCX invalide.") from error

            for rels_name in sorted(name for name in names if name.endswith(".rels")):
                try:
                    root = ET.fromstring(archive.read(rels_name))
                except ET.ParseError as error:
                    raise DocxOptimizationError(
                        f"Relations XML invalides : {rels_name}"
                    ) from error
                for relationship in root.findall(
                    f"{{{RELATIONSHIPS_NS}}}Relationship"
                ):
                    if relationship.get("TargetMode", "").lower() == "external":
                        continue
                    target = relationship.get("Target")
                    if not target:
                        continue
                    resolved = _resolve_internal_target(rels_name, target)
                    if resolved and resolved not in names:
                        raise DocxOptimizationError(
                            f"Relation interne cassée : {rels_name} -> {target}"
                        )
    except zipfile.BadZipFile as error:
        raise DocxOptimizationError(f"Archive DOCX invalide : {document}") from error


def optimize_docx(
    source: str | os.PathLike[str],
    output: str | os.PathLike[str] | None = None,
    *,
    mode: str = "smart",
    jpeg_quality: int = 85,
    min_savings_percent: float = 10.0,
) -> DocxOptimizationResult:
    """Optimise un DOCX sans modifier l'original.

    Modes :
    - ``lossless`` : recompression PNG sans perte uniquement ;
    - ``smart`` : idem + conversion JPEG des PNG opaques à profil photographique ;
    - ``aggressive`` : idem + tous les PNG opaques et recompression des JPEG existants.
    """
    _require_pillow()
    normalized_mode = _normalize_mode(mode)
    quality = _validate_quality(jpeg_quality)
    min_gain = _validate_min_gain(min_savings_percent)

    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise DocxOptimizationError(f"Document introuvable : {source_path}")
    if source_path.suffix.lower() != ".docx":
        raise DocxOptimizationError("Seuls les fichiers .docx sont pris en charge.")

    output_path = (
        Path(output).expanduser().resolve()
        if output is not None
        else _default_output_path(source_path).resolve()
    )
    if output_path.suffix.lower() != ".docx":
        output_path = output_path.with_suffix(".docx")
    if output_path == source_path:
        raise DocxOptimizationError("Le fichier de sortie ne peut pas écraser le DOCX original.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path = unique_path(output_path)

    original_size = source_path.stat().st_size
    replacements: dict[str, tuple[str, bytes]] = {}
    xml_replacements: dict[str, bytes] = {}
    rename_map: dict[str, str] = {}
    changes: list[DocxMediaChange] = []

    try:
        with zipfile.ZipFile(source_path, "r") as archive:
            _validate_docx_structure(archive, source_path)
            infos = archive.infolist()
            names = {info.filename for info in infos}
            used_names = set(names)
            media_names = sorted(
                name
                for name in names
                if name.startswith("word/media/") and not name.endswith("/")
            )

            for name in media_names:
                suffix = PurePosixPath(name).suffix.lower()
                if suffix not in {".png", ".jpg", ".jpeg"}:
                    continue
                data = archive.read(name)
                try:
                    if suffix == ".png":
                        candidate = _candidate_png(
                            name,
                            data,
                            mode=normalized_mode,
                            jpeg_quality=quality,
                            min_savings_percent=min_gain,
                        )
                        if candidate is None:
                            continue
                        optimized, action, transparent, photographic = candidate
                        if action == "png_to_jpeg":
                            output_name = _choose_media_name(name, used_names)
                            rename_map[name] = output_name
                        else:
                            output_name = name
                        replacements[name] = (output_name, optimized)
                        changes.append(
                            DocxMediaChange(
                                source_name=name,
                                output_name=output_name,
                                action=action,
                                original_size=len(data),
                                optimized_size=len(optimized),
                                transparent=transparent,
                                photographic=photographic,
                            )
                        )
                    elif normalized_mode == "aggressive":
                        candidate = _candidate_jpeg(
                            data,
                            jpeg_quality=quality,
                            min_savings_percent=min_gain,
                        )
                        if candidate is not None:
                            replacements[name] = (name, candidate)
                            changes.append(
                                DocxMediaChange(
                                    source_name=name,
                                    output_name=name,
                                    action="jpeg_recompressed",
                                    original_size=len(data),
                                    optimized_size=len(candidate),
                                )
                            )
                except Exception as error:
                    raise DocxOptimizationError(
                        f"Impossible d'analyser le média {name} : {error}"
                    ) from error

            if rename_map:
                for rels_name in sorted(name for name in names if name.endswith(".rels")):
                    updated, changed_count = _update_relationships(
                        rels_name, archive.read(rels_name), rename_map
                    )
                    if changed_count:
                        xml_replacements[rels_name] = updated
                xml_replacements["[Content_Types].xml"] = _update_content_types(
                    archive.read("[Content_Types].xml"), rename_map
                )

            if not replacements:
                shutil.copy2(source_path, output_path)
            else:
                file_descriptor, temporary_name = tempfile.mkstemp(
                    prefix=".sudmedia_docx_",
                    suffix=".tmp",
                    dir=output_path.parent,
                )
                os.close(file_descriptor)
                temporary_path = Path(temporary_name)
                try:
                    with zipfile.ZipFile(
                        temporary_path,
                        "w",
                        allowZip64=True,
                    ) as output_archive:
                        for info in infos:
                            name = info.filename
                            if name in replacements:
                                output_name, data = replacements[name]
                                target_info = _clone_zip_info(info, output_name)
                                _write_entry(output_archive, target_info, data)
                                continue
                            data = xml_replacements.get(name)
                            if data is None:
                                data = archive.read(name)
                            _write_entry(
                                output_archive,
                                _clone_zip_info(info, name),
                                data,
                            )
                    verify_docx_package(temporary_path)
                    os.replace(temporary_path, output_path)
                finally:
                    temporary_path.unlink(missing_ok=True)
    except zipfile.BadZipFile as error:
        raise DocxOptimizationError(f"Archive DOCX invalide : {source_path}") from error

    verify_docx_package(output_path)
    return DocxOptimizationResult(
        source=source_path,
        output=output_path,
        original_size=original_size,
        optimized_size=output_path.stat().st_size,
        media_total=len(media_names),
        changes=changes,
    )
