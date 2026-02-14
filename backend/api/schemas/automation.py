from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class TaskFeedbackRequest(BaseModel):
    verdict: str = Field(..., description="correct|incorrect|partial")
    comment: Optional[str] = None
    reviewer: Optional[str] = "operator"
    tags: Optional[List[str]] = Field(default_factory=list)


class TriggerDiagnosisRequest(BaseModel):
    sample_id: int


class TriggerAlertsRequest(BaseModel):
    site_id: Optional[int] = None


class FeedbackItemResponse(BaseModel):
    id: int
    verdict: str
    comment: Optional[str] = None
    reviewer: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class TaskFeedbackListResponse(BaseModel):
    task_id: int
    total: int
    feedbacks: List[FeedbackItemResponse]


class FeedbackStatsItemResponse(BaseModel):
    total: int
    correct: int
    incorrect: int
    partial: int
    correct_rate: float
    incorrect_rate: float
    partial_rate: float
    is_sample_sufficient: bool
    window_days: int
    min_samples: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class FeedbackStatsResponse(BaseModel):
    total_types: int
    stats: Dict[str, FeedbackStatsItemResponse]


class FeedbackTrendPointResponse(BaseModel):
    date: str
    total: int
    correct: int
    incorrect: int
    partial: int
    correct_rate: float
    incorrect_rate: float
    partial_rate: float


class FeedbackTrendsResponse(BaseModel):
    window_days: int
    diagnosis_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    trends: Dict[str, List[FeedbackTrendPointResponse]]


class FeedbackInsightItemResponse(BaseModel):
    diagnosis_type: str
    total: int
    incorrect_rate: float
    correct_rate: float
    is_sample_sufficient: bool
    suggestion: str


class FeedbackInsightsResponse(BaseModel):
    top_n: int
    insights: List[FeedbackInsightItemResponse]


class ManualActionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
