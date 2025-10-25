import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def default_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=True)
    role = Column(String(24), nullable=False, default="seeker")  # seeker|employer
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    company = relationship("Company", back_populates="owner", uselist=False)
    applications = relationship("Application", back_populates="applicant")


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="company")
    jobs = relationship("Job", back_populates="company")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(128), nullable=True)
    salary_cents = Column(Integer, nullable=True)
    category = Column(String(64), nullable=True)
    employment_type = Column(String(24), nullable=True)  # full_time|part_time|contract|internship|temporary
    is_remote = Column(Boolean, nullable=False, default=False)
    status = Column(String(16), nullable=False, default="open")  # open|closed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    cover_letter = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="applied")  # applied|reviewed|accepted|rejected|withdrawn
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("Job", back_populates="applications")
    applicant = relationship("User", back_populates="applications")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_favorites_user_job"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class JobTag(Base):
    __tablename__ = "job_tags"
    __table_args__ = (
        UniqueConstraint("job_id", "tag", name="uq_job_tags_job_tag"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    tag = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WebhookEndpoint(Base):
    __tablename__ = "jobs_webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("url", name="uq_jobs_webhook_url"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=default_uuid)
    url = Column(String(512), nullable=False)
    secret = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
