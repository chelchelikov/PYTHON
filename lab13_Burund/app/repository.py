"""MongoRepository: CRUD и запросы к коллекции rooms."""

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models import Room, ValidationError


class NotFoundError(LookupError):
    pass


def to_object_id(room_id: str) -> ObjectId:
    try:
        return ObjectId(room_id)
    except (InvalidId, TypeError):
        raise ValidationError(f"Некорректный идентификатор: {room_id}") from None


class MongoRepository:
    def __init__(self, db: Database, collection: str = "rooms") -> None:
        self.collection: Collection = db[collection]

    def create_indexes(self) -> list[str]:
        return [
            # Уникальный номер комнаты: поиск по номеру и защита от дубликатов
            self.collection.create_index([("number", ASCENDING)], unique=True,
                                         name="uniq_number"),
            # Поиск свободных номеров по типу с сортировкой по цене
            self.collection.create_index([("state", ASCENDING), ("room_type", ASCENDING),
                                          ("price", ASCENDING)], name="state_type_price"),
            # Поиск по элементу массива удобств (multikey-индекс)
            self.collection.create_index([("amenities", ASCENDING)], name="amenities"),
        ]

    # --- CRUD ---
    def add(self, room: Room) -> Room:
        try:
            result = self.collection.insert_one(room.validate().to_document())
        except DuplicateKeyError:
            raise ValidationError(f"Номер {room.number} уже существует") from None
        room.id = str(result.inserted_id)
        return room

    def insert_many(self, rooms: list[Room]) -> int:
        result = self.collection.insert_many([r.validate().to_document() for r in rooms])
        return len(result.inserted_ids)

    def get(self, room_id: str) -> Room:
        document = self.collection.find_one({"_id": to_object_id(room_id)})
        if document is None:
            raise NotFoundError(f"Номер с id={room_id} не найден")
        return Room.from_document(document)

    def get_by_number(self, number: str) -> Room:
        document = self.collection.find_one({"number": number})
        if document is None:
            raise NotFoundError(f"Номер {number} не найден")
        return Room.from_document(document)

    def list_all(self, limit: int = 0) -> list[Room]:
        cursor = self.collection.find().sort("number", ASCENDING).limit(limit)
        return [Room.from_document(d) for d in cursor]

    def update(self, room_id: str, changes: dict[str, Any]) -> Room:
        current = self.get(room_id)
        merged = {**current.to_document(), **changes}
        if "features" in changes:
            merged["features"] = {**current.to_document()["features"], **changes["features"]}
        Room.from_document(merged).validate()
        try:
            document = self.collection.find_one_and_update(
                {"_id": to_object_id(room_id)}, {"$set": merged},
                return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            raise ValidationError(f"Номер {merged['number']} уже существует") from None
        return Room.from_document(document)

    def delete(self, room_id: str) -> None:
        result = self.collection.delete_one({"_id": to_object_id(room_id)})
        if result.deleted_count == 0:
            raise NotFoundError(f"Номер с id={room_id} не найден")

    def count(self) -> int:
        return self.collection.count_documents({})

    def clear(self) -> None:
        self.collection.delete_many({})

    # --- запросы ---
    def find(self, query: dict[str, Any], sort: list[tuple[str, int]] | None = None,
             limit: int = 0) -> list[Room]:
        cursor = self.collection.find(query)
        if sort:
            cursor = cursor.sort(sort)
        return [Room.from_document(d) for d in cursor.limit(limit)]

    def free_rooms(self, room_type: str | None = None, min_beds: int = 1,
                   max_price: float | None = None) -> list[Room]:
        """Фильтр по нескольким полям, в т.ч. вложенному features.beds; сортировка по цене."""
        query: dict[str, Any] = {"state": "free", "features.beds": {"$gte": min_beds}}
        if room_type:
            query["room_type"] = room_type
        if max_price is not None:
            query["price"] = {"$lte": max_price}
        return self.find(query, [("price", ASCENDING), ("number", ASCENDING)])

    def by_type(self, room_type: str) -> list[Room]:
        return self.find({"room_type": room_type}, [("price", DESCENDING)])

    def by_price_range(self, low: float, high: float) -> list[Room]:
        return self.find({"price": {"$gte": low, "$lte": high}}, [("price", ASCENDING)])

    def with_view(self, view: str) -> list[Room]:
        return self.find({"features.view": view}, [("number", ASCENDING)])

    def with_amenity(self, amenity: str) -> list[Room]:
        return self.find({"amenities": amenity}, [("number", ASCENDING)])

    def with_all_amenities(self, amenities: list[str]) -> list[Room]:
        return self.find({"amenities": {"$all": amenities}}, [("price", ASCENDING)])

    def most_expensive(self, limit: int = 3) -> list[Room]:
        return self.find({}, [("price", DESCENDING)], limit)

    def largest(self, limit: int = 3) -> list[Room]:
        return self.find({}, [("features.area_m2", DESCENDING)], limit)

    # --- агрегации ---
    def stats_by_type(self) -> list[dict[str, Any]]:
        pipeline = [
            {"$group": {"_id": "$room_type", "count": {"$sum": 1},
                        "avg_price": {"$avg": "$price"}, "min_price": {"$min": "$price"},
                        "max_price": {"$max": "$price"}}},
            {"$sort": {"avg_price": 1}},
        ]
        return [{**d, "avg_price": round(d["avg_price"], 2)}
                for d in self.collection.aggregate(pipeline)]

    def stats_by_state(self) -> dict[str, int]:
        pipeline = [{"$group": {"_id": "$state", "count": {"$sum": 1}}}]
        return {d["_id"]: d["count"] for d in self.collection.aggregate(pipeline)}

    def amenity_popularity(self) -> list[tuple[str, int]]:
        pipeline = [
            {"$unwind": "$amenities"},
            {"$group": {"_id": "$amenities", "rooms": {"$sum": 1}}},
            {"$sort": {"rooms": -1, "_id": 1}},
        ]
        return [(d["_id"], d["rooms"]) for d in self.collection.aggregate(pipeline)]

    def explain_free_rooms(self) -> str:
        plan = self.collection.find({"state": "free", "room_type": "suite"}).sort(
            "price", ASCENDING).explain()
        winning = plan["queryPlanner"]["winningPlan"]
        stages = []
        while winning:
            stages.append(winning.get("stage", "?") + (f"({winning['indexName']})"
                                                       if "indexName" in winning else ""))
            winning = winning.get("inputStage")
        return " <- ".join(stages)
