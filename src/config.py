"""Configuration loading with Pydantic validation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ScheduleSection(BaseModel):
    enabled: bool
    mode: str
    day: str | None = None
    time: str | None = None
    timezone: str = "UTC"


class WindowSection(BaseModel):
    daily_days: int
    weekly_days: int
    monthly_days: int


class LimitsSection(BaseModel):
    max_candidates_per_source: int
    max_total_candidates: int
    max_runtime_minutes: int


class ScheduleConfig(BaseModel):
    schedule: ScheduleSection
    window: WindowSection
    limits: LimitsSection


class QuerySpec(BaseModel):
    name: str
    query: str


class CrossrefSource(BaseModel):
    enabled: bool
    mailto_env: str = "CROSSREF_MAILTO"
    queries: list[QuerySpec]
    max_results: int


class ArxivSource(BaseModel):
    enabled: bool
    categories: list[str] = []
    queries: list[QuerySpec]
    max_results: int


class SourcesConfig(BaseModel):
    crossref: CrossrefSource
    arxiv: ArxivSource


class RuleFilterSpec(BaseModel):
    require_year_after: int | None = None
    require_abstract: bool = False
    blacklist_keywords: list[str] = []


class ResearchProfile(BaseModel):
    name: str
    slug: str
    field: str
    core_topics: list[str] = []
    reject_topics: list[str] = []
    rule_filter: RuleFilterSpec = Field(default_factory=RuleFilterSpec)


class AppConfig(BaseModel):
    schedule: ScheduleSection
    window: WindowSection
    limits: LimitsSection
    sources: SourcesConfig
    profile: ResearchProfile


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(config_dir: Path, profile: str) -> AppConfig:
    schedule_raw = _read_yaml(config_dir / "schedule.yaml")
    sources_raw = _read_yaml(config_dir / "sources.yaml")
    profile_raw = _read_yaml(config_dir / "profiles" / profile / "research_profile.yaml")

    schedule_cfg = ScheduleConfig(**schedule_raw)
    sources_cfg = SourcesConfig(**sources_raw["sources"])
    profile_obj = ResearchProfile(**profile_raw["research_profile"])

    return AppConfig(
        schedule=schedule_cfg.schedule,
        window=schedule_cfg.window,
        limits=schedule_cfg.limits,
        sources=sources_cfg,
        profile=profile_obj,
    )
