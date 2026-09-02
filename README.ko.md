# Click — 코딩 에이전트를 위한 revision-aware evidence

[English](README.md) | 한국어 | [简体中文](README.zh-CN.md)

커뮤니티: [LINUX DO](https://linux.do/)

[![CI](https://github.com/grapefruit0205/click/actions/workflows/ci.yml/badge.svg)](https://github.com/grapefruit0205/click/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 테스트 결과가 지금 코드에도 유효한지 기억합니다.

Click의 핵심은 **revision-aware evidence**입니다.

쉽게 말하면, “예전에 테스트가 통과했다”가 아니라 **어떤 코드에서 어떤 검사가 통과했는지** 기록하는 플러그인입니다.

평소처럼 AI에게 일을 맡기면 Click이 다음을 기억합니다.

- 무엇을 요청했는지
- 코드가 언제 바뀌었는지
- 어떤 검사를 실제로 실행했는지
- 이전 결과를 지금도 재사용해도 되는지

모델의 생각 방식이나 파일 탐색 순서를 강제하지는 않습니다.

## 예시 하나로 이해하기

~~~text
revision 12  인증 코드 수정 → 인증 테스트 실행 → 통과
revision 13  README만 수정   → 인증 관련 파일은 그대로 → 결과 재사용
revision 14  인증 코드 수정 → 이전 결과는 오래됨 → 테스트 재실행
~~~

Click이 없으면 AI가 오래된 테스트 결과를 현재 결과처럼 믿거나, 문서 하나를 고친 뒤 큰 테스트 묶음을 다시 돌릴 수 있습니다.

Click은 **결과를 유효하게 만든 입력이 그대로일 때만** 그 결과를 재사용합니다. 판단 근거가 부족하면 다시 검사합니다.

이것이 Click의 가장 중요한 기능입니다.

## 사용 방식

| 모드 | 언제 쓰나요? | 사용자 경험 |
| --- | --- | --- |
| **Evidence** (기본) | 일반적인 코딩 작업 | Click 승인 없이 평소처럼 작업하고 마지막에 증거 영수증을 받습니다. |
| **Guarded** | 결제·인증·삭제처럼 경계가 중요한 작업 | 짧은 계약을 한 번 확인한 뒤 그 범위 안에서 실행합니다. |
| **Off** | Click이 필요 없는 작업 | 실행 권한을 host에 그대로 맡깁니다. |

### Evidence: 평소에는 이것만 쓰면 됩니다

Codex나 host의 기존 권한을 그대로 사용합니다. Click이 작업을 승인한 척하지 않습니다.

영수증에는 다음처럼 적힙니다.

~~~text
approval_bound: false
execution_authority: host
~~~

### Guarded: 잘못 바꾸면 위험한 작업에 사용합니다

사용자는 복잡한 JSON 대신 네 부분만 확인합니다.

~~~text
작업 목표
무엇이 완성되어야 하나요?

변경 범위
어디까지 바꿔도 되나요?

변경하지 않는 부분
무엇을 그대로 두어야 하나요?

완료 확인
무엇이 통과하면 끝인가요?
~~~

원본 JSON은 필요할 때만 기술 계약으로 볼 수 있습니다. 승인 후 기존 범위 안의 세부 요청은 다시 승인하지 않고 계속 처리합니다.

## 설치

~~~bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
~~~

Codex를 다시 시작해 Hook을 새로 불러온 뒤 새 작업을 시작하세요.

새 설치의 기본값은 Evidence입니다.

~~~text
click-gate default evidence
click-gate default guarded
click-gate default off
~~~

Evidence에서는 평소처럼 요청하면 됩니다.

~~~text
인증 파서를 리팩터링하고 외부 동작은 그대로 유지해줘.
~~~

Guarded를 직접 선택할 수도 있습니다.

~~~text
@Click 주문 취소 기능을 추가하고 중복 환불을 막아줘.
~~~

## 업데이트

현재 릴리스: **v0.50.0**

~~~bash
codex plugin marketplace upgrade click
codex plugin add click@click
~~~

업데이트 후에는 새 작업을 시작하세요.

변경 이력은 [릴리스 노트](RELEASE_NOTES.md)에 있습니다.

## evidence를 언제 재사용하나요?

다음과 같은 정보가 계속 일치해야 합니다.

- 실행한 검사
- 검사와 관련된 파일과 내용
- 현재 workspace 상태
- 실행 환경과 실행 파일
- host Hook coverage

하나라도 확실하지 않으면 실제 검사를 다시 실행합니다.

revision을 넘어 결과를 재사용하려면 선택적으로 다음 파일에 의존 관계를 기록할 수 있습니다.

~~~text
.click/evidence-dependencies.json
~~~

커밋된 의존 관계 파일이 검사별 재사용 권한을 정합니다. 구체적으로 적은 파일은
항상 의존성으로 유지합니다. baseline 관찰이 완전하면 `*`, `**`, 디렉터리 같은
확장 패턴은 실제로 검사가 사용한 입력까지 좁히고, 관찰된 입력을 영수증에 함께
해시합니다. 작업 트리에서만 바꾼 의존 관계 파일은 커밋된 정책을 좁힐 수
없습니다. 관찰 기능이 없거나 실패했거나, 외부 입력을 읽었거나, 자식 프로세스
전체를 추적하지 못했다면 Click은 코드가 바뀐 뒤 검사를 다시 실행합니다.
의존 관계 파일이 없어도 Click은 동작하지만 역시 재실행합니다.

README나 문서처럼 특정 검사에 영향을 주지 않는다고 저장소가 확실히 아는
변경에는 observer 없이 다음 안전 변경 정책을 커밋할 수 있습니다.

~~~json
{
  "version": 1,
  "entries": [
    {
      "checks": [["python3", "-m", "pytest", "tests/unit"]],
      "reuse_if_only_changed": ["README.md", "docs/**"]
    }
  ]
}
~~~

파일명은 `.click/evidence-reuse.json`입니다. 검사가 처음 성공하면 Click은 Git
커밋과 당시 실제 미커밋 파일의 간결한 지문을 저장합니다. 다음번 같은 검사를
실행하기 전에 기준점과 현재점 사이의 순변경 경로를 보여주고, 모든 경로가 계속
같은 커밋된 정책에 포함될 때만 결과를 재사용합니다. 목록에 없는 파일, 정책
변경, 해석할 수 없는 Git 상태, 환경·실행 파일 변경, mutation 이후 추가 변경은
실제 검사를 실행합니다. 정책 파일 자체를 안전 대상으로 선언할 수도 없습니다.
Git과 플러그인의 Python만 사용하므로 Linux, macOS, Windows에서 별도 관찰기나
추가 설치가 필요 없습니다. 이 목록은 저장소 소유자의 명시적 정책이며 Click이
모든 의존성을 자동 발견했다는 뜻은 아닙니다.

## 완료 영수증

현재 코드에 맞는 evidence가 준비되면 영수증을 내보내고 확인할 수 있습니다.

~~~text
click-gate receipt export
click-gate receipt verify ./completion-receipt.json
~~~

영수증에는 요청 흐름, mutation revision, 최종 workspace, 검사 결과, 환경, 실행 파일, host coverage, 재사용 이력이 묶입니다.

현재 검증 결과는 **unsigned-integrity-only**입니다. 영수증이 바뀌었는지는 확인하지만 발행자 신원까지 증명하지는 않습니다.

## Click이 강제로 지키는 것

- Guarded의 승인과 계약 ID
- one-use 실행과 replay 방지
- 코드 변경 revision과 오래된 evidence 무효화
- 실제 검증 결과의 receipt
- managed service 정리
- 영수증 무결성

탐색 횟수, 계획 방식, 재시도 횟수, 모델의 추론 전략은 막지 않습니다. 필요한 경우 안내만 제공합니다.

## Antigravity

실험적인 Google Antigravity 어댑터도 포함되어 있습니다.

~~~bash
agy plugin install ./dist/antigravity
~~~

Antigravity가 제공하는 Hook 범위 안에서 Evidence와 Guarded를 지원합니다. 관찰할 수 없는 경로를 관찰했다고 과장하지 않습니다.

자세한 내용은 [Antigravity 어댑터 안내](platforms/antigravity/README.md)를 참고하세요.

## 한계

Click은 workflow guardrail이지 운영체제 sandbox가 아닙니다.

숨은 추론, 의미적 정확성, Hook과 연결되지 않은 외부 도구, 모델이 고른 테스트의 품질까지 증명할 수는 없습니다. 코드 리뷰, CI, branch protection, 배포 통제와 함께 사용하세요.

## 기술 문서

README는 일부러 쉽게 유지합니다. 세부 프로토콜은 아래 문서에 있습니다.

- [제품 헌법](PRODUCT_CONSTITUTION.md)
- [Guard 분류](GUARD_CLASSIFICATION.md)
- [동작 모드](skills/click/references/modes.md)
- [Guarded 계약 형식](skills/click/references/directive-format.md)
- [검증 profile](skills/click/references/verification-profiles.md)
- [Capability protocol](skills/click/references/capability-protocol.md)
- [Anti-loop 정책](skills/click/references/anti-loop-policy.md)

## 라이선스

[MIT](LICENSE)
