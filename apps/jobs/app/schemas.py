from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RequestOtpIn(BaseModel):
    phone: str


class VerifyOtpIn(BaseModel):
    phone: str
    otp: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = Field(None, description="Optional initial role: seeker|employer")


class CompanyCreateIn(BaseModel):
    name: str
    description: Optional[str] = None


class CompanyOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class JobCreateIn(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    salary_cents: Optional[int] = Field(None, ge=0)
    category: Optional[str] = Field(None, description="e.g., Engineering, Sales")
    employment_type: Optional[Literal["full_time", "part_time", "contract", "internship", "temporary"]] = None
    is_remote: Optional[bool] = False
    tags: Optional[List[str]] = Field(default=None, description="List of tags")


class JobOut(BaseModel):
    id: str
    company_id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    salary_cents: Optional[int] = None
    category: Optional[str] = None
    employment_type: Optional[Literal["full_time", "part_time", "contract", "internship", "temporary"]] = None
    is_remote: bool = False
    tags: List[str] = []
    status: str
    created_at: datetime


class JobsListOut(BaseModel):
    jobs: List[JobOut]
    total: Optional[int] = None
    next_offset: Optional[int] = None


class ApplyIn(BaseModel):
    cover_letter: Optional[str] = None


class ApplicationOut(BaseModel):
    id: str
    job_id: str
    user_id: str
    status: str
    cover_letter: Optional[str] = None
    created_at: datetime


class ApplicationsListOut(BaseModel):
    applications: List[ApplicationOut]


class JobUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    salary_cents: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, description="open|closed")
    category: Optional[str] = None
    employment_type: Optional[Literal["full_time", "part_time", "contract", "internship", "temporary"]] = None
    is_remote: Optional[bool] = None
    tags: Optional[List[str]] = Field(default=None, description="Replace tags with given list")


class ApplicationStatusUpdateIn(BaseModel):
    status: str = Field(..., description="applied|reviewed|accepted|rejected")
