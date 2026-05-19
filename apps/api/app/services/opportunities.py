import json
import math
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.opportunity import Opportunity, OpportunityCategory
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityListOut,
    OpportunityOut,
    PaginatedOpportunities,
)


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[àáâãä]", "a", text)
    text = re.sub(r"[èéêë]", "e", text)
    text = re.sub(r"[ìíîï]", "i", text)
    text = re.sub(r"[òóôõö]", "o", text)
    text = re.sub(r"[ùúûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _make_slug(title: str, type_: str) -> str:
    base = f"{_slugify(type_)}-{_slugify(title[:80])}"
    suffix = uuid.uuid4().hex[:8]
    return f"{base}-{suffix}"


def _build_filters(
    type_: str | None,
    status: str | None,
    province: str | None,
    search: str | None,
) -> list:
    """Build reusable WHERE conditions shared by count and data queries."""
    conditions = []
    if type_:
        conditions.append(Opportunity.type == type_.upper())
    # Default to ACTIVE when no status filter provided
    conditions.append(
        Opportunity.status == status.upper() if status else Opportunity.status == "ACTIVE"
    )
    if province:
        conditions.append(Opportunity.province.ilike(f"%{province}%"))
    if search:
        conditions.append(
            or_(
                Opportunity.title.ilike(f"%{search}%"),
                Opportunity.description_structured.ilike(f"%{search}%"),
            )
        )
    return conditions


class OpportunityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _load_options(self) -> list:
        return [
            selectinload(Opportunity.organization),
            selectinload(Opportunity.categories),
        ]

    async def list(
        self,
        page: int = 1,
        per_page: int = 20,
        type_: str | None = None,
        status: str | None = None,
        province: str | None = None,
        category: str | None = None,
        search: str | None = None,
        sort: str | None = None,
    ) -> PaginatedOpportunities:
        per_page = min(per_page, 50)
        offset = (page - 1) * per_page
        filters = _build_filters(type_, status, province, search)

        # Count query — separate from data query to avoid selectinload conflicts
        count_q = select(func.count(Opportunity.id.distinct())).where(*filters)
        if category:
            count_q = count_q.join(
                OpportunityCategory,
                OpportunityCategory.opportunity_id == Opportunity.id,
            ).where(OpportunityCategory.category.ilike(f"%{category}%"))
        total: int = (await self.db.execute(count_q)).scalar_one()

        # Data query
        data_q = (
            select(Opportunity)
            .options(*self._load_options())
            .where(*filters)
        )
        if category:
            data_q = (
                data_q.join(
                    OpportunityCategory,
                    OpportunityCategory.opportunity_id == Opportunity.id,
                )
                .where(OpportunityCategory.category.ilike(f"%{category}%"))
                .distinct()
            )
        order_col = (
            Opportunity.deadline.asc().nullslast()
            if sort == "deadline"
            else Opportunity.created_at.desc()
        )
        data_q = data_q.order_by(order_col).offset(offset).limit(per_page)

        result = await self.db.execute(data_q)
        items = result.scalars().unique().all()

        return PaginatedOpportunities(
            items=[OpportunityListOut.model_validate(o) for o in items],
            total=total,
            page=page,
            per_page=per_page,
            pages=math.ceil(total / per_page) if total else 1,
        )

    async def get_by_slug(self, slug: str) -> OpportunityOut:
        result = await self.db.execute(
            select(Opportunity)
            .options(*self._load_options())
            .where(Opportunity.slug == slug)
        )
        opp = result.scalar_one_or_none()
        if not opp:
            raise NotFoundException("Opportunity")

        opp.view_count += 1
        await self.db.commit()
        return OpportunityOut.model_validate(opp)

    async def create(self, data: OpportunityCreate) -> OpportunityOut:
        slug = _make_slug(data.title, data.type)

        opp = Opportunity(
            slug=slug,
            title=data.title,
            type=data.type,
            status=data.status,
            modality=data.modality,
            description_structured=data.description_structured,
            requirements=json.dumps(data.requirements) if data.requirements else None,
            benefits=json.dumps(data.benefits) if data.benefits else None,
            tags=json.dumps(data.tags) if data.tags else None,
            province=data.province,
            municipality=data.municipality,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            salary_currency=data.salary_currency,
            source_url=data.source_url,
            source_name=data.source_name,
            deadline=data.deadline,
            extracted_at=datetime.now(timezone.utc),
        )
        self.db.add(opp)
        await self.db.flush()

        if data.tags:
            for tag in data.tags:
                self.db.add(OpportunityCategory(opportunity_id=opp.id, category=tag))
        await self.db.flush()

        # Re-query with eager relationships after all inserts
        created = await self.db.scalar(
            select(Opportunity)
            .options(*self._load_options())
            .where(Opportunity.id == opp.id)
        )
        return OpportunityOut.model_validate(created)
