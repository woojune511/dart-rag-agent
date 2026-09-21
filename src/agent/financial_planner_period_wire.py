"""One Planner period shape, lowered only from its explicit field choices."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from src.agent.financial_measurement_periods import period_contract_error


class PlannerMeasurementPeriod(BaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    precision: Literal["unspecified", "year", "date", "date_interval", "unresolved"] = Field(
        description=(
            "Precision requested, independent of source availability. year covers absolute and "
            "relative years without calendar endpoints. date/date_interval require explicitly "
            "requested full dates. unspecified means no period request; unresolved means the "
            "request itself cannot be interpreted."
        ),
    )
    reference_year: StrictInt | None = Field(ge=1, le=9999, description=(
        "For year precision, the named target year or explicit relative anchor year. "
        "Otherwise null. A document's report year is not a default."
    ))
    year_offset: StrictInt | None = Field(description=(
        "For year precision, zero for the named target year, or the explicitly requested "
        "signed offset from reference_year. Code adds it; do not shift the reference too. "
        "Otherwise null."
    ))
    coverage: Literal["whole_year", "within_year"] | None = Field(description=(
        "For year precision, whole_year requires the complete year; within_year also permits "
        "a point or shorter measurement inside that year. Neither chooses fiscal endpoints. "
        "Otherwise null."
    ))
    start_date: str | None = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description=(
        "Explicit ISO YYYY-MM-DD date for date precision, or inclusive start for date_interval. "
        "Otherwise null; never derive dates from a year."
    ))
    end_date: str | None = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description=(
        "Explicit inclusive ISO YYYY-MM-DD end for date_interval only; otherwise null. "
        "An interval remains an interval even if its endpoints are equal."
    ))
    request_unit_ids: list[str] = Field(description=(
        "Output-owned original request units supporting this period, including its anchor, "
        "offset and coverage. Empty only for unspecified."
    ))

    @model_validator(mode="after")
    def validate_choices(self):
        self.to_internal()
        return self

    def to_internal(self) -> dict:
        """Reject incompatible fields; never infer precision, dates or coverage."""
        fields = {
            "reference_year": self.reference_year, "year_offset": self.year_offset,
            "coverage": self.coverage, "start_date": self.start_date, "end_date": self.end_date,
        }
        required = {
            "year": {"reference_year", "year_offset", "coverage"},
            "date": {"start_date"}, "date_interval": {"start_date", "end_date"},
        }.get(self.precision, set())
        if {name for name, value in fields.items() if value is not None} != required:
            raise ValueError("invalid_measurement_period")
        if self.precision == "unspecified":
            if self.request_unit_ids:
                raise ValueError("invalid_measurement_period_request")
            return {"kind": "unspecified"}
        result = {"kind": self.precision, "request_unit_ids": list(self.request_unit_ids)}
        if self.precision == "year":
            result["coverage"] = self.coverage
            if self.year_offset == 0:
                result["year"] = self.reference_year
            else:
                result.update(kind="relative_year", anchor_year=self.reference_year, year_offset=self.year_offset)
        elif self.precision == "date":
            result["date"] = self.start_date
        elif self.precision == "date_interval":
            result.update(start_date=self.start_date, end_date=self.end_date)
        if error := period_contract_error(result):
            raise ValueError(error)
        return result
