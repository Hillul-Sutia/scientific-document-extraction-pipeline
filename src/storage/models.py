from sqlalchemy import Column, String
from src.storage.db import Base


class FoodMaster(Base):
    __tablename__ = "food_master"

    food_id = Column(String, primary_key=True)
    food_name = Column(String, nullable=False)
    category = Column(String)
    type = Column(String)
    ethnic_group = Column(String)
    source_pdf = Column(String)