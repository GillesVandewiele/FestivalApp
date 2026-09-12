from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..deps import get_current_user, get_db
from ..models.catalog import Bar, Edition, Product, Staff
from ..models.common import MongoModel

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(get_current_user)])

RESOURCES: dict[str, tuple[str, type[MongoModel]]] = {
    "editions": ("editions", Edition),
    "bars": ("bars", Bar),
    "products": ("products", Product),
    "staff": ("staff", Staff),
}


def _serialise(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


def _register(plural: str, collection: str, model: type[MongoModel]) -> None:
    singular = plural[:-1] if plural.endswith("s") else plural

    @router.get(f"/{plural}", name=f"list_{plural}")
    async def list_items(
        edition_id: str | None = Query(default=None),
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> list[dict]:
        query = {"edition_id": edition_id} if edition_id else {}
        return [_serialise(d) async for d in db[collection].find(query)]

    @router.post(f"/{plural}", status_code=status.HTTP_201_CREATED, name=f"create_{plural}")
    async def create_item(
        body: model,  # type: ignore[valid-type]
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> dict:
        try:
            await db[collection].insert_one(body.to_mongo())
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A {singular} with this key already exists",
            ) from exc
        return _serialise(body.to_mongo())

    @router.patch(f"/{plural}/{{item_id}}", name=f"update_{plural}")
    async def update_item(
        item_id: str,
        body: dict[str, Any],
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> dict:
        body.pop("_id", None)
        body.pop("id", None)
        doc = await db[collection].find_one_and_update(
            {"_id": item_id}, {"$set": body}, return_document=ReturnDocument.AFTER
        )
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"{singular} not found"
            )
        return _serialise(doc)

    @router.delete(
        f"/{plural}/{{item_id}}",
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{plural}",
    )
    async def delete_item(item_id: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
        result = await db[collection].delete_one({"_id": item_id})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"{singular} not found"
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)


for _plural, (_collection, _model) in RESOURCES.items():
    _register(_plural, _collection, _model)
