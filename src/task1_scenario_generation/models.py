from pydantic import BaseModel, Field
from typing import List, Optional


class TestStep(BaseModel):
    action: str = Field(description="操作步骤，例如 '点击新建项目按钮'")
    target: Optional[str] = Field(None, description="操作的目标元素描述")


class TestExpectation(BaseModel):
    description: str = Field(description="预期状态描述，例如 '页面显示新建项目对话框'")


class TestScenario(BaseModel):
    name: str = Field(description="测试场景名称")
    description: str = Field(description="场景描述")
    steps: List[TestStep] = Field(description="操作步骤列表")
    expectations: List[TestExpectation] = Field(description="预期结果列表")


class FeaturePoint(BaseModel):
    name: str = Field(description="功能点名称")
    description: str = Field(description="功能点描述")
    scenarios: List[TestScenario] = Field(default_factory=list, description="该功能点下的测试场景列表")
