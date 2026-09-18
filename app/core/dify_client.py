import os
import requests
import re
from typing import Dict, Any, List
from dotenv import load_dotenv

class DifyTBMClient:
    """
    Dify 워크플로우 API 클라이언트 및 KOSHA 표준 지능형 Fallback 안전 엔진
    """
    def __init__(self):
        self.reload_config()

    def reload_config(self):
        load_dotenv(override=True)
        self.api_key = os.getenv("DIFY_API_KEY", "").strip()
        self.base_url = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").rstrip("/")

    def generate_tbm_report(self, site_name: str, work_date: str, work_desc: str, worker_count: str, allow_generative_accident: bool = True) -> Dict[str, Any]:
        """
        Dify Workflow API(POST /v1/workflows/run)를 호출하여 위험성평가 및 TBM 데이터 생성
        API 키가 없거나 호출 실패 시 고용노동부/KOSHA 표준 지능형 엔진으로 자동 Fallback
        """
        self.reload_config()
        
        last_error = None
        if self.api_key:
            try:
                url = f"{self.base_url}/workflows/run"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                # Dify 워크플로우에서 site_name 또는 site_name_ 등으로 변수명이 설정된 경우 모두 대응
                payload = {
                    "inputs": {
                        "site_name": site_name,
                        "site_name_": site_name,
                        "work_date": work_date,
                        "work_date_": work_date,
                        "work_description": work_desc,
                        "work_description_": work_desc,
                        "worker_count": str(worker_count),
                        "worker_count_": str(worker_count),
                        "allow_generative_accident": "true" if allow_generative_accident else "false"
                    },
                    "response_mode": "blocking",
                    "user": "site_manager"
                }
                resp = requests.post(url, json=payload, headers=headers, timeout=60)
                resp_json = resp.json()
                
                if resp.status_code == 200:
                    data = resp_json.get("data", {})
                    workflow_status = data.get("status")
                    if workflow_status == "failed":
                        last_error = data.get("error", "Workflow execution failed")
                        print(f"[Dify Workflow Error] {last_error}")
                    else:
                        outputs = data.get("outputs", {})
                        tbm_data = outputs.get("tbm_data")
                        if not tbm_data:
                            tbm_data = outputs
                        
                        # 문자열 형태의 JSON으로 반환된 경우 파싱
                        if isinstance(tbm_data, str):
                            try:
                                import json
                                cleaned = tbm_data.strip()
                                if cleaned.startswith("```"):
                                    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                                    cleaned = re.sub(r"\s*```$", "", cleaned)
                                tbm_data = json.loads(cleaned)
                            except Exception:
                                pass

                        if isinstance(tbm_data, dict) and tbm_data.get("risk_assessments"):
                            tbm_data["engine_mode"] = "dify"
                            tbm_data["site_name"] = tbm_data.get("site_name") or site_name
                            tbm_data["work_date"] = tbm_data.get("work_date") or work_date
                            tbm_data["worker_count"] = tbm_data.get("worker_count") or worker_count
                            tbm_data["allow_generative_accident"] = allow_generative_accident

                            acc_case = (tbm_data.get("accident_cases") or "").strip()
                            # Dify 프롬프트의 부정문("지식베이스에 없습니다") 필터링
                            is_negative_or_empty = (
                                not acc_case or
                                "지식베이스에 없습니다" in acc_case or
                                "지식베이스에 등록된" in acc_case or
                                "사례가 지식베이스에" in acc_case or
                                "등록된 중대재해 사례가" in acc_case
                            )

                            if is_negative_or_empty:
                                if allow_generative_accident:
                                    fb = self._generate_fallback_report(site_name, work_date, work_desc, worker_count, allow_generative_accident=True)
                                    tbm_data["accident_cases"] = fb.get("accident_cases", "")
                                    tbm_data["accident_source"] = "generative_kosha"
                                else:
                                    tbm_data["accident_cases"] = "■ 지식 베이스(KOSHA DB)에 등록된 동종 중대재해 사고사례가 없습니다.\n(생성형 AI 보완 옵션이 해제되어 있어 공식 지식 문서만을 참조합니다. 표준 안전작업지침을 준수하십시오.)"
                                    tbm_data["accident_source"] = "none"
                            else:
                                tbm_data["accident_source"] = "generative_kosha" if allow_generative_accident else "knowledge_base"

                            return tbm_data
                        elif isinstance(tbm_data, dict) and tbm_data.get("error"):
                            last_error = f"Dify LLM 반환 오류: {tbm_data.get('error')}"
                            print(f"[Dify LLM Output Error] {last_error}")
                        else:
                            last_error = "Dify 출력에 유효한 위험성평가(risk_assessments) 데이터가 없습니다."
                            print(f"[Dify Response Missing Data] {last_error}")
                else:
                    last_error = resp_json.get("message", f"HTTP {resp.status_code}")
                    print(f"[Dify API Error] {last_error}")
            except Exception as e:
                last_error = str(e)
                print(f"[Dify Client Exception] {e}. KOSHA 지능형 로컬 엔진으로 전환합니다.")
        
        # Fallback to KOSHA Rule-based Local Safety Engine
        fallback_data = self._generate_fallback_report(site_name, work_date, work_desc, worker_count, allow_generative_accident=allow_generative_accident)
        if last_error:
            fallback_data["dify_error"] = last_error
        return fallback_data

    def _generate_fallback_report(self, site_name: str, work_date: str, work_desc: str, worker_count: str, allow_generative_accident: bool = True) -> Dict[str, Any]:
        """
        KOSHA 및 고용노동부 5x5 위험성평가 매트릭스 표준 기반 로컬 규칙 생성 엔진
        """
        text = work_desc.lower()
        assessments: List[Dict[str, Any]] = []
        classified_processes = []
        core_rules = []

        # 공종별 위험성 분석 지식베이스 (KOSHA 표준 작업지침 기반)
        knowledge_base = [
            {
                "keywords": ["비계", "비계해체", "비계설치", "발판", "비계공"],
                "process_name": "비계 설치/해체 작업",
                "hazard_factor": "비계 해체 및 발판 이동 중 중심 상실 및 안전난간 미설치 구간에서 고소 추락",
                "frequency": 3,
                "severity": 4,
                "countermeasure": "안전대 2중 걸이(카라비너 2구) 체결 철저, 달줄·달포대를 이용한 자재 인하, 하부 5m 반경 출입통제 및 신호수 배치",
                "action_owner": "비계반장 / 안전담당자",
                "rule": "비계 상부 이동 시 안전대 고리 무조건 100% 체결 (미체결 시 즉시 퇴출)",
                "accident_case": "■ [비계 해체 중 추락 사망사고]: 2025년 OO 신축현장 외벽 비계 해체 중 작업자가 2중 안전대 고리를 걸지 않고 발판을 해체하다 발판이 기울어지며 14m 하부로 추락 사망함. (원인: 안전대 고리 미체결 및 안전난간 선 해체)"
            },
            {
                "keywords": ["도장", "페인트", "도색", "롤러", "스프레이"],
                "process_name": "외부 고소 도장 작업",
                "hazard_factor": "달비계/고소작업대 탑승 도장 중 로프 손상으로 인한 추락 및 유기용제 증기 흡입에 의한 중독·어지럼증",
                "frequency": 2,
                "severity": 4,
                "countermeasure": "구명줄 및 수직 추락방지대 별도 설치, 방독마스크(유기화합물용) 및 보안경 착용 의무화, 작업 전 로프 마모 점검",
                "action_owner": "도장반장",
                "rule": "도장 작업 구역 10m 이내 화기 사용 절대 금지 및 유기용제용 방독마스크 필착",
                "accident_case": "■ [달비계 로프 파단 추락사고]: 2024년 OO 아파트 외벽 도장 작업 중 옥상 난간 콘크리트 모서리 부위에 로프 보호덮개를 설치하지 않아 로프 마찰 파단으로 지상 추락 사망함. (원인: 로프 보호덮개 미설치 및 구명줄 미설치)"
            },
            {
                "keywords": ["용접", "절단", "아크", "가스절단", "불꽃", "철골"],
                "process_name": "철골 조립 및 아크 용접",
                "hazard_factor": "고소 철골 부재 용접 중 비산 불티에 의한 하부 가연물 화재 및 감전, 고소 작업 중 실족 추락",
                "frequency": 3,
                "severity": 4,
                "countermeasure": "용접 작업 반경 11m 이내 가연물 제거 및 방염포(불티받이포) 설치, 이동식 소화기 2대 비치, 화재감시자 전담 배치",
                "action_owner": "용접반장 / 화재감시자",
                "rule": "화재감시자 미배치 및 소화기 미비치 상태에서 용접·용단 작업 절대 금지",
                "accident_case": "■ [철골 용접 불티 화재사고]: 2024년 OO 복합물류센터 철골 조립 중 아크 용접 불티가 8m 하부 우레탄 단열재에 튀어 대형 화재가 발생하고 유독가스로 인명피해 발생함. (원인: 방염포 미설치 및 화재감시자 미배치)"
            },
            {
                "keywords": ["굴착", "터파기", "토공", "포크레인", "굴착기", "흙막이"],
                "process_name": "토공사 터파기 및 굴착 작업",
                "hazard_factor": "굴착사면 및 흙막이 벽체 붕괴에 의한 매몰, 굴착기 선회 반경 내 근로자 접근으로 인한 협착(부딪힘)",
                "frequency": 2,
                "severity": 5,
                "countermeasure": "토질별 안전기울기 준수, 굴착기 후방카메라 및 협착방지 경보장치 점검, 장비 회전반경 출입금지 펜스 설치 및 전담 유도원 배치",
                "action_owner": "토공반장 / 신호수",
                "rule": "굴착 장비 선회 반경 내 작업자 임의 접근 금지 및 유도원 신호 엄수",
                "accident_case": "■ [흙막이 띠장·버팀대 해체 중 추락 및 붕괴사고]: 2025년 OO 굴착 현장에서 슬라브 타설 후 지보재(띠장·버팀대)를 조립 역순 절차 없이 임의 해체하다 빔 반동으로 작업자가 굴착 바닥으로 추락 사망함. (원인: 안전대 부착설비 누락 및 2중 걸이 미체결)"
            },
            {
                "keywords": ["양중", "크레인", "호이스트", "자재인양", "줄걸이"],
                "process_name": "타워크레인/이동식크레인 양중 작업",
                "hazard_factor": "샤클·와이어로프 등 줄걸이 불량으로 인한 인양물 낙하 및 강풍 시 크레인 붐대 선회에 따른 주변 구조물 충돌",
                "frequency": 2,
                "severity": 5,
                "countermeasure": "2줄걸이 이상 체결 원칙, 인양 하중별 와이어로프 손상 여부 점검, 인양물 하부 절대 통행 금지 및 무전 신호수 지정",
                "action_owner": "양중반장 / 신호수",
                "rule": "인양 자재 하부 출입 통제 엄수 및 유도 로프(보조줄) 미사용 인양 금지",
                "accident_case": "■ [타워크레인 인양 자재 낙하사고]: 2024년 OO 아파트 현장에서 타워크레인으로 H빔 인양 중 1줄걸이 슬링벨트 파단으로 자재가 낙하하여 하부 신호수를 타격 사망함. (원인: 2줄걸이 원칙 위반 및 인양 하부 통제선 미설치)"
            },
            {
                "keywords": ["타설", "콘크리트", "레미콘", "펌프카", "슬라브", "거푸집"],
                "process_name": "콘크리트 타설 및 거푸집 동바리 작업",
                "hazard_factor": "타설 하중 집중에 의한 거푸집 동바리 붕괴 및 펌프카 배관 요동에 의한 근로자 타격 추락",
                "frequency": 2,
                "severity": 4,
                "countermeasure": "구조검토서에 따른 동바리 수평연결재 체결 확인, 편심 타설 금지(고른 분산 타설), 펌프카 붐대 하부 근로자 접근 통제",
                "action_owner": "타설반장 / 거푸집반장",
                "rule": "콘크리트 타설 시 편심 타설 절대 금지 및 타설 하부 동바리 변형 감시원 상주",
                "accident_case": "■ [슬라브 타설 중 거푸집 동바리 붕괴사고]: 2024년 OO 신축공사 3층 슬라브 타설 중 한쪽에 콘크리트를 집중 타설(편심 타설)하여 동바리가 연쇄 붕괴되면서 작업자 3명이 매몰됨. (원인: 편심 타설 및 수평연결재 체결 불량)"
            },
            {
                "keywords": ["밀폐", "맨홀", "정화조", "탱크", "지하실", "배관연결", "피트", "반응기", "알곤", "질식", "폐수", "환기"],
                "process_name": "밀폐공간(피트·반응기) 배관 및 알곤용접 작업",
                "hazard_factor": "밀폐공간 내부 알곤가스 및 유해가스 체류로 인한 산소결핍(18% 미만) 질식, 인화성 가스 잔류 시 용접 불꽃에 의한 화재·폭발",
                "frequency": 2,
                "severity": 5,
                "countermeasure": "작업 전 4대 복합가스(산소, CO, H2S, 가연성) 측정 기록, 작업 중 연속 급배기 송풍기 강제 환기 가동, 송기마스크 및 비상 탈출용 삼각대 비치, 외부 감시인 상주",
                "action_owner": "밀폐공간 안전관리자 / 화재감시자",
                "rule": "밀폐공간 진입 전 가스농도 측정 미실시 시 진입 절대 금지 및 송풍기 상시 가동",
                "accident_case": "■ [밀폐 피트 알곤 용접 질식 사망사고]: 2024년 OO 사업장 지하 폐수처리 피트 내 배관 알곤(Ar) TIG 용접 작업 중, 공기보다 무거운 아르곤 가스가 바닥에 체류하여 산소농도 14% 미만의 산소결핍 상태가 됨. 작업자가 송풍기 미가동 상태에서 보호구 없이 진입했다가 질식 사망함. (원인: 사전 가스농도 미측정, 강제 환기 미유지, 감시인 미배치 / 교훈: 밀폐공간 출입 전 산소농도 측정 및 작업 중 급배기 송풍기 상시 가동 필수)"
            },
            {
                "keywords": ["사다리", "우마", "A형사다리", "말비계"],
                "process_name": "이동식 사다리 및 말비계 작업",
                "hazard_factor": "A형 사다리 최상단 디딤대 작업 중 균형 상실로 인한 전도 및 추락",
                "frequency": 4,
                "severity": 2,
                "countermeasure": "사다리는 이동통로용으로만 사용 원칙(3.5m 이상 작업 금지), 2인 1조 작업(1인 하부 지지), 안전모 턱끈 체결 철저",
                "action_owner": "작업반장",
                "rule": "사다리 최상단 및 2단 디딤대 탑승 작업 절대 금지 및 2인 1조 작업 준수",
                "accident_case": "■ [A형 사다리 최상단 추락사고]: 2025년 OO 공장 배관 보수 작업 중 2m 높이 A형 사다리 최상단에 올라서서 작업하다 중심을 잃고 콘크리트 바닥으로 전도 추락하여 머리 충격으로 사망함. (원인: 사다리 최상단 탑승 금지 위반 및 1인 단독 작업)"
            },
            {
                "keywords": ["전기", "배전반", "케이블", "간이분전함", "결선"],
                "process_name": "임시 전력 설비 및 전기 결선 작업",
                "hazard_factor": "누전 및 피복 손상 전선 접촉에 의한 감전 쇼크, 분전함 내 단락에 의한 아크 폭발 화상",
                "frequency": 2,
                "severity": 4,
                "countermeasure": "작업 전 전로 차단(LOTO 실시), 누전차단기 정격 감도 확인, 절연장갑 착용 및 접지선 연결 상태 확인",
                "action_owner": "전기안전관리자",
                "rule": "활선 상태 임의 결선 작업 절대 금지 및 전원 차단 후 검전기 확인 필수",
                "accident_case": "■ [임시 분전반 활선 감전사고]: 2024년 OO 신축현장 임시 분전반 결선 작업 중 차단기를 내리지 않은 활선 상태에서 나선에 손이 접촉되어 감전 쇼크로 사망함. (원인: 전로 차단 LOTO 미실시 및 절연장갑 미착용)"
            }
        ]

        matched = []
        for item in knowledge_base:
            if any(k in text for k in item["keywords"]):
                matched.append(item)

        # 일치하는 키워드가 없으면 일반 고소 및 현장 정화 작업 기본 세트 적용
        if not matched:
            matched = [
                {
                    "process_name": "일반 현장 정리 및 자재 운반",
                    "hazard_factor": "작업장 바닥 개구부 미덮개 구간 및 돌출 철근에 걸려 넘어짐/추락",
                    "frequency": 3,
                    "severity": 3,
                    "countermeasure": "작업 통로 구획 및 조명 확보, 개구부 덮개 고정 및 경고표지 부착, 안전화 및 안전모 착용",
                    "action_owner": "직영반장",
                    "rule": "현장 내 지정 안전통로 준수 및 개구부 덮개 임의 해체 금지"
                },
                {
                    "process_name": "도구 및 소형 장비 취급 작업",
                    "hazard_factor": "전동공구 누전 또는 회전체 날물 접촉에 의한 베임/협착",
                    "frequency": 2,
                    "severity": 3,
                    "countermeasure": "방호덮개(안전커버) 부착 확인, 전원선 누전차단기 연결, 방진/보안경 착용",
                    "action_owner": "안전담당자",
                    "rule": "회전체 안전커버 임의 탈거 사용 절대 금지"
                }
            ]

        for item in matched:
            classified_processes.append(item["process_name"])
            freq = item["frequency"]
            sev = item["severity"]
            score = freq * sev
            
            if score >= 9:
                level_str = f"고위험 ({score})"
            elif score >= 4:
                level_str = f"보통 ({score})"
            else:
                level_str = f"낮음 ({score})"

            assessments.append({
                "process_name": item["process_name"],
                "hazard_factor": item["hazard_factor"],
                "frequency": freq,
                "severity": sev,
                "risk_level": level_str,
                "risk_score": score,
                "countermeasure": item["countermeasure"],
                "action_owner": item["action_owner"]
            })
            if "rule" in item and len(core_rules) < 3:
                core_rules.append(item["rule"])

        # 추가 핵심 수칙 보강 (항상 3가지 유지)
        default_rules = [
            "개인 보호구(안전모 턱끈 체결, 안전대, 안전화) 100% 착용 전 현장 투입 불가",
            "위험 요소 발견 시 즉시 작업 중지 및 관리자 보고 (근로자 작업중지권 보장)",
            "음주 작업 절대 금지 및 지정 흡연구역 외 흡연 시 즉각 퇴출"
        ]
        for r in default_rules:
            if len(core_rules) < 3 and r not in core_rules:
                core_rules.append(r)

        # 10분 TBM 브리핑 스크립트 작성
        processes_str = ", ".join(classified_processes[:3])
        briefing_script = (
            f"반장님들과 팀원 여러분, 안녕하십니까! 오늘 {work_date}, {site_name} 현장의 아침 안전점검회의(TBM)를 시작하겠습니다. "
            f"오늘 우리 작업에는 총 {worker_count}명이 투입되어 [{processes_str}] 공종을 중점적으로 진행할 예정입니다.\n\n"
            f"오늘 특히 주의하셔야 할 중대 위험 요인은 다음과 같습니다. "
        )
        for idx, assess in enumerate(assessments[:3], 1):
            briefing_script += f"\n첫째, {assess['process_name']} 시 {assess['hazard_factor']}의 위험이 매우 큽니다. 따라서 {assess['countermeasure']} 조치를 철저히 이행해 주십시오."

        briefing_script += (
            f"\n\n오늘 현장에서 반드시 지켜야 할 절대 금지 수칙 3가지를 명심해 주십시오. "
            f"첫째, {core_rules[0]}, 둘째, {core_rules[1]}, 셋째, {core_rules[2]}입니다. "
            f"작업 중 조금이라도 불안전한 상태나 이상 징후를 발견하시면 주저하지 마시고 즉시 작업을 중지하고 안전관리자에게 알려주시기 바랍니다. "
            f"오늘 하루도 가족을 위해 무사고·무재해로 안전하게 작업을 마무리합시다. 모두 안전!"
        )

        accident_list = [item["accident_case"] for item in matched if "accident_case" in item]
        if allow_generative_accident:
            final_acc_cases = "\n\n".join(accident_list[:2]) if accident_list else ""
            accident_source = "generative_kosha"
        else:
            final_acc_cases = "■ 지식 베이스(KOSHA DB)에 등록된 동종 중대재해 사고사례가 없습니다.\n(생성형 AI 보완 옵션이 해제되어 있어 공식 지식 문서만을 참조합니다. 표준 안전작업지침을 준수하십시오.)"
            accident_source = "none"

        return {
            "site_name": site_name,
            "work_date": work_date,
            "worker_count": worker_count,
            "classified_processes": classified_processes,
            "tbm_briefing_script": briefing_script,
            "core_safety_rules": core_rules[:3],
            "risk_assessments": assessments,
            "accident_cases": final_acc_cases,
            "accident_source": accident_source,
            "allow_generative_accident": allow_generative_accident,
            "engine_mode": "kosha_smart_engine"
        }
