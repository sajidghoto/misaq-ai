from enum import Enum


class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ActCode(_StrEnum):
    CA1872 = "CA1872"      # Contract Act, 1872
    SGA1930 = "SGA1930"    # Sale of Goods Act, 1930
    SRA1877 = "SRA1877"    # Specific Relief Act, 1877


class BlockType(_StrEnum):
    BODY = "body"
    ILLUSTRATION = "illustration"
    EXPLANATION = "explanation"
    PROVISO = "proviso"


class SectionStatus(_StrEnum):
    UNKNOWN = "unknown"        # parsed, not yet classified (parsing stage output)
    IN_FORCE = "in_force"
    REPEALED = "repealed"      # printed in contents as [Repealed] or "Rep. by ..."
    OMITTED = "omitted"        # printed as "[Omitted]" or inside an omitted range


class SystemId(_StrEnum):
    S1 = "S1"   # plain LLM
    S2 = "S2"   # structured prompt, no retrieval
    S3 = "S3"   # full RAG
    S4 = "S4"   # oracle RAG


class Backend(_StrEnum):
    CLOUD = "cloud"
    LOCAL = "local"


class CitationVerdict(_StrEnum):
    VALID = "valid"
    VALID_SECTION_BAD_SUBSECTION = "valid_section_bad_subsection"
    NONEXISTENT_SECTION = "nonexistent_section"
    WRONG_ACT = "wrong_act"
    REPEALED_OR_OMITTED = "repealed_or_omitted"
    OUT_OF_CORPUS = "out_of_corpus"     # real law we do not hold: NOT counted as fabricated
    MALFORMED = "malformed"


class SupportLabel(_StrEnum):
    SUPPORTS = "supports"
    PARTIAL = "partial"
    DOES_NOT = "does_not_support"


class ErrorType(_StrEnum):
    WRONG_RETRIEVAL = "wrong_retrieval"
    IGNORED_EVIDENCE = "ignored_evidence"
    FABRICATED_CITATION = "fabricated_citation"
    OVER_CLAIMING = "over_claiming"
