from sqlalchemy import Column, Integer, String, Text, Numeric
from app.core.database import Base

class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)

    question = Column(String(255), nullable=False)
    answer = Column(Text, nullable=False)

    embedding = Column(Text, nullable=False)