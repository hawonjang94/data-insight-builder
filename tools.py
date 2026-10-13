import glob
import os
import re
import pandas as pd


def get_year_columns(df):
    """DataFrame에서 4자리 연도(1800~2099) 형태의 컬럼 목록을 반환합니다."""
    return [str(col).strip() for col in df.columns if re.match(r"^(18|19|20)\d{2}$", str(col).strip())]


def find_entity_column(df):
    """국가명, 항목명 등 분석 대상의 기준이 되는 대표 문자열 컬럼을 찾습니다."""
    for col in df.columns:
        if str(col).strip().lower() in ["country name", "country", "name", "entity", "nation"]:
            return col
    for col in df.columns:
        if df[col].dtype == "object" or "str" in str(df[col].dtype).lower():
            return col
    return df.columns[0] if len(df.columns) > 0 else None


COUNTRY_ALIASES = {
    "대한민국": "Korea, Rep.",
    "한국": "Korea, Rep.",
    "남한": "Korea, Rep.",
    "korea": "Korea, Rep.",
    "south korea": "Korea, Rep.",
    "kor": "Korea, Rep.",
    "북한": "Korea, Dem. People's Rep.",
    "north korea": "Korea, Dem. People's Rep.",
    "미국": "United States",
    "usa": "United States",
    "일본": "Japan",
    "중국": "China",
    "독일": "Germany",
    "영국": "United Kingdom",
    "프랑스": "France",
    "러시아": "Russian Federation",
    "사우디": "Saudi Arabia",
    "사우디아라비아": "Saudi Arabia",
    "아랍에미리트": "United Arab Emirates",
    "uae": "United Arab Emirates",
    "바레인": "Bahrain",
    "쿠웨이트": "Kuwait",
    "카타르": "Qatar",
    "덴마크": "Denmark",
    "노르웨이": "Norway",
    "스웨덴": "Sweden",
    "핀란드": "Finland",
    "스위스": "Switzerland",
    "싱가포르": "Singapore",
    "호주": "Australia",
    "캐나다": "Canada"
}


def resolve_entity_name(df, name_query, entity_col=None):
    """
    한글 국가명('대한민국', '한국', '미국' 등)이나 약어를 영문 공식 World Bank 국가명으로 자동 변환합니다.
    """
    if not name_query:
        return name_query

    if entity_col is None:
        entity_col = find_entity_column(df)
    if not entity_col or entity_col not in df.columns:
        return name_query

    q = str(name_query).strip()
    q_lower = q.lower()

    # 1. Alias 사전 매핑
    if q_lower in COUNTRY_ALIASES:
        target = COUNTRY_ALIASES[q_lower]
        if target in df[entity_col].values:
            return target

    # 2. 정확 일치 (대소문자 무시)
    for val in df[entity_col].dropna().unique():
        if str(val).strip().lower() == q_lower:
            return val

    # 3. 부분 일치 검색
    for val in df[entity_col].dropna().unique():
        val_str = str(val).strip().lower()
        if q_lower in val_str or val_str in q_lower:
            return val

    return name_query


def filter_pure_entities(df, exclude_aggregates=True, entity_col=None):
    """
    집계 요약 행(World, OECD, Region, IncomeGroup 등)을 제외하고
    순수 개별 국가/항목 데이터만 필터링합니다.
    """
    if entity_col is None:
        entity_col = find_entity_column(df)

    if not exclude_aggregates or not entity_col or entity_col not in df.columns:
        return df.copy(), 0, []

    agg_keywords = [
        "world", "oecd", "euro area", "european union", "income",
        "area", "total", "ida & ibrd", "latin america", "east asia",
        "sub-saharan", "middle east", "north america", "caribbean", "arab world"
    ]

    is_agg = df[entity_col].astype(str).str.lower().apply(
        lambda val: any(k in val for k in agg_keywords)
    )

    pure_df = df[~is_agg].copy()
    excluded_count = int(is_agg.sum())
    excluded_names = df.loc[is_agg, entity_col].tolist()

    return pure_df, excluded_count, excluded_names


# ==========================================================
# [도구 1 ~ 4] 기본 구조화 및 품질 탐지
# ==========================================================

def reshape_wide_to_long(df, id_vars=None, value_name="value"):
    """
    [T1] 연도 열들을 행으로 접어 세로형(Long Format) 데이터로 재구조화합니다.
    """
    year_cols = get_year_columns(df)
    total_rows = len(df)

    if not year_cols:
        return {
            "tool_name": "reshape_wide_to_long",
            "base_period": None,
            "used_rows_count": total_rows,
            "excluded_rows_count": 0,
            "exclusion_reason": "감지된 연도 열이 없습니다.",
            "used_columns": list(df.columns),
            "unit": "행(row)",
            "caveats": ["연도 열이 존재하지 않아 원본 형태를 유지합니다."],
            "result": {"status": "skipped", "message": "연도 열이 없습니다."},
            "chart_data": None
        }

    if id_vars is None:
        id_vars = [col for col in df.columns if col not in year_cols]

    melted_df = pd.melt(
        df,
        id_vars=id_vars,
        value_vars=year_cols,
        var_name="year",
        value_name=value_name
    )

    valid_melted = melted_df.dropna(subset=[value_name])
    preview = valid_melted.head(10).where(pd.notna(valid_melted.head(10)), None).to_dict(orient="records")

    return {
        "tool_name": "reshape_wide_to_long",
        "base_period": f"{sorted(year_cols)[0]}~{sorted(year_cols)[-1]}",
        "used_rows_count": total_rows,
        "excluded_rows_count": 0,
        "exclusion_reason": "전체 엔티티 행을 대상으로 연도 축 변환 수행",
        "used_columns": id_vars + ["year", value_name],
        "unit": "행(row)",
        "caveats": ["가로로 긴 연도 데이터를 시계열 분석 및 차트 시각화가 용이한 세로형으로 변환했습니다."],
        "result": {
            "original_shape": [total_rows, len(df.columns)],
            "melted_total_rows": len(melted_df),
            "valid_data_rows": len(valid_melted),
            "preview": preview
        },
        "chart_data": None
    }


def quality_report(df):
    """
    [T2] 결측치, 중복, 열 데이터 타입, Unnamed 열 등 종합 데이터 품질을 진단합니다.
    """
    total_rows = len(df)
    total_cols = len(df.columns)
    columns = [str(c).strip() for c in df.columns]

    missing_info = []
    for col in columns:
        cnt = int(df[col].isna().sum())
        pct = round((cnt / total_rows) * 100, 2) if total_rows > 0 else 0.0
        missing_info.append({
            "column": col,
            "missing_count": cnt,
            "missing_percent": pct,
            "dtype": str(df[col].dtype)
        })

    missing_info.sort(key=lambda x: x["missing_percent"], reverse=True)

    dup_count = int(df.duplicated().sum())
    unnamed_cols = [c for c in columns if c.startswith("Unnamed:") or c == ""]
    empty_cols = [c for c in columns if df[c].isna().all()]

    return {
        "tool_name": "quality_report",
        "base_period": "전체 데이터",
        "used_rows_count": total_rows,
        "excluded_rows_count": 0,
        "exclusion_reason": "품질 진단은 데이터셋 전체 행을 대상으로 수행",
        "used_columns": columns,
        "unit": "건수 / %",
        "caveats": [
            f"중복 행: {dup_count}건",
            f"이름 없는 열: {len(unnamed_cols)}개",
            f"완전 결측 열: {len(empty_cols)}개"
        ],
        "result": {
            "total_rows": total_rows,
            "total_columns": total_cols,
            "duplicate_rows": dup_count,
            "unnamed_columns": unnamed_cols,
            "empty_columns": empty_cols,
            "top_missing_columns": missing_info[:10]
        },
        "chart_data": None
    }


def year_coverage(df):
    """
    [T3] 연도별 유효 데이터 개수 및 비율을 계산하고, 분석에 최적인 권장 기준연도를 제안합니다.
    """
    year_cols = sorted(get_year_columns(df))
    total_rows = len(df)

    if not year_cols:
        return {
            "tool_name": "year_coverage",
            "base_period": None,
            "used_rows_count": total_rows,
            "excluded_rows_count": 0,
            "exclusion_reason": "연도 열이 없습니다.",
            "used_columns": [],
            "unit": "개국(항목)",
            "caveats": ["분석 가능한 연도 열이 감지되지 않았습니다."],
            "result": {},
            "chart_data": None
        }

    coverage_data = []
    labels = []
    counts = []
    recommended_year = None

    for y in year_cols:
        cnt = int(df[y].notna().sum())
        pct = round((cnt / total_rows) * 100, 2) if total_rows > 0 else 0.0
        coverage_data.append({"year": y, "valid_count": cnt, "valid_percent": pct})
        labels.append(y)
        counts.append(cnt)

    for row in reversed(coverage_data):
        if row["valid_percent"] >= 70.0:
            recommended_year = row["year"]
            break

    if not recommended_year:
        recommended_year = max(coverage_data, key=lambda x: x["valid_count"])["year"]

    return {
        "tool_name": "year_coverage",
        "base_period": f"{year_cols[0]}~{year_cols[-1]}",
        "used_rows_count": total_rows,
        "excluded_rows_count": 0,
        "exclusion_reason": "전체 연도 열에 대한 데이터 충실도를 검사",
        "used_columns": year_cols,
        "unit": "유효 데이터 개수(개)",
        "caveats": [
            f"권장 기준연도는 데이터가 가장 충실한 최근 연도인 {recommended_year}년입니다.",
            "초기 연도는 수집된 데이터가 적을 수 있으므로 시계열 비교 시 주의가 필요합니다."
        ],
        "result": {
            "recommended_year": recommended_year,
            "year_count": len(year_cols),
            "coverage_list": coverage_data
        },
        "chart_data": {
            "type": "bar",
            "labels": labels,
            "datasets": [
                {
                    "label": "유효 데이터 수",
                    "data": counts,
                    "backgroundColor": "rgba(54, 162, 235, 0.6)"
                }
            ]
        }
    }


def detect_aggregates(df, entity_col=None):
    """
    [T4] 국가/개별 항목이 아닌 지역, 소득군, 세계 전체 등 집계 행(Aggregates)을 탐지합니다.
    """
    total_rows = len(df)
    if entity_col is None or entity_col not in df.columns:
        entity_col = find_entity_column(df)

    agg_keywords = [
        "world", "oecd", "euro area", "european union", "income",
        "area", "total", "ida & ibrd", "latin america", "east asia",
        "sub-saharan", "middle east", "north america", "caribbean", "arab world"
    ]

    agg_indices = []
    agg_names = []
    pure_indices = []

    for idx, val in df[entity_col].dropna().items():
        val_str = str(val).lower()
        if any(k in val_str for k in agg_keywords):
            agg_indices.append(int(idx))
            agg_names.append(str(val))
        else:
            pure_indices.append(int(idx))

    return {
        "tool_name": "detect_aggregates",
        "base_period": "전체 기준",
        "used_rows_count": len(pure_indices),
        "excluded_rows_count": len(agg_indices),
        "exclusion_reason": "World, 소득 계층, 대륙/지역 등 집계 요약 행",
        "used_columns": [entity_col],
        "unit": "개국(행)",
        "caveats": [
            f"개별 국가 순위나 평균을 낼 때는 감지된 {len(agg_indices)}개의 집계 행을 제외해야 왜곡이 없습니다."
        ],
        "result": {
            "entity_column": entity_col,
            "total_rows": total_rows,
            "pure_entities_count": len(pure_indices),
            "aggregate_count": len(agg_indices),
            "aggregate_names": agg_names
        },
        "chart_data": None
    }


# ==========================================================
# [도구 5 ~ 8] 기초통계, 추이, 순위, 그룹 요약
# ==========================================================

def describe_numeric(df, column=None, base_period=None, exclude_aggregates=True):
    """
    [T5] 특정 열 또는 기준연도 데이터의 기초통계(개수, 평균, 중앙값, 최솟값, 최댓값, 표준편차)를 산출합니다.
    """
    target_col = str(base_period).strip() if base_period else column
    if not target_col or target_col not in df.columns:
        year_cols = get_year_columns(df)
        target_col = year_cols[-1] if year_cols else df.select_dtypes(include=["number"]).columns[0]

    pure_df, agg_excluded_cnt, _ = filter_pure_entities(df, exclude_aggregates=exclude_aggregates)
    series = pd.to_numeric(pure_df[target_col], errors="coerce").dropna()
    used_rows = len(series)
    missing_excluded_cnt = len(pure_df) - used_rows
    total_excluded = agg_excluded_cnt + missing_excluded_cnt

    stats = {
        "count": used_rows,
        "mean": round(float(series.mean()), 2) if used_rows > 0 else None,
        "median": round(float(series.median()), 2) if used_rows > 0 else None,
        "min": round(float(series.min()), 2) if used_rows > 0 else None,
        "max": round(float(series.max()), 2) if used_rows > 0 else None,
        "std": round(float(series.std()), 2) if used_rows > 1 else None,
    }

    return {
        "tool_name": "describe_numeric",
        "base_period": target_col,
        "used_rows_count": used_rows,
        "excluded_rows_count": total_excluded,
        "exclusion_reason": f"집계 행 {agg_excluded_cnt}개, 결측치 {missing_excluded_cnt}개 제외",
        "used_columns": [target_col],
        "unit": "수치(%)",
        "caveats": [f"기준 시점 {target_col}에 대한 순수 국가 기초 통계입니다."],
        "result": stats,
        "chart_data": {
            "type": "bar",
            "labels": ["최솟값", "중앙값", "평균", "최댓값"],
            "datasets": [
                {
                    "label": f"{target_col} 요약 통계",
                    "data": [stats["min"], stats["median"], stats["mean"], stats["max"]],
                    "backgroundColor": [
                        "rgba(255, 99, 132, 0.6)",
                        "rgba(54, 162, 235, 0.6)",
                        "rgba(255, 206, 86, 0.6)",
                        "rgba(75, 192, 192, 0.6)"
                    ]
                }
            ]
        }
    }


def trend_line(df, entities=None, start_year=None, end_year=None, entity_col=None):
    """
    [T6] 선택된 주요 국가들의 연도별 시계열 변화 추이를 선 차트(Line Chart) 데이터로 추출합니다.
    """
    if entity_col is None:
        entity_col = find_entity_column(df)

    year_cols = sorted(get_year_columns(df))
    if not year_cols:
        raise ValueError("시계열 추이를 분석할 연도 열이 없습니다.")

    if start_year and str(start_year) in year_cols:
        year_cols = [y for y in year_cols if y >= str(start_year)]
    if end_year and str(end_year) in year_cols:
        year_cols = [y for y in year_cols if y <= str(end_year)]

    available_entities = df[entity_col].dropna().tolist()
    if not entities:
        default_candidates = ["Korea, Rep.", "United States", "Japan", "Germany", "China"]
        entities = [c for c in default_candidates if c in available_entities] or available_entities[:3]
    elif isinstance(entities, str):
        entities = [entities]

    datasets = []
    used_entities = []
    palette = [
        "rgba(54, 162, 235, 1)",
        "rgba(255, 99, 132, 1)",
        "rgba(75, 192, 192, 1)",
        "rgba(255, 159, 64, 1)",
        "rgba(153, 102, 255, 1)",
        "rgba(245, 158, 11, 1)",
        "rgba(16, 185, 129, 1)"
    ]

    korea_keywords = ["korea, rep.", "korea", "대한민국", "한국", "남한"]

    for idx, ent in enumerate(entities):
        resolved_name = resolve_entity_name(df, ent, entity_col)
        row = df[df[entity_col] == resolved_name]
        if row.empty:
            row = df[df[entity_col].astype(str).str.lower() == str(resolved_name).lower()]
        if row.empty:
            continue

        real_name = row[entity_col].values[0]
        used_entities.append(real_name)
        values = [
            round(float(val), 2) if pd.notna(val) else None
            for val in row[year_cols].values[0]
        ]

        is_korea = any(k in str(real_name).lower() for k in korea_keywords) or any(k in str(ent).lower() for k in korea_keywords)

        display_label = real_name
        if is_korea and "대한민국" not in real_name:
            display_label = f"{real_name} (대한민국)"

        # 대한민국은 강조 빨간색(두꺼운 선), 다른 모든 나라는 통일된 단일 슬레이트 그레이(기본 선)
        if is_korea:
            color = "rgba(239, 68, 68, 1)"  # 대한민국: 눈에 띄는 빨강
            bg_color = "rgba(239, 68, 68, 0.15)"
            line_width = 3.5
            point_r = 4.5
        else:
            color = "rgba(148, 163, 184, 0.85)"  # 다른 모든 나라: 통일된 단일 회색
            bg_color = "rgba(148, 163, 184, 0.05)"
            line_width = 1.8
            point_r = 2.5

        datasets.append({
            "label": display_label,
            "data": values,
            "borderColor": color,
            "backgroundColor": bg_color,
            "borderWidth": line_width,
            "pointRadius": point_r,
            "pointHoverRadius": point_r + 2,
            "fill": False,
            "tension": 0.15
        })

    return {
        "tool_name": "trend_line",
        "base_period": f"{year_cols[0]}~{year_cols[-1]}",
        "used_rows_count": len(used_entities),
        "excluded_rows_count": len(df) - len(used_entities),
        "exclusion_reason": f"선택된 분석 대상 {len(used_entities)}개국 외 행 제외",
        "used_columns": [entity_col] + year_cols,
        "unit": "연도별 수치(%)",
        "caveats": [f"{len(used_entities)}개 국가의 {year_cols[0]}년~{year_cols[-1]}년 시계열 추이 분석입니다."],
        "result": {"entities": used_entities, "years": year_cols},
        "chart_data": {"type": "line", "labels": year_cols, "datasets": datasets}
    }


def top_bottom_n(df, base_period=None, n=10, mode="top", exclude_aggregates=True, entity_col=None):
    """
    [T7] 기준연도를 받아, 해당 시점의 상위 또는 하위 N개 국가 순위를 산출합니다.
    (기준 시점이 생략된 경우 데이터의 최신 연도를 자동으로 사용합니다)
    """
    if not base_period:
        year_cols = get_year_columns(df)
        if year_cols:
            base_period = sorted(year_cols)[-1]
        else:
            raise ValueError("도구 T7(top_bottom_n)을 실행할 수 있는 연도 열이 데이터에 없습니다.")

    target_col = str(base_period).strip()
    if target_col not in df.columns:
        raise ValueError(f"지정한 기준 시점({target_col})이 데이터의 열에 존재하지 않습니다.")

    if entity_col is None:
        entity_col = find_entity_column(df)

    pure_df, agg_excluded_cnt, _ = filter_pure_entities(df, exclude_aggregates=exclude_aggregates, entity_col=entity_col)
    valid_df = pure_df[[entity_col, target_col]].dropna(subset=[target_col]).copy()
    valid_df[target_col] = pd.to_numeric(valid_df[target_col], errors="coerce")
    valid_df = valid_df.dropna(subset=[target_col])

    missing_excluded_cnt = len(pure_df) - len(valid_df)
    total_excluded = agg_excluded_cnt + missing_excluded_cnt

    is_ascending = (mode.lower() == "bottom")
    sorted_df = valid_df.sort_values(by=target_col, ascending=is_ascending).head(n)

    labels = sorted_df[entity_col].tolist()
    values = [round(float(v), 2) for v in sorted_df[target_col].tolist()]
    rank_list = [{"rank": i + 1, "name": labels[i], "value": values[i]} for i in range(len(labels))]

    # 대한민국 여부에 따른 차별화 배색: 대한민국은 빨간색, 다른 모든 나라는 통일된 블루
    korea_keywords = ["korea, rep.", "korea", "대한민국", "한국", "남한"]
    bg_colors = []
    border_colors = []
    for lbl in labels:
        if any(k in str(lbl).lower() for k in korea_keywords):
            bg_colors.append("rgba(239, 68, 68, 0.85)")
            border_colors.append("rgba(239, 68, 68, 1)")
        else:
            default_bg = "rgba(59, 130, 246, 0.65)" if mode.lower() == "top" else "rgba(148, 163, 184, 0.65)"
            default_border = "rgba(59, 130, 246, 0.95)" if mode.lower() == "top" else "rgba(148, 163, 184, 0.95)"
            bg_colors.append(default_bg)
            border_colors.append(default_border)

    return {
        "tool_name": "top_bottom_n",
        "base_period": target_col,
        "used_rows_count": len(sorted_df),
        "excluded_rows_count": total_excluded,
        "exclusion_reason": f"집계 행 {agg_excluded_cnt}개 및 상위/하위 {n}위 외 행 제외",
        "used_columns": [entity_col, target_col],
        "unit": "수치(%)",
        "caveats": [f"{target_col}년 기준 {'상위' if mode == 'top' else '하위'} {len(sorted_df)}개국 순위입니다."],
        "result": {"mode": mode, "ranking": rank_list},
        "chart_data": {
            "type": "bar",
            "labels": labels,
            "datasets": [{
                "label": f"{target_col}년 인터넷 이용률 (%)",
                "data": values,
                "backgroundColor": bg_colors,
                "borderColor": border_colors,
                "borderWidth": 1.2
            }]
        }
    }


def group_summary(df, group_col="IncomeGroup", base_period=None, agg_func="mean", entity_col=None):
    """
    [T8] 기준연도를 받아, 소득 그룹 또는 지역별 요약을 산출합니다.
    (기준 시점이 생략된 경우 데이터의 최신 연도를 자동으로 사용합니다)
    """
    if not base_period:
        year_cols = get_year_columns(df)
        base_period = sorted(year_cols)[-1] if year_cols else None

    if not base_period:
        raise ValueError("도구 T8(group_summary)은 분석할 연도 열이 데이터에 필요합니다.")

    target_col = str(base_period).strip()
    if target_col not in df.columns:
        raise ValueError(f"지정한 기준 시점({target_col})이 데이터 열에 존재하지 않습니다.")

    working_df = df.copy()
    if group_col not in working_df.columns:
        meta_files = glob.glob("data/Metadata_Country*.csv")
        if meta_files:
            meta_df = pd.read_csv(meta_files[0])
            if "Country Code" in working_df.columns and "Country Code" in meta_df.columns:
                working_df = pd.merge(working_df, meta_df[["Country Code", group_col]], on="Country Code", how="left")

    if group_col not in working_df.columns:
        raise ValueError(f"그룹 분석에 필요한 '{group_col}' 열을 찾을 수 없습니다.")

    valid_df = working_df[[group_col, target_col]].dropna().copy()
    valid_df[target_col] = pd.to_numeric(valid_df[target_col], errors="coerce")
    valid_df = valid_df.dropna()

    summary_series = valid_df.groupby(group_col)[target_col].agg(agg_func).round(2)
    labels = summary_series.index.tolist()
    values = [float(v) for v in summary_series.values]
    summary_records = [{"group": labels[i], "value": values[i]} for i in range(len(labels))]

    return {
        "tool_name": "group_summary",
        "base_period": target_col,
        "used_rows_count": len(valid_df),
        "excluded_rows_count": len(df) - len(valid_df),
        "exclusion_reason": f"그룹 정보 또는 {target_col}년 결측치 제외",
        "used_columns": [group_col, target_col],
        "unit": f"그룹별 {agg_func}(%)",
        "caveats": [f"{target_col}년 기준 {group_col}별 {agg_func} 비교 요약입니다."],
        "result": {"group_column": group_col, "agg_func": agg_func, "summary": summary_records},
        "chart_data": {
            "type": "bar",
            "labels": labels,
            "datasets": [{"label": f"{target_col}년 {group_col}별 {agg_func}", "data": values, "backgroundColor": "rgba(153, 102, 255, 0.6)"}]
        }
    }


# ==========================================================
# [도구 9 ~ 12] 변화율, 분포, 상관계수, 1대전체 비교
# ==========================================================

def change_rate(df, start_period, end_period, top_n=10, exclude_aggregates=True, entity_col=None):
    """
    [T9] 두 시점(start_period, end_period) 사이의 변화량(p.p) 및 변화율(%)을 계산하고 가장 많이 성장한 국가를 추출합니다.
    """
    if not start_period or not end_period:
        raise ValueError("도구 T9(change_rate)는 시작 시점(start_period)과 종료 시점(end_period)이 모두 필수입니다.")

    p1, p2 = str(start_period).strip(), str(end_period).strip()
    if p1 not in df.columns or p2 not in df.columns:
        raise ValueError(f"시점 열({p1} 또는 {p2})이 데이터에 존재하지 않습니다.")

    if entity_col is None:
        entity_col = find_entity_column(df)

    pure_df, agg_excluded_cnt, _ = filter_pure_entities(df, exclude_aggregates=exclude_aggregates, entity_col=entity_col)
    valid_df = pure_df[[entity_col, p1, p2]].dropna(subset=[p1, p2]).copy()
    valid_df[p1] = pd.to_numeric(valid_df[p1], errors="coerce")
    valid_df[p2] = pd.to_numeric(valid_df[p2], errors="coerce")
    valid_df = valid_df.dropna(subset=[p1, p2])

    valid_df["diff_abs"] = (valid_df[p2] - valid_df[p1]).round(2)
    # 0으로 나누기 방지
    valid_df["diff_pct"] = valid_df.apply(
        lambda r: round(((r[p2] - r[p1]) / r[p1]) * 100, 2) if r[p1] > 0 else 0.0, axis=1
    )

    sorted_df = valid_df.sort_values(by="diff_abs", ascending=False).head(top_n)
    labels = sorted_df[entity_col].tolist()
    values = sorted_df["diff_abs"].tolist()

    records = [
        {
            "name": r[entity_col],
            "start_val": round(float(r[p1]), 2),
            "end_val": round(float(r[p2]), 2),
            "change_points": round(float(r["diff_abs"]), 2),
            "change_percent": round(float(r["diff_pct"]), 2)
        }
        for _, r in sorted_df.iterrows()
    ]

    return {
        "tool_name": "change_rate",
        "base_period": f"{p1} vs {p2}",
        "used_rows_count": len(sorted_df),
        "excluded_rows_count": len(df) - len(sorted_df),
        "exclusion_reason": f"집계 행 {agg_excluded_cnt}개, 양 시점 결측치 제외 및 상위 {top_n}위 외 제외",
        "used_columns": [entity_col, p1, p2],
        "unit": "%p(포인트 증가량)",
        "caveats": [f"{p1}년부터 {p2}년까지 인터넷 보급률이 가장 크게 증가한 상위 {top_n}개국입니다."],
        "result": {"start_year": p1, "end_year": p2, "top_growth": records},
        "chart_data": {
            "type": "bar",
            "labels": labels,
            "datasets": [
                {
                    "label": f"{p1}~{p2} 증가량 (%p)",
                    "data": values,
                    "backgroundColor": "rgba(75, 192, 192, 0.6)"
                }
            ]
        }
    }


def distribution(df, base_period=None, bins=5, exclude_aggregates=True, entity_col=None):
    """
    [T10] 기준연도를 받아, 해당 시점의 데이터 구간별 빈도(히스토그램)를 계산합니다.
    (기준 시점이 생략된 경우 데이터의 최신 연도를 자동으로 사용합니다)
    """
    if not base_period:
        year_cols = get_year_columns(df)
        base_period = sorted(year_cols)[-1] if year_cols else None

    if not base_period:
        raise ValueError("도구 T10(distribution)은 분석할 연도 열이 데이터에 필요합니다.")

    target_col = str(base_period).strip()
    if target_col not in df.columns:
        raise ValueError(f"기준 시점 열({target_col})이 존재하지 않습니다.")

    pure_df, agg_excluded_cnt, _ = filter_pure_entities(df, exclude_aggregates=exclude_aggregates, entity_col=entity_col)
    series = pd.to_numeric(pure_df[target_col], errors="coerce").dropna()

    if len(series) == 0:
        raise ValueError(f"{target_col}년에 유효한 데이터가 없습니다.")

    # 0~100% 비율 지표의 경우 5구간(20%씩) 기본 분할
    cut_bins = [0, 20, 40, 60, 80, 100]
    bin_labels = ["0~20%", "20~40%", "40~60%", "60~80%", "80~100%"]
    binned = pd.cut(series, bins=cut_bins, labels=bin_labels, include_lowest=True)
    counts = binned.value_counts().sort_index()

    labels = counts.index.tolist()
    data_counts = [int(c) for c in counts.values]

    dist_records = [{"bin": labels[i], "count": data_counts[i]} for i in range(len(labels))]

    return {
        "tool_name": "distribution",
        "base_period": target_col,
        "used_rows_count": len(series),
        "excluded_rows_count": len(df) - len(series),
        "exclusion_reason": f"집계 행 {agg_excluded_cnt}개 및 결측치 제외",
        "used_columns": [target_col],
        "unit": "국가 수(개)",
        "caveats": [f"{target_col}년 인터넷 보급률의 5개 구간별 국가 수 분포입니다."],
        "result": {"distribution": dist_records},
        "chart_data": {
            "type": "bar",
            "labels": labels,
            "datasets": [
                {
                    "label": f"{target_col}년 구간별 국가 수",
                    "data": data_counts,
                    "backgroundColor": "rgba(255, 159, 64, 0.6)"
                }
            ]
        }
    }


def correlation_scatter(df, col_x, col_y, exclude_aggregates=True, entity_col=None):
    """
    [T11] 두 시점(연도) 또는 두 숫자 열 간의 피어슨 상관계수를 계산하고 산점도(Scatter) 데이터를 생성합니다.
    """
    if not col_x or not col_y:
        raise ValueError("도구 T11(correlation_scatter)은 col_x와 col_y 두 변수가 모두 필수입니다.")

    x_col, y_col = str(col_x).strip(), str(col_y).strip()
    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError(f"열({x_col} 또는 {y_col})이 데이터에 없습니다.")

    if entity_col is None:
        entity_col = find_entity_column(df)

    pure_df, agg_excluded_cnt, _ = filter_pure_entities(df, exclude_aggregates=exclude_aggregates, entity_col=entity_col)
    valid_df = pure_df[[entity_col, x_col, y_col]].dropna().copy()
    valid_df[x_col] = pd.to_numeric(valid_df[x_col], errors="coerce")
    valid_df[y_col] = pd.to_numeric(valid_df[y_col], errors="coerce")
    valid_df = valid_df.dropna()

    corr_val = round(float(valid_df[[x_col, y_col]].corr().iloc[0, 1]), 4)

    scatter_points = [
        {
            "x": round(float(r[x_col]), 2),
            "y": round(float(r[y_col]), 2),
            "entity": str(r[entity_col])
        }
        for _, r in valid_df.iterrows()
    ]

    return {
        "tool_name": "correlation_scatter",
        "base_period": f"{x_col} vs {y_col}",
        "used_rows_count": len(valid_df),
        "excluded_rows_count": len(df) - len(valid_df),
        "exclusion_reason": f"집계 행 {agg_excluded_cnt}개 및 양 변수 결측치 제외",
        "used_columns": [x_col, y_col],
        "unit": "상관계수 r (-1 ~ 1)",
        "caveats": [f"{x_col}과 {y_col}의 상관계수는 r = {corr_val}로 강한 선형 관계를 나타냅니다."],
        "result": {
            "correlation_r": corr_val,
            "sample_count": len(valid_df)
        },
        "chart_data": {
            "type": "scatter",
            "labels": [p["entity"] for p in scatter_points],
            "datasets": [
                {
                    "label": f"{x_col} vs {y_col} 산점도",
                    "data": scatter_points,
                    "backgroundColor": "rgba(54, 162, 235, 0.7)"
                }
            ]
        }
    }


def compare_one_vs_all(df, base_period=None, target_entity="Korea, Rep.", exclude_aggregates=True, entity_col=None):
    """
    [T12] 기준연도를 받아, 특정 국가의 수치와 전체 국가의 평균 및 중앙값을 비교하는 강조 차트를 생성합니다.
    (기준 시점이 생략된 경우 데이터의 최신 연도를 자동으로 사용합니다)
    """
    if not base_period:
        year_cols = get_year_columns(df)
        base_period = sorted(year_cols)[-1] if year_cols else None

    if not base_period:
        raise ValueError("도구 T12(compare_one_vs_all)은 분석할 연도 열이 데이터에 필요합니다.")

    target_col = str(base_period).strip()
    if target_col not in df.columns:
        raise ValueError(f"기준 시점 열({target_col})이 존재하지 않습니다.")

    if entity_col is None:
        entity_col = find_entity_column(df)

    pure_df, agg_excluded_cnt, _ = filter_pure_entities(df, exclude_aggregates=exclude_aggregates, entity_col=entity_col)
    series = pd.to_numeric(pure_df[target_col], errors="coerce").dropna()

    mean_val = round(float(series.mean()), 2)
    median_val = round(float(series.median()), 2)

    resolved_target = resolve_entity_name(pure_df, target_entity, entity_col)
    target_row = pure_df[pure_df[entity_col].astype(str).str.lower() == str(resolved_target).lower()]
    if target_row.empty:
        target_row = pure_df[pure_df[entity_col].astype(str).str.contains(str(resolved_target), case=False, na=False)]

    if target_row.empty:
        raise ValueError(f"대상 항목 '{target_entity}'을(를) 데이터에서 찾을 수 없습니다.")

    target_real_name = target_row[entity_col].values[0]
    target_val = round(float(pd.to_numeric(target_row[target_col], errors="coerce").values[0]), 2)

    diff_from_mean = round(target_val - mean_val, 2)
    diff_from_median = round(target_val - median_val, 2)

    target_display = "Korea, Rep. (대한민국)" if target_real_name == "Korea, Rep." else target_real_name
    labels = [target_display, "전체 중앙값", "전체 평균"]
    values = [target_val, median_val, mean_val]

    return {
        "tool_name": "compare_one_vs_all",
        "base_period": target_col,
        "used_rows_count": len(series),
        "excluded_rows_count": len(df) - len(series),
        "exclusion_reason": f"집계 행 {agg_excluded_cnt}개 및 결측치 제외",
        "used_columns": [entity_col, target_col],
        "unit": "수치(%)",
        "caveats": [f"{target_real_name}의 {target_col}년 수치는 세계 평균 대비 {diff_from_mean:+}%p 수준입니다."],
        "result": {
            "entity_name": target_real_name,
            "entity_value": target_val,
            "overall_mean": mean_val,
            "overall_median": median_val,
            "diff_from_mean": diff_from_mean,
            "diff_from_median": diff_from_median
        },
        "chart_data": {
            "type": "bar",
            "labels": labels,
            "datasets": [
                {
                    "label": f"{target_col}년 비교 (%)",
                    "data": values,
                    "backgroundColor": [
                        "rgba(255, 99, 132, 0.8)",  # 강조 색상 (빨강)
                        "rgba(54, 162, 235, 0.6)",  # 중앙값 (파랑)
                        "rgba(255, 206, 86, 0.6)"   # 평균 (노랑)
                    ]
                }
            ]
        }
    }


# ==========================================================
# 도구 카탈로그 메타데이터 (Gemini 제안 및 UI 연동용)
# ==========================================================
TOOL_CATALOG = [
    {"id": "T1", "name": "reshape_wide_to_long", "title": "연도 열 행 변환", "description": "가로로 긴 연도 데이터를 세로형(Long format)으로 재구조화"},
    {"id": "T2", "name": "quality_report", "title": "데이터 품질 진단", "description": "결측치 순위, 중복, 불필요한 열 등 종합 품질 검사"},
    {"id": "T3", "name": "year_coverage", "title": "연도별 충실도 분석", "description": "연도별 유효 데이터 수 계산 및 최적의 권장 기준연도 판별"},
    {"id": "T4", "name": "detect_aggregates", "title": "집계/묶음 행 탐지", "description": "World, OECD 등 지역/소득군 요약 행 탐지 및 순수 국가 분리"},
    {"id": "T5", "name": "describe_numeric", "title": "기초 통계량 산출", "description": "특정 시점의 평균, 중앙값, 최솟값, 최댓값, 표준편차 계산"},
    {"id": "T6", "name": "trend_line", "title": "시계열 추이 선 차트", "description": "주요 국가들의 연도별 성장 곡선 및 시계열 변화 비교"},
    {"id": "T7", "name": "top_bottom_n", "title": "상위/하위 N 순위", "description": "기준연도 기준 상위 또는 하위 순위 산출 (막대 차트)"},
    {"id": "T8", "name": "group_summary", "title": "그룹별 요약 비교", "description": "소득 수준 또는 지역 그룹별 평균/합계 비교 (막대 차트)"},
    {"id": "T9", "name": "change_rate", "title": "두 시점 변화량 분석", "description": "두 연도 사이의 포인트 증가량(%p) 및 성장률 상위 국가 추출"},
    {"id": "T10", "name": "distribution", "title": "구간별 빈도 분포", "description": "기준연도 데이터의 5개 구간별 국가 수 히스토그램 생성"},
    {"id": "T11", "name": "correlation_scatter", "title": "상관계수 및 산점도", "description": "두 시점 또는 두 변수 간 피어슨 상관계수 r 및 산점도 시각화"},
    {"id": "T12", "name": "compare_one_vs_all", "title": "특정 국가 vs 전체 비교", "description": "대한민국 등 특정 국가의 수치와 전체 평균·중앙값 강조 비교"}
]
