import csv
import io
import json
import os
import re
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template
import pandas as pd

# 환경변수 로드 (.env)
load_dotenv()

app = Flask(__name__)

# 파일 업로드 용량 제한 설정 (기본값: 10MB)
max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", 10))
app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024

# 메모리에 업로드된 단일 데이터셋 보관 (서버 재시작 시 초기화됨)
CURRENT_DATASET = {}


def load_csv_from_bytes(file_bytes):
    """
    다양한 인코딩을 순차적으로 시도하고, 상위 라인을 검사하여
    실제 헤더(열 이름) 위치를 자동으로 감지하여 DataFrame으로 변환합니다.
    """
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]
    last_error = None

    for enc in encodings:
        try:
            text = file_bytes.decode(enc)
            lines = text.splitlines()

            # 상위 최대 15줄을 검사하여 가장 많은 유효 열을 가진 행을 헤더 위치로 결정
            max_cols = 0
            best_skip = 0
            for idx in range(min(15, len(lines))):
                line = lines[idx].strip()
                if not line:
                    continue
                row = list(csv.reader([line]))[0]
                if len(row) > max_cols:
                    max_cols = len(row)
                    best_skip = idx

            # pandas로 읽기
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, skiprows=best_skip)
            return df, enc, best_skip
        except Exception as e:
            last_error = e
            continue

    raise ValueError(f"지원하는 인코딩으로 파일을 읽지 못했습니다. 오류: {last_error}")


def diagnose_dataframe(df):
    """
    DataFrame의 품질을 정밀하게 진단합니다:
    결측치, 중복, Unnamed/빈 열, 연도별 충실도, 권장 기준연도, 집계 행 후보, 경고 목록 등
    """
    row_count = len(df)
    columns = [str(col).strip() for col in df.columns]
    df.columns = columns

    # 1. 열 분류
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    string_cols = [c for c in columns if c not in numeric_cols]
    year_cols = [col for col in columns if re.match(r"^(18|19|20)\d{2}$", col)]

    # 2. 결측치 및 비율 (열별)
    missing_by_column = {}
    for col in columns:
        cnt = int(df[col].isna().sum())
        pct = round((cnt / row_count) * 100, 2) if row_count > 0 else 0.0
        missing_by_column[col] = {"missing_count": cnt, "missing_percent": pct}

    # 3. 중복 행 수
    duplicate_rows_count = int(df.duplicated().sum())

    # 4. Unnamed 열 및 전체 빈 열
    unnamed_cols = [col for col in columns if col.startswith("Unnamed:") or col == ""]
    empty_cols = [col for col in columns if df[col].isna().all()]

    # 5. 연도별 데이터 충실도 및 권장 기준연도
    year_coverage = {}
    recommended_year = None
    if year_cols:
        sorted_years = sorted(year_cols)
        for y in sorted_years:
            valid_cnt = int(df[y].notna().sum())
            valid_pct = round((valid_cnt / row_count) * 100, 2) if row_count > 0 else 0.0
            year_coverage[y] = {
                "valid_count": valid_cnt,
                "valid_percent": valid_pct
            }

        # 최근 연도 중 유효 데이터 비율이 70% 이상인 연도를 우선 권장
        for y in reversed(sorted_years):
            if year_coverage[y]["valid_percent"] >= 70.0:
                recommended_year = y
                break

        # 70% 이상인 연도가 없다면 데이터가 가장 많은 연도를 권장
        if not recommended_year:
            recommended_year = max(sorted_years, key=lambda y: df[y].notna().sum())

    # 6. 집계 행(Aggregates) 후보 탐지 (예: World, OECD, Region, Income 그룹 등)
    agg_keywords = [
        "world", "oecd", "euro area", "european union", "income",
        "area", "total", "ida & ibrd", "latin america", "east asia",
        "sub-saharan", "middle east", "north america", "caribbean"
    ]
    aggregate_candidates = []
    first_str_col = string_cols[0] if string_cols else None
    if first_str_col:
        for idx, val in df[first_str_col].dropna().items():
            val_lower = str(val).lower()
            if any(k in val_lower for k in agg_keywords):
                aggregate_candidates.append({
                    "row_index": int(idx),
                    "name": str(val)
                })

    # 7. 경고 목록 생성
    warnings = []
    if unnamed_cols:
        warnings.append(f"이름 없는 열 또는 불필요한 열이 감지되었습니다: {', '.join(unnamed_cols)}")
    if empty_cols:
        warnings.append(f"데이터가 완전히 비어있는 열이 {len(empty_cols)}개 있습니다.")
    if duplicate_rows_count > 0:
        warnings.append(f"완전히 중복된 행이 {duplicate_rows_count}개 있습니다.")
    if aggregate_candidates:
        warnings.append(
            f"지역 또는 소득 그룹 등 집계용 요약 행이 {len(aggregate_candidates)}개 감지되었습니다. "
            f"개별 국가 분석 시 왜곡을 피하기 위해 필터링을 권장합니다."
        )

    # 8. 데이터 미리보기 (상위 10행, 브라우저 JSON.parse 규격 준수를 위해 NaN -> null 변환)
    preview_rows = []
    for row in df.head(10).to_dict(orient="records"):
        cleaned_row = {k: (None if pd.isna(v) else v) for k, v in row.items()}
        preview_rows.append(cleaned_row)

    return {
        "columns": columns,
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "numeric_columns": numeric_cols,
        "string_columns": string_cols,
        "year_columns": year_cols,
        "missing_by_column": missing_by_column,
        "duplicate_rows_count": duplicate_rows_count,
        "unnamed_columns": unnamed_cols,
        "empty_columns": empty_cols,
        "year_coverage": year_coverage,
        "recommended_year": recommended_year,
        "aggregate_candidates": aggregate_candidates,
        "aggregate_candidates_count": len(aggregate_candidates),
        "warnings": warnings,
        "preview_rows": preview_rows
    }


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "message": "Data Insight Builder server is running",
        "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    }), 200


@app.route("/inspect", methods=["POST"])
def inspect_file():
    print("\n[Backend] POST /inspect 요청 수신")

    if "file" not in request.files:
        print("[Backend Error] 업로드 요청에 'file' 키가 없습니다.")
        return jsonify({"error": "업로드된 파일이 없습니다 ('file' 필드 누락)"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".csv"):
        print(f"[Backend Error] 지원되지 않는 파일: {file.filename}")
        return jsonify({"error": "CSV 파일(.csv)만 업로드할 수 있습니다."}), 400

    try:
        file_bytes = file.read()
        file_size = len(file_bytes)
        print(f"[Backend] 파일명: {file.filename}, 크기: {file_size:,} bytes")

        # 인코딩 및 헤더 자동 감지 후 DataFrame 로드
        df, encoding, skipped_rows = load_csv_from_bytes(file_bytes)
        print(f"[Backend] 인코딩 성공: {encoding}, 건너뛴 헤더 행: {skipped_rows}줄, 크기: {df.shape}")

        # 정밀 품질 진단 수행
        diagnosis = diagnose_dataframe(df)

        # 메모리에 데이터셋 저장 (단일 세션)
        CURRENT_DATASET.clear()
        CURRENT_DATASET.update({
            "df": df,
            "filename": file.filename,
            "file_size": file_size,
            "encoding": encoding,
            "skipped_rows": skipped_rows,
            "diagnosis": diagnosis
        })

        # 최종 진단 응답 반환
        response_payload = {
            "status": "success",
            "filename": file.filename,
            "file_size_bytes": file_size,
            "encoding": encoding,
            "skipped_rows": skipped_rows,
            "row_count": len(df),
            "column_count": len(df.columns),
            **diagnosis
        }

        print(f"[Backend] 진단 완료: 경고 {len(diagnosis['warnings'])}건, 권장 기준연도: {diagnosis['recommended_year']}")
        return jsonify(response_payload), 200

    except Exception as e:
        print(f"[Backend Exception] inspect 실패: {e}")
        return jsonify({"error": f"CSV 파일 분석 중 오류가 발생했습니다: {str(e)}"}), 500


@app.route("/suggest", methods=["POST"])
def suggest_analyses():
    print("\n[Backend] POST /suggest 요청 수신")

    # 1. 진단 정보 확보 (요청 본문 또는 서버 메모리)
    diagnosis = None
    if request.is_json and request.get_json():
        diagnosis = request.get_json().get("diagnosis")
    if not diagnosis:
        diagnosis = CURRENT_DATASET.get("diagnosis")

    if not diagnosis:
        print("[Backend Error] 진단 정보 부재")
        return jsonify({"error": "먼저 CSV 파일을 업로드하여 진단(/inspect)을 완료해야 합니다."}), 400

    api_key = os.environ.get("GEMINI_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if not api_key:
        print("[Backend Error] GEMINI_API_KEY 미설정")
        return jsonify({"error": "GEMINI_API_KEY가 설정되지 않았습니다 (.env 확인 필요)."}), 500

    try:
        from google import genai
        from google.genai import types
        import tools

        # 절대 규칙: Gemini에게 원본 CSV 전체를 보내지 않고, 진단 요약 메타데이터만 전송
        df = CURRENT_DATASET.get("df")
        summary_info = {
            "filename": CURRENT_DATASET.get("filename", "uploaded.csv"),
            "row_count": len(df) if df is not None else 0,
            "columns": diagnosis.get("columns", [])[:15],  # 상위 주요 열
            "numeric_columns_count": len(diagnosis.get("numeric_columns", [])),
            "year_columns_range": f"{diagnosis.get('year_columns', ['?'])[0]} ~ {diagnosis.get('year_columns', ['?'])[-1]}" if diagnosis.get("year_columns") else "없음",
            "recommended_year": diagnosis.get("recommended_year"),
            "aggregate_candidates_count": diagnosis.get("aggregate_candidates_count", 0),
            "warnings": diagnosis.get("warnings", [])
        }

        catalog = tools.TOOL_CATALOG

        system_instruction = (
            "당신은 공공데이터 분석 전문 AI 조언자입니다. "
            "주어진 데이터셋 진단 요약 정보와 12개의 도구 카탈로그(T1~T12)를 바탕으로, "
            "이 데이터로 수행할 수 있는 가장 유의미하고 가치 있는 분석 3~4개를 골라 JSON 배열로 제안하세요.\n\n"
            "절대 규칙:\n"
            "1. 반드시 제공된 12개 도구 카탈로그(T1~T12)에 있는 도구만 골라야 합니다.\n"
            "2. 데이터에 없는 컬럼이나 존재하지 않는 도구는 절대 제안하지 마세요.\n"
            "3. 각 제안 항목은 tool_id, tool_name, title, reason, params 키를 가져야 합니다.\n"
            "4. params에는 해당 도구 실행에 필요한 인자(예: base_period, mode, n 등)를 정확히 명시하세요. "
            f"기준연도가 필요한 경우 가급적 권장 기준연도('{summary_info['recommended_year']}')를 우선 활용하세요."
        )

        user_prompt = f"""
[데이터셋 진단 요약]
{json.dumps(summary_info, ensure_ascii=False, indent=2)}

[사용 가능한 12개 도구 카탈로그]
{json.dumps(catalog, ensure_ascii=False, indent=2)}

위 데이터를 바탕으로 가장 가치 있는 분석 3~4개를 골라 JSON 배열 형식으로 반환하세요.
반환 규격:
[
  {{
    "tool_id": "T7",
    "tool_name": "top_bottom_n",
    "title": "2024년 인터넷 이용률 글로벌 상위 10개국 순위",
    "reason": "최신 권장 연도를 기준으로 전 세계 디지털 인프라 최상위 국가들을 파악합니다.",
    "params": {{
      "base_period": "{summary_info['recommended_year']}",
      "mode": "top",
      "n": 10
    }}
  }}
]
"""

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2
            )
        )

        suggestions = json.loads(resp.text)
        print(f"[Backend] Gemini ({model_name}) 분석 제안 생성 완료: {len(suggestions)}건")

        return jsonify({
            "status": "success",
            "model": model_name,
            "suggestions": suggestions
        }), 200

    except Exception as e:
        print(f"[Backend Exception] suggest 실패: {e}")
        return jsonify({"error": f"Gemini 분석 제안 생성 중 오류 발생: {str(e)}"}), 500


@app.route("/run", methods=["POST"])
def run_analysis_tool():
    print("\n[Backend] POST /run 요청 수신")

    df = CURRENT_DATASET.get("df")
    if df is None:
        print("[Backend Error] 업로드된 데이터셋이 없습니다.")
        return jsonify({"error": "분석을 실행할 데이터셋이 없습니다. 먼저 CSV를 업로드해주세요."}), 400

    data = request.get_json() or {}
    tool_name = data.get("tool_name") or data.get("tool_id")
    params = data.get("params") or {}

    if not tool_name:
        return jsonify({"error": "실행할 도구 이름(tool_name 또는 tool_id)을 지정해야 합니다."}), 400

    import tools

    tool_dispatch = {
        "T1": tools.reshape_wide_to_long,
        "reshape_wide_to_long": tools.reshape_wide_to_long,
        "T2": tools.quality_report,
        "quality_report": tools.quality_report,
        "T3": tools.year_coverage,
        "year_coverage": tools.year_coverage,
        "T4": tools.detect_aggregates,
        "detect_aggregates": tools.detect_aggregates,
        "T5": tools.describe_numeric,
        "describe_numeric": tools.describe_numeric,
        "T6": tools.trend_line,
        "trend_line": tools.trend_line,
        "T7": tools.top_bottom_n,
        "top_bottom_n": tools.top_bottom_n,
        "T8": tools.group_summary,
        "group_summary": tools.group_summary,
        "T9": tools.change_rate,
        "change_rate": tools.change_rate,
        "T10": tools.distribution,
        "distribution": tools.distribution,
        "T11": tools.correlation_scatter,
        "correlation_scatter": tools.correlation_scatter,
        "T12": tools.compare_one_vs_all,
        "compare_one_vs_all": tools.compare_one_vs_all
    }

    func = tool_dispatch.get(tool_name)
    if not func:
        return jsonify({"error": f"지원하지 않는 도구입니다: '{tool_name}' (T1~T12 중 선택 필요)"}), 400

    try:
        df_copy = df.copy()
        print(f"[Backend] 도구 실행 시작: {tool_name}, 파라미터: {params}")

        # 기준 시점(base_period) 자동 보정 안전장치
        if not params.get("base_period"):
            if params.get("year"):
                params["base_period"] = params.get("year")
            elif params.get("period"):
                params["base_period"] = params.get("period")
            else:
                rec_year = CURRENT_DATASET.get("diagnosis", {}).get("recommended_year")
                year_cols = tools.get_year_columns(df)
                if rec_year:
                    params["base_period"] = rec_year
                elif year_cols:
                    params["base_period"] = sorted(year_cols)[-1]

        # Pandas 계산 도구 실행
        calc_result = func(df_copy, **params)

        # 결과 메모리에 저장 (POST /explain 연동용)
        CURRENT_DATASET["last_run_result"] = calc_result

        print(f"[Backend] 도구 실행 성공: {tool_name}, 사용 행: {calc_result.get('used_rows_count')}, 제외 행: {calc_result.get('excluded_rows_count')}")

        return jsonify({
            "status": "success",
            "tool_name": tool_name,
            **calc_result
        }), 200

    except Exception as e:
        print(f"[Backend Exception] 도구 실행 실패: {e}")
        return jsonify({"error": f"도구 실행 중 오류가 발생했습니다: {str(e)}"}), 500


@app.route("/explain", methods=["POST"])
def explain_analysis_result():
    print("\n[Backend] POST /explain 요청 수신")

    data = request.get_json() or {}
    mode = str(data.get("mode", "B")).upper()  # 'A': 비교용(허술함), 'B': 정식(7개 헤더)
    calc_result = data.get("calc_result") or CURRENT_DATASET.get("last_run_result")

    if mode == "B" and not calc_result:
        print("[Backend Error] 해석할 계산 결과 부재")
        return jsonify({"error": "해석할 계산 결과가 없습니다. 먼저 도구(/run)를 실행해주세요."}), 400

    api_key = os.environ.get("GEMINI_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY가 설정되지 않았습니다 (.env 확인 필요)."}), 500

    try:
        from google import genai
        from google.genai import types

        # 모드별 프롬프트 분기 (규칙 준수)
        if mode == "A":
            # 모드 A (비교용, 의도적으로 허술하게): Pandas 계산 결과를 주지 않고 진단 요약만 전달
            mode_title = "모드 A (비교용, 의도적으로 허술한 프롬프트)"
            system_instruction = "당신은 AI 조언자입니다. 주어진 데이터 진단 정보만 보고 자유롭게 데이터 분석 보고서를 작성하세요."
            diagnosis = CURRENT_DATASET.get("diagnosis", {})
            prompt_content = f"""
파일명: {CURRENT_DATASET.get('filename')}
행 수: {len(CURRENT_DATASET.get('df', []))}
열 목록: {diagnosis.get('columns', [])[:10]}
이 데이터를 분석해서 전반적인 보고서를 한국어로 써줘.
"""
        else:
            # 모드 B (정식): 7개 필수 헤더 및 엄격한 규칙 적용
            mode_title = "모드 B (정식 보고서, 7개 헤더 준수)"
            system_instruction = (
                "당신은 공공데이터 분석 전문 리포터입니다. "
                "제공된 Pandas 계산 결과만을 바탕으로 아래 8가지 엄격한 규칙을 준수하여 보고서를 작성하세요.\n\n"
                "[절대 규칙]\n"
                "1. 제공된 계산 결과에 있는 숫자만 사용한다.\n"
                "2. 직접 계산하거나 추정하지 않는다.\n"
                "3. 데이터에 없는 국가·연도·열을 언급하지 않는다.\n"
                "4. 기준 시점과 제외된 행 수를 반드시 본문에 명시한다.\n"
                "5. 상관관계를 인과관계로 표현하지 않는다.\n"
                "6. 지표의 정의와 출처를 보고서 앞부분에 표기한다.\n"
                "7. 확인할 수 없는 것은 '이 데이터로는 확인할 수 없다'라고 쓴다.\n"
                "8. 중학생도 이해할 수 있게 쓰되 정확성을 희생하지 않는다.\n\n"
                "[반드시 준수할 출력 형식 (7개 헤더)]\n"
                "## 무엇을 봤는가\n"
                "## 데이터 출처와 정의\n"
                "## 기준 시점과 제외된 항목\n"
                "## 계산 결과\n"
                "## 읽어낼 수 있는 것\n"
                "## 이 데이터로는 알 수 없는 것\n"
                "## 다음에 확인해볼 것"
            )

            prompt_content = f"""
[분석 도구 정보]
- 도구명: {calc_result.get('tool_name')}
- 기준 시점: {calc_result.get('base_period')}
- 사용한 행 수: {calc_result.get('used_rows_count')}
- 제외한 행 수: {calc_result.get('excluded_rows_count')} (사유: {calc_result.get('exclusion_reason')})
- 단위: {calc_result.get('unit')}
- 주의사항: {calc_result.get('caveats')}

[Pandas 실제 계산 결과 수치]
{json.dumps(calc_result.get('result', {}), ensure_ascii=False, indent=2)}

위의 계산된 숫자만을 근거로 삼아, 정확히 7개의 필수 헤더를 사용하여 보고서를 작성해 주세요.
"""

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2
            )
        )

        explanation_text = resp.text.strip()
        print(f"[Backend] Gemini ({model_name}) 해석 작성 완료 (모드 {mode})")

        return jsonify({
            "status": "success",
            "mode": mode,
            "mode_title": mode_title,
            "model": model_name,
            "explanation": explanation_text,
            "base_period": calc_result.get("base_period") if calc_result else None,
            "used_rows_count": calc_result.get("used_rows_count") if calc_result else None,
            "excluded_rows_count": calc_result.get("excluded_rows_count") if calc_result else None
        }), 200

    except Exception as e:
        print(f"[Backend Exception] explain 실패: {e}")
        return jsonify({"error": f"Gemini 해석 생성 중 오류 발생: {str(e)}"}), 500


@app.route("/ask", methods=["POST"])
def ask_question_about_data():
    print("\n[Backend] POST /ask 후속 질문 수신")
    data = request.get_json() or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "질문 내용을 입력해주세요."}), 400

    api_key = os.environ.get("GEMINI_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY가 설정되지 않았습니다."}), 500

    try:
        from google import genai
        from google.genai import types

        df = CURRENT_DATASET.get("df")
        diagnosis = CURRENT_DATASET.get("diagnosis", {})
        last_calc = CURRENT_DATASET.get("last_run_result", {})

        system_instruction = (
            "당신은 중고등학생에게 데이터를 쉽고 재미있게 가르쳐주는 친절한 '데이터 과학 멘토'입니다.\n"
            "사용자가 데이터 분석 결과나 통계에 대해 질문하면, 아래 규칙에 맞춰 답변해 주세요:\n\n"
            "[답변 원칙]\n"
            "1. 난이도: 중고등학생(14~18세) 눈높이에 맞춰 일상 비유와 쉬운 예시를 들어 설명하세요.\n"
            "2. 근거 기반: 제공된 데이터 진단 정보와 최근 계산 결과를 바탕으로 팩트를 말하세요.\n"
            "3. 한계 인정: 표에 없는 내용(예: 특정 국가의 구체적 법률이나 정치 상황)은 '이 표에는 나와있지 않지만~'이라고 명확히 구분하세요.\n"
            "4. 친절하고 격려하는 말투(~해요, ~답니다)를 사용하세요."
        )

        context_info = {
            "파일명": CURRENT_DATASET.get("filename"),
            "전체행수": len(df) if df is not None else 0,
            "권장연도": diagnosis.get("recommended_year"),
            "최근_실행_도구": last_calc.get("tool_name"),
            "기준시점": last_calc.get("base_period"),
            "사용한행수": last_calc.get("used_rows_count"),
            "제외행수": last_calc.get("excluded_rows_count"),
            "제외사유": last_calc.get("exclusion_reason"),
            "최근_계산_결과": last_calc.get("result", {})
        }

        user_prompt = f"""
[현재 보고 있는 데이터 및 계산 결과]
{json.dumps(context_info, ensure_ascii=False, indent=2)}

[학생의 질문]
"{question}"

위 데이터를 참고하여 학생이 단번에 이해할 수 있게 친절하고 명쾌하게 답변해 주세요!
"""

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3
            )
        )

        answer = resp.text.strip()
        print(f"[Backend] POST /ask 답변 완료 (길이: {len(answer)}자)")

        return jsonify({
            "status": "success",
            "question": question,
            "answer": answer
        }), 200

    except Exception as e:
        print(f"[Backend Exception] ask 실패: {e}")
        return jsonify({"error": f"질문 답변 중 오류가 발생했습니다: {str(e)}"}), 500


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="127.0.0.1", port=5000, debug=debug)
