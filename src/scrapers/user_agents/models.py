"""
User Agent Database Models

Defines the database schema for user agent management.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class UserAgent(Base):
    """Simplified database model for user agents with essential lifecycle tracking"""
    
    __tablename__ = 'user_agents'
    
    id = Column(Integer, primary_key=True)
    user_agent = Column(Text, nullable=False, unique=True)
    status = Column(String(20), default='unknown')  # working, failing, retired, unknown
    fail_count = Column(Integer, default=0)
    last_tested = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<UserAgent(id={self.id}, status='{self.status}', ua='{self.user_agent[:50]}...')>"
