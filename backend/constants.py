import json

# Core subject identifiers (Korean) encoded via Unicode escapes to remain ASCII-only
SUBJECT_KO_KOREAN = "\uad6d\uc5b4"
SUBJECT_KO_MATH = "\uc218\ud559"
SUBJECT_KO_ENGLISH = "\uc601\uc5b4"

SUBJECTS = [
    SUBJECT_KO_KOREAN,
    SUBJECT_KO_MATH,
    SUBJECT_KO_ENGLISH,
]

STUDY_TAG = "study"
STUDY_TAG_KO = "\ud559\uc2b5"

DEFAULT_SUBJECT_RATIO_JSON = json.dumps(
    {
        SUBJECT_KO_KOREAN: 0.33,
        SUBJECT_KO_MATH: 0.34,
        SUBJECT_KO_ENGLISH: 0.33,
    },
    ensure_ascii=True,
)
