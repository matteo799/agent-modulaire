#!/usr/bin/env python3
"""
Extracteur d'informations clés de prospectus / KID / DICI / KIID
==================================================================
Version 3.0 — Multi-émetteur, FR/EN/DE, robuste

Fonctionne sans LLM, par recherche de patterns (regex + mots-clés + tables).
Testé sur des documents Amundi, BNP Paribas, BlackRock, Lyxor, Natixis,
AXA IM, Carmignac, Société Générale, etc.

Dépendances : pdfplumber (pip install pdfplumber)

Usage :
    python prospectus_extractor.py <fichier.pdf> [--json] [--output fichier.json]
    python prospectus_extractor.py <fichier.pdf> --csv           # une ligne CSV
    python prospectus_extractor.py dossier/ --json --output all.json  # batch
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import traceback
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("Erreur : pdfplumber requis. Installez-le avec : pip install pdfplumber")


# ─────────────────────────────────────────────
#  CONFIDENCE / EXTRACTION METHOD
# ─────────────────────────────────────────────


class ExtractionMethod(str, Enum):
    EXACT = "exact"  # Matched via explicit label pattern
    PROXIMITY = "proximity"  # Found via keyword proximity / window search
    TABLE = "table"  # Extracted from a parsed PDF table
    INFERRED = "inferred"  # Derived logically (e.g. "capital_garanti" from negative clause)
    MISSING = "missing"  # Not found


@dataclass
class ExtractedField:
    """Wraps a single extracted value with its confidence metadata."""

    value: str | None = None
    method: ExtractionMethod = ExtractionMethod.MISSING

    def __bool__(self):
        return self.value is not None and self.value != ""

    def __str__(self):
        return self.value or ""


# ─────────────────────────────────────────────
#  UNICODE / TEXT NORMALIZATION
# ─────────────────────────────────────────────

# Map of common Unicode variants to ASCII equivalents for matching
_UNICODE_MAP = {
    "\u2019": "'",  # right single quote → apostrophe
    "\u2018": "'",  # left single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2013": "-",  # en-dash
    "\u2014": "-",  # em-dash
    "\u00a0": " ",  # no-break space (also \xa0)
    "\u202f": " ",  # narrow no-break space
    "\u2009": " ",  # thin space
    "\u200b": "",  # zero-width space
    "\ufeff": "",  # BOM
}

# Diacritics map for French/German/Spanish — stripping accents makes regex
# patterns work regardless of whether the PDF uses accented or plain text
_ACCENT_MAP = str.maketrans(
    {
        "\u00e0": "a",
        "\u00e2": "a",
        "\u00e4": "a",
        "\u00e1": "a",
        "\u00e3": "a",
        "\u00e5": "a",
        "\u00e8": "e",
        "\u00e9": "e",
        "\u00ea": "e",
        "\u00eb": "e",
        "\u00ec": "i",
        "\u00ed": "i",
        "\u00ee": "i",
        "\u00ef": "i",
        "\u00f2": "o",
        "\u00f3": "o",
        "\u00f4": "o",
        "\u00f5": "o",
        "\u00f6": "o",
        "\u00f9": "u",
        "\u00fa": "u",
        "\u00fb": "u",
        "\u00fc": "u",
        "\u00fd": "y",
        "\u00ff": "y",
        "\u00e7": "c",
        "\u00f1": "n",
        "\u00c0": "A",
        "\u00c2": "A",
        "\u00c4": "A",
        "\u00c1": "A",
        "\u00c3": "A",
        "\u00c5": "A",
        "\u00c8": "E",
        "\u00c9": "E",
        "\u00ca": "E",
        "\u00cb": "E",
        "\u00cc": "I",
        "\u00cd": "I",
        "\u00ce": "I",
        "\u00cf": "I",
        "\u00d2": "O",
        "\u00d3": "O",
        "\u00d4": "O",
        "\u00d5": "O",
        "\u00d6": "O",
        "\u00d9": "U",
        "\u00da": "U",
        "\u00db": "U",
        "\u00dc": "U",
        "\u00dd": "Y",
        "\u0178": "Y",
        "\u00c7": "C",
        "\u00d1": "N",
    }
)
# Ligatures (1→2 char): handle via str.replace in normalize
_LIGATURE_MAP = {"\u0153": "oe", "\u00e6": "ae", "\u0152": "OE", "\u00c6": "AE"}


def normalize(text: str) -> str:
    """Normalize Unicode characters and strip diacritics for consistent regex matching.

    This ensures patterns like 'resultats' match 'résultats',
    'depositaire' matches 'dépositaire', etc.
    """
    if not text:
        return ""
    for src, dst in _UNICODE_MAP.items():
        text = text.replace(src, dst)
    for src, dst in _LIGATURE_MAP.items():
        text = text.replace(src, dst)
    text = text.translate(_ACCENT_MAP)
    return text


def clean(text: str) -> str:
    """Normalize spaces and special characters (strips accents)."""
    if not text:
        return ""
    text = normalize(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_spaces(text: str) -> str:
    """Normalize spaces only, preserving accented characters."""
    if not text:
        return ""
    # Only normalize special spaces, not accents
    for src, dst in _UNICODE_MAP.items():
        text = text.replace(src, dst)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─────────────────────────────────────────────
#  DATA MODEL
# ─────────────────────────────────────────────


@dataclass
class PerformanceScenario:
    scenario: str = ""
    valeur_1an: str = ""
    rendement_1an: str = ""
    valeur_detention: str = ""  # valeur à la période de détention recommandée
    rendement_detention: str = ""
    extraction_method: str = ExtractionMethod.MISSING.value  # tracks how this scenario was found


@dataclass
class ProspectusData:
    # ── Identification ──
    nom_produit: str | None = None
    type_produit: str | None = None
    classification: str | None = None
    societe_gestion: str | None = None
    depositaire: str | None = None
    teneur_comptes: str | None = None
    commissaire_comptes: str | None = None
    devise: str | None = None
    isin: str | None = None
    identifiant: str | None = None
    lei: str | None = None
    duree: str | None = None
    date_document: str | None = None
    valeur_initiale_part: str | None = None
    domicile: str | None = None
    forme_juridique: str | None = None

    # ── Objectif & Stratégie ──
    indice_reference: str | None = None
    objectif_gestion: str | None = None
    exposition_min: str | None = None
    exposition_max: str | None = None
    politique_distribution: str | None = None

    # ── Risque ──
    sri: str | None = None
    srri: str | None = None
    periode_detention: str | None = None
    capital_garanti: str | None = None

    # ── Coûts ──
    commission_souscription: str | None = None
    commission_rachat: str | None = None
    frais_gestion: str | None = None
    frais_courants: str | None = None
    frais_fonctionnement: str | None = None
    frais_indirects: str | None = None
    couts_transaction: str | None = None
    commission_surperformance: str | None = None
    couts_totaux_1an: str | None = None
    couts_totaux_detention: str | None = None
    incidence_annuelle_1an: str | None = None
    incidence_annuelle_detention: str | None = None

    # ── ESG ──
    classification_sfdr: str | None = None
    investissements_durables_min: str | None = None
    approche_esg: str | None = None
    taxonomie_min: str | None = None

    # ── Scénarios de performance ──
    scenarios: list[PerformanceScenario] = field(default_factory=list)

    # ── Métadonnées ──
    fichier_source: str | None = None
    champs_trouves: int = 0
    champs_total: int = 0
    taux_extraction: str = ""
    pages_analysees: int = 0
    # ── Confidence map: field_name → ExtractionMethod ──
    confidence: dict[str, str] = field(default_factory=dict)


# ─────────────────────────────────────────────
#  PATTERN HELPERS
# ─────────────────────────────────────────────

# Apostrophe-agnostic: matches ' or ' or Unicode variants
_APO = r"['\u2019\u2018]"
# Common "d'" or "de " prefix
_DE = rf"(?:d{_APO}|de\s+)"


def find_pattern(
    text: str, patterns: list, group: int = 1, flags=re.IGNORECASE, orig_text: str | None = None
) -> str | None:
    """Return the first captured group from the first matching pattern.

    If orig_text is provided, the match positions found in `text` (normalized)
    are used to extract the corresponding substring from `orig_text` (original).
    This preserves accented characters in the output.
    """
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            try:
                if orig_text and len(orig_text) == len(text):
                    return clean_spaces(orig_text[m.start(group) : m.end(group)])
                return clean(m.group(group))
            except IndexError:
                if orig_text and len(orig_text) == len(text):
                    return clean_spaces(orig_text[m.start(0) : m.end(0)])
                return clean(m.group(0))
    return None


def find_all_patterns(text: str, patterns: list, flags=re.IGNORECASE) -> list[str]:
    """Return all matches (group 1) across all patterns."""
    results = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags):
            try:
                results.append(clean(m.group(1)))
            except IndexError:
                results.append(clean(m.group(0)))
    return results


def find_near_keyword(
    text: str, keywords: list, radius: int = 400, orig_text: str | None = None
) -> str | None:
    """Extract text around the first matching keyword.

    Stops at the next section heading (a line of 4+ uppercase words) to
    prevent bleeding across sections.
    If orig_text provided and same length, extracts from orig_text.
    """
    text_lower = text.lower()
    # Pattern for a section heading: short all-caps line (e.g. "OBJECTIFS ET POLITIQUE")
    _SECTION_HEADING = re.compile(r"\n[A-Z\s\-]{4,60}\n")
    for kw in keywords:
        idx = text_lower.find(kw.lower())
        if idx != -1:
            src = orig_text if (orig_text and len(orig_text) == len(text)) else text
            context = src[idx : idx + radius]
            # Truncate at next section heading to avoid bleeding
            stop = _SECTION_HEADING.search(context, 1)  # skip pos 0 (might be heading itself)
            if stop:
                context = context[: stop.start()]
            return clean_spaces(context)
    return None


def find_cost(text: str, keywords: list, window_size: int = 300) -> str | None:
    """Find a cost (percentage or amount) near keywords.

    Searches for each keyword, then looks forward in a window for:
    1. "Neant" / "None" / "N/A" / "0,00"
    2. A percentage (e.g. 1,50 %)
    3. An amount (e.g. 2,11 EUR)
    """
    text_n = normalize(text)
    text_lower = text_n.lower()
    for kw in keywords:
        idx = text_lower.find(kw.lower())
        if idx == -1:
            continue
        window = text_n[idx : idx + window_size]
        # Check for zero / none
        if re.search(
            r"(?:Neant|none|n/a|nil|0[.,]00\s*(?:EUR|€|%|GBP|USD|\b))", window[:120], re.IGNORECASE
        ):
            return "Neant"
        # Percentage — tightened to 1-2 digits before decimal to avoid
        # matching years (2024) or large numbers near a stray % sign
        m = re.search(r"(\d{1,2}[.,]\d{1,4})\s*\%", window)
        if m:
            result = m.group(0).strip()
            tail = window[m.end() : m.end() + 40].lower()
            if "maximum" in tail or "max" in tail:
                result += " maximum"
            return result
        # Amount with currency
        m = re.search(r"(\d[\d\s]*[.,]?\d*)\s*(?:EUR|€|GBP|USD|CHF)", window)
        if m:
            return clean(m.group(0))
    return None


# ─────────────────────────────────────────────
#  MAIN EXTRACTOR
# ─────────────────────────────────────────────


class ProspectusExtractor:
    """Rule-based KID/DICI/KIID extractor — multi-manager, FR/EN/DE."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.full_text = ""  # raw text from PDF
        self.norm_text = ""  # normalized (accent-stripped) for pattern matching
        self.orig_text = ""  # space-normalized only (preserves accents) for display
        self.pages_text: list[str] = []
        self.tables: list[list[list[str]]] = []
        self.data = ProspectusData()
        self.data.fichier_source = os.path.basename(pdf_path)

    def _set(
        self, field_name: str, value: str | None, method: ExtractionMethod = ExtractionMethod.EXACT
    ):
        """Set a field on self.data and record its extraction method."""
        setattr(self.data, field_name, value)
        if value is not None:
            self.data.confidence[field_name] = method.value
        else:
            self.data.confidence[field_name] = ExtractionMethod.MISSING.value

    # ── PDF reading ──

    def read_pdf(self):
        """Read PDF: extract text + tables from all pages."""
        with pdfplumber.open(self.pdf_path) as pdf:
            self.data.pages_analysees = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                self.pages_text.append(page_text)
                for table in page.extract_tables():
                    if table:
                        cleaned = []
                        for row in table:
                            cleaned.append([clean(cell) if cell else "" for cell in row])
                        self.tables.append(cleaned)
            self.full_text = "\n".join(self.pages_text)
            self.orig_text = clean_spaces(self.full_text)  # accents preserved
            self.norm_text = normalize(self.full_text)  # accents stripped

    def extract_all(self) -> ProspectusData:
        """Run all extraction rules."""
        self.read_pdf()
        self._extract_identification()
        self._extract_objectif()
        self._extract_risque()
        self._extract_couts()
        self._extract_esg()
        self._extract_scenarios()
        self._post_process()
        self._compute_stats()
        return self.data

    # ────────────────────────────────────
    #  IDENTIFICATION
    # ────────────────────────────────────

    def _extract_identification(self):
        t = self.norm_text

        # ── Nom du produit ──
        self.data.nom_produit = find_pattern(
            t,
            [
                # FR: "Le Fonds a pour dénomination ..."
                r"(?:Fonds|OPCVM|OPC|FIA) a pour denomination\s+([^\n.]{3,80})",
                # FR: "Produit\n<NOM>"  (KID header)
                r"Produit\s*\n\s*([A-Z0-9][A-Z0-9\s%'&€\-/]{3,80}?)\s*\n",
                # EN: "Product name:" or "Fund name:"
                r"(?:Product|Fund)\s*(?:name)?\s*[:\s]+([^\n]{3,80})",
                # FR: "Dénomination" label
                r"Denomination\s*(?:du (?:produit|fonds?))?\s*[:\s]+([^\n]{3,80})",
                # DE: "Produktname" / "Fondsname"
                r"(?:Produkt|Fonds)name\s*[:\s]+([^\n]{3,80})",
                # Generic: first big uppercase line in first 2000 chars
                r"^([A-Z][A-Z0-9\s%'&€\-/]{5,60})\s*$",
            ],
            flags=re.IGNORECASE | re.MULTILINE,
        )

        # ── ISIN ──
        # Standard format: 2-letter country + 10 alphanumeric + 1 check digit
        # Validate with Luhn-derived ISIN checksum instead of a hardcoded country list
        def _isin_checksum_valid(isin: str) -> bool:
            """Validate ISIN check digit (ISO 6166)."""
            digits = ""
            for ch in isin[:-1]:
                digits += str(ord(ch) - 55) if ch.isalpha() else ch
            total = 0
            for i, d in enumerate(reversed(digits)):
                n = int(d)
                if i % 2 == 1:
                    n *= 2
                    if n > 9:
                        n -= 9
                total += n
            check = (10 - (total % 10)) % 10
            return check == int(isin[-1])

        for m in re.finditer(r"\b([A-Z]{2}[0-9A-Z]{9}\d)\b", t):
            candidate = m.group(1)
            if re.search(r"\d", candidate[2:]) and _isin_checksum_valid(candidate):
                self._set("isin", candidate, ExtractionMethod.EXACT)
                break
        # Fallback: no checksum validation (some KIDs print ISINs with a typo)
        if not self.data.isin:
            for m in re.finditer(r"\b([A-Z]{2}[0-9A-Z]{10})\b", t):
                candidate = m.group(1)
                if re.search(r"\d", candidate[2:]):
                    self._set("isin", candidate, ExtractionMethod.PROXIMITY)
                    break

        # ── Identifiant numérique (AMF/interne) ──
        val = find_pattern(
            t,
            [
                r"(\d{12,15})\s*[-]\s*[Dd]evise",
                r"(?:Code|Identifiant|Reference|Code AMF)\s*[:\s]+(\d{6,15})",
                r"(?:AMF|Visa)\s*(?:n[°o]?)?\s*[:\s]*([A-Z]*\d{6,15})",
            ],
        )
        self._set("identifiant", val, ExtractionMethod.EXACT)

        # ── LEI ──
        lei = find_pattern(
            t,
            [
                r"(?:LEI|Legal Entity Identifier|Identifiant d.entite juridique)\s*[:\s]*\n?\s*([A-Z0-9]{20})",
            ],
        )
        if lei:
            self._set("lei", lei, ExtractionMethod.EXACT)
        else:
            # LEI format: starts with digits, 20 chars total
            m = re.search(r"\b(\d{4,6}[A-Z0-9]{14,16})\b", t)
            if m and len(m.group(1)) == 20:
                self._set("lei", m.group(1), ExtractionMethod.PROXIMITY)

        # ── Devise ──
        val = find_pattern(
            t,
            [
                r"(?:Devise|Currency|Wahrung)\s*(?:de reference|of (?:the )?(?:fund|share))?\s*[:\s]*(EUR|USD|GBP|CHF|JPY|SEK|NOK|DKK|CAD|AUD)",
                r"Investissement\s+[\d\s]+\s*(EUR|USD|GBP|CHF)",
            ],
        )
        self._set("devise", val, ExtractionMethod.EXACT if val else ExtractionMethod.MISSING)

        # ── Société de gestion ──
        val = find_pattern(
            t,
            [
                r"(?:Societe de gestion|Management [Cc]ompany|Gestionnaire|Verwaltungsgesellschaft|Initiateur)\s*[:\s]+([^\n,]{5,100}?)(?:\s*\(|$|\n)",
                r"(?:Fabricant|Manufacturer|Producteur)\s*[:\s]+([^\n,]{5,100}?)(?:\s*\(|$|\n)",
            ],
            flags=re.IGNORECASE | re.MULTILINE,
        )
        self._set(
            "societe_gestion", val, ExtractionMethod.EXACT if val else ExtractionMethod.MISSING
        )

        # ── Dépositaire ──
        val = find_pattern(
            t,
            [
                r"(?:Depositaire)\s*(?:est)?\s*:\s*([A-Z][^\n,.]{2,80}?)(?:\.\s|\n|,|\s*\()",
                r"(?:Le Depositaire est)\s+([A-Z][^\n,.]{2,80}?)(?:\.\s|\n|,)",
                r"(?:Depositary|Custodian|Verwahrstelle)\s*[:\s]+([^\n,.]{3,80}?)(?:\s*\(|$|\n|,)",
            ],
        )
        self._set("depositaire", val, ExtractionMethod.EXACT if val else ExtractionMethod.MISSING)

        # ── Teneur de comptes ──
        self.data.teneur_comptes = find_pattern(
            t,
            [
                r"(?:Teneur de comptes?(?:-conservateur)?|Account Keeper|Transfer Agent|Agent de transfert|Centralisateur)\s*[:\s]+([^\n,.]{3,80}?)(?:\s*\(|$|\n|,)",
            ],
        )

        # ── Commissaire aux comptes ──
        cac = find_pattern(
            t,
            [
                r"(?:Commissaire aux comptes|Statutory Auditor|Wirtschaftsprufer)\s*(?:est|is)?\s*[:\s]+([A-Z][^\n,.]{2,80})",
                r"(?:Cabinet d.audit|Audit firm)\s*[:\s]+([A-Z][^\n,.]{2,80})",
            ],
        )
        if cac:
            cac = re.sub(r"^(?:Le Commissaire aux comptes est\s+)", "", cac).strip()
            self.data.commissaire_comptes = cac

        # ── Type / forme juridique ──
        self.data.forme_juridique = find_pattern(
            t,
            [
                r"\b(FCPE|FCP|SICAV|SICAV-SIF|ETF|OPCVM|UCITS|FIA|AIF|FIC|ELTIF|RAIF|SCS|SCA|SA)\b",
            ],
        )
        self.data.type_produit = find_pattern(
            t,
            [
                r"(?:Type)\s*[:\s]+(?:(?:Parts?|Shares?)\s+(?:de|du|of)\s+)?(.{10,150}?)(?:\.\s|\n)",
                r"((?:FCPE|FCP|SICAV|ETF|OPCVM|FIA|UCITS)\s[^\n.]{10,100})",
            ],
            flags=re.IGNORECASE | re.MULTILINE,
        )

        # ── Classification AMF ──
        self.data.classification = find_pattern(
            t,
            [
                r"Classification\s*(?:AMF)?\s*[^:]*:\s*(?:[«\"]\s*)?((?:FCPE|Actions?|Obligations?|Monetaire|Diversifie|Mixed)[^\n\"»]{3,80})",
                r"Classification\s*(?:AMF)?\s*[^:]*:\s*([^\n]{5,80})",
                r"(?:Morningstar|Lipper)\s*[Cc]ategory\s*[:\s]+([^\n]{5,80})",
            ],
        )

        # ── Durée ──
        self.data.duree = find_pattern(
            t,
            [
                r"cree pour une duree de\s+(\d+\s*ans?)",
                r"(?:Duree|Duration|Laufzeit)\s*(?:du (?:fonds?|FCPE|FCP|produit))?\s*[:\s]+([^\n.]{5,60}?)(?:\.\s|\n)",
                r"duree\s+(indeterminee|illimitee)",
            ],
        )

        # ── Valeur initiale ──
        self.data.valeur_initiale_part = find_pattern(
            t,
            [
                r"valeur initiale de la part.*?(?:est de|:)\s*(\d+[.,]?\d*\s*(?:euros?|€|EUR|USD|GBP|CHF))",
                r"(?:valeur (?:initiale|d.origine)|initial NAV|prix d.emission initial)\s*(?:de la part)?\s*(?:est de|was|:)\s*(\d+[.,]?\d*\s*(?:euros?|€|EUR|USD|GBP|CHF))",
                r"(?:valeur nominale|nominal value|VL initiale)\s*(?:de|of)?\s*[:\s]*(\d+[.,]?\d*\s*(?:euros?|€|EUR|USD|GBP|CHF))",
            ],
        )

        # ── Date du document ──
        self.data.date_document = find_pattern(
            t,
            [
                r"document d.informations cles\s*[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
                r"(?:Date (?:de production|du document|of (?:the )?(?:document|KID)))\s*[^:]*[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
                r"(?:This document was (?:produced|published) on)\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
                r"(?:Datum des Dokuments)\s*[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
                r"(?:Date)\s*[:\s]+(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+\d{4})",
            ],
        )

        # ── Domicile ──
        self.data.domicile = find_pattern(
            t,
            [
                r"(?:Domicile|Domiciliation|Country of (?:domicile|registration))\s*[:\s]+([A-Z][a-zA-Z\s]{2,30}?)(?:\n|,|\.|$)",
                r"(?:agree en|authorised in|registered in)\s+(France|Luxembourg|Irlande|Ireland|Allemagne|Germany|Belgique|Belgium|Pays-Bas|Netherlands)",
            ],
        )

    # ────────────────────────────────────
    #  OBJECTIF & STRATÉGIE
    # ────────────────────────────────────

    def _extract_objectif(self):
        t = self.norm_text

        # ── Indice de référence ──
        self.data.indice_reference = find_pattern(
            t,
            [
                # FR
                r"(?:indice de reference|indicateur de reference)\s*[,:\s]+(?:le\s+|l')?([A-Z][A-Za-z0-9\s&/\-]{3,60}?)(?:\s*\(|,|\.|dividendes|net return|total return|NR|TR|avec)",
                # EN
                r"(?:benchmark|reference index)\s*(?:is|:)?\s*(?:the\s+)?([A-Z][A-Za-z0-9\s&/\-]{3,60}?)(?:\s*\(|,|\.|Index|\n)",
                # Known index families
                r"\b((?:MSCI|EURO STOXX|STOXX|CAC\s*\d+|FTSE|S&P|Bloomberg|BofA|Barclays|JP Morgan|ICE BofA|EONIA|€STR|SOFR|SONIA)[A-Za-z0-9\s&/\-]*?)(?:\s*\(|,|\.\s|dividendes|net return|NR|TR|\n)",
            ],
        )

        # ── Objectif de gestion ──
        obj_text = find_near_keyword(
            t,
            [
                "objectif de gestion",
                "objectifs et politique d'investissement",
                "investment objective",
                "objectives and investment policy",
                "anlageziel",
                "ziel und anlagepolitik",
            ],
            radius=500,
        )
        if obj_text:
            self.data.objectif_gestion = obj_text[:300].rsplit(" ", 1)[0] + "..."

        # ── Exposition min/max ──
        expo_patterns = [
            r"(?:expose|investi)\s*(?:de\s+|entre\s+)?(\d+)\s*(?:a|to|-)\s*(\d+)\s*%",
            r"(\d+)\s*%\s*(?:a|to|-)\s*(\d+)\s*%\s*(?:en|in|aux?|of)?\s*(?:actions?|equit)",
            r"(?:minimum|min\.?)\s*(?:de\s+|of\s+)?(\d+)\s*%.*?(?:maximum|max\.?)\s*(?:de\s+|of\s+)?(\d+)\s*%",
        ]
        for pat in expo_patterns:
            m = re.search(pat, t, re.IGNORECASE)
            if m:
                self.data.exposition_min = m.group(1) + " %"
                self.data.exposition_max = m.group(2) + " %"
                break

        # ── Politique de distribution ──
        # Look in specific section first
        dist_window = (
            find_near_keyword(
                t,
                [
                    "affectation des sommes",
                    "distribution policy",
                    "politique de distribution",
                    "income treatment",
                    "affectation du resultat",
                ],
                radius=250,
            )
            or ""
        )

        # Capitalize if explicit
        cap_signals = r"(?:non[- ]distribution|reinvestis|capitalisation des revenus|accumulation|thesaurierung)"
        dist_signals = r"(?:parts?\s+de\s+distribution|distributing|distribuera|ausschuttung)"

        if dist_window:
            dw_lower = dist_window.lower()
            has_cap = bool(re.search(cap_signals, dw_lower))
            has_dist = bool(re.search(dist_signals, dw_lower))
            if has_cap and has_dist:
                self.data.politique_distribution = "Capitalisation / Distribution"
            elif has_cap:
                self.data.politique_distribution = "Capitalisation"
            elif has_dist:
                self.data.politique_distribution = "Distribution"

        # Fallback: look for explicit statement in full text
        if not self.data.politique_distribution and (
            re.search(
                r"(?:non[- ]distribution|revenus.*reinvestis|resultats?.*capitalises)",
                t,
                re.IGNORECASE,
            )
            or re.search(r"\bparts?\s*(?:de\s+)?capitalisation\b", t, re.IGNORECASE)
        ):
            self.data.politique_distribution = "Capitalisation"

    # ────────────────────────────────────
    #  RISQUE
    # ────────────────────────────────────

    def _extract_risque(self):
        t = self.norm_text

        # ── SRI (1-7, PRIIPS) ──
        sri = find_pattern(
            t,
            [
                r"(?:classe de risque|risk class|indicateur.*risque|summary risk indicator|Gesamtrisikoindikator)\s*(?:est de\s+|is\s+|:?\s*)(\d)\s*(?:sur|/|out of|von)\s*(\d)",
                r"(?:classe|rated).*?(?:classe|class)\s*(?:de risque\s*)?(\d)\s*(?:sur|/|out of)\s*(\d)",
            ],
            group=0,
        )
        if sri:
            nums = re.findall(r"\d", sri)
            if len(nums) >= 2:
                self._set("sri", f"{nums[0]} / {nums[1]}", ExtractionMethod.EXACT)

        # ── SRRI (1-7, UCITS KIID — older format) ──
        srri = find_pattern(
            t,
            [
                r"(?:SRRI|profil de risque et de rendement)\s*[:\s]*(\d)\s*/?\s*(\d)?",
            ],
            group=0,
        )
        if srri and not self.data.sri:
            nums = re.findall(r"\d", srri)
            if nums:
                self._set("srri", f"{nums[0]} / 7", ExtractionMethod.EXACT)

        # ── Période de détention ──
        val = find_pattern(
            t,
            [
                r"(?:Periode de detention recommandee|Recommended holding period|Empfohlene Haltedauer)\s*[:\s]*((?:More than|Au moins|Mindestens|Plus de)?\s*\d+\s*(?:ans?|years?|Jahr[e]?|mois|months?))",
                r"(?:conserver|detenir|hold)\s*(?:votre investissement|your investment)?\s*(?:pendant)?\s*(?:au moins|for at least|mindestens)?\s*(\d+\s*(?:ans?|years?|mois|months?))",
                r"(?:Periode de detention recommandee|Recommended holding period)\s*[:\s]*([^\n.]{3,40})",
            ],
        )
        self._set(
            "periode_detention", val, ExtractionMethod.EXACT if val else ExtractionMethod.MISSING
        )

        # ── Capital garanti ──
        # Classified as INFERRED because it's derived from surrounding prose, not an explicit label
        if re.search(
            r"(aucun rendement minimal garanti|pas de protection|"
            r"capital n.est pas garanti|perdre tout|lose (?:all|your entire)|"
            r"no (?:capital )?(?:protection|guarantee)|kein Kapitalschutz|"
            r"vous pourriez perdre|you could lose)",
            t,
            re.IGNORECASE,
        ):
            self._set("capital_garanti", "Non", ExtractionMethod.INFERRED)
        elif re.search(
            r"(capital garanti|capital protection|garantie du capital|Kapitalgarantie)",
            t,
            re.IGNORECASE,
        ):
            self._set("capital_garanti", "Oui", ExtractionMethod.INFERRED)

    # ────────────────────────────────────
    #  COÛTS
    # ────────────────────────────────────

    def _extract_couts(self):
        t = self.norm_text

        # ── Souscription / Entrée ──
        val = find_cost(
            t,
            [
                "commission de souscription",
                "couts d'entree",
                "co\xfbts d'entr\xe9e",
                "entry cost",
                "entry charge",
                "frais d'entree",
                "subscription fee",
                "ausgabeaufschlag",
                "front-end load",
                "frais d'entree",
                "initial charge",
            ],
        )
        self._set(
            "commission_souscription",
            val,
            ExtractionMethod.EXACT if val else ExtractionMethod.MISSING,
        )

        # ── Rachat / Sortie ──
        val = find_cost(
            t,
            [
                "commission de rachat",
                "couts de sortie",
                "exit cost",
                "exit charge",
                "frais de sortie",
                "redemption fee",
                "rucknahmeabschlag",
                "back-end load",
            ],
        )
        self._set(
            "commission_rachat", val, ExtractionMethod.EXACT if val else ExtractionMethod.MISSING
        )

        # ── Frais de gestion financière ──
        val = find_cost(
            t,
            [
                "frais de gestion financiere",
                "p1 frais de gestion",
                "annual management charge",
            ],
        )
        method = ExtractionMethod.EXACT
        if not val:
            val = find_cost(
                t,
                [
                    "management fee",
                    "frais de gestion max",
                    "verwaltungsgebuhr",
                    "management charge",
                ],
            )
            method = ExtractionMethod.PROXIMITY if val else ExtractionMethod.MISSING
        self._set("frais_gestion", val, method)

        # ── Frais courants (KIID) ──
        val = find_cost(
            t,
            [
                "frais courants",
                "ongoing charges",
                "ongoing costs",
                "laufende kosten",
                "frais recurrents",
                "gestion et autres couts administratifs",
                "gestion et autres co",
            ],
        )
        self._set(
            "frais_courants", val, ExtractionMethod.EXACT if val else ExtractionMethod.MISSING
        )

        # ── Frais de fonctionnement ──
        val = find_cost(
            t,
            [
                "frais de fonctionnement",
                "operating cost",
                "operating expense",
                "frais administratif",
                "betriebskosten",
            ],
        )
        self._set(
            "frais_fonctionnement", val, ExtractionMethod.EXACT if val else ExtractionMethod.MISSING
        )

        # ── Frais indirects ──
        val = find_cost(
            t,
            [
                "frais indirects",
                "indirect cost",
                "underlying fund cost",
                "acquired fund fees",
                "kosten der zugrunde",
            ],
        )
        self._set(
            "frais_indirects", val, ExtractionMethod.EXACT if val else ExtractionMethod.MISSING
        )

        # ── Transaction ──
        val = find_cost(
            t,
            [
                "couts de transaction",
                "transaction cost",
                "frais de transaction",
                "portfolio transaction",
                "transaktionskosten",
            ],
        )
        method = ExtractionMethod.EXACT
        if not val:
            # Fallback: look for the € amount near "transaction"
            m = re.search(r"[Tt]ransaction.*?(\d+[.,]\d+)\s*(EUR|€)", t)
            if m:
                val = m.group(1) + " " + m.group(2)
                method = ExtractionMethod.PROXIMITY
            else:
                method = ExtractionMethod.MISSING
        self._set("couts_transaction", val, method)

        # ── Surperformance ──
        perf = find_cost(
            t,
            [
                "commission liee aux resultats",
                "commission de surperformance",
                "commissions liees aux resultats",
                "performance fee",
                "success fee",
                "erfolgsbezogene vergutung",
                "commissions de surperformance",
            ],
        )
        if perf:
            self._set("commission_surperformance", perf, ExtractionMethod.EXACT)
        elif re.search(
            r"(?:pas de commission|il n.y a pas|no performance|keine|neant|nil|0[.,]00\s*EUR)"
            r".*?"
            r"(?:surperformance|resultats|performance fee|success)",
            t,
            re.IGNORECASE,
        ) or re.search(
            r"(?:surperformance|resultats|performance fee|success)"
            r".*?"
            r"(?:neant|nil|0[.,]00\s*EUR|pas de|no )",
            t,
            re.IGNORECASE,
        ):
            self._set("commission_surperformance", "Neant", ExtractionMethod.INFERRED)

        # ── Coûts totaux & Incidence ──
        self._extract_total_costs()

    def _extract_total_costs(self):
        """Extract total costs and annual cost impact from text and tables."""
        t = self.norm_text

        # ── Text-based: "Coûts totaux €554 €1 800" ──
        m = re.search(
            r"(?:co.ts totaux|total costs|gesamtkosten)\s*€?\s*([\d\s]+(?:[.,]\d+)?)\s*€?\s*([\d\s]+(?:[.,]\d+)?)",
            t,
            re.IGNORECASE,
        )
        if m:
            v1, v2 = clean(m.group(1)), clean(m.group(2))
            if v1:
                self._set("couts_totaux_1an", "€" + v1, ExtractionMethod.EXACT)
            if v2:
                self._set("couts_totaux_detention", "€" + v2, ExtractionMethod.EXACT)

        # ── Text-based: "Incidence des coûts annuels** 5,6% 3,0%" ──
        m2 = re.search(
            r"(?:incidence|impact|reduction in yield|RIY)\s*(?:des co.ts)?\s*(?:annuels?)?\s*\**\s*(\d+[.,]\d+\s*%)\s*(\d+[.,]\d+\s*%)",
            t,
            re.IGNORECASE,
        )
        if m2:
            self._set("incidence_annuelle_1an", m2.group(1), ExtractionMethod.EXACT)
            self._set("incidence_annuelle_detention", m2.group(2), ExtractionMethod.EXACT)

        # ── Table-based fallback ──
        for table in self.tables:
            for row in table:
                rt = " ".join(c or "" for c in row)
                rt_lower = rt.lower()

                if not self.data.couts_totaux_1an and ("total" in rt_lower and "co" in rt_lower):
                    amounts = re.findall(r"€\s*([\d\s]+(?:[.,]\d+)?)", rt)
                    amounts = [clean(a) for a in amounts if a.strip()]
                    if len(amounts) >= 1:
                        self._set("couts_totaux_1an", "€" + amounts[0], ExtractionMethod.TABLE)
                    if len(amounts) >= 2:
                        self._set(
                            "couts_totaux_detention", "€" + amounts[1], ExtractionMethod.TABLE
                        )

                if not self.data.incidence_annuelle_1an and (
                    "incidence" in rt_lower or "impact" in rt_lower or "riy" in rt_lower
                ):
                    pcts = re.findall(r"\d+[.,]\d+\s*%", rt)
                    if len(pcts) >= 1:
                        self._set("incidence_annuelle_1an", pcts[0], ExtractionMethod.TABLE)
                    if len(pcts) >= 2:
                        self._set("incidence_annuelle_detention", pcts[1], ExtractionMethod.TABLE)

    # ────────────────────────────────────
    #  ESG / SFDR
    # ────────────────────────────────────

    def _extract_esg(self):
        t = self.norm_text

        # ── SFDR classification ──
        sfdr = find_pattern(
            t,
            [
                r"(?:classe|classified|falls under|releve de l')\s*(?:article|art\.?)\s*(\d+)",
                r"(?:article|art\.?)\s*(\d+)\s*(?:au sens|du|of|pursuant)?\s*(?:du\s+)?(?:R[ee]glement|Regulation)\s*(?:\(UE\))?\s*2019/2088",
                r"(?:article|art\.?)\s*(\d+)\s*.*?(?:SFDR|Disclosure|durabilite|sustainability)",
                r"SFDR\s*(?:article|art\.?)\s*(\d+)",
            ],
        )
        if sfdr:
            nums = re.findall(r"\d+", sfdr)
            if nums and nums[0] in ("6", "8", "9"):
                self.data.classification_sfdr = f"Article {nums[0]}"

        # ── Investissements durables min ──
        sd = find_pattern(
            t,
            [
                r"(?:proportion minimale|minimum (?:proportion|share))\s*(?:de\s+|of\s+)?(\d+[.,]?\d*)\s*%\s*(?:d.)?(?:investissements? durables?|sustainable investments?)",
                r"(\d+[.,]?\d*)\s*%\s*(?:d.)?(?:investissements?\s*(?:actifs?\s*)?durables?|sustainable investments?)",
                r"(?:detenir|hold|maintain)\s*(?:un minimum|a minimum|au moins|at least)\s*(?:de\s+|of\s+)?(\d+[.,]?\d*)\s*%",
            ],
        )
        if sd:
            self.data.investissements_durables_min = sd + " %"

        # ── Taxonomie min ──
        taxo = find_pattern(
            t,
            [
                r"(?:alignes?\s+(?:sur\s+)?la\s+)?[Tt]axo(?:no)?mie\s*[:\s]*(\d+[.,]?\d*)\s*%",
                r"(\d+[.,]?\d*)\s*%\s*(?:taxonomy[- ]aligned|alignes?\s+taxo)",
                r"[Tt]axonomy\s*(?:alignment)?\s*[:\s]*(\d+[.,]?\d*)\s*%",
            ],
        )
        if taxo:
            self.data.taxonomie_min = taxo + " %"

        # ── Approche ESG ──
        esg_approaches = [
            (r"best.?in.?class", "Best-in-class"),
            (r"best.?in.?universe", "Best-in-universe"),
            (r"best.?effort", "Best-effort"),
            (r"impact invest", "Impact investing"),
            (r"(?:ISR|SRI)\b.*(?:label|certified)", "Label ISR"),
            (
                r"(?:transition energetique|greenfin|towards sustainability)",
                "Greenfin / Transition",
            ),
            (r"exclusion\s*(?:normative)?.*(?:ESG|integration)", "Exclusion + integration ESG"),
            (r"integration\s*ESG", "Integration ESG"),
        ]
        for pattern, label in esg_approaches:
            if re.search(pattern, t, re.IGNORECASE):
                self.data.approche_esg = label
                break

    # ────────────────────────────────────
    #  SCÉNARIOS DE PERFORMANCE
    # ────────────────────────────────────

    def _extract_scenarios(self):
        """Extract performance scenarios (PRIIPS KID format)."""
        t = self.norm_text
        found: dict[str, PerformanceScenario] = {}

        # Scenario name mapping (FR / EN / DE → canonical French label)
        scenario_map = {
            "tensions": "Scenario de tensions",
            "stress": "Scenario de tensions",
            "stressszenario": "Scenario de tensions",
            "defavorable": "Scenario defavorable",
            "unfavourable": "Scenario defavorable",
            "pessimistisch": "Scenario defavorable",
            "intermediaire": "Scenario intermediaire",
            "moderate": "Scenario intermediaire",
            "mittleres": "Scenario intermediaire",
            "favorable": "Scenario favorable",
            "favourable": "Scenario favorable",
            "optimistisch": "Scenario favorable",
        }

        # ── Strategy 1: Structured text parsing ──
        # Pattern: "...obtenir... €XXXX €YYYY\nScénario <name>\nRendement... X% Y%"
        for canon_key, label in [
            ("tensions", "Scénario de tensions"),
            ("defavorable", "Scénario défavorable"),
            ("intermediaire", "Scénario intermédiaire"),
            ("(?<!de)favorable", "Scénario favorable"),
        ]:
            # Forward pattern: amount line → scenario name → rendement line
            pat = (
                r"(?:obtenir|get back).*?€\s*([\d\s]+(?:[.,]\d+)?)\s*€\s*([\d\s]+(?:[.,]\d+)?)"
                r"\s*\n?\s*(?:Scenario\s*(?:de\s*)?"
                + canon_key
                + r"|"
                + canon_key
                + r"\s*scenario)"
                r"\s*\n?\s*(?:Rendement|Average return|Return).*?(-?\d+[.,]\d+)\s*%\s*(-?\d+[.,]\d+)\s*%"
            )
            m = re.search(pat, t, re.IGNORECASE)
            if m:
                found[label] = PerformanceScenario(
                    scenario=label,
                    valeur_1an="€" + clean(m.group(1)),
                    valeur_detention="€" + clean(m.group(2)),
                    rendement_1an=m.group(3) + "%",
                    rendement_detention=m.group(4) + "%",
                    extraction_method=ExtractionMethod.EXACT.value,
                )

        # ── Strategy 2: Proximity-based fallback ──
        if len(found) < 2:
            for key_lower, label in scenario_map.items():
                if label in found:
                    continue
                # Find keyword in text — use regex to avoid partial matches
                # e.g. "favorable" should not match inside "defavorable"
                pattern = r"(?<!\w)" + re.escape(key_lower) + r"(?!\w)"
                positions = [m.start() for m in re.finditer(pattern, t.lower())]
                for pos in positions:
                    window = t[max(0, pos - 250) : pos + 250]
                    amounts = re.findall(r"€\s*([\d\s]+)", window)
                    amounts = [clean(a) for a in amounts if re.search(r"\d{3}", a)]
                    pcts = re.findall(r"(-?\d+[.,]\d+)\s*%", window)

                    if amounts or pcts:
                        sc = PerformanceScenario(
                            scenario=label,
                            extraction_method=ExtractionMethod.PROXIMITY.value,
                        )
                        if len(amounts) >= 1:
                            sc.valeur_1an = "€" + amounts[0]
                        if len(amounts) >= 2:
                            sc.valeur_detention = "€" + amounts[1]
                        if len(pcts) >= 1:
                            sc.rendement_1an = pcts[0] + "%"
                        if len(pcts) >= 2:
                            sc.rendement_detention = pcts[1] + "%"
                        found[label] = sc
                        break

        # ── Strategy 3: Table-based ──
        if len(found) < 2:
            for table in self.tables:
                for row in table:
                    row_text = " ".join(c or "" for c in row)
                    row_lower = row_text.lower()
                    for key_lower, label in scenario_map.items():
                        if key_lower in row_lower and label not in found:
                            amounts = re.findall(r"€\s*([\d\s]+)", row_text)
                            amounts = [clean(a) for a in amounts if re.search(r"\d{3}", a)]
                            pcts = re.findall(r"(-?\d+[.,]\d+)\s*%", row_text)
                            sc = PerformanceScenario(
                                scenario=label,
                                extraction_method=ExtractionMethod.TABLE.value,
                            )
                            if "rendement" in row_lower or "return" in row_lower:
                                if pcts:
                                    sc.rendement_1an = pcts[0] + "%"
                                if len(pcts) >= 2:
                                    sc.rendement_detention = pcts[1] + "%"
                            else:
                                if amounts:
                                    sc.valeur_1an = "€" + amounts[0]
                                if len(amounts) >= 2:
                                    sc.valeur_detention = "€" + amounts[1]
                            if sc.valeur_1an or sc.rendement_1an:
                                found[label] = sc

        # Order output
        order = [
            "Scénario de tensions",
            "Scénario défavorable",
            "Scénario intermédiaire",
            "Scénario favorable",
        ]
        self.data.scenarios = [found[k] for k in order if k in found]

    # ────────────────────────────────────
    #  POST-PROCESSING
    # ────────────────────────────────────

    def _post_process(self):
        """Clean up extracted values and restore accents for display fields."""
        d = self.data
        ot = self.orig_text  # accent-preserved text

        # ── Restore accents for text-heavy display fields ──
        # Re-search in orig_text for fields where accent loss is visible
        if d.objectif_gestion:
            # Re-extract from accent-preserved text
            for kw in [
                "objectif de gestion",
                "objectifs et politique d'investissement",
                "investment objective",
            ]:
                idx = ot.lower().find(kw)
                if idx != -1:
                    obj_orig = clean_spaces(ot[idx : idx + 500])
                    d.objectif_gestion = obj_orig[:300].rsplit(" ", 1)[0] + "..."
                    break

        if d.commissaire_comptes:
            m = re.search(
                r"(?:Commissaire aux comptes|Statutory Auditor)\s*(?:est|is)?\s*[:\s]+([A-Z][^\n,.]{2,80})",
                ot,
                re.IGNORECASE,
            )
            if m:
                val = clean_spaces(m.group(1))
                val = re.sub(r"^(?:Le Commissaire aux comptes est\s+)", "", val).strip()
                d.commissaire_comptes = val

        if d.classification:
            m = re.search(
                r"Classification\s*(?:AMF)?\s*[^:]*:\s*(?:[«\"]\s*)?(.{5,80}?)(?:\n|\")",
                ot,
                re.IGNORECASE,
            )
            if m:
                d.classification = clean_spaces(m.group(1))

        # ── Fix Néant display (restore accent) ──
        for attr in [
            "commission_rachat",
            "frais_indirects",
            "commission_surperformance",
            "commission_souscription",
            "couts_transaction",
        ]:
            val = getattr(d, attr, None)
            if val and val.lower() == "neant":
                setattr(d, attr, "Néant")

        # Trim société de gestion — remove trailing qualifiers
        if d.societe_gestion:
            d.societe_gestion = re.sub(r"\s*\(ci-apr[ee]s.*$", "", d.societe_gestion).strip()

        # Normalize durée
        if d.duree:
            m = re.search(r"(\d+)\s*ans?", d.duree, re.IGNORECASE)
            if m:
                d.duree = m.group(1) + " ans"
            elif re.search(r"indeterminee|illimitee", d.duree, re.IGNORECASE):
                d.duree = "Indéterminée"

        # If no SRI but SRRI found, use it
        if not d.sri and d.srri:
            d.sri = d.srri

    # ────────────────────────────────────
    #  STATS
    # ────────────────────────────────────

    def _compute_stats(self):
        """Compute extraction fill rate across all extractable fields.

        Counts every substantive field on ProspectusData — both primary and
        secondary — so the reported rate reflects actual coverage, not a
        hand-picked subset.
        """
        d = self.data
        # All fields that represent extracted content (exclude metadata fields)
        _META = {
            "fichier_source",
            "champs_trouves",
            "champs_total",
            "taux_extraction",
            "pages_analysees",
            "confidence",
            "scenarios",
        }
        fields = []
        for f_name, f_val in d.__dict__.items():
            if f_name in _META:
                continue
            fields.append(f_val)

        # Scenarios count as one composite field (found / not found)
        fields.append(bool(d.scenarios) or None)

        d.champs_total = len(fields)
        d.champs_trouves = sum(1 for f in fields if f is not None and f != "")
        pct = (d.champs_trouves / d.champs_total * 100) if d.champs_total else 0
        d.taux_extraction = f"{pct:.0f}%"


# ─────────────────────────────────────────────
#  OUTPUT FORMATTING
# ─────────────────────────────────────────────


def format_table(data: ProspectusData) -> str:
    """Format results as a readable terminal table."""
    sep = "─" * 76
    lines = []

    def section(title):
        lines.append(f"\n{'═' * 76}")
        lines.append(f"  {title}")
        lines.append(f"{'═' * 76}")

    def row(label, value, field_name: str | None = None):
        v = value or "—"
        # Append confidence tag when a field_name is provided
        if field_name and data.confidence.get(field_name):
            method = data.confidence[field_name]
            if method != ExtractionMethod.EXACT.value and method != ExtractionMethod.MISSING.value:
                v = f"{v}  [{method}]"
        lines.append(f"  {label:<42} {v}")

    lines.append(sep)
    lines.append("  EXTRACTEUR DE PROSPECTUS v3.0 — Résultats")
    lines.append(f"  Fichier : {data.fichier_source} ({data.pages_analysees} pages)")
    lines.append(
        f"  Taux d'extraction : {data.taux_extraction} ({data.champs_trouves}/{data.champs_total} champs)"
    )

    # Confidence breakdown
    if data.confidence:
        counts: dict[str, int] = {}
        for m in data.confidence.values():
            counts[m] = counts.get(m, 0) + 1
        conf_parts = []
        for method in (
            ExtractionMethod.EXACT,
            ExtractionMethod.INFERRED,
            ExtractionMethod.PROXIMITY,
            ExtractionMethod.TABLE,
            ExtractionMethod.MISSING,
        ):
            n = counts.get(method.value, 0)
            if n:
                conf_parts.append(f"{method.value}: {n}")
        lines.append(f"  Confiance : {' | '.join(conf_parts)}")
    lines.append(sep)

    section("IDENTIFICATION")
    row("Nom du produit", data.nom_produit, "nom_produit")
    row("Type / Forme juridique", data.type_produit or data.forme_juridique)
    row("Classification", data.classification, "classification")
    row("Société de gestion", data.societe_gestion, "societe_gestion")
    row("Dépositaire", data.depositaire, "depositaire")
    row("Teneur de comptes", data.teneur_comptes)
    row("Commissaire aux comptes", data.commissaire_comptes)
    row("Devise", data.devise, "devise")
    row("ISIN", data.isin, "isin")
    row("Identifiant", data.identifiant, "identifiant")
    row("LEI", data.lei, "lei")
    row("Domicile", data.domicile)
    row("Durée", data.duree)
    row("Valeur initiale de la part", data.valeur_initiale_part)
    row("Date du document", data.date_document)

    section("OBJECTIF & STRATÉGIE")
    row("Indice de référence", data.indice_reference)
    row("Exposition min", data.exposition_min)
    row("Exposition max", data.exposition_max)
    row("Politique de distribution", data.politique_distribution)
    if data.objectif_gestion:
        lines.append("\n  Objectif de gestion :")
        words = data.objectif_gestion.split()
        line = "    "
        for w in words:
            if len(line) + len(w) > 72:
                lines.append(line)
                line = "    "
            line += w + " "
        if line.strip():
            lines.append(line)

    section("RISQUE")
    row("Indicateur de risque (SRI/SRRI)", data.sri or data.srri, "sri")
    row("Période de détention recommandée", data.periode_detention, "periode_detention")
    row("Capital garanti", data.capital_garanti, "capital_garanti")

    section("COÛTS")
    row(
        "Commission de souscription (entrée)",
        data.commission_souscription,
        "commission_souscription",
    )
    row("Commission de rachat (sortie)", data.commission_rachat, "commission_rachat")
    row("Frais de gestion financière", data.frais_gestion, "frais_gestion")
    row("Frais courants", data.frais_courants, "frais_courants")
    row("Frais de fonctionnement", data.frais_fonctionnement, "frais_fonctionnement")
    row("Frais indirects", data.frais_indirects, "frais_indirects")
    row("Coûts de transaction", data.couts_transaction, "couts_transaction")
    row("Commission de surperformance", data.commission_surperformance, "commission_surperformance")
    row("Coûts totaux à 1 an", data.couts_totaux_1an, "couts_totaux_1an")
    row("Coûts totaux (détention)", data.couts_totaux_detention, "couts_totaux_detention")
    row("Incidence annuelle (1 an)", data.incidence_annuelle_1an, "incidence_annuelle_1an")
    row(
        "Incidence annuelle (détention)",
        data.incidence_annuelle_detention,
        "incidence_annuelle_detention",
    )

    section("ESG & DURABILITÉ")
    row("Classification SFDR", data.classification_sfdr, "classification_sfdr")
    row(
        "Investissements durables min.",
        data.investissements_durables_min,
        "investissements_durables_min",
    )
    row("Alignement Taxonomie min.", data.taxonomie_min, "taxonomie_min")
    row("Approche ESG", data.approche_esg, "approche_esg")

    if data.scenarios:
        section("SCÉNARIOS DE PERFORMANCE")
        for sc in data.scenarios:
            method_tag = (
                f"  [{sc.extraction_method}]"
                if sc.extraction_method != ExtractionMethod.EXACT.value
                else ""
            )
            lines.append(f"\n  {sc.scenario}{method_tag}")
            row("  Valeur à 1 an", sc.valeur_1an)
            row("  Rendement à 1 an", sc.rendement_1an)
            row("  Valeur (détention recommandée)", sc.valeur_detention)
            row("  Rendement (détention recommandée)", sc.rendement_detention)

    lines.append(f"\n{sep}")
    return "\n".join(lines)


def to_json(data: ProspectusData) -> str:
    """Convert to clean JSON."""
    return json.dumps(asdict(data), ensure_ascii=False, indent=2)


def to_csv_row(data: ProspectusData) -> str:
    """Convert to a single CSV row (header + data)."""
    d = asdict(data)
    # Flatten scenarios
    for i, sc in enumerate(data.scenarios):
        d[f"scenario_{i + 1}_nom"] = sc.scenario
        d[f"scenario_{i + 1}_valeur_1an"] = sc.valeur_1an
        d[f"scenario_{i + 1}_rendement_1an"] = sc.rendement_1an
        d[f"scenario_{i + 1}_valeur_detention"] = sc.valeur_detention
        d[f"scenario_{i + 1}_rendement_detention"] = sc.rendement_detention
    del d["scenarios"]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=d.keys())
    writer.writeheader()
    writer.writerow(d)
    return buf.getvalue()


# ─────────────────────────────────────────────
#  BATCH PROCESSING
# ─────────────────────────────────────────────


def process_batch(folder: str) -> list[ProspectusData]:
    """Process all PDFs in a folder."""
    results = []
    pdf_files = sorted(Path(folder).glob("*.pdf")) + sorted(Path(folder).glob("*.PDF"))
    for pdf_path in pdf_files:
        print(f"  → {pdf_path.name}...", end=" ", flush=True)
        try:
            ext = ProspectusExtractor(str(pdf_path))
            data = ext.extract_all()
            results.append(data)
            print(f"OK ({data.taux_extraction})")
        except Exception as e:
            print(f"ERREUR: {e}")
            traceback.print_exc()
    return results


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Extrait les informations clés d'un ou plusieurs prospectus PDF (KID/DICI/KIID)."
    )
    parser.add_argument("pdf", help="Fichier PDF ou dossier contenant des PDFs")
    parser.add_argument("--json", action="store_true", help="Sortie en JSON")
    parser.add_argument("--csv", action="store_true", help="Sortie en CSV (une ligne par PDF)")
    parser.add_argument("--output", "-o", help="Ecrire le resultat dans un fichier")
    args = parser.parse_args()

    target = Path(args.pdf)

    if target.is_dir():
        # Batch mode
        results = process_batch(str(target))
        if not results:
            print("Aucun PDF trouvé.", file=sys.stderr)
            sys.exit(1)

        if args.json:
            output = json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2)
        elif args.csv:
            # Combine all CSV rows
            all_dicts = []
            for data in results:
                d = asdict(data)
                for i, sc in enumerate(data.scenarios):
                    d[f"scenario_{i + 1}_nom"] = sc.scenario
                    d[f"scenario_{i + 1}_valeur_1an"] = sc.valeur_1an
                    d[f"scenario_{i + 1}_rendement_1an"] = sc.rendement_1an
                    d[f"scenario_{i + 1}_valeur_detention"] = sc.valeur_detention
                    d[f"scenario_{i + 1}_rendement_detention"] = sc.rendement_detention
                del d["scenarios"]
                all_dicts.append(d)

            # Union of all keys
            all_keys = list(dict.fromkeys(k for d in all_dicts for k in d))
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=all_keys)
            writer.writeheader()
            for d in all_dicts:
                writer.writerow(d)
            output = buf.getvalue()
        else:
            output = "\n\n".join(format_table(r) for r in results)

        print(f"\n{'═' * 76}")
        print(f"  BATCH : {len(results)} fichiers traités")
        rates = [int(r.taux_extraction.replace("%", "")) for r in results if r.taux_extraction]
        if rates:
            print(f"  Taux moyen : {sum(rates) / len(rates):.0f}%")
        print(f"{'═' * 76}\n")

    elif target.exists():
        # Single file
        extractor = ProspectusExtractor(str(target))
        data = extractor.extract_all()

        if args.json:
            output = to_json(data)
        elif args.csv:
            output = to_csv_row(data)
        else:
            output = format_table(data)
    else:
        print(f"Erreur : '{args.pdf}' introuvable.", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Résultat écrit dans : {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
