"""
Seed: Real opportunity from Jornal de Angola (17 Maio 2026).
Source: ESPECIAL section, page 12 — EDITAL N.º 02/ADMIMED/ADM-DCIM/2026
Extracted manually from PressReader screenshot spread_02.

Run: docker compose exec api python -m app.scripts.seed_jda_opportunity
"""
import asyncio, json
from datetime import date, timedelta

from app.database import AsyncSessionLocal, Base, engine
from app.models import Opportunity, OpportunityCategory, Organization
from app.models.opportunity import Modality, OpportunityStatus, OpportunityType
from app.models.organization import OrgType
from app.services.opportunities import _make_slug
from app.services.trust_classifier import classifier as trust


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:

        # ─── Organization: ANRM ──────────────────────────────────────────────
        from sqlalchemy import select
        existing = await db.execute(
            select(Organization).where(Organization.slug == "anrm")
        )
        anrm = existing.scalar_one_or_none()
        if not anrm:
            anrm = Organization(
                name="Agência Nacional de Recursos Minerais — ANRM",
                slug="anrm",
                type=OrgType.PUBLIC,
                website="https://anrm.gov.ao",
                is_verified=True,
            )
            db.add(anrm)
            await db.flush()
            print("  Created org: ANRM")
        else:
            print("  Org ANRM already exists")

        # ─── Opportunity: EDITAL ANRM ─────────────────────────────────────────
        SOURCE_URL = "https://edicoesnovembro.pressreader.com/jornal-de-angola/20260517"
        trust_level = trust.classify_url(SOURCE_URL)
        trust_score = trust.trust_score(SOURCE_URL)

        opp_data = {
            "title": "Edital N.º 02/ADMIMED/ADM-DCIM/2026 — Concessão Mineira Sociedade Mineira do Tchiol LDA",
            "type": OpportunityType.CONCURSO,
            "status": OpportunityStatus.ACTIVE,
            "modality": None,
            "description_structured": (
                "A Agência Nacional de Recursos Minerais (ANRM) notifica os interessados "
                "sobre o processo de concessão mineira N.º 7/304/42/ADM/INT.7.1/2023 "
                "para a Sociedade Mineira do Tchiol LDA, referente a área das concessões "
                "minerais, geologia e minas. Publicado em dois avisos (1.º e 2.º) no "
                "Jornal de Angola edição de 17 de Maio de 2026."
            ),
            "requirements": json.dumps([
                "Consultar edital completo no Jornal de Angola",
                "Processo N.º 7/304/42/ADM/INT.7.1/2023",
                "EDITAL N.º 02/ADMIMED/ADM-DCIM/2026",
            ]),
            "province": "Luanda",
            "source_url": SOURCE_URL,
            "source_name": "Jornal de Angola",
            "deadline": date.today() + timedelta(days=30),
            "application_type": "IN_PERSON",
            "trust_level": trust_level.value,
            "trust_score": trust_score,
        }

        slug = _make_slug(opp_data["title"], opp_data["type"].value)

        # Check if already exists
        existing_opp = await db.execute(
            select(Opportunity).where(Opportunity.slug == slug)
        )
        if existing_opp.scalar_one_or_none():
            print(f"  Opportunity already exists: {slug}")
            await db.commit()
            return

        opp = Opportunity(
            slug=slug,
            organization_id=anrm.id,
            ai_extracted=False,
            ai_confidence_score=0.95,
            requires_review=False,
            published_at=None,
            source_logo_url=None,
            source_url_ok=None,
            **{k: v for k, v in opp_data.items()
               if k not in ("trust_level", "trust_score", "application_type")},
        )
        # Set trust and application fields directly
        opp.trust_level     = opp_data["trust_level"]
        opp.trust_score     = opp_data["trust_score"]
        opp.application_type = opp_data["application_type"]

        db.add(opp)
        await db.flush()

        for cat in ["Concessões Minerais", "Editais", "ANRM", "Concurso Público"]:
            db.add(OpportunityCategory(opportunity_id=opp.id, category=cat))

        await db.commit()
        print(f"  Created: {opp.title[:70]}")
        print(f"  Slug:    {opp.slug}")
        print(f"  Trust:   {opp.trust_level} (score={opp.trust_score})")
        print(f"  Source:  {opp.source_url}")


if __name__ == "__main__":
    asyncio.run(seed())
