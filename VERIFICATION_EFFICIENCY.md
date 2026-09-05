# 검증 효율 대시보드

Click의 실제 canonical plan과 runner 결과를 읽기 전용으로 보여줍니다.
화면이 실행 계획을 만들거나 재사용 권한을 판단하지 않습니다.

## 열기와 공유

Click을 사용하는 현재 작업에서 `click-gate dashboard start`로 열고,
`click-gate dashboard status`로 상태를 확인하며, 확인 후 `click-gate dashboard stop`으로 닫습니다.
Observer는 별개이며 `click-gate observer off` 상태에서도 계측·receipt·기존 재사용이 동작합니다.
새 코드가 설치되지 않은 환경의 기존 viewer에는 새 화면이 나타나지 않습니다.

대시보드는 개별 계약이나 Evidence 배치가 아니라 **검증 가능한 host 세션 + 작업 공간**에
속합니다. 한 번 열면 같은 범위에서 `수정 → 검증 → 다음 Evidence 작업 → 수정 → 검증`을
반복해도 같은 URL과 접근 토큰으로 현재 배치와 이전 배치를 계속 읽습니다. 새 Evidence
작업이 이전 Guarded 승인, runner token, 미완료 명령, 완료 상태를 상속한다는 뜻은 아닙니다.
`click-gate cancel`은 실행 권한을 폐기하지만 이미 열린 읽기 전용 화면은 최근 결과를
history-only 상태로 보여줍니다. `dashboard stop`, SessionEnd, 기존 최대 수명 정리는 계속
viewer를 종료합니다. 다른 host 세션이나 작업 공간은 별도 바인딩이므로 연결되지 않습니다.

상단은 선택한 배치의 **검증 묶음** 수입니다. 개별 테스트 케이스 수나 시간 절감률이 아닙니다.
최근 배치를 선택하면 계획, 실제 시작·완료·통과·실패·중단·미실행, 재사용 적용,
영어 reason code와 한국어 설명, 이전 성공 실행 표본을 확인할 수 있습니다.
각 묶음이 끝나는 즉시 다음 묶음이 시작되기 전에 완료 상태와 실행 구간을 저장하므로,
`A 통과 → B 실행 중`인 순간에도 A는 통과로 보입니다. 이후 취소하더라도 A의 실행 사실은
유지되고, B는 확인한 범위에 따라 중단/결과 미확정, 뒤 묶음은 미실행으로 남습니다.
첫 묶음 실패로 다음 묶음이 시작되지 않았다면 실제 실행 1개 / 미실행 1개입니다.
종료를 확인하지 못한 실행은 미확정으로 남습니다. 재사용 예정은 적용 실적이 아닙니다.
Evidence Map은 최신 배치의 상세 분석이며 과거 배치의 입력 그래프를 추측해 복원하지 않습니다.
표시 제한 48개에 맞춰 실제 렌더링 수와 생략 수를 표시합니다.

## Reuse Diagnostics 읽기

Reuse Diagnostics는 기본적으로 켜져 있으며 `click-gate diagnostics on|off|status`로 제어합니다.
이 설정은 설명 기록만 바꾸고 canonical decision, 실제 runner batch, Evidence/Guarded 권한,
one-use token, receipt에는 영향을 주지 않습니다. 화면은 첫 번째 authoritative reason과 함께,
같은 판정 과정에서 이미 계산된 다른 binding 불일치도 보여줍니다. 추가 파일 읽기나 hash가 필요한
조건은 진단 숫자를 채우려고 다시 검사하지 않고 `not-evaluated`로 남깁니다.

원인별 표에는 해당 원인으로 분류된 묶음 수, 통과한 실제 실행 구간, 이전 성공 baseline 유무,
단일 원인/복합 원인 수, 시간 미확인 수가 표시됩니다. 실패·중단·미실행은 정상 통과 비용과
분리합니다. 한 묶음에 환경과 실행 파일 불일치가 함께 있으면 같은 실행시간이 두 원인에 각각
나타날 수 있으므로 원인별 시간을 더하면 안 됩니다. 별도의 **중복 제거한 통과 실행 구간**만
전체로 읽습니다. 시간이 없으면 0ms가 아니라 측정 정보 없음입니다. 이 값은 현재 규칙에 따라
실제로 다시 실행한 비용이며 절약 시간, 불필요한 재실행의 증명, 새 재사용 후보의 권한이 아닙니다.

새 기록을 끄더라도 이전에 저장된 안전한 진단 history는 대시보드에서 계속 읽을 수 있습니다.
저장하는 값은 stable condition/reason code, bool/상태, digest 식별자, 실행 결과와 시간뿐입니다.
원시 명령, 환경 값, prompt, token, 파일 내용, 절대 경로는 projection과 공유 리포트에 넣지 않습니다.

화면의 **JSON 내보내기**, **독립형 HTML 내보내기**는 선택한 실제 배치와 가져온 비교 측정을
브라우저 다운로드로 저장합니다. HTML은 외부 스크립트·자산·분석 서비스 없이 열립니다.
공유본은 원시 명령·파일 내용·입력 파일 경로·절대경로·환경 값·runner/access token을 제외합니다.
검증을 실행하거나 재사용 권한을 바꾸지 않습니다. 서명이나 발행자 인증이 있는 receipt는 아닙니다.
사용자 문자열은 DOM textContent로 표시하여 HTML로 실행하지 않습니다.

## 시간을 읽는 법

| 값 | 의미와 계측 경계 |
| --- | --- |
| 전체 검증 대기시간 `request_wall_ms` | 요청 처리부터 반환까지. 현재 제품의 분리된 Hook/runner 구조는 전체 경계를 관찰하지 못하므로 **null / 측정 정보 없음**. 0ms로 채우지 않습니다. |
| 부분 처리 구간 `measured_processing_ms` | 준비 함수 진입부터 기존 판정·상태 저장 직후까지, 그리고 runner 진입부터 결과 기록 중 계측 저장 직전까지의 **각 프로세스 로컬 경과시간 합계**. 서로 다른 monotonic 원점을 빼지 않습니다. 호스트 대기·전달, 계측 자체의 최종 저장, host 최종 반환은 제외합니다. |
| 검사 실행 구간 `executed_duration_ms` | 실제 시작이 관찰된 묶음의 명령 호출 구간 합계. spawn/시작 기록과 Observer 준비·수집·정리 비용이 이 호출 안에 있으면 포함됩니다. 순수 테스트 CPU 시간이 아닙니다. |
| 생략한 비용 `estimated_avoided_ms` | **실제로 적용된 재사용**의 최근 성공 실행 표본을 합한 추정치. 실행하지 않은 현재 명령의 반사실적 시간은 알 수 없으며 실측 절약이라고 부르지 않습니다. |

전부 재사용이면 명령 실행 시간은 0이지만 준비 처리시간은 측정됩니다.
부분 계측에는 Hook 프로세스 시작·모듈 로딩·준비 함수 이전의 제어문 해석도 포함되지 않습니다.
거부·실패·일반 중단에서도 관찰한 부분 시간과 상태가 남습니다. 원시 요청조차 검증할 수 없으면
묶음 수는 알 수 없습니다. 실행 전 거부는 실행 실적이 아니고, 미실행은 절감 실적이 아닙니다.
명령 시작은 성공한 프로세스 시작/재개 경계에서 기록합니다. Linux Shadow에서는 대상 명령을
포함한 strace launcher 시작 경계이며 대상 exec 실패도 실패한 호출로 남습니다.
강제 프로세스 종료나 저장 실패로 종료를 확인하지 못하면 완료 시간을 만들지 않습니다.

과거 시간 표본에는 원래 실행 revision, check digest, batch id, 관측 시각, 표본 수(묶음 실행 1회)가
연결됩니다. 일부 재사용 묶음의 표본만 있으면 그 부분만 합하고 **추정 가능 / 전체 재사용** 수를 표시합니다.
옛 정수 시간 필드만 있는 데이터는 정확한 출처가 없으므로 새 추정 근거로 꾸미지 않습니다.
Observer overhead는 별도 Shadow 정보이며 위 실행 구간에 다시 더하거나 빼지 않습니다.
tracing slowdown은 비교 측정하지 않았으며 Shadow 후보를 실제 재사용 수나 실측 절약에 합치지 않습니다.

## 실제 비교 벤치마크

명시적으로 로컬에서만 실행합니다. 평상시 verify와 viewer 새로고침은 비교용 검사를 실행하지 않습니다.

```sh
python3 benchmarks/incremental_verification.py --iterations 3 --warmups 1 --output /tmp/click-comparison.json
python3 benchmarks/incremental_verification.py --mode guarded --iterations 3 --warmups 1 --output /tmp/click-guarded-comparison.json
```

Windows에서는 쓰기 가능한 출력 경로와 현재 Python 명령을 사용하세요. 기존 출력 파일을 덮어쓰지 않습니다.
비교 driver, Hook 준비, 실제 runner는 같은 Python으로 고정합니다. Windows의 `py -3`가 다른 버전을
선택해 비교 환경이 달라지는 것을 막되, 발급된 capability와 실제 재사용 권한 검사는 그대로 유지합니다.
`--scenario`는 first-run, unchanged, docs, partial-reuse, code, environment,
first-failure 중 여러 번 지정할 수 있습니다.
`--workload-rounds`는 PBKDF2 계산량이며 sleep은 사용하지 않습니다.

각 비교 쌍은 별도 임시 Git 저장소에 같은 코드·두 test 파일·정확한 shard inventory·안전 변경 정책을
먼저 커밋합니다. 양쪽 모두 동일 절차의 실제 baseline을 준비한 뒤 고정 변경을 적용합니다.
Click arm은 실제 prompt/pre/post Hook, 재사용 판정, one-use runner, 결과 저장을 거칩니다.
ledger·passing receipt·dependency observation·skip 결정은 주입하지 않습니다.
Guarded fixture는 **임시 테스트 사용자**가 실제 stage와 다음 turn의 pass를 통과하고,
비교 종료 조건을 가진 계약을 유지합니다. 사용자 저장소의 실제 승인으로 간주하지 않습니다.

`partial-reuse`는 기본 Evidence에서 baseline 완료 후 실제 다음 Evidence lifecycle로 넘어간
다음 README를 변경합니다. 커밋된 서로 다른 정책 때문에 alpha는 이전 실제 성공을 후보로
가져와 현재 상태에서 safe-change 규칙을 다시 통과해 재사용하고, beta는 정책 범위 밖이라
실제로 실행합니다. 정책 기반 결과이며 자동 의존성 발견이라고 표현하지 않습니다.
Guarded fixture는 기존 계약 안에서 같은 권한 규칙을 사용하며 계약 간 승인을 상속하지 않습니다.
현재 native Shadow는 authoritative dependency observation이 아니므로 코드 변경의 부분 재사용을
미리 지정하지 않습니다. 실행 권한이 없으면 보수적 재실행 결과를 그대로 보고합니다.

비교 기준은 (1) 같은 두 샤드를 전부 직접 실행 (2) 동일한 두 파일을 발견하는 원래 unittest discover입니다.
대조군은 실제 명령 반환까지, Click은 driver의 Hook 요청부터 runner 반환까지 단일 프로세스 시계로 잽니다.
baseline 준비 시간은 양쪽 측정에서 제외합니다. 두 경로의 코드·범위는 같지만 서로 다른 절대 root의 receipt를
교차 재사용하지 않습니다. 원래 parent는 검증 묶음 1개, shard 경로는 2개입니다.
새 체크아웃, baseline 유무, bytecode 비활성, OS 캐시 미초기화, 실행 순서와 반복 조건을 JSON에 남깁니다.
쌍별 순서를 번갈아 실행합니다. OS 캐시와 스케줄러 영향을 완전히 제어하지는 않습니다.

`delta_ms = baseline_wall_ms - incremental_wall_ms`이며 baseline이 양수일 때만 비율을 계산합니다.
느려지면 음수를 유지합니다. 성공한 비워밍업 표본의 중앙값·최소·최대와 모든 원시 쌍별 시간을 남깁니다.
실패·중단과 워밍업 표본은 성공 성능 통계에서 제외하지만 JSON에는 제외 이유와 함께 남습니다.
benchmark JSON의 `reuse_diagnostics`는 각 incremental arm의 실제 batch를 batch/source id로
중복 제거해 같은 원인 집계를 제공합니다. 비교 delta와 합쳐 절약 증명으로 사용하지 않습니다.
화면에서 JSON을 선택하면 실제 비교 조건·측정 수·음수 결과를 포함한 비교 그래프를 표시합니다.
비교 파일이 없으면 실행 안내만 보이며 추정 비용으로 가상의 전체 재실행 baseline을 만들지 않습니다.
가져온 파일은 로컬·서명 없는 측정 자료이며 Click authority의 새 증거가 아닙니다.

작은 fixture는 관리 비용 때문에 오히려 느릴 수 있습니다. 특정 절감률을 통과 기준으로 두지 않으며
임시 저장소 결과를 사용자 저장소 전체의 성능으로 일반화하지 않습니다.

## 저장소 shard 안전 변경 정책 감사

현재 `full-suite`는 명시적인 unittest module 목록을 실행하는 다섯 runtime shard와,
저장소 전체의 문서·JSON·Hook·배포본·평가 자료를 직접 탐색하는 `repository-policy` shard로
나뉩니다. 각 runtime shard의 실제 argv, 테스트 모듈, 공용 fixture/import, 파일 열기와
하위 프로세스 호출을 확인했습니다. 그 결과 다섯 runtime shard에만 다음 **루트 파일의 정확한
경로**를 안전 변경으로 선언합니다.

- `COMMUNITY_POSTS.md`, `COMPATIBILITY_SURFACE.md`, `GUARD_CLASSIFICATION.md`
- `LICENSE`, `PRODUCT_CONSTITUTION.md`
- `README.md`, `README.ko.md`, `README.zh-CN.md`
- `RELEASE_NOTES.md`, `SECURITY.md`, `VERIFICATION_EFFICIENCY.md`

이 파일들은 `core-state`, `capability-runtime`, `gate-lifecycle`, `verification-evidence`,
`observer-host`의 명시된 테스트가 입력으로 읽지 않는 설명 문서입니다. 정책은 해당 다섯
shard의 정확한 argv와 연결됩니다. argv가 바뀌면 같은 정책 entry로 인정되지 않습니다.

`repository-policy`에는 안전 변경 entry를 두지 않습니다. 이 shard는 README와 위 기술 문서,
모든 JSON, `hooks/`, `skills/`, `evals/`, 배포본과 workflow 일관성을 실제로 검사하므로 문서만
바뀌어도 실행해야 합니다. 또한 다음 범위는 이름만 보고 안전하다고 판단하지 않고 보류합니다:
`hooks/**`, `tests/**`, `skills/**`, `platforms/**`, `dist/**`, `evals/**`, `scripts/**`,
`.github/**`, `assets/**`, `.click/**`. 공용 import, 동적 파일 탐색, 새 테스트 발견, 패키징과
adapter 일관성, 권한 설정 자체가 남은 반례입니다. 넓은 `docs/**`나 다른 package 전체 패턴도
선언하지 않습니다.

정책 작업트리 변경은 권한이 아닙니다. `.click/evidence-reuse.json`, dependency 선언과 shard
정의는 보호 경로이며, 커밋된 내용과 작업트리가 정확히 같아야 합니다. 정책을 커밋한 뒤에는
새 정책으로 실제 검증한 baseline을 먼저 만들어야 하며 기존 baseline을 소급 승격하지 않습니다.
완전한 dependency observation이 정책보다 우선하고, 불완전한 관측·외부 입력·Shadow 예측은
정책으로 우회하지 않습니다.

부분 재사용이 포함된 실행 계획을 만든 뒤 작업트리가 바뀌면 runner는 one-use claim 전에
계획 시점의 토큰 결합 Git 지문과 다시 대조합니다. 정책 파일을 포함해 차이가 있거나 지문을
읽지 못하면 검사 하나도 실행하지 않고 해당 batch의 재사용도 적용 실적으로 기록하지 않습니다.
다음 요청은 불명확한 mutation boundary 때문에 실제 검사를 다시 실행합니다.

`partial-reuse` benchmark는 임시 Git 저장소에 서로 다른 shard 정책을 커밋하고 실제 baseline과
후속 Evidence 작업을 거칩니다. README 변경에서 alpha만 정책 기반으로 재사용하고 beta는 실제
실행합니다. 이는 자동 의존성 발견의 증거가 아니며, 임시 fixture 측정값은 실사용 절감률이 아닙니다.

## 이력과 호환성

canonical plan v2/v3는 계획만 저장하고, 실제 결과는 `verification-batch` event에 batch_id로 연결합니다.
v3는 실행 전 동결된 content-free Reuse Diagnostics를 포함합니다. 진단을 끈 현재 plan과 이전 v2
데이터는 계속 읽으며 진단 정보 없음으로 표시합니다.
같은 batch의 재전송·재기록은 갱신 또는 no-op이며 별도 실행으로 누적되지 않습니다.
계획만 있는 v1 데이터도 읽지만 실제 실행과 시간은 unknown입니다. 최종 상태가 확인된 batch만 누적 통계에 씁니다.
각 이력은 기존 1,000 events / 7일 / 4 MiB 중 먼저 닿는 제한으로 오래된 기록부터 제거합니다.
화면에는 최근 최대 30개 배치만 보이고 실제 보관·표시 개수를 구분합니다.
취소 시 계측만 담은 `efficiency-history-*.json` 보관본을 기존 managed state 위치에 원자적으로 저장합니다.
권한·명령·환경·원시 요청은 보관본에 없고 다음 lifecycle에 결과 이력만 합칩니다.
취소된 실행의 실제 자식 종료가 확인되지 않으면 미확정 중단으로 표시하며 재사용 후보는 적용하지 않습니다.
파일 시스템 오류가 나면 기록이 없을 수 있지만 계측 실패가 승인 경계·검사 결과·취소를 변경하지 않습니다.
정상 저장은 기존 atomic replace 방식을 사용하므로 저장 도중 종료에도 반쪽 JSON을 노출하지 않습니다.

완료된 Evidence lifecycle은 같은 host 세션·작업 공간의 다음 Evidence 작업에 이전 성공을
**재판정 후보**로만 전달할 수 있습니다. 후보는 원래 evidence session, batch, source 사실과
무결성 digest를 보존합니다. 새 요청의 source/check 범위, 현재 Git tree, mutation boundary,
환경, 실행 파일, host coverage를 다시 비교하고, 변경된 tree에서는 기존 complete dependency
observation 또는 현재 커밋된 safe-change policy까지 다시 통과해야 실제 재사용됩니다. revision
숫자가 우연히 같거나 과거 실행시간이 있다는 이유만으로는 재사용하지 않습니다. Dashboard
history, 공유 리포트와 Shadow record를 authoritative evidence로 역변환하지 않습니다.
현재 조합을 안전하게 입증할 수 없으면 reason code를 남기고 실제 검사를 실행합니다.

후속 Evidence 재사용이 있는 completion receipt는 v4 `successor-reused` lineage로 원래 batch와
Evidence session, 원래 revision, 재판정 방식(exact/dependency/safe-change), 후보 digest를
기록합니다. 이것은 여전히 `unsigned-integrity-only`이며 발행자 신원 인증은 아닙니다.
