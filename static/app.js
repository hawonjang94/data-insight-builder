/**
 * AI Data Insight Builder - Frontend Logic (Vanilla JS)
 */

document.addEventListener("DOMContentLoaded", () => {
    console.log("[PAGE] 페이지 로드 완료");

    // 전역 상태
    let selectedFile = null;
    let currentDiagnosis = null;
    let lastRunResult = null;
    let chartInstance = null;

    // DOM 요소 캐싱
    const serverStatusBadge = document.getElementById("server-status");
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("csv-file-input");
    const fileSelectLabel = document.getElementById("file-select-label");
    const btnInspect = document.getElementById("btn-inspect");

    const inspectPanel = document.getElementById("inspect-result-panel");
    const metaFilename = document.getElementById("meta-filename");
    const metaEncoding = document.getElementById("meta-encoding");
    const metaShape = document.getElementById("meta-shape");
    const metaRecYear = document.getElementById("meta-rec-year");
    const warningsBox = document.getElementById("warnings-box");
    const warningsList = document.getElementById("warnings-list");
    const btnTogglePreview = document.getElementById("btn-toggle-preview");
    const previewTableWrapper = document.getElementById("preview-table-wrapper");
    const previewThead = document.getElementById("preview-thead");
    const previewTbody = document.getElementById("preview-tbody");

    // 2단계: 탭 및 직접 선택 컨트롤
    const suggestSection = document.getElementById("suggest-section");
    const tabCustomBtn = document.getElementById("tab-custom-btn");
    const tabAiBtn = document.getElementById("tab-ai-btn");
    const panelCustomControl = document.getElementById("panel-custom-control");
    const panelAiSuggestions = document.getElementById("panel-ai-suggestions");
    const selectTool = document.getElementById("select-tool");
    const selectBaseYear = document.getElementById("select-base-year");
    const selectSubOption = document.getElementById("select-sub-option");
    const labelSubOption = document.getElementById("label-sub-option");
    const groupBaseYear = document.getElementById("group-base-year");
    const groupSubOption = document.getElementById("group-sub-option");
    const btnCustomRun = document.getElementById("btn-custom-run");
    const btnGetSuggestions = document.getElementById("btn-get-suggestions");
    const suggestionsContainer = document.getElementById("suggestions-container");

    // 3단계: 결과 & 차트
    const resultSection = document.getElementById("result-section");
    const resultToolBadge = document.getElementById("result-tool-badge");
    const calcBasePeriod = document.getElementById("calc-base-period");
    const calcUsedRows = document.getElementById("calc-used-rows");
    const calcExcludedRows = document.getElementById("calc-excluded-rows");
    const calcUnit = document.getElementById("calc-unit");
    const calcExclusionReason = document.getElementById("calc-exclusion-reason");
    const calcTableContainer = document.getElementById("calc-table-container");

    // 4단계: 보고서 해석
    const explainSection = document.getElementById("explain-section");
    const btnExplain = document.getElementById("btn-explain");
    const explainOutputBox = document.getElementById("explain-output-box");
    const reportModeBadge = document.getElementById("report-mode-badge");
    const reportModelName = document.getElementById("report-model-name");
    const reportContent = document.getElementById("report-content");

    // ==========================================================
    // 1. 서버 헬스 체크
    // ==========================================================
    fetch("/health")
        .then(res => res.json())
        .then(data => {
            if (data.status === "ok") {
                serverStatusBadge.textContent = `Server: OK (${data.model})`;
                serverStatusBadge.className = "badge badge-success";
            }
        })
        .catch(err => {
            console.error("[ERROR] 서버 헬스 체크 실패:", err);
            serverStatusBadge.textContent = "Server: 연결 실패";
            serverStatusBadge.className = "badge";
            serverStatusBadge.style.backgroundColor = "#fee2e2";
            serverStatusBadge.style.color = "#991b1b";
        });

    // ==========================================================
    // 2. 파일 드래그 앤 드롭 및 선택
    // ==========================================================
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    function handleFileSelect(file) {
        if (!file.name.toLowerCase().endsWith(".csv")) {
            alert("CSV 파일(.csv)만 업로드할 수 있습니다.");
            console.error("[ERROR] 지원하지 않는 파일 확장자 선택:", file.name);
            return;
        }
        selectedFile = file;
        console.log(`[UPLOAD] 파일 선택: name=${file.name}, size=${file.size} bytes`);
        fileSelectLabel.textContent = `선택된 파일: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        btnInspect.disabled = false;
        btnInspect.textContent = "파일 진단 시작";
    }

    // ==========================================================
    // 3. 1단계: CSV 파일 진단 (/inspect)
    // ==========================================================
    btnInspect.addEventListener("click", async () => {
        if (!selectedFile) return;

        btnInspect.disabled = true;
        btnInspect.textContent = "분석 진단 중...";
        console.log("[INSPECT] 진단 요청 시작");

        const formData = new FormData();
        formData.append("file", selectedFile);

        try {
            const res = await fetch("/inspect", {
                method: "POST",
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || "파일 진단에 실패했습니다.");
            }

            const data = await res.json();
            currentDiagnosis = data;
            console.log(`[INSPECT] 진단 응답 수신: rows=${data.row_count}, columns=${data.column_count}, warnings=${data.warnings.length}`);

            // 진단 결과 UI 갱신
            metaFilename.textContent = data.filename;
            metaEncoding.textContent = `${data.encoding} (헤더 스킵: ${data.skipped_rows}줄)`;
            metaShape.textContent = `${data.row_count.toLocaleString()}행 × ${data.column_count}열`;
            metaRecYear.textContent = data.recommended_year ? `${data.recommended_year}년` : "연도 열 없음";

            // 자연어 질의 패널 상태 배지 갱신
            const nlBadge = document.getElementById("nl-dataset-status-badge");
            if (nlBadge) {
                nlBadge.className = "badge badge-success";
                nlBadge.textContent = `📊 원천 데이터셋 연동 모드: ${data.filename}`;
            }

            // 경고 목록 렌더링
            if (data.warnings && data.warnings.length > 0) {
                warningsList.innerHTML = data.warnings.map(w => `<li>${w}</li>`).join("");
                warningsBox.classList.remove("hidden");
            } else {
                warningsBox.classList.add("hidden");
            }

            // 10행 미리보기 테이블 렌더링
            renderPreviewTable(data.columns, data.preview_rows);

            inspectPanel.classList.remove("hidden");
            btnInspect.textContent = "진단 완료";

            // 2단계: 연도 드롭다운 메뉴 채우기
            populateYearDropdown(data.year_columns, data.recommended_year);

            // 2단계 섹션 표시
            suggestSection.classList.remove("hidden");

            // AI 추천도 백그라운드로 로드
            fetchSuggestions();

        } catch (err) {
            console.error("[ERROR] 진단 오류 발생:", err);
            alert(`진단 오류: ${err.message}`);
            btnInspect.disabled = false;
            btnInspect.textContent = "다시 시도";
        }
    });

    btnTogglePreview.addEventListener("click", () => {
        previewTableWrapper.classList.toggle("hidden");
    });

    function renderPreviewTable(columns, rows) {
        if (!columns || !rows || rows.length === 0) return;
        previewThead.innerHTML = `<tr>${columns.map(c => `<th>${c}</th>`).join("")}</tr>`;
        previewTbody.innerHTML = rows.map(r => {
            const cells = columns.map(c => `<td>${r[c] !== null && r[c] !== undefined ? r[c] : "<span style='color:#cbd5e1'>null</span>"}</td>`).join("");
            return `<tr>${cells}</tr>`;
        }).join("");
    }

    // ==========================================================
    // 4. 2단계: 직접 도구 & 연도 선택 제어 (사용자 맞춤형 컨트롤)
    // ==========================================================
    // 탭 전환
    tabCustomBtn.addEventListener("click", () => {
        tabCustomBtn.classList.add("active");
        tabAiBtn.classList.remove("active");
        panelCustomControl.classList.remove("hidden");
        panelAiSuggestions.classList.add("hidden");
    });

    tabAiBtn.addEventListener("click", () => {
        tabAiBtn.classList.add("active");
        tabCustomBtn.classList.remove("active");
        panelAiSuggestions.classList.remove("hidden");
        panelCustomControl.classList.add("hidden");
    });

    // 연도 드롭다운 옵션 동적 생성
    function populateYearDropdown(yearCols, recommendedYear) {
        if (!yearCols || yearCols.length === 0) {
            selectBaseYear.innerHTML = "<option value=''>연도 없음</option>";
            return;
        }

        // 최신 연도부터 내림차순 정렬 (2024, 2023, ..., 1960)
        const sortedYears = [...yearCols].sort((a, b) => b.localeCompare(a));
        selectBaseYear.innerHTML = sortedYears.map(y => {
            const isRec = (y === recommendedYear);
            return `<option value="${y}" ${isRec ? "selected" : ""}>${y}년 ${isRec ? "(⭐ 권장연도)" : ""}</option>`;
        }).join("");
    }

    // 도구 선택 변경 시 옵션 컨트롤 동적 변경
    selectTool.addEventListener("change", (e) => {
        const toolId = e.target.value;
        updateToolControlOptions(toolId);
    });

    function updateToolControlOptions(toolId) {
        // 기본적으로 연도와 서브옵션 표시
        groupBaseYear.classList.remove("hidden");
        groupSubOption.classList.remove("hidden");

        if (toolId === "T7") {
            // 상위/하위 N
            labelSubOption.innerHTML = "<strong>순위 옵션</strong>";
            selectSubOption.innerHTML = `
                <option value="top_10" selected>상위 10개국 (Top 10)</option>
                <option value="top_5">상위 5개국 (Top 5)</option>
                <option value="bottom_10">하위 10개국 (Bottom 10)</option>
                <option value="bottom_5">하위 5개국 (Bottom 5)</option>
            `;
        } else if (toolId === "T6") {
            // 시계열 추이
            labelSubOption.innerHTML = "<strong>비교 대상 국가</strong>";
            selectSubOption.innerHTML = `
                <option value="korea_us_jp" selected>한국, 미국, 일본</option>
                <option value="brics">중국, 인도, 브라질</option>
                <option value="europe">독일, 영국, 프랑스</option>
            `;
        } else if (toolId === "T8") {
            // 그룹 요약
            labelSubOption.innerHTML = "<strong>그룹 기준</strong>";
            selectSubOption.innerHTML = `
                <option value="IncomeGroup" selected>소득 수준별 (IncomeGroup)</option>
                <option value="Region">지역/대륙별 (Region)</option>
            `;
        } else if (toolId === "T9") {
            // 변화량
            labelSubOption.innerHTML = "<strong>비교 시작 연도</strong>";
            selectSubOption.innerHTML = `
                <option value="2014" selected>10년 전 (2014년)</option>
                <option value="2000">2000년</option>
                <option value="1990">1990년</option>
            `;
        } else if (toolId === "T12") {
            // 한국 vs 전체
            labelSubOption.innerHTML = "<strong>비교할 국가</strong>";
            selectSubOption.innerHTML = `
                <option value="Korea, Rep." selected>대한민국 (Korea, Rep.)</option>
                <option value="United States">미국 (United States)</option>
                <option value="Japan">일본 (Japan)</option>
            `;
        } else if (toolId === "T1" || toolId === "T2" || toolId === "T3" || toolId === "T4") {
            // 전체 대상 도구는 연도/서브옵션 불필요
            groupBaseYear.classList.add("hidden");
            groupSubOption.classList.add("hidden");
        } else {
            groupSubOption.classList.add("hidden");
        }
    }

    // [직접 설정으로 분석 실행] 버튼 클릭
    btnCustomRun.addEventListener("click", () => {
        const toolId = selectTool.value;
        const selectedYear = selectBaseYear.value || (currentDiagnosis ? currentDiagnosis.recommended_year : "2024");
        const subOptionVal = selectSubOption.value;

        const params = {};

        if (toolId === "T7") {
            params.base_period = selectedYear;
            if (subOptionVal === "top_5") { params.mode = "top"; params.n = 5; }
            else if (subOptionVal === "top_10") { params.mode = "top"; params.n = 10; }
            else if (subOptionVal === "bottom_5") { params.mode = "bottom"; params.n = 5; }
            else if (subOptionVal === "bottom_10") { params.mode = "bottom"; params.n = 10; }
        } else if (toolId === "T6") {
            if (subOptionVal === "korea_us_jp") params.entities = ["Korea, Rep.", "United States", "Japan"];
            else if (subOptionVal === "brics") params.entities = ["China", "India", "Brazil"];
            else if (subOptionVal === "europe") params.entities = ["Germany", "United Kingdom", "France"];
        } else if (toolId === "T8") {
            params.base_period = selectedYear;
            params.group_col = subOptionVal;
            params.agg_func = "mean";
        } else if (toolId === "T9") {
            params.start_period = subOptionVal;
            params.end_period = selectedYear;
            params.top_n = 10;
        } else if (toolId === "T10") {
            params.base_period = selectedYear;
        } else if (toolId === "T11") {
            params.col_x = "2014";
            params.col_y = selectedYear;
        } else if (toolId === "T12") {
            params.base_period = selectedYear;
            params.target_entity = subOptionVal;
        } else if (toolId === "T5") {
            params.base_period = selectedYear;
        }

        console.log(`[USER_CONTROL] 사용자가 직접 설정한 분석 실행: tool=${toolId}, params=`, params);
        runAnalysis(toolId, params);
    });

    // ==========================================================
    // 5. 2단계 (보조): Gemini 맞춤 분석 제안 (/suggest)
    // ==========================================================
    btnGetSuggestions.addEventListener("click", fetchSuggestions);

    async function fetchSuggestions() {
        suggestionsContainer.innerHTML = "<p style='color:var(--text-muted);'>AI가 데이터에 맞는 최적의 분석을 선별하는 중입니다...</p>";
        console.log("[SUGGEST] 제안 요청 시작");

        try {
            const res = await fetch("/suggest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ diagnosis: currentDiagnosis })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || "제안 생성 실패");
            }

            const data = await res.json();
            const list = data.suggestions || [];
            console.log(`[SUGGEST] 제안 응답 수신: 제안 개수=${list.length}`);

            renderSuggestionCards(list);

        } catch (err) {
            console.error("[ERROR] 제안 오류 발생:", err);
            suggestionsContainer.innerHTML = `<p style='color:#ef4444;'>AI 제안 생성 실패: ${err.message}</p>`;
        }
    }

    function renderSuggestionCards(suggestions) {
        if (!suggestions || suggestions.length === 0) {
            suggestionsContainer.innerHTML = "<p>제안 가능한 분석이 없습니다.</p>";
            return;
        }

        suggestionsContainer.innerHTML = suggestions.map((s, idx) => `
            <div class="suggest-card">
                <div>
                    <div class="suggest-card-header">
                        <span class="badge badge-info">${s.tool_id || s.tool_name}</span>
                        <small style="color:var(--text-muted); font-size:0.75rem;">추천 ${idx + 1}</small>
                    </div>
                    <div class="suggest-title">${s.title}</div>
                    <div class="suggest-reason">${s.reason}</div>
                    <div class="suggest-params">파라미터: ${JSON.stringify(s.params || {})}</div>
                </div>
                <button class="btn btn-primary btn-run-suggest" 
                        data-tool="${s.tool_id || s.tool_name}" 
                        data-params='${JSON.stringify(s.params || {})}'>
                    ▶ 이 추천 분석 실행하기
                </button>
            </div>
        `).join("");

        document.querySelectorAll(".btn-run-suggest").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const toolName = e.target.getAttribute("data-tool");
                const params = JSON.parse(e.target.getAttribute("data-params") || "{}");
                runAnalysis(toolName, params);
            });
        });
    }

    // ==========================================================
    // 6. 3단계: 도구 실행 및 차트 렌더링 (/run)
    // ==========================================================
    async function runAnalysis(toolName, params) {
        console.log(`[RUN] 도구 실행 시작: tool=${toolName}, base_period=${params.base_period || "none"}`);
        resultSection.classList.remove("hidden");
        resultSection.scrollIntoView({ behavior: "smooth" });

        try {
            const res = await fetch("/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tool_name: toolName, params: params })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || "도구 실행 실패");
            }

            const data = await res.json();
            lastRunResult = data;
            console.log(`[RUN] 결과 수신: tool=${data.tool_name}, used_rows=${data.used_rows_count}, excluded_rows=${data.excluded_rows_count}`);

            // 메타데이터 갱신
            resultToolBadge.textContent = `${data.tool_name}`;
            calcBasePeriod.textContent = data.base_period || "전체";
            calcUsedRows.textContent = `${data.used_rows_count}개`;
            calcExcludedRows.textContent = `${data.excluded_rows_count}개`;
            calcUnit.textContent = data.unit || "-";
            calcExclusionReason.textContent = data.exclusion_reason ? `ℹ️ 제외 사유: ${data.exclusion_reason}` : "";

            // 차트 렌더링
            renderChart(data.chart_data);

            // 계산 결과 수치 테이블/목록 표시
            renderResultTable(data.result);

            // 4단계 해석 섹션 활성화
            explainSection.classList.remove("hidden");

        } catch (err) {
            console.error("[ERROR] 도구 실행 오류:", err);
            alert(`도구 실행 오류: ${err.message}`);
        }
    }

    function renderChart(chartData) {
        const ctx = document.getElementById("insightChart").getContext("2d");

        if (chartInstance) {
            chartInstance.destroy();
            chartInstance = null;
        }

        if (!chartData) {
            document.getElementById("chart-wrapper").classList.add("hidden");
            return;
        }

        document.getElementById("chart-wrapper").classList.remove("hidden");

        chartInstance = new Chart(ctx, {
            type: chartData.type || "bar",
            data: {
                labels: chartData.labels || [],
                datasets: chartData.datasets || []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: "top" }
                },
                scales: chartData.type === "scatter" ? {
                    x: { type: "linear", position: "bottom" }
                } : {}
            }
        });

        console.log(`[CHART] 차트 렌더 완료 (타입: ${chartData.type || "bar"})`);
    }

    function renderResultTable(resultObj) {
        if (!resultObj) {
            calcTableContainer.innerHTML = "";
            return;
        }

        if (resultObj.ranking && Array.isArray(resultObj.ranking)) {
            calcTableContainer.innerHTML = `
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>순위</th><th>항목(국가)</th><th>수치</th></tr></thead>
                        <tbody>${resultObj.ranking.map(r => `<tr><td><strong>${r.rank}위</strong></td><td>${r.name}</td><td>${r.value}</td></tr>`).join("")}</tbody>
                    </table>
                </div>`;
            return;
        }

        if (resultObj.summary && Array.isArray(resultObj.summary)) {
            calcTableContainer.innerHTML = `
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>그룹</th><th>수치</th></tr></thead>
                        <tbody>${resultObj.summary.map(r => `<tr><td><strong>${r.group}</strong></td><td>${r.value}</td></tr>`).join("")}</tbody>
                    </table>
                </div>`;
            return;
        }

        const keys = Object.keys(resultObj);
        if (keys.length > 0 && typeof resultObj[keys[0]] !== "object") {
            calcTableContainer.innerHTML = `
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>지표</th><th>값</th></tr></thead>
                        <tbody>${keys.map(k => `<tr><td>${k}</td><td><strong>${resultObj[k]}</strong></td></tr>`).join("")}</tbody>
                    </table>
                </div>`;
        } else {
            calcTableContainer.innerHTML = "";
        }
    }

    // ==========================================================
    // 7. 4단계: Gemini 보고서 해석 (/explain)
    // ==========================================================
    btnExplain.addEventListener("click", async () => {
        const mode = document.querySelector('input[name="explain-mode"]:checked').value;
        console.log(`[EXPLAIN] 해석 요청 시작: mode=${mode}`);

        btnExplain.disabled = true;
        btnExplain.textContent = "AI가 7대 원칙 보고서를 작성하는 중입니다...";

        try {
            const res = await fetch("/explain", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode: mode, calc_result: lastRunResult })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || "해석 생성 실패");
            }

            const data = await res.json();
            console.log(`[EXPLAIN] 해석 응답 수신 완료 (모드 ${data.mode})`);

            reportModeBadge.textContent = data.mode_title;
            reportModeBadge.className = data.mode === "B" ? "badge badge-purple" : "badge badge-info";
            reportModelName.textContent = data.model;

            reportContent.innerHTML = formatMarkdown(data.explanation);

            explainOutputBox.classList.remove("hidden");
            explainOutputBox.scrollIntoView({ behavior: "smooth" });

        } catch (err) {
            console.error("[ERROR] 해석 생성 오류:", err);
            alert(`해석 생성 오류: ${err.message}`);
        } finally {
            btnExplain.disabled = false;
            btnExplain.textContent = "📝 선택한 모드로 AI 보고서 생성";
        }
    });

    // ==========================================================
    // 8. 5단계: AI 데이터 분석관 후속 질문 Q&A (/ask)
    // ==========================================================
    const qaInput = document.getElementById("qa-input");
    const btnQaSend = document.getElementById("btn-qa-send");
    const chatMessages = document.getElementById("chat-messages");

    btnQaSend.addEventListener("click", sendQuestion);
    qaInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });

    // 5단계 추천 질문 칩 클릭
    document.querySelectorAll("#qa-section .chip-btn").forEach(chip => {
        chip.addEventListener("click", () => {
            const q = chip.getAttribute("data-q");
            qaInput.value = q;
            sendQuestion();
        });
    });

    async function sendQuestion() {
        const question = qaInput.value.trim();
        if (!question) return;

        // 1. 사용자 말풍선 추가
        appendChatMessage("user", "나", question);
        qaInput.value = "";
        btnQaSend.disabled = true;

        // 2. 임시 AI 로딩 말풍선
        const loadingId = "loading-" + Date.now();
        appendChatMessage("ai", "📊 AI 데이터 분석관", "데이터 및 계산 결과를 바탕으로 분석 중입니다...", loadingId);

        try {
            console.log(`[QA] 후속 질문 전송: "${question}"`);
            const res = await fetch("/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: question })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || "답변을 불러오지 못했습니다.");
            }

            const data = await res.json();
            console.log(`[QA] 답변 수신 완료 (길이: ${data.answer.length}자)`);

            // 로딩 말풍선 교체
            const loadingBubble = document.getElementById(loadingId);
            if (loadingBubble) {
                loadingBubble.querySelector(".chat-text").innerHTML = formatMarkdown(data.answer);
            }
        } catch (err) {
            console.error("[ERROR] Q&A 오류:", err);
            const loadingBubble = document.getElementById(loadingId);
            if (loadingBubble) {
                loadingBubble.querySelector(".chat-text").textContent = `오류가 발생했습니다: ${err.message}`;
            }
        } finally {
            btnQaSend.disabled = false;
            qaInput.focus();
        }
    }

    function appendChatMessage(senderType, senderName, text, elementId = null) {
        const bubble = document.createElement("div");
        bubble.className = `chat-bubble chat-${senderType}`;
        if (elementId) bubble.id = elementId;

        bubble.innerHTML = `
            <div class="chat-sender">${senderName}</div>
            <div class="chat-text">${formatMarkdown(text)}</div>
        `;
        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // ==========================================================
    // 9. 자연어 데이터 질의 & 맞춤 시각화 (자유 프롬프트 /query_visualize)
    // ==========================================================
    const nlQueryInput = document.getElementById("nl-query-input");
    const btnNlQuerySend = document.getElementById("btn-nl-query-send");
    const nlOutputBox = document.getElementById("nl-output-box");
    const nlOutputBadge = document.getElementById("nl-output-badge");
    const nlOutputMeta = document.getElementById("nl-output-meta");
    const nlAnswerContent = document.getElementById("nl-answer-content");
    const nlChartWrapper = document.getElementById("nl-chart-wrapper");
    const nlSyncBanner = document.getElementById("nl-sync-banner");
    const btnNlGoReport = document.getElementById("btn-nl-go-report");

    let nlChartInstance = null; // Chart.js 인스턴스 전용 참조 변수 (window 네임스페이스 오염 방지)

    // 추천 질문 칩 클릭 바인딩
    document.querySelectorAll(".nl-chip-btn").forEach(chip => {
        chip.addEventListener("click", () => {
            const q = chip.getAttribute("data-q");
            nlQueryInput.value = q;
            sendNlQuery();
        });
    });

    btnNlQuerySend.addEventListener("click", sendNlQuery);
    nlQueryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendNlQuery();
        }
    });

    async function sendNlQuery() {
        const query = nlQueryInput.value.trim();
        if (!query) return;

        btnNlQuerySend.disabled = true;
        btnNlQuerySend.textContent = "분석 및 시각화 생성 중...";
        nlOutputBox.classList.remove("hidden");
        nlAnswerContent.innerHTML = "<p><em>질문 의도를 심층 분석하고 데이터 및 시각화를 구성하고 있습니다. 잠시만 기다려 주십시오...</em></p>";
        nlChartWrapper.classList.add("hidden");
        nlSyncBanner.classList.add("hidden");

        try {
            console.log(`[NL_QUERY] 자연어 질의 전송: "${query}"`);
            const res = await fetch("/query_visualize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || "해당 데이터가 존재하지 않거나 처리할 수 없습니다.");
            }

            const data = await res.json();
            console.log(`[NL_QUERY] 응답 수신: intent=${data.intent}, has_chart=${data.has_chart}`);

            // 1. 배지 및 메타데이터 갱신
            if (data.executed_tool_name) {
                nlOutputBadge.className = "badge badge-success";
                nlOutputBadge.textContent = `Pandas 도구 실측 실행: ${data.executed_tool_name}`;
                nlOutputMeta.textContent = `${data.filename || "데이터셋"} 연동`;
                nlSyncBanner.classList.remove("hidden");

                // Step 3 및 4 연동 데이터 업데이트
                if (data.tool_result) {
                    lastRunResult = data.tool_result;
                }
            } else if (data.has_dataset) {
                nlOutputBadge.className = "badge badge-info";
                nlOutputBadge.textContent = "원천 데이터셋 기반 분석";
                nlOutputMeta.textContent = `${data.filename} 참조`;
            } else {
                nlOutputBadge.className = "badge badge-purple";
                nlOutputBadge.textContent = "일반 공공 통계 분석";
                nlOutputMeta.textContent = "Gemini 수석 분석관 모델";
            }

            // 2. 진지하고 분석적인 답변 렌더링
            nlAnswerContent.innerHTML = formatMarkdown(data.explanation || "");

            // 3. 맞춤 차트 시각화 (데이터가 있는 경우에만 차트 렌더링)
            if (data.has_chart && data.chart_data && Array.isArray(data.chart_data.labels) && data.chart_data.labels.length > 0) {
                nlChartWrapper.classList.remove("hidden");
                renderNlQueryChart(data.chart_data);
            } else {
                nlChartWrapper.classList.add("hidden");
                // 도구 실행을 시도했으나 데이터가 비어있는 경우
                if (data.intent === "run_tool" && (!data.chart_data || !data.chart_data.labels || data.chart_data.labels.length === 0)) {
                    nlAnswerContent.innerHTML += `
                        <div class="nl-empty-notice">
                            <p>⚠️ <strong>해당 데이터가 존재하지 않습니다.</strong></p>
                            <p class="text-muted">요청하신 조건(국가명, 기준 연도 등)에 해당하는 수치가 데이터셋에 존재하지 않거나 결측치로 인해 시각화할 수 없습니다.</p>
                        </div>`;
                }
            }

        } catch (err) {
            console.error("[ERROR] NL 질의 처리 실패:", err);
            nlChartWrapper.classList.add("hidden");
            nlOutputBox.classList.remove("hidden");
            nlOutputBadge.className = "badge badge-warning";
            nlOutputBadge.textContent = "데이터 조회 불가";

            // 친절하고 직관적인 '해당 데이터가 존재하지 않습니다' 안내 박스 렌더링
            nlAnswerContent.innerHTML = `
                <div class="nl-empty-notice">
                    <p>⚠️ <strong>해당 데이터가 존재하지 않습니다.</strong></p>
                    <p class="text-muted">요청하신 조건(국가명, 기준 연도, 지표 등)을 데이터셋에서 찾을 수 없습니다. 질문 내용이나 기준 연도를 다시 확인해 주시기 바랍니다.</p>
                </div>`;
        } finally {
            btnNlQuerySend.disabled = false;
            btnNlQuerySend.textContent = "질의 및 시각화 실행";
        }
    }

    function renderNlQueryChart(chartData) {
        const canvasEl = document.getElementById("nlQueryChart");
        if (!canvasEl) return;

        // 기존 차트가 있으면 안전하게 파기 (Chart.getChart 또는 nlChartInstance)
        const existingChart = typeof Chart.getChart === "function" ? Chart.getChart(canvasEl) : null;
        if (existingChart) {
            existingChart.destroy();
        } else if (nlChartInstance && typeof nlChartInstance.destroy === "function") {
            nlChartInstance.destroy();
        }
        nlChartInstance = null;

        if (!chartData || !Array.isArray(chartData.labels) || chartData.labels.length === 0) {
            nlChartWrapper.classList.add("hidden");
            return;
        }

        const ctx = canvasEl.getContext("2d");
        const chartType = (chartData.type || "bar").toLowerCase();

        // 색상 팔레트
        const bgColors = [
            "rgba(37, 99, 235, 0.75)",
            "rgba(16, 185, 129, 0.75)",
            "rgba(245, 158, 11, 0.75)",
            "rgba(239, 68, 68, 0.75)",
            "rgba(139, 92, 246, 0.75)",
            "rgba(14, 165, 233, 0.75)",
            "rgba(236, 72, 153, 0.75)",
            "rgba(100, 116, 139, 0.75)",
            "rgba(20, 184, 166, 0.75)",
            "rgba(249, 115, 22, 0.75)"
        ];
        const borderColors = bgColors.map(c => c.replace("0.75", "1"));

        const datasets = (chartData.datasets || []).map((ds, idx) => ({
            label: ds.label || "값",
            data: ds.data || [],
            backgroundColor: chartType === "line" ? "rgba(37, 99, 235, 0.15)" : bgColors,
            borderColor: chartType === "line" ? "rgba(37, 99, 235, 1)" : borderColors,
            borderWidth: 1.5,
            fill: chartType === "line",
            tension: 0.25
        }));

        nlChartInstance = new Chart(ctx, {
            type: chartType,
            data: {
                labels: chartData.labels || [],
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: !!chartData.title,
                        text: chartData.title || "",
                        font: { size: 15, weight: "bold" },
                        padding: { top: 10, bottom: 15 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const val = context.parsed.y !== undefined ? context.parsed.y : context.parsed;
                                return ` ${context.dataset.label || ''}: ${val !== null ? Number(val).toFixed(2) + '%' : '데이터 없음'}`;
                            }
                        }
                    },
                    legend: {
                        display: datasets.length > 1 || chartType === "line"
                    }
                },
                scales: chartType !== "pie" && chartType !== "doughnut" ? {
                    y: {
                        beginAtZero: true,
                        grid: { color: "#f1f5f9" }
                    },
                    x: {
                        grid: { color: "#f8fafc" }
                    }
                } : {}
            }
        });
    }

    if (btnNlGoReport) {
        btnNlGoReport.addEventListener("click", () => {
            explainSection.classList.remove("hidden");
            explainSection.scrollIntoView({ behavior: "smooth" });
            generateReport("B");
        });
    }

    // ==========================================================
    // 10. 상단 유틸리티 (화면 저장, 인쇄/PDF, 링크 복사, 토스트)
    // ==========================================================
    const btnSaveScreen = document.getElementById("btn-save-screen");
    const btnPrintScreen = document.getElementById("btn-print-screen");
    const btnCopyLink = document.getElementById("btn-copy-link");
    const toastEl = document.getElementById("toast");

    let toastTimer = null;
    function showToast(message) {
        if (!toastEl) return;
        toastEl.textContent = message;
        toastEl.classList.remove("hidden");
        void toastEl.offsetWidth; // reflow
        toastEl.classList.add("show");

        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toastEl.classList.remove("show");
            setTimeout(() => toastEl.classList.add("hidden"), 260);
        }, 2800);
    }

    if (btnSaveScreen) {
        btnSaveScreen.addEventListener("click", () => {
            const now = new Date();
            const timeStr = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}${String(now.getSeconds()).padStart(2,'0')}`;
            const filename = `AI_Data_Insight_${timeStr}.html`;

            // Canvas 차트를 영구 보존용 Base64 이미지로 변환하여 복제본에 인라인 삽입
            const docClone = document.documentElement.cloneNode(true);
            const canvasList = document.querySelectorAll("canvas");
            const cloneCanvasList = docClone.querySelectorAll("canvas");

            canvasList.forEach((origCanvas, idx) => {
                try {
                    const dataUrl = origCanvas.toDataURL("image/png");
                    const img = docClone.createElement("img");
                    img.src = dataUrl;
                    img.style.maxWidth = "100%";
                    img.style.height = "auto";
                    img.alt = "Exported Chart";
                    if (cloneCanvasList[idx]) {
                        cloneCanvasList[idx].parentNode.replaceChild(img, cloneCanvasList[idx]);
                    }
                } catch (e) {
                    console.warn("Canvas export fallback:", e);
                }
            });

            // 스크립트 태그 제거하여 가벼운 정적 아카이브로 다운로드
            docClone.querySelectorAll("script").forEach(s => s.remove());

            const htmlContent = "<!DOCTYPE html>\n" + docClone.outerHTML;
            const blob = new Blob([htmlContent], { type: "text/html;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showToast("💾 현재 분석 화면 및 차트가 HTML 파일로 저장되었습니다!");
        });
    }

    if (btnPrintScreen) {
        btnPrintScreen.addEventListener("click", () => {
            showToast("🖨️ 인쇄 대화상자를 호출합니다 (PDF로 저장 가능)...");
            setTimeout(() => {
                window.print();
            }, 300);
        });
    }

    if (btnCopyLink) {
        btnCopyLink.addEventListener("click", async () => {
            const url = window.location.href;
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(url);
                } else {
                    const temp = document.createElement("input");
                    temp.value = url;
                    document.body.appendChild(temp);
                    temp.select();
                    document.execCommand("copy");
                    document.body.removeChild(temp);
                }
                showToast("🔗 링크가 클립보드에 복사되었습니다!");
            } catch (err) {
                showToast(`링크 복사: ${url}`);
            }
        });
    }

    // ==========================================================
    // 11. 마크다운 렌더러 (형광펜 강조 ==단어== 및 태그 지원)
    // ==========================================================
    function formatMarkdown(text) {
        if (!text) return "";
        let html = text
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            // 형광펜 하이라이트 문법 변환
            .replace(/==(.*?)==/g, '<mark class="highlight-pen">$1</mark>')
            .replace(/&lt;mark&gt;(.*?)&lt;\/mark&gt;/gi, '<mark class="highlight-pen">$1</mark>')
            .replace(/^## (.*$)/gim, "<h2>$1</h2>")
            .replace(/^### (.*$)/gim, "<h3>$1</h3>")
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/^\* (.*$)/gim, "<li>$1</li>")
            .replace(/^- (.*$)/gim, "<li>$1</li>")
            .replace(/(<li>.*<\/li>)/gis, "<ul>$1</ul>")
            .replace(/\n\n/g, "<br><br>");
        return html;
    }
});
