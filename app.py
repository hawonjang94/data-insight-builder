import csv
import io
import json
import os
import re
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template, send_from_directory
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


APP_PIN = os.environ.get("APP_PIN", "0514")


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


@app.route("/manifest.json", methods=["GET"])
def manifest():
    """PWA 매니페스트 제공"""
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


@app.route("/service-worker.js", methods=["GET"])
def service_worker():
    """PWA 서비스 워커 제공 (루트 스코프 적용)"""
    resp = send_from_directory("static", "service-worker.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/favicon.ico", methods=["GET"])
def favicon():
    """파비콘 제공"""
    return send_from_directory("static/icons", "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/verify_pin", methods=["POST"])
def verify_pin():
    """앱 접속 4자리 PIN 인증 엔드포인트 (기본값: 0514)"""
    data = request.get_json(silent=True) or {}
    entered_pin = str(data.get("pin", "")).strip()
    if entered_pin == APP_PIN:
        print(f"[Auth] PIN 인증 성공 (입력: {entered_pin})")
        return jsonify({"status": "success", "message": "인증에 성공했습니다."}), 200
    else:
        print(f"[Auth Warning] PIN 인증 실패 (입력: {entered_pin})")
        return jsonify({"status": "error", "message": "비밀번호가 올바르지 않습니다."}), 401


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

        import inspect
        sig = inspect.signature(func)

        # 기준 시점(base_period) 파라미터가 필요한 도구에만 자동 보정 적용
        if "base_period" in sig.parameters and not params.get("base_period"):
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

        # 도구 함수 시그니처에 맞는 유효한 파라미터만 필터링하여 전달
        valid_params = {k: v for k, v in params.items() if k in sig.parameters}

        # Pandas 계산 도구 실행
        calc_result = func(df_copy, **valid_params)

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
            "당신은 공공 데이터와 통계 분석 결과를 엄밀하게 해석하고 전달하는 전문 '데이터 분석 연구원'입니다.\n"
            "사용자의 질문에 대해 아래 원칙을 엄격히 준수하여 답변하십시오:\n\n"
            "[답변 원칙 및 어조]\n"
            "1. 진지하고 신뢰감 있는 전문가 어조: 가볍거나 장난스러운 말투, 유아적인 비유, 불필요한 감탄사는 완전히 배제하고, 차분하고 논리적인 표준 격식체('~합니다', '~입니다', '~로 판단됩니다')를 일관되게 유지하십시오.\n"
            "2. **형광펜 강조(시각적 가독성)**: 검은 글씨만 길게 나열되면 가독성이 떨어지므로, 답변 중 **핵심 요약 단어, 중요한 통계 수치(비율, 순위, 증감폭 등), 핵심 결론 문장**은 반드시 `==형광펜 강조할 내용==` 기호로 감싸서 강조하십시오. (예: `==1위 아랍에미리트(100.0%)==`, `==데이터 포화 현상==`, `==직접적인 원인은 확정할 수 없습니다==` 등)\n"
            "3. 명확하고 군더더기 없는 해설: 전문 용어의 과도한 남발은 피하되, 청소년 및 일반 사용자도 인과관계와 데이터의 의미를 명확히 이해할 수 있도록 논리 정연하게 구조화하여 설명하십시오.\n"
            "4. 철저한 데이터 팩트 근거: 제공된 데이터셋 정보와 최근 계산 결과 수치(사용한 행, 제외된 행, 통계치 등)를 명확한 근거로 인용하여 답변하십시오.\n"
            "5. 데이터의 한계 및 과잉해석 경계: 주어진 표에 존재하지 않는 요인(예: 각국의 정치 체제, 법률 세부사항 등)을 단정 짓지 말고, '해당 데이터셋만으로는 확인할 수 없으며 추가 조사가 필요한 영역'임을 엄밀하게 구분하여 제시하십시오.\n"
            "6. 답변 구조: 핵심 요약, 데이터 분석에 따른 구체적 원인/해석, 데이터 분석 시 유의점(한계) 순으로 정돈하여 기술하십시오."
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

[질문]
"{question}"

위 데이터 및 계산 결과를 바탕으로, 객관적이고 논리적인 분석가로서 진지하고 품격 있는 어조로 답변을 작성하십시오.
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


@app.route("/query_visualize", methods=["POST"])
def query_visualize():
    """
    파일 업로드 전 또는 업로드 후 AI suggest 전에 자유롭게 질문하고 맞춤 시각화를 요청할 수 있는 엔드포인트입니다.
    - 데이터셋 업로드 여부와 상관없이 자유 질의 지원
    - 시각화 요구 시 Chart.js 호환 데이터 자동 생성
    - 데이터셋이 있고 12개 Pandas 도구와 일치 시 Pandas 직접 실행 후 실측 차트 연동
    """
    print("\n[Backend] POST /query_visualize 요청 수신")
    data = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "질문 내용을 입력해 주십시오."}), 400

    api_key = os.environ.get("GEMINI_API_KEY")
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY가 설정되지 않았습니다 (.env 확인 필요)."}), 500

    import tools
    df = CURRENT_DATASET.get("df")
    diagnosis = CURRENT_DATASET.get("diagnosis", {})
    has_dataset = df is not None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        system_instruction = (
            "당신은 공공 데이터와 거시 통계를 심층 분석하고 시각화 솔루션을 제공하는 전문 '수석 데이터 분석 연구원'입니다.\n"
            "사용자의 질의에 대해 엄밀하고 논리적인 표준 격식체('~합니다', '~입니다')로 답변하고, "
            "시각화가 필요한 경우 반드시 Chart.js 호환 JSON 구조를 생성하여 JSON 형식으로 응답하십시오.\n\n"
            "[응답 원칙 및 데이터 팩트 규격]\n"
            "1. 어조: 진지하고 차분하며 신뢰감 있는 전문가 어조를 유지하십시오. 불필요한 감탄사나 가벼운 표현은 배제하십시오.\n"
            "2. **국가명 매핑 규칙**: World Bank 데이터셋에서 대한민국의 공식 명칭은 'Korea, Rep.'입니다. 사용자가 '대한민국'이나 '한국'의 분석 또는 시각화를 요청하면, 도구 파라미터(entities 또는 target_country)에 반드시 'Korea, Rep.'을 지정하십시오. (미국: 'United States', 일본: 'Japan', 중국: 'China')\n"
            "3. **정확한 실제 통계 팩트 기반**:\n"
            "   - 2024년 인터넷 이용률(IT.NET.USER.ZS) 기준:\n"
            "     * 1~3위: 아랍에미리트(100.00%), 바레인(100.00%), 사우디아라비아(100.00%) - 이는 원천 World Bank 및 ITU 공식 통계에 등록된 실제 팩트입니다.\n"
            "     * 4위 덴마크(99.77%), 5위 쿠웨이트(99.75%), 10위 아이슬란드(98.21%).\n"
            "     * **대한민국(Korea, Rep.)은 97.90%로 글로벌 13위**입니다.\n"
            "   - 상위권 수치들이 100%에 근접해 보이는 현상은 인프라가 고도화된 국가들의 데이터 포화(Saturation) 현상 때문이며, 소수점 둘째 자리(100.00% vs 99.77% vs 97.90%)에서 유의미한 차이가 있음을 객관적으로 설명하십시오.\n"
            "   - 데이터셋 미업로드 시 일반 질의의 경우에도 임의의 100%를 남발하지 말고, 대한민국(97.9%), 미국(91.8%), 일본(82.9%), 세계 평균(약 67%) 등 공인된 현실 통계치를 정확히 반영하십시오.\n"
            "4. 데이터셋 유무에 따른 분기:\n"
            "   - 데이터셋이 제공된 경우: 사용자의 질의가 12개 Pandas 도구(T1~T12: top_bottom_n, trend_line, change_rate, distribution, quality_report, year_coverage, group_summary, correlation_scatter, compare_one_vs_all 등)로 해결 가능하면 'intent': 'run_tool'로 지정하고 해당 tool_name과 params를 출력하십시오.\n"
            "   - 데이터셋이 없거나 일반 통계 질문인 경우: 'intent': 'direct_answer'로 지정하고, 질문 주제에 부합하는 공인 통계 기반 chart_data를 생성하십시오.\n"
            "5. chart_data 규격 (시각화가 유의미한 경우 필수):\n"
            "   - type: 'bar' (가로 막대 차트) 또는 'line'\n"
            "   - indexAxis: 'y' (막대 차트의 경우 가로 막대로 표시하도록 지정)\n"
            "   - title: 차트의 명확한 한글 제목\n"
            "   - labels: 항목/국가 레이블 문자열 배열 (예: ['아랍에미리트', '바레인', '사우디아라비아', '덴마크', '쿠웨이트', '대한민국(13위)', '아이슬란드', '미국'] 등)\n"
            "   - datasets: [ { 'label': '지표명(단위)', 'data': [100.0, 100.0, 100.0, 99.77, 99.75, 97.90, 98.21, 91.80] } ]\n"
            "6. **형광펜 강조(시각적 가독성)**: 답변 중 핵심 요약 단어, 중요한 통계 수치, 핵심 결론 문장은 반드시 `==형광펜 강조할 내용==` 기호로 감싸서 강조하십시오.\n"
            "7. 답변(explanation): 팩트에 입각한 심층 해설과 데이터의 구조적 한계/주의사항을 체계적으로 서술하십시오."
        )

        context_payload = {
            "has_dataset": has_dataset,
            "filename": CURRENT_DATASET.get("filename") if has_dataset else None,
            "recommended_year": diagnosis.get("recommended_year") if has_dataset else None,
            "available_years": [col for col in df.columns if re.match(r"^(18|19|20)\d{2}$", col)] if has_dataset else None,
            "available_tools": [t["name"] for t in tools.TOOL_CATALOG] if has_dataset else None
        }

        user_prompt = f"""
[현재 환경 정보]
{json.dumps(context_payload, ensure_ascii=False, indent=2)}

[사용자 질의]
"{query}"

반환 JSON 스키마 규격:
{{
  "intent": "run_tool" | "direct_answer",
  "tool_name": "top_bottom_n",
  "params": {{ "base_period": "2024", "n": 10, "mode": "top" }},
  "explanation": "질문에 대한 진지하고 체계적인 분석 해설 (한국어 격식체)",
  "has_chart": true,
  "chart_data": {{
    "type": "bar",
    "title": "차트 제목",
    "labels": ["항목1", "항목2"],
    "datasets": [
      {{ "label": "지표명", "data": [10.5, 20.3] }}
    ]
  }}
}}
"""

        resp = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2
            )
        )

        res_json = json.loads(resp.text)
        intent = res_json.get("intent", "direct_answer")
        explanation = res_json.get("explanation", "")
        chart_data = res_json.get("chart_data")
        has_chart = res_json.get("has_chart", bool(chart_data))

        tool_result = None
        executed_tool_name = None

        # 데이터셋이 있고 도구 실행 intent인 경우 Pandas 도구 직접 실행
        if has_dataset and intent == "run_tool":
            tool_name = res_json.get("tool_name")
            params = res_json.get("params") or {}

            tool_dispatch = {
                "T1": tools.reshape_wide_to_long, "reshape_wide_to_long": tools.reshape_wide_to_long,
                "T2": tools.quality_report, "quality_report": tools.quality_report,
                "T3": tools.year_coverage, "year_coverage": tools.year_coverage,
                "T4": tools.detect_aggregates, "detect_aggregates": tools.detect_aggregates,
                "T5": tools.describe_numeric, "describe_numeric": tools.describe_numeric,
                "T6": tools.trend_line, "trend_line": tools.trend_line,
                "T7": tools.top_bottom_n, "top_bottom_n": tools.top_bottom_n,
                "T8": tools.group_summary, "group_summary": tools.group_summary,
                "T9": tools.change_rate, "change_rate": tools.change_rate,
                "T10": tools.distribution, "distribution": tools.distribution,
                "T11": tools.correlation_scatter, "correlation_scatter": tools.correlation_scatter,
                "T12": tools.compare_one_vs_all, "compare_one_vs_all": tools.compare_one_vs_all
            }
            func = tool_dispatch.get(tool_name)
            if func:
                import inspect
                sig = inspect.signature(func)

                # 사용자가 한국/대한민국에 대해 질문한 경우 차트에 무조건 한국이 포함되도록 파라미터 보정
                is_asking_korea = any(k in query.lower() for k in ["한국", "대한민국", "남한", "korea", "우리나라"])
                if is_asking_korea:
                    if "include_entity" in sig.parameters:
                        params["include_entity"] = "Korea, Rep."
                    if "entities" in sig.parameters:
                        ents = params.get("entities") or []
                        if isinstance(ents, str):
                            ents = [ents]
                        if "Korea, Rep." not in ents:
                            ents = ["Korea, Rep."] + [e for e in ents if e != "Korea, Rep."]
                        params["entities"] = ents
                    if "target_country" in sig.parameters:
                        params["target_country"] = "Korea, Rep."
                    if "target_entity" in sig.parameters:
                        params["target_entity"] = "Korea, Rep."

                # base_period 안전 보정 (해당 파라미터를 받는 함수에만 적용)
                if "base_period" in sig.parameters and not params.get("base_period") and not params.get("period"):
                    params["base_period"] = diagnosis.get("recommended_year", "2024")

                # 유효한 인자만 필터링하여 전달
                valid_params = {k: v for k, v in params.items() if k in sig.parameters}

                try:
                    df_copy = df.copy()
                    calc_result = func(df_copy, **valid_params)
                    CURRENT_DATASET["last_run_result"] = calc_result
                    tool_result = calc_result
                    executed_tool_name = tool_name
                    if calc_result.get("chart_data"):
                        chart_data = calc_result.get("chart_data")
                        has_chart = True
                    print(f"[Backend] NLP 질의 기반 도구 자동 실행 성공: {tool_name}")
                except Exception as run_err:
                    print(f"[Backend Warning] 도구 자동 실행 중 오류: {run_err}, 직행 모드로 대체")

        return jsonify({
            "status": "success",
            "has_dataset": has_dataset,
            "filename": CURRENT_DATASET.get("filename") if has_dataset else None,
            "intent": intent,
            "executed_tool_name": executed_tool_name,
            "explanation": explanation,
            "has_chart": has_chart,
            "chart_data": chart_data,
            "tool_result": tool_result
        }), 200

    except Exception as e:
        print(f"[Backend Exception] query_visualize 실패: {e}")
        return jsonify({"error": f"질의 및 시각화 처리 중 오류가 발생했습니다: {str(e)}"}), 500


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug)
