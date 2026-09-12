import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import get_current_user, get_db
from ..services import procurement, stats

router = APIRouter(prefix="/api/v1", tags=["stats"], dependencies=[Depends(get_current_user)])


async def _timezone_of(db: AsyncIOMotorDatabase, edition_id: str) -> str:
    edition = await db.editions.find_one({"_id": edition_id})
    if edition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="edition not found")
    return edition.get("timezone", "Europe/Brussels")


@router.get("/stats/overview")
async def overview(edition_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    await _timezone_of(db, edition_id)
    return await stats.overview(db, edition_id)


@router.get("/stats/by-product")
async def by_product(edition_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> list[dict]:
    await _timezone_of(db, edition_id)
    return await stats.by_product(db, edition_id)


@router.get("/stats/by-bar")
async def by_bar(edition_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> list[dict]:
    await _timezone_of(db, edition_id)
    return await stats.by_bar(db, edition_id)


@router.get("/stats/by-staff")
async def by_staff(edition_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> list[dict]:
    await _timezone_of(db, edition_id)
    return await stats.by_staff(db, edition_id)


@router.get("/stats/by-hour")
async def by_hour(edition_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> list[dict]:
    tz = await _timezone_of(db, edition_id)
    return await stats.by_hour(db, edition_id, tz)


@router.get("/stats/peak-per-bar")
async def peak_per_bar(edition_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> list[dict]:
    tz = await _timezone_of(db, edition_id)
    return await stats.peak_per_bar(db, edition_id, tz)


@router.get("/stats/compare")
async def compare(
    edition_a: str, edition_b: str, db: AsyncIOMotorDatabase = Depends(get_db)
) -> list[dict]:
    await _timezone_of(db, edition_a)
    await _timezone_of(db, edition_b)
    return await stats.compare(db, edition_a, edition_b)


@router.get("/stats/procurement")
async def advise(
    edition_id: str,
    growth_pct: float | None = Query(default=None),
    safety_pct: float = Query(default=procurement.DEFAULT_SAFETY_PCT),
    compare_to: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[dict]:
    await _timezone_of(db, edition_id)
    return await procurement.advise(
        db, edition_id, growth_pct=growth_pct, safety_pct=safety_pct, compare_to=compare_to
    )


REPORTS = {
    "by-product": stats.by_product,
    "by-bar": stats.by_bar,
    "by-staff": stats.by_staff,
}


@router.get("/export/{report}.csv")
async def export_csv(
    report: str, edition_id: str, db: AsyncIOMotorDatabase = Depends(get_db)
) -> Response:
    tz = await _timezone_of(db, edition_id)

    if report == "by-hour":
        rows = await stats.by_hour(db, edition_id, tz)
    elif report == "procurement":
        rows = await procurement.advise(db, edition_id)
    elif report in REPORTS:
        rows = await REPORTS[report](db, edition_id)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown report")

    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{report}.csv"'},
    )
