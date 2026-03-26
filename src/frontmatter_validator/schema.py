from datetime import date
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

CategoryType = Literal["blog post", "find", "newsletter", "standalone"]
StatusType = Literal["idea", "draft", "review", "published"]

class UniversalFields(BaseModel):
    Category: str = Field(..., description="blog post | find | newsletter | standalone")
    status: StatusType
    created: Optional[Union[date, str]] = None
    published_date: Optional[Union[date, str]] = None
    canonical_url: Optional[str] = ""
    tags: List[str] = []

    @model_validator(mode="after")
    def check_published_date(self) -> "UniversalFields":
        if self.status == "published" and not self.published_date:
            raise ValueError("published_date is required when status is 'published'")
        return self

class BlogPostFields(UniversalFields):
    series: Optional[str] = ""
    series_position: int = 0
    title: str
    description: Optional[str] = ""
    newsletter_url: Optional[str] = ""
    promo_file: Optional[str] = ""

class FindFields(UniversalFields):
    source_url: str
    source_title: str
    source_author: Optional[str] = ""
    source_type: Literal["article", "video", "tool", "repo", "thread", "podcast"]
    captured: Optional[Union[date, str]] = None

class NewsletterFields(UniversalFields):
    issue_number: int
    beehiiv_url: Optional[str] = ""
    blog_post: Optional[str] = ""
    finds_included: List[str] = []

class StandaloneFields(UniversalFields):
    pass
