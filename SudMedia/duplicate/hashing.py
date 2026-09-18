"""Façade de compatibilité."""
from SudMedia.utils.hashing.binary import content_hash
from SudMedia.utils.hashing.visual import difference_hash, hamming_distance

__all__ = ["content_hash", "difference_hash", "hamming_distance"]
