from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_admin, get_optional_user
from app.models.user import User
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityOut,
    PaginatedOpportunities,
    SourceCheckResult,
)
from app.services.opportunities import OpportunityService
from app.services.url_checker import verify_opportunity_url

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


@router.get("", response_model=PaginatedOpportunities)
async def list_opportunities(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    type: str | None = Query(None, description="VAGA | CONCURSO | BOLSA | ESTAGIO | FORMACAO"),
    province: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    sort: str | None = Query(None, description="recent | deadline"),
    db: AsyncSession = Depends(get_db),
    _: User | None = Depends(get_optional_user),
):
    service = OpportunityService(db)
    return await service.list(
        page=page,
        per_page=per_page,
        type_=type,
        province=province,
        category=category,
        search=search,
        sort=sort,
    )


@router.get("/{slug}", response_model=OpportunityOut)
async def get_opportunity(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: User | None = Depends(get_optional_user),
):
    service = OpportunityService(db)
    return await service.get_by_slug(slug)


@router.post("", response_model=OpportunityOut, status_code=201)
async def create_opportunity(
    data: OpportunityCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    service = OpportunityService(db)
    opp = await service.create(data)
    # Verify source URL in background — non-blocking
    background_tasks.add_task(verify_opportunity_url, opp.id)
    return opp


@router.post("/{slug}/check-source", response_model=SourceCheckResult)
async def check_source_url(
    slug: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Trigger an async source URL health check for one opportunity."""
    service = OpportunityService(db)
    opp = await service.get_by_slug(slug)
    background_tasks.add_task(verify_opportunity_url, opp.id)
    return SourceCheckResult(
        slug=opp.slug,
        source_url=opp.source_url,
        source_url_ok=opp.source_url_ok,
        source_url_checked_at=opp.source_url_checked_at,
        message="URL check scheduled in background.",
    )
