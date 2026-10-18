"""ドメインモデル。

- Exercise 系: 教材YAMLを読み込むための pydantic モデル(入力の検証が目的)
- GradeResult 系: 採点結果を表す dataclass(アプリ内部で受け渡すだけの値)
"""

from dataclasses import dataclass, field
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

LEVEL_NAMES: dict[int, str] = {1: "基礎", 2: "中級", 3: "標準ライブラリ", 4: "実務"}


class IOCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = ""
    stdin: str = ""
    expected_stdout: str


class Exercise(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^l[1-4]-\d{3}-[a-z0-9-]+$")
    title: str = Field(min_length=1)
    level: int = Field(ge=1, le=4)
    topic: str = Field(min_length=1)
    kind: Literal["write", "bugfix"] = "write"
    description: str = Field(min_length=1)
    starter_code: str
    grading: Literal["pytest", "io"]
    cases: list[IOCase] = Field(default_factory=list)
    hints: list[str] = Field(min_length=3, max_length=3)
    solution: str = Field(min_length=1)
    php_note: str | None = None
    tags: list[str] = Field(default_factory=list)
    time_limit_sec: float = Field(default=5.0, gt=0, le=30)
    # YAML ではなく同じディレクトリの test_solution.py から読み込む
    test_source: str | None = None

    @model_validator(mode="after")
    def _check_grading_inputs(self) -> Self:
        if self.grading == "pytest" and not self.test_source:
            raise ValueError("grading=pytest の演習には test_solution.py が必要です")
        if self.grading == "io" and not self.cases:
            raise ValueError("grading=io の演習には cases が1件以上必要です")
        return self

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES[self.level]


@dataclass(frozen=True)
class CaseOutcome:
    name: str
    passed: bool
    message: str = ""
    details: str = ""


@dataclass(frozen=True)
class GradeResult:
    passed: bool
    cases: list[CaseOutcome] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timed_out: bool = False
    truncated: bool = False
    error_type: str | None = None  # 例: "AssertionError", "SyntaxError", "Timeout"

    @property
    def passed_count(self) -> int:
        return sum(c.passed for c in self.cases)
