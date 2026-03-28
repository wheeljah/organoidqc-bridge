# =============================================
# schemas.py — API 요청/응답 데이터 모델
# Step 2: 이미지 메타, 저장 경로 추가
# Step 3: 개별 오가노이드 속성 구조화
# =============================================
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class OrganType(str, Enum):
    intestine = "intestine"
    liver     = "liver"
    cortical  = "cortical"
    unknown   = "unknown"


# ----- 개별 오가노이드 (Step 3) -----
class OrganoIDOrganoid(BaseModel):
    """세그멘테이션으로 검출된 개별 오가노이드 속성"""
    id:            int   = Field(..., description="오가노이드 인덱스")
    area_px:       float = Field(..., description="면적 (픽셀²)")
    circularity:   float = Field(..., description="원형도 (0~1)")
    centroid_x:    float = Field(..., description="중심 X 좌표")
    centroid_y:    float = Field(..., description="중심 Y 좌표")
    mean_intensity:float = Field(..., description="평균 밝기 (0~255)")
    bbox:          Optional[List[int]] = Field(None, description="[x, y, w, h] bounding box")


# ----- /analyze 응답 -----
class OrganoIDResult(BaseModel):
    """OrganoID 분석 결과"""
    # 집계 지표
    organoid_count:   int   = Field(..., description="검출된 오가노이드 수")
    mean_area_px:     float = Field(..., description="평균 면적 (픽셀²)")
    size_cv:          float = Field(..., description="크기 변동계수 (%)")
    mean_circularity: float = Field(..., description="평균 원형도 (0~1)")
    viability_proxy:  float = Field(..., description="밝기 기반 생존율 추정 (%)")
    qc_score:         float = Field(..., description="종합 QC 점수 (0~100)")
    osi_pass:         bool  = Field(..., description="OSI 최소 기준 통과 여부")

    # 개별 오가노이드 목록 (Step 3)
    organoids: Optional[List[OrganoIDOrganoid]] = Field(
        None, description="개별 오가노이드 속성 목록"
    )

    # 이미지 메타 (Step 2)
    image_width:    int = 0
    image_height:   int = 0
    image_channels: int = 0
    saved_path:     Optional[str] = Field(None, description="서버 저장 경로")

    # 분석 모드
    analysis_mode: str = "stub"   # "stub" | "pixel" | "organoID"


class AnalyzeResponse(BaseModel):
    success:  bool
    result:   Optional[OrganoIDResult] = None
    error:    Optional[str]            = None
    filename: Optional[str]            = None
    version:  str = "bridge-v0.3"


# ----- /health 응답 -----
class HealthResponse(BaseModel):
    status:           str
    organoID_loaded:  bool
    organoID_dir_ok:  bool = False   # Step 3: OrganoID 레포 존재 여부
    version:          str
