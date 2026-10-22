"""Country code (ISO 3166-1 alpha-2) to continent, from a static mapping."""

from __future__ import annotations

UNKNOWN = "Unknown"

# RU, TR and CY are assigned to Europe so that shows in Moscow or Istanbul read as European tour legs;
# the Caucasus and Kazakhstan stay in Asia.
_CODES_BY_CONTINENT = {
    "Africa": (
        "AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG EH ER ET GA GH GM GN GQ GW KE KM LR LS LY MA MG ML MR MU MW "
        "MZ NA NE NG RE RW SC SD SH SL SN SO SS ST SZ TD TG TN TZ UG YT ZA ZM ZW"
    ),
    "Antarctica": "AQ BV GS HM TF",
    "Asia": (
        "AE AF AM AZ BD BH BN BT CC CN CX GE HK ID IL IN IO IQ IR JO JP KG KH KP KR KW KZ LA LB LK MM MN MO MV "
        "MY NP OM PH PK PS QA SA SG SY TH TJ TL TM TW UZ VN YE"
    ),
    "Europe": (
        "AD AL AT AX BA BE BG BY CH CY CZ DE DK EE ES FI FO FR GB GG GI GR HR HU IE IM IS IT JE LI LT LU LV MC "
        "MD ME MK MT NL NO PL PT RO RS RU SE SI SJ SK SM TR UA VA XK"
    ),
    "North America": (
        "AG AI AW BB BL BM BQ BS BZ CA CR CU CW DM DO GD GL GP GT HN HT JM KN KY LC MF MQ MS MX NI PA PM PR SV "
        "SX TC TT US VC VG VI"
    ),
    "Oceania": "AS AU CK FJ FM GU KI MH MP NC NF NR NU NZ PF PG PN PW SB TK TO TV UM VU WF WS",
    "South America": "AR BO BR CL CO EC FK GF GY PE PY SR UY VE",
}

CONTINENT_BY_CODE: dict[str, str] = {
    code: continent for continent, codes in _CODES_BY_CONTINENT.items() for code in codes.split()
}


def continent(country_code: str | None) -> str:
    """Continent name for an ISO 3166-1 alpha-2 code (case-insensitive); "Unknown" when not mapped."""
    if not country_code:
        return UNKNOWN
    code = country_code.strip().upper()
    if code == "UK":  # common non-ISO alias
        code = "GB"
    return CONTINENT_BY_CODE.get(code, UNKNOWN)
