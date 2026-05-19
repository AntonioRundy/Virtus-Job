"""
Source Trust Classification System for Virtus Job.

Philosophy: CONFIANÇA E VERACIDADE — every opportunity must be traceable
to a verifiable institutional source. Trust is derived from domain analysis
against curated whitelists of official Angolan entities.

Levels (highest → lowest):
  OFFICIAL_GOVERNMENT  — ministries, state agencies, .gov.ao domains
  OFFICIAL_COMPANY     — major state-owned and verified private companies
  INSTITUTIONAL        — universities, hospitals, international orgs
  VERIFIED_PARTNER     — verified Angolan .ao domains, known publishers
  UNVERIFIED           — unknown or non-Angolan generic sources
"""
from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse


class TrustLevel(str, Enum):
    OFFICIAL_GOVERNMENT = "OFFICIAL_GOVERNMENT"
    OFFICIAL_COMPANY = "OFFICIAL_COMPANY"
    INSTITUTIONAL = "INSTITUTIONAL"
    VERIFIED_PARTNER = "VERIFIED_PARTNER"
    UNVERIFIED = "UNVERIFIED"


TRUST_SCORES: dict[TrustLevel, float] = {
    TrustLevel.OFFICIAL_GOVERNMENT: 100.0,
    TrustLevel.OFFICIAL_COMPANY: 85.0,
    TrustLevel.INSTITUTIONAL: 75.0,
    TrustLevel.VERIFIED_PARTNER: 55.0,
    TrustLevel.UNVERIFIED: 20.0,
}

TRUST_LABELS: dict[TrustLevel, str] = {
    TrustLevel.OFFICIAL_GOVERNMENT: "Fonte Oficial — Governo",
    TrustLevel.OFFICIAL_COMPANY: "Empresa Oficial",
    TrustLevel.INSTITUTIONAL: "Fonte Institucional",
    TrustLevel.VERIFIED_PARTNER: "Fonte Verificada",
    TrustLevel.UNVERIFIED: "Fonte Não Verificada",
}

# ─── Angola Government Domains ──────────────────────────────────────────────
# All .gov.ao domains are auto-classified OFFICIAL_GOVERNMENT.
# This list covers known specific portals.
OFFICIAL_GOVERNMENT_DOMAINS: frozenset[str] = frozenset({
    # Presidência e Tribunal
    "presidencia.ao",
    "tribunal.ao",
    "parlamento.ao",
    "angolapress.ao",

    # Ministérios
    "med.gov.ao",        # Ministério da Educação
    "minfin.gov.ao",     # Ministério das Finanças
    "minjus.gov.ao",     # Ministério da Justiça
    "mdn.gov.ao",        # Ministério da Defesa Nacional
    "mirex.gov.ao",      # Ministério das Relações Exteriores
    "mintrans.gov.ao",   # Ministério dos Transportes
    "mape.gov.ao",       # Ministério da Administração Pública
    "ms.gov.ao",         # Ministério da Saúde
    "maptss.gov.ao",     # Ministério da Acção Social
    "minagri.gov.ao",    # Ministério da Agricultura
    "minea.gov.ao",      # Ministério da Energia e Águas
    "mtti.gov.ao",       # Ministério das Telecomunicações e TI
    "mch.gov.ao",        # Ministério do Comércio e Hotelaria
    "mf.gov.ao",
    "mj.gov.ao",

    # Institutos e Agências do Estado
    "inagbe.gov.ao",     # Gestão de Bolsas de Estudo
    "inapem.gov.ao",     # Apoio às PMEs
    "ina.gov.ao",        # Instituto Nacional de Administração
    "angosat.ao",        # Satélite Angola
    "ige.gov.ao",        # Inspecção-Geral do Estado
    "mapess.gov.ao",     # Administração Pública
    "maptss.gov.ao",
    "isp.gov.ao",        # Instituto Superior Politécnico
})

# ─── Official Companies (State-owned & verified major private) ───────────────
OFFICIAL_COMPANY_DOMAINS: frozenset[str] = frozenset({
    # Petróleo e Energia
    "sonangol.co.ao",
    "angolalng.com",
    "eni.com",           # ENI Angola
    "bp.com",            # BP Angola
    "totalenergies.com", # TotalEnergies Angola
    "chevron.com",       # Chevron Angola
    "ende.co.ao",        # Empresa Nacional de Distribuição de Electricidade
    "prodel.co.ao",
    "endiama.co.ao",     # Endiama (diamantes)

    # Telecomunicações
    "unitel.ao",
    "movicel.ao",
    "angola-telecom.ao",

    # Banca
    "bna.ao",            # Banco Nacional de Angola
    "bai.ao",            # Banco BAI
    "bfa.ao",            # Banco de Fomento Angola
    "bco.ao",            # Banco de Comércio e Indústria
    "atlantico.ao",      # Banco Atlântico
    "sol.ao",            # Banco SOL
    "keve.co.ao",
    "bci.ao",

    # Seguros e outros
    "ensa.ao",           # ENSA Seguros
    "nossa.co.ao",       # Nossa Seguros
    "taag.com",          # TAAG Angola Airlines
    "aeroportos.co.ao",  # Aeroportos de Angola
    "aa.co.ao",
})

# ─── Institutional Sources ───────────────────────────────────────────────────
INSTITUTIONAL_DOMAINS: frozenset[str] = frozenset({
    # Universidades angolanas
    "uan.ao",
    "uanangola.ao",
    "ujes.ao",
    "uca.ao",            # Universidade Católica de Angola
    "umap.ao",
    "uni.ao",
    "gregorio-semedo.ed.ao",
    "ispef.ao",

    # Saúde
    "joanalvares.ao",
    "josediogo.ao",

    # ONGs e organizações sem fins lucrativos angolanas
    "adpp.ao",
    "action.ao",
    "helpage.ao",

    # Organismos internacionais com presença em Angola
    "unicef.org",
    "un.org",
    "undp.org",
    "worldbank.org",
    "imf.org",
    "ifc.org",
    "who.int",
    "ilo.org",           # Organização Internacional do Trabalho
    "oas.org",
    "unhcr.org",
    "wfp.org",
    "fao.org",
    "africandevelopmentbank.org",
    "afdb.org",

    # Embaixadas e organismos diplomáticos (publicam vagas em Angola)
    "usembassy.gov",
    "gov.uk",
    "diplomatie.gouv.fr",
    "giz.de",            # GIZ Alemanha (cooperação técnica em Angola)

    # Media institucional angolana (fontes com estatuto editorial verificado)
    "jornaldeangola.ao",              # Jornal de Angola — jornal oficial do Estado
    "jornaldeanola.co.ao",            # alias alternativo
    "edicoesnovembro.pressreader.com",# Jornal de Angola via PressReader
    "ja.edicoesnovembro.ao",          # Jornal de Angola portal digital
    "angop.ao",                       # Angola Press (agência noticiosa oficial)
    "angoladigital.net",
    "expansao.ao",
    "valoreconomico.co.ao",
})

# ─── Known legitimate Angolan publishers (.ao but not yet classified) ────────
# These get VERIFIED_PARTNER status automatically since they have .ao domains.
# All other .ao domains also get VERIFIED_PARTNER (automatic — see classifier).

UNTRUSTWORTHY_PATTERNS: frozenset[str] = frozenset({
    # Generic job boards that don't verify Angolan sources
    "indeed.com",
    "linkedin.com",     # Treat as verified_partner (individual posts unverified)
    "jobstreet.com",
    "glassdoor.com",
    "monster.com",
})


def _extract_domain(url: str) -> str:
    """Extract lowercase domain from URL, removing www. prefix."""
    try:
        parsed = urlparse(url.strip())
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


class TrustClassifier:
    """
    Classifies the trust level of a source URL based on domain analysis.
    Single source of truth for all trust decisions in Virtus Job.
    """

    def classify_url(self, url: str) -> TrustLevel:
        domain = _extract_domain(url)
        if not domain:
            return TrustLevel.UNVERIFIED

        # .gov.ao — always official government
        if domain.endswith(".gov.ao"):
            return TrustLevel.OFFICIAL_GOVERNMENT

        # Explicit whitelist lookups
        if domain in OFFICIAL_GOVERNMENT_DOMAINS:
            return TrustLevel.OFFICIAL_GOVERNMENT

        if domain in OFFICIAL_COMPANY_DOMAINS:
            return TrustLevel.OFFICIAL_COMPANY

        if domain in INSTITUTIONAL_DOMAINS:
            return TrustLevel.INSTITUTIONAL

        # Any .ao domain = Angolan entity, at minimum VERIFIED_PARTNER
        if domain.endswith(".ao"):
            return TrustLevel.VERIFIED_PARTNER

        # Known problematic sources
        if domain in UNTRUSTWORTHY_PATTERNS:
            return TrustLevel.UNVERIFIED

        return TrustLevel.UNVERIFIED

    def trust_score(self, url: str) -> float:
        level = self.classify_url(url)
        return TRUST_SCORES[level]

    def label(self, url: str) -> str:
        level = self.classify_url(url)
        return TRUST_LABELS[level]

    def is_institutional_or_above(self, url: str) -> bool:
        """True if source is institutional, official company, or government."""
        level = self.classify_url(url)
        return level in (
            TrustLevel.OFFICIAL_GOVERNMENT,
            TrustLevel.OFFICIAL_COMPANY,
            TrustLevel.INSTITUTIONAL,
        )


# Module-level singleton
classifier = TrustClassifier()
