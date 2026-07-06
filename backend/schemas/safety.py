from pydantic import BaseModel, Field


class SafetyFinding(BaseModel):
    model_config = {"extra": "forbid"}

    severity: str = Field(description="Severity of the finding: 'Low', 'Medium', 'High', or 'Critical'")
    finding_type: str = Field(description="Type of safety gap: 'Missing Lockout/Isolation', 'Incorrect PPE', 'Procedural Deviation', 'Hazard Warning', or 'Other'")
    description: str = Field(description="Detailed explanation of the safety finding or gap")
    recommendation: str = Field(description="Actionable corrective recommendation to mitigate the risk")
    reference_source: str = Field(description="Source document or SOP reference, or empty string if not applicable")


class SafetyReviewReport(BaseModel):
    model_config = {"extra": "forbid"}

    status: str = Field(description="Overall audit outcome: 'Safe', 'Needs Review', or 'Unsafe'")
    summary: str = Field(description="High-level executive summary of the safety audit findings")
    findings: list[SafetyFinding] = Field(description="List of specific safety findings and procedural gaps identified")


class PTWReviewRequest(BaseModel):
    permit_text: str = Field(min_length=10, description="The raw permit text or steps of the task to be reviewed")
    equipment: str | None = Field(default=None, description="Optional equipment name/model to filter the source manuals")
    manufacturer: str | None = Field(default=None, description="Optional manufacturer to filter the source manuals")
