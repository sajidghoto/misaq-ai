"""Supported model and chunking combinations for Experiment B."""

EXP_B_COMBINATIONS: tuple[tuple[str, str], ...] = (
    ("bge-small-en-v1.5", "section_aware"),
    ("bge-small-en-v1.5", "fixed_size"),
    ("bge-base-en-v1.5", "section_aware"),
    ("bge-base-en-v1.5", "fixed_size"),
    ("bge-large-en-v1.5", "section_aware"),
    ("bge-large-en-v1.5", "fixed_size"),
    ("all-MiniLM-L6-v2", "fixed_size"),
)
