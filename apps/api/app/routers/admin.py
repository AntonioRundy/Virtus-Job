"""
Admin router — operações de manutenção protegidas por SECRET_KEY.
Apenas para uso interno / deploy inicial.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])


def verify_admin_secret(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.SECRET_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/seed", dependencies=[Depends(verify_admin_secret)])
async def run_seed(db: AsyncSession = Depends(get_db)):
    """Popula a BD com dados de exemplo. Requer header X-Admin-Secret."""
    import json
    from datetime import date, timedelta
    from app.models import Opportunity, OpportunityCategory, Organization
    from app.models.opportunity import Modality, OpportunityStatus, OpportunityType
    from app.models.organization import OrgType
    from app.services.opportunities import _make_slug
    from app.services.trust_classifier import classifier as trust_classifier

    orgs_data = [
        {"name": "Ministério da Educação", "slug": "ministerio-da-educacao",
         "type": OrgType.PUBLIC, "website": "https://med.gov.ao", "is_verified": True},
        {"name": "Refriango", "slug": "refriango",
         "type": OrgType.PRIVATE, "website": "https://refriango.ao", "is_verified": True},
        {"name": "Sonangol", "slug": "sonangol",
         "type": OrgType.PUBLIC, "website": "https://sonangol.co.ao", "is_verified": True},
        {"name": "Angola LNG", "slug": "angola-lng",
         "type": OrgType.PRIVATE, "website": "https://angolalng.com", "is_verified": True},
        {"name": "INAGBE", "slug": "inagbe",
         "type": OrgType.PUBLIC, "website": "https://inagbe.gov.ao", "is_verified": True},
    ]

    opps_data = [
        {"title": "Coordenador de Armazém", "type": OpportunityType.VAGA,
         "status": OpportunityStatus.ACTIVE, "modality": Modality.PRESENCIAL,
         "description_structured": "A Refriango recruta Coordenador de Armazém para gestão de stocks e logística interna em Luanda.",
         "requirements": json.dumps(["Licenciatura em Gestão ou Logística", "Mínimo 3 anos de experiência"]),
         "province": "Luanda", "source_url": "https://jornaldeangola.ao/emprego",
         "source_name": "Jornal de Angola", "deadline": date.today() + timedelta(days=20),
         "application_type": "EMAIL", "contact_email": "rh@refriango.ao",
         "org_slug": "refriango", "categories": ["Logística", "Armazém"]},
        {"title": "Concurso Público para Professor do Ensino Médio — Luanda",
         "type": OpportunityType.CONCURSO, "status": OpportunityStatus.ACTIVE,
         "modality": Modality.PRESENCIAL,
         "description_structured": "Ministério da Educação abre concurso para professores de Matemática, Física e Química.",
         "requirements": json.dumps(["Licenciatura em área relevante", "2 anos de experiência", "Nacionalidade angolana"]),
         "province": "Luanda", "source_url": "https://med.gov.ao",
         "source_name": "Ministério da Educação", "deadline": date.today() + timedelta(days=30),
         "application_type": "IN_PERSON", "org_slug": "ministerio-da-educacao",
         "categories": ["Educação", "Concurso Público"]},
        {"title": "Engenheiro de Processo Sénior — Setor Petrolífero",
         "type": OpportunityType.VAGA, "status": OpportunityStatus.ACTIVE,
         "modality": Modality.PRESENCIAL,
         "description_structured": "Angola LNG procura Engenheiro de Processo Sénior com experiência em GNL para Soyo.",
         "requirements": json.dumps(["Eng. Química ou similar", "8 anos em GNL", "Inglês fluente"]),
         "benefits": json.dumps(["Salário competitivo", "Seguro saúde", "Alojamento"]),
         "province": "Zaire", "municipality": "Soyo",
         "salary_min": 800000.0, "salary_max": 1500000.0, "salary_currency": "AOA",
         "source_url": "https://angolalng.com", "source_name": "Angola LNG",
         "deadline": date.today() + timedelta(days=15),
         "application_type": "URL", "org_slug": "angola-lng",
         "categories": ["Engenharia", "Petróleo e Gás", "Sénior"]},
        {"title": "Estágio Profissional em TI — Sonangol",
         "type": OpportunityType.ESTAGIO, "status": OpportunityStatus.ACTIVE,
         "modality": Modality.HIBRIDO,
         "description_structured": "Sonangol abre estágio para recém-licenciados em Tecnologias de Informação.",
         "requirements": json.dumps(["Licenciatura recente (máx 2 anos)", "Python ou Java", "Disponibilidade imediata"]),
         "province": "Luanda", "source_url": "https://sonangol.co.ao",
         "source_name": "Sonangol", "deadline": date.today() + timedelta(days=10),
         "application_type": "IN_PERSON", "org_slug": "sonangol",
         "categories": ["TI", "Estágio", "Tecnologia"]},
        {"title": "Bolsa de Mestrado em Portugal — INAGBE 2026",
         "type": OpportunityType.BOLSA, "status": OpportunityStatus.ACTIVE,
         "description_structured": "INAGBE abre bolsas para mestrado em universidades portuguesas em Engenharia, Medicina e Direito.",
         "requirements": json.dumps(["Licenciatura ≥ 14 valores", "Máx 35 anos", "Cidadão angolano"]),
         "province": "Luanda", "source_url": "https://inagbe.gov.ao",
         "source_name": "INAGBE", "deadline": date.today() + timedelta(days=45),
         "application_type": "FORM", "contact_email": "bolsas@inagbe.gov.ao",
         "org_slug": "inagbe", "categories": ["Bolsa", "Mestrado", "Portugal"]},
    ]

    DB_FIELDS = {"title","type","status","modality","description_structured","requirements",
                 "benefits","province","municipality","salary_min","salary_max","salary_currency",
                 "source_url","source_name","deadline","contact_email","application_url",
                 "document_url","application_type"}

    org_map = {}
    created = 0

    for od in orgs_data:
        org = Organization(**od)
        db.add(org)
        await db.flush()
        org_map[org.slug] = org

    for raw in opps_data:
        data = dict(raw)
        cats = data.pop("categories", [])
        org_slug = data.pop("org_slug", None)
        kwargs = {k: v for k, v in data.items() if k in DB_FIELDS}
        trust_level = trust_classifier.classify_url(data["source_url"])
        trust_score = trust_classifier.trust_score(data["source_url"])
        opp = Opportunity(
            slug=_make_slug(data["title"], data["type"].value),
            organization_id=org_map[org_slug].id if org_slug and org_slug in org_map else None,
            trust_level=trust_level.value, trust_score=trust_score, **kwargs,
        )
        db.add(opp)
        await db.flush()
        for cat in cats:
            db.add(OpportunityCategory(opportunity_id=opp.id, category=cat))
        created += 1

    await db.commit()
    return {"message": f"Seed completo — {created} oportunidades criadas"}
