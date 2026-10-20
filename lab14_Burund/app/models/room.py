from sqlalchemy import JSON, CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("floor >= 0", name="ck_room_floor"),
        CheckConstraint("capacity > 0", name="ck_room_capacity"),
        CheckConstraint("price > 0", name="ck_room_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    room_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    floor: Mapped[int] = mapped_column(nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False,
                                         index=True)
    is_available: Mapped[bool] = mapped_column(nullable=False, default=True)
    amenities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
