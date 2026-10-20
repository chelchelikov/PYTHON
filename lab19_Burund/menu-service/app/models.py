from sqlalchemy import CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (CheckConstraint("price > 0", name="ck_dish_price"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    is_available: Mapped[bool] = mapped_column(nullable=False, default=True)
