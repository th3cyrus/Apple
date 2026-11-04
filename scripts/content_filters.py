"""Exclude radio stations explicitly devoted to religious programming.

Do not classify ordinary Arabic-language stations, countries, or personal names
as religious. Only explicit station identity, description, tags and stream text
count; we do not inspect listeners or infer anyone's religion.
"""
import re

_EXCLUDED = re.compile(
    r"(?:\b(?:qur(?:an|aan|a?n)|koran|islam(?:ic|ism)?|muslim|masjid|mosque|"
    r"hadith|sunnah|adhan|azaan|azan|nasheed|naat|allah|al[- ]?quran|"
    r"makkah|mecca|medina|madinah|hajj|shariah|salaat|salah[- ]?radio|"
    r"christian(?:ity)?|gospel|bible|biblical|church|catholic|evangelical|"
    r"orthodox[- ]?faith|jesus|christ[- ]?radio|religious|religion|"
    r"worship|scripture|prayer|hymns?|hinduism?|buddhis[mt]|"
    r"sikh[- ]?religion|torah|synagogue|diyanet|ilahiyat|kuran|kuran[iı]|"
    r"kur['’]?an|tasavvuf|vaaz)\b|"
    r"قرآن|قران|القرآن|القران|اسلام|إسلام|اسلامي|إسلامي|مسلم|مسجد|"
    r"أذان|اذان|تلاوة|تلاوه|الحديث|السنّة|السنة|القرءان|"
    r"القران الكريم|القرآن الكريم|دعوة إسلامية|دعوة اسلامية|اذاعة القرآن|إذاعة القرآن|"
    r"قورئان|قورئانی|ئایینی|مزگەوت|"
    r"مسیحی|مسيحي|الانجيل|إنجيل|انجیل|کلیسا|الكنيسة|"
    r"مذهبی|مذهبي|دینی|ديني|صلوات|ترتيل|تراتيل|"
    r"православ|христиан|ислам|коран|библи[яи]|церков|молитв|"
    r"религи|духовн(?:ое|ая|ый|ости)|"
    r"(\bilahi\b)|(\bdini(?:\s+radyo)?\b))",
    re.IGNORECASE,
)


def is_excluded_program(*fields):
    return any(isinstance(field, str) and _EXCLUDED.search(field)
               for field in fields)
