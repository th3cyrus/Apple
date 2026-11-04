"""Exclude stations explicitly devoted to Islamic/Quranic religious programming.

Do not classify ordinary Arabic-language stations, countries, or personal names
as religious. Only explicit station identity, description, tags and stream text
count; we do not inspect listeners or infer anyone's religion.
"""
import re

_EXCLUDED = re.compile(
    r"(?:\b(?:qur(?:an|aan|a?n)|koran|islam(?:ic|ism)?|muslim|masjid|mosque|"
    r"hadith|sunnah|adhan|azaan|azan|nasheed|naat|allah|al[- ]?quran|"
    r"makkah|mecca|medina|madinah|hajj|shariah|salaat|salah[- ]?radio)\b|"
    r"قرآن|قران|القرآن|القران|اسلام|إسلام|اسلامي|إسلامي|مسلم|مسجد|"
    r"أذان|اذان|تلاوة|تلاوه|الحديث|السنّة|السنة|القرءان|"
    r"القران الكريم|القرآن الكريم|دعوة إسلامية|دعوة اسلامية|اذاعة القرآن|إذاعة القرآن)",
    re.IGNORECASE,
)


def is_excluded_program(*fields):
    return any(isinstance(field, str) and _EXCLUDED.search(field)
               for field in fields)
