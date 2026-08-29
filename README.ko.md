# Click

[English](README.md) | 한국어 | [简体中文](README.zh-CN.md)

[![CI](https://github.com/grapefruit0205/click/actions/workflows/ci.yml/badge.svg)](https://github.com/grapefruit0205/click/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 구현 경계를 한 번 승인하고, 다시 계획하지 않고, 한 번만 검증합니다.

Click은 성능 좋은 모델이 소프트웨어 작업에서 계획을 다시 세우고, 같은 파일을 다시 읽고, 저장소를 다시 훑고, 검증을 과하게 반복하는 데 지친 사람을 위한 Codex 플러그인입니다. 처음 한 번 **Always ON(추천)** 또는 **Manual**을 선택합니다. Always ON은 소프트웨어 생성·수정·삭제·리팩터링·수리에 자동 적용되고, Manual은 `@Click`을 멘션했을 때만 적용됩니다.

변경 요청에서는 가장 좁은 관련 저장소 맥락을 확인하고, 요청을 축약 실행 계약으로 번역하고, 같은 내용을 쉬운 말로 설명한 뒤 코드 수정 전에 한 번만 승인을 요청합니다. 승인 뒤에는 그 경계 안에서 One-shot으로 구현합니다. 활성 작업 중에는 버전이 있는 argv 기반 `inspect`·`mutate`·`verify` runner로 지원 명령의 의도를 분명히 하고 shell 없이 실행합니다. Hook은 관찰 가능한 재읽기·재탐색·재계획·예산 밖 검증 루프를 막되, 승인된 범위 안에서 필요한 구현 선택은 열어 둡니다.

Always ON이어도 질문·설명·단순 조회는 평소처럼 처리합니다. 코드 리뷰도 구현 계약이나 승인이 필요하지 않습니다. 대신 읽기 전용 anti-loop 안전망을 적용해 처음 필요한 근거 수집은 허용하고, 성공한 동일 shell 조회와 저장소 전체 재탐색 반복을 막습니다.

Click은 아키텍처 패턴 선택기나 완전한 명세 시스템이 아닙니다. 사용자가 모듈러 모노리스, 이벤트 드리븐, 배치, 함수형 중 하나를 미리 고를 필요가 없습니다. 요청한 동작과 기존 시스템에 실제로 필요한 최소 설계 언어를 Click이 도출합니다.

## 빠르게 시작하기

```bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

ChatGPT 데스크톱 앱을 다시 시작하고 포함된 Click Hook을 검토해 신뢰한 뒤 새 작업을 시작합니다. 첫 코드 변경 요청 전에 Click이 한 번만 묻습니다.

```text
앞으로 소프트웨어 변경에 Always ON을 사용할까요(추천), 아니면 @Click을 부를 때만 Manual로 사용할까요?
```

기본 경험을 원하면 Always ON을 선택합니다. 명시적으로만 사용하려면 Manual을 고른 뒤 다음처럼 호출합니다.

```text
@Click 주문 취소 기능을 추가해줘. 중복 환불을 방지하고 기존 API 호환성을 유지해야 해.
```

나중에 “Click을 Always ON으로 설정해줘” 또는 “Click을 Manual로 설정해줘”라고 바꿀 수 있고, 이 설정은 대상 저장소 밖에 유지됩니다. 정확히 한 turn만 우회하려면 사용자 프롬프트 첫 줄에 `@Click bypass` 또는 자동완성 형식인 `[@Click](plugin://click@click) bypass`를 씁니다. Hook은 같은 turn의 `click-gate bypass` 한 번만 승인하고 active 계약은 그대로 보존합니다. active 계약을 버릴 때는 같은 형식의 `cancel` 명령으로 `click-gate cancel` 한 번을 승인합니다. `@Click` 이름과 명령의 대소문자는 구분하지 않지만 plugin URI는 정확히 일치해야 하며, 명령 줄에 다른 문구를 붙일 수 없습니다. 실제 작업 내용은 둘째 줄부터 이어서 쓸 수 있습니다. 두 권한은 재사용하거나 다음 turn으로 가져갈 수 없습니다. Click은 프로젝트 안에 설정이나 계약 파일을 만들지 않습니다.

<details>
<summary>Build Brief 또는 예전 Click 설치에서 이전하기</summary>

`click@build-brief` 0.9.0을 설치했다면:

```bash
codex plugin remove click@build-brief
codex plugin marketplace remove build-brief
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

Build Brief 0.8이라면 첫 번째 명령을 `codex plugin remove build-brief@build-brief`로 바꿉니다.

</details>

## 작동 방식

```mermaid
flowchart TB
    A["처음 사용"] --> B{"한 번 선택"}
    B -->|Always ON| C["소프트웨어 변경에<br/>자동 적용"]
    B -->|Manual| D["원할 때<br/>@Click 호출"]
    C --> E["축약 실행 계약<br/>+ 쉬운 설명"]
    D --> E
    E --> F["계약 stage 후<br/>응답 대기"]
    F --> I{"다음 사용자 turn:<br/>한 번 승인?"}
    I -->|수정 또는 취소| E
    I -->|승인| G["One-shot 구현"]
    G --> H["예산 안에서<br/>최종 검증 한 번"]
```

처음 한 요청을 아직 보지 못한 설계에 대한 승인으로 간주하지 않습니다. Click이 먼저 개발자용 계약과 쉬운 설명을 stage해서 보여주고 멈춥니다. Hook은 `staged_turn_id`를 기록하고 같은 `UserPromptSubmit` turn의 pass와 두 번째 stage를 거부하며, 다음 사용자 turn에서만 정확히 같은 계약을 받을 수 있습니다. 사용자는 그때 제안을 수정하거나 취소할 수 있습니다. 승인하면 `approved_turn_id`를 기록하고 의미 계약을 고정한 뒤, 또 다른 계획을 승인해 달라고 묻지 않은 채 구현합니다. 이 장치는 다른 사용자 응답이 있었다는 사실을 증명하지만, 그 자연어가 실제로 승인을 뜻하는지는 Skill이 충실하게 해석해야 합니다.

승인한 결과·경계·반드시 지킬 동작·검증 약속이 실제로 바뀌는 경우에만 중단합니다. 승인 경계 안에서 필요한 파일·라이브러리·도구·서비스·구현 수단은 새 계약이 필요하지 않습니다.

Manual의 fail-open은 active Click 계약이 없을 때만 적용됩니다. 계약을 stage했거나 승인했지만 현재 revision 검증을 끝내지 않았다면 그 세션 상태가 다음 turn에서도 일반 mutation을 막습니다. 따라서 승인 turn에서 정확한 계약을 pass하기 전에 실수로 코드를 바꿀 수 없습니다. 승인된 구현이 중단되어 다음 turn에 이어갈 때는 같은 계약을 다시 arm·pass한 뒤 계속하며, 새 계약을 만들지는 않습니다.

현재 코드 revision의 최종 검증까지 성공하면 다음 변경 요청은 새 계약을 정상적으로 stage할 수 있습니다. 검증 전·실행 중·실패·추가 수정으로 stale인 계약은 교체할 수 없습니다. 새 계약은 조회·mutation·검증 상태를 깨끗하게 초기화하고 다시 한 번 승인을 받으므로 `bypass`나 상태 파일 수동 삭제가 필요 없습니다.

## 예시: 요청에서 승인까지

다음처럼 요청했다고 가정합니다.

```text
@Click 주문 취소 기능을 추가해줘. 중복 환불을 방지하고 기존 API 호환성을 유지해야 해.
```

Click은 코드를 건드리기 전에 다음과 같은 축약 계약을 제시할 수 있습니다.

```json
{
  "outcome": "기존 API로 취소 가능한 주문을 취소하고 환불은 최대 한 번만 실행한다.",
  "boundary": {
    "in_scope": ["현재 주문 취소 및 환불 경로"],
    "out_of_scope": ["새 결제 사업자 추가", "관련 없는 주문 상태 정리"]
  },
  "must_hold": [
    "동시에 요청하거나 재시도해도 두 번째 환불이 생기지 않는다.",
    "기존 요청 필드, 응답 필드, 상태 의미를 호환되게 유지한다.",
    "결제 사업자 호출 실패를 환불 완료 상태로 기록하지 않는다."
  ],
  "build": {
    "approach": [
      "현재 취소 경로를 재사용하고 멱등 환불 기록과 원자적인 환불 상태 전이를 추가한다."
    ],
    "semantics": [
      "환불 결과는 한 번만 기록하고 반복 요청에는 기록된 결과를 반환한다."
    ]
  },
  "verification": {
    "scale": "full",
    "done_when": [
      "환불 동작이 정확하다 — 주 증거: 성공, 중복, 동시 요청, 결제 사업자 실패를 다루는 주문 취소 테스트.",
      "공개 API가 호환된다 — 주 증거: 기존 API 회귀 테스트."
    ]
  },
  "plain_language": "고객은 취소 가능한 주문을 취소할 수 있지만 재시도하거나 동시에 요청해도 환불은 한 번만 됩니다. 공개 API는 그대로 유지되고 결제 호출 실패가 환불 완료로 잘못 기록되지 않습니다. 결제와 동시성을 다루므로 Click은 full 검증을 추천합니다."
}
```

그다음 Click은 이 계약과 검증 규모를 승인할지, 고칠지, 취소할지 한 번 묻습니다. 승인은 쉬운 요약만이 아니라 계약에 담긴 개발자 의미 전체를 승인한다는 뜻이며, 승인하면 구현이 시작됩니다.

실제 설계는 저장소마다 달라집니다. 이 예시는 모든 환불 시스템에 적용되는 정답이 아니라 계약의 형태를 보여줍니다.

## 축약 계약

| 필드 | 고정하는 것 |
| --- | --- |
| `outcome` | 구체적인 결과와 사용자에게 보이는 동작 |
| `boundary` | 바꿔도 되는 범위와 건드리지 않을 범위 |
| `must_hold` | 관찰 가능한 안전·호환성·정확성 약속 |
| `build` | 저장소에 맞춘 가장 작은 구현 경로 |
| `verification` | 위험에 맞춘 검증 규모 하나와 완료 근거 |
| `plain_language` | 비개발자도 이해할 수 있게 풀어쓴 같은 계약 |

`build.semantics`, `build.order`, `verification.intermediate_gate`는 상태 의미, 안전한 순서, 되돌리기 어려운 경계가 실제로 필요할 때만 추가합니다. 같은 작업을 phases, steps, tasks, plan으로 반복해 늘어놓지 않습니다.

계약은 결과와 경계를 고정하지만 모든 저수준 구현 선택까지 고정하지는 않습니다. 그래서 승인 범위 안에서 의존성·파일·도구가 필요해져도 매번 재승인하지 않고 작게 유지할 수 있습니다.

## 방해하지 않는 Always ON

| 요청 | Always ON 동작 |
| --- | --- |
| 소프트웨어 생성·수정·삭제·리팩터링·수리 | 축약 계약과 쉬운 설명을 보여주고 승인 한 번을 기다림 |
| 수정 없는 코드 리뷰 | 구현 계약과 승인 없이 읽기 전용 anti-loop 안전망만 적용 |
| 질문 또는 설명 | 평소처럼 바로 답변 |
| 단순 읽기 전용 조회 | 관찰 기록을 만들지 않고 평소처럼 확인 |
| 첫 줄이 일반 또는 자동완성 `@Click bypass` | 해당 turn의 우회 한 번을 승인하고 active 계약은 유지 |
| 첫 줄이 일반 또는 자동완성 `@Click cancel` | active 계약을 지우는 cancel 한 번을 승인 |

코드 리뷰에서는 필요하면 저장소 전체 목록을 처음 한 번 확인할 수 있습니다. 성공한 뒤에는 범위를 좁혀 확인해야 하며, 동일한 성공 읽기·검색과 두 번째 저장소 전체 목록 탐색을 차단합니다. 계획 도구 반복과 프로젝트 수정도 리뷰 모드에서는 거부합니다. 발견 사항을 나중에 고쳐 달라고 요청하면 별도의 축약 구현 계약을 시작합니다.

인식 가능한 단순 직접 조회는 계속 편하게 쓸 수 있습니다. 애매하거나 기록해야 하는 작업은 shell 문자열을 억지로 추측하지 않고 프로그램과 인자 배열을 받는 `click-gate inspect`를 사용합니다. 리뷰 안전망은 지원되는 로컬 Hook 경로만 다루며, 숨은 추론, hosted search, matcher 밖 connector, 사용자 정의 래퍼의 반복까지 제거하지는 못합니다.

## 실행 루프 없이 구현

계약 stage부터 리뷰·구현·검증까지 Hook은 다음 관찰 가능한 행동을 제한합니다.

| 안전망 | 동작 |
| --- | --- |
| 이미 얻은 근거 재사용 | 한 번 성공한 동일 구조화 읽기·검색은 범위 안의 코드 수정으로 근거가 오래되기 전까지 차단합니다. |
| 병렬 계획 금지 | workflow가 armed·staged·승인 후 미완료·review 상태인 동안 이후 turn에서도 `update_plan`을 거부합니다. 사용자 승인 bypass는 그 turn의 계획만 허용하고, 현재 revision 검증을 완료해야 이후 일반 계획이 다시 허용됩니다. |
| 전체 목록 재탐색 금지 | 루트의 `rg --files`, `find .`, 루트 재귀 목록, 동등한 Git 목록 스캔을 거부하고 경로를 좁힌 확인은 허용합니다. |
| 명령 의도를 명시 | 활성 상태에서 애매한 Bash는 거부하고 조회는 `inspect`, 구현 명령은 `mutate`, 최종 검사는 `verify`를 사용하도록 안내합니다. |
| 검증을 예산 안에 유지 | 최종 검사는 구조화된 `click-gate verify` 묶음으로 실행하고 승인한 규모 안에 들어야 합니다. |
| Browser 근거 제한 | Browser MCP는 주 증거로 명시한 경우만 3회·90초 대표 세션을 허용하며 긴 시간 진행과 완료 후 재호출을 거부합니다. |
| 로컬 서버 수명주기 소유 | 인식 가능한 개발 서버는 `click-gate service`로 시작·종료해 Click이 정확한 격리 자식을 정리합니다. |
| 제안과 승인 분리 | 같은 turn의 pass와 대체 stage를 거부하고, 정확한 digest는 다음 `UserPromptSubmit` 뒤에만 pass합니다. |

실패한 관찰 또는 출력이 48,000바이트를 넘은 관찰은 변경 없이 한 번 재시도할 수 있습니다. 소스가 수정되면 이전 근거가 오래됐을 수 있으므로 성공 관찰 기록을 초기화합니다. Hook 상태 변경에는 크로스 플랫폼 잠금을 사용해 병렬 결과 기록이 잘못된 “실행 중” 상태를 남기지 않게 합니다. Hook은 요청 digest와 본문을 포함하지 않는 메타데이터만 저장하며 명령과 출력은 저장하지 않습니다.

이 안전망은 도구 수준에서 동작하며 추론 토큰 제한이나 운영체제 샌드박스가 아닙니다. Hook은 숨은 추론, 자연어로만 쓴 계획, matcher 밖 connector나 hosted tool, 의미상 경계 준수 여부를 볼 수 없고, 허용된 사용자 코드 안에 여러 작업을 숨기는 것도 막지 못합니다.

### 구조화 capability

각 capability는 프로토콜 버전 `1`을 사용하고 실행 파일과 모든 인자를 분리합니다. 승인된 argv 배열은 새 POSIX session 또는 Windows process group에서 `shell=False`로 실행되므로 요청 안에 pipeline, redirection, command substitution, shell wrapper를 숨길 수 없고 자식의 group 대상 signal이 Codex 부모 group에 닿지 않습니다.

```text
click-gate inspect '{"version":1,"commands":[["git","status","--short"],["sed","-n","1,160p","src/app.py"]]}'
click-gate mutate '{"version":1,"argv":["python3","scripts/generate.py","--target","src"]}'
click-gate service '{"version":1,"action":"start","argv":["python3","-m","http.server","4173","--bind","127.0.0.1"]}'
click-gate service '{"version":1,"action":"stop"}'
```

`inspect`는 Hook이 허용한 제한된 읽기 전용 작업만 받습니다. Git 조회는 subcommand별 positive option policy를 사용하며 `git grep`, `git cat-file`, 임의의 `--format`/`--pretty` 출력, signature 출력 옵션, `git status -v/-vv`는 제외합니다. 허용된 Git 조회는 상속된 `GIT_*` 변수와 system/global Git config를 무시하고 안전한 log·diff 설정, pager·optional lock 비활성화, 지원되는 diff 출력의 `--no-ext-diff`·`--no-textconv`를 강제합니다. `mutate`는 정확한 계약 승인이 있어야 하고 이전 근거를 오래된 것으로 표시합니다. 인식 가능한 장시간 개발 서버는 `mutate`에서 거부하고 `service`로 시작합니다. Click supervisor가 정확한 자식과 process group을 소유해 명시적 stop, `SessionEnd`, 최대 2시간 제한에서 정리합니다. `apply_patch`, `Edit`, `Write` 같은 명확한 편집 도구는 shell envelope 없이 그대로 지원합니다. 잘못된 요청, shell interpreter, `kill`, `pkill`, `killall`, `taskkill`, `Stop-Process` 같은 직접 process-control 실행 파일은 fail-closed로 거부합니다. 허용된 사용자 정의 프로그램은 명시적인 process 작업을 내부에 숨길 수 있으므로 Click은 운영체제 sandbox가 아니라 workflow guardrail입니다. 정확한 schema와 적용 경계는 [capability protocol](skills/click/references/capability-protocol.md)에 있습니다.

SSH Git 조회는 **Experimental이며 원격 POSIX shell만 지원**합니다. 제한된 `git status`, `git rev-parse HEAD`, `git merge-base`, `git remote get-url`만 허용하고 사용자가 SSH option을 넣을 수 없습니다. 이미 알려진 host key를 요구하며 대화형 password, host-key 갱신, forwarding, local command, TTY를 끄고 connection·keepalive 제한으로 빠르게 실패합니다. 모르는 host, POSIX가 아닌 원격 shell, 응답하지 않는 server는 fail-closed입니다. 일반 원격 실행기나 보안 sandbox가 아닙니다.

## 자동 검증 예산

Click은 현재 위험과 저장소 근거로 충분한 최소 규모를 고릅니다. 사용자는 계약과 함께 그 규모를 승인하므로 검증 예산만 따로 다시 묻지 않습니다.

각 `done_when` 조건에는 충분하면서 가장 싼 주 증거를 정확히 하나만 지정합니다. 증거 하나가 여러 조건을 함께 충족해도 됩니다. Click은 현재 revision에 유효한 근거와 좁은 자동 검사를 먼저 사용하고, 더 싼 근거로 조건을 증명할 수 없을 때만 브라우저·수동·hosted·전체 suite·시간이 긴 end-to-end 검증을 사용합니다. 자동 검사 결과를 다른 화면에서 다시 증명하지 않으며 모든 조건에 현재 근거가 생기면 즉시 멈춥니다. 의미상 충분성은 Skill과 grader가 판단하지만, Hook은 표준 Browser MCP 경로를 직접 계측합니다. `done_when`의 주 증거에 브라우저가 명시된 경우에만 3회 호출·측정 시간 90초의 직렬 대표 세션을 허용하며, 30초 초과 tool timeout, 5초 초과 명시적 wait, 완료 후 재호출을 거부합니다. 이후 수정은 브라우저 근거를 초기화하며 matcher 밖 connector는 이 계측 범위 밖입니다.

| 규모 | 주로 쓰는 경우 | 자동 상한 |
| --- | --- | ---: |
| `quick` | 작고 국소적이며 되돌리기 쉬운 변경 | 1단위 |
| `focused` | 범위가 정해진 일반 기능 또는 수정 | 4단위 |
| `full` | 결제·인증·삭제·마이그레이션·공개 계약·경계를 넘는 동시성 | 10단위 |

`targeted` 검사는 1단위, `broad` 검사는 3단위, `deep` 검사는 5단위입니다. 제출한 값을 그대로 비용으로 믿지 않습니다. Hook은 runner 종류를 먼저 찾고 실제 범위를 따로 추론합니다. 정확한 파일이나 test node 하나는 targeted일 수 있지만 `-k`·regex filter, 여러 파일·package, directory, 전체 suite는 최소 broad입니다. integration·security node 하나는 broad이고 해당 suite 전체는 deep입니다. 더 낮게 제출한 검사는 자동으로 올린 뒤 총비용을 계산합니다. 상한일 뿐 반드시 모두 쓸 목표가 아닙니다.

Click은 항목마다 명시적인 argv 검사 하나를 다음 runner에 전달합니다.

```text
click-gate verify '{"version":1,"checks":[{"argv":["python3","-m","unittest","discover","-s","tests","-q"],"class":"broad"},{"argv":["git","diff","--check"],"class":"targeted"}]}'
```

Hook이 제출한 class를 검증·정규화하고 승인된 최종 묶음을 shell 없이 실행해 실제 종료 코드를 기록합니다. Python 검증은 pytest·unittest·coverage의 명시적 module runner를 받으며 Windows의 `py -3 -m ...`도 지원하지만, Python `-c`와 직접 Python 스크립트는 거부합니다. 정확한 파일을 지정한 `node --check`·`node --test`, `uv run pytest`, `npm run lint`, `npm run build`, `ruff check`, `mypy`, `tsc --noEmit`, `cargo check`, `cargo clippy`, `go vet` 같은 형태도 인식해 실제 범위에 맞춰 계산합니다. 전체 `node --test`는 broad이며 Node eval·print는 검증으로 받지 않습니다. 예전 shell 문자열 `commands` 형식은 이전 방법을 안내하며 거부합니다. 일시적인 실패라면 같은 묶음을 변경 없이 한 번 재시도할 수 있고, 그 뒤에는 범위 안의 수정이 필요합니다. 이후 소스를 수정하면 앞선 성공 결과가 오래된 것으로 간주되어 같은 묶음을 다시 실행할 수 있습니다.

Git worktree에서는 batch 전의 tracked content와 기존 **non-ignored untracked** content를 snapshot합니다. 보호한 내용이 검증 도중 바뀌면 거짓 성공으로 기록하지 않고 batch를 stale 실패로 처리하며 mutation revision을 올립니다. 검증 뒤 새로 생긴 non-ignored untracked 경로는 모두 보고하며, 경로 종류와 무관하게 workspace 변경으로 처리해 stale 실패시키고 mutation revision을 올립니다. source·config처럼 의심스러운 분류는 메시지를 더 명확하게 보여주는 데만 사용합니다. 검증 중 생성이 예상되는 산출물은 Git ignore 대상으로 두거나 승인된 mutation 단계에서 미리 생성해야 합니다. Git에서 ignored인 경로는 이 snapshot으로 볼 수 없습니다. Git 밖에서는 content-diff 안전망을 사용할 수 없지만 argv 검증, shell 없는 실행, revision 상태 검사는 계속 적용됩니다.

최소 class 추론은 단순한 비용 축소 제출을 막습니다. 알 수 없는 검증형 이름의 사용자 정의 래퍼는 보수적으로 `deep`으로 계산하고 인식하지 못한 명령은 거부하지만, 허용된 프로그램 내부에 비싼 작업을 숨길 가능성까지 측정하지는 못합니다. 따라서 보안·자원 샌드박스가 아니며 선택한 테스트의 의미가 충분하다고 증명하지도 않습니다.

## 최소설계가 중요한 것을 빼지는 않습니다

최소설계는 형식과 반복을 줄이는 것이지 필요한 안전 조건을 지우는 것이 아닙니다.

| 관심사 | 필요할 때 계약이 지키는 것 |
| --- | --- |
| 동시성 | 경합 동작, 중복 실행, 멱등성 |
| 상태 | 허용 상태 전이, 저장 시점, 소유권 |
| 실패 | 부분 실패, 재시도, 복구, 외부 오류 |
| 보안 | 인증, 권한, 비밀정보, 개인정보 경계 |
| 호환성 | 기존 API, 데이터, 상태값, 사용자 동작 |

중요한 조건은 `must_hold`에, 구체적인 상태·실패 의미는 필요할 때 `build.semantics`에, 관찰 가능한 완료 근거는 `verification.done_when`에 둡니다. Hook은 계약 형식·승인 순서·digest 동일성·보이는 반복·보이는 검증 범위를 지킵니다. 구현이 아키텍처적으로 옳고 의미까지 정확하다고 Hook 하나로 증명하는 것은 아닙니다.

정확히 말하면 Click Hook은 새 마이크로서비스·queue·추상화가 과설계인지 의미적으로 판정하지 않습니다. Skill과 의미 grader가 근거 있는 최소설계를 선호하고, Hook은 설계를 계속 불리는 원인이 되기 쉬운 반복 계획·저장소 전체 재탐색·반복 검증 루프를 차단합니다. 제품 주장은 이 관찰 가능한 적용 경계로 제한합니다.

## 누구를 위한 플러그인인가요?

Click의 핵심 대상은 다음 두 그룹입니다.

- 성능 좋은 모델의 재계획·반복 탐색·과도한 검증에 피로를 느끼는 사용자
- 최소설계 뒤 끊지 않고 MVP·내부 도구·자동화·명확한 기능을 구현하고 싶은 사용자

특히 다음 작업에 잘 맞습니다.

- 기존 API를 유지해야 하는 브라운필드 기능;
- 멱등성·동시성·상태 전이·실패 복구가 있는 작업;
- 안전 경계가 명확한 마이그레이션이나 영향도가 큰 변경;
- 다른 사람이나 에이전트가 같은 의미를 구현해야 하는 인수인계;
- 최소 계획 뒤에 끊지 않고 구현하고 싶은 MVP·내부 도구·자동화.

작고 명확하고 되돌리기 쉬운 수정이나 탐색 작업이며 승인 경계를 남길 필요가 없다면 Manual 또는 현재 turn 우회가 더 간단합니다. 법률·규제·보안·운영상 되돌리기 어려운 작업에서 Click은 전문가 검토, 권한 확인, 배포 통제를 대신하지 않습니다.

## 근거와 솔직한 한계

v0.19.0 소스는 결정적 suite를 release gate로 사용합니다. 영구 모드, turn 분리 승인, active-contract 잠금, 읽기·계획 anti-loop, 범위 중심 로컬 검증, Browser 주 증거 할당과 예산, 관리형 서버 시작·종료, Node 파일 검사, 강화된 Git 조회, process 격리, 검증 중 workspace 변경 감지, Browser A/B runtime metric, 배포 일관성, 저장소 정책을 다룹니다. 필수 CI는 Linux·macOS·Windows에서 suite를 실행하고 Ubuntu에서는 plugin·marketplace·Click/Fix Skill·Python compilation·whitespace도 검증합니다.

저장소에는 version 17 golden case, 의미 grader, A/B runner도 포함되어 있습니다. A/B suite는 고정된 self-hosted 작업 6개, 조건 3개, 조건별 무작위 순서 5회, `gpt-5.6-sol`의 `max` 추론으로 설정되어 있습니다. 유료 호출 전에 source checkout이 clean인지와 suite·manifest 버전이 같은지 검사하고, 정확한 Click commit을 임시 local marketplace에 clone하여 임시 `CODEX_HOME`에 설치합니다. candidate는 실행자의 실제 사용자 config가 아니라 이 격리 config만 읽고, runner는 발견한 다른 plugin을 모두 명시적으로 끄며 trial별 Click 상태도 분리합니다. plugin이 필요 없는 judge만 `--ignore-user-config`를 사용합니다. summary에는 Codex 버전, Click 버전·commit, 임시 config 경로, OS, Python, installed plugin, 조건별 active plugin을 기록하고 임시 runtime은 종료 뒤 삭제합니다. root inventory metric은 문자열 검색 대신 Hook의 argv parser를 재사용합니다. 정확성·토큰·경과 시간·완료 tool item·성공 명령 중복·root inventory 반복·plan item·검증 명령·Browser 호출 수·Browser 총시간·긴 타이머 호출의 분포와 no-plugin baseline 대비 paired delta를 기록합니다. 총 90개 condition trial은 유료 모델 시간과 비용이 들기 때문에 설치나 CI에서 **자동 실행하지 않습니다**.

이는 평가 기반 시설이지 benchmark 결과가 아닙니다. 실제로 실행하고 사람이 표본 보정한 뒤, 서로 관련 없는 여러 실제 저장소에서도 반복하기 전까지 Click이 프로젝트 전반의 성공률·정확도·시간·토큰·과설계를 개선한다고 주장하지 않습니다. 저장된 v0.5.0 단일 pilot은 과거 실패 근거일 뿐 v0.19.0의 효과 증거가 아닙니다.

Click이 이 분야에서 최초이거나 유일하다고 주장하지 않습니다. spec-driven·autonomous loop·승인 게이트 도구와 겹치지만, 영구 선택 한 번·축약 계약 하나·승인 한 번·One-shot 구현·관찰 가능한 anti-loop 안전망·최종 검증 예산 하나에 의도적으로 좁게 집중합니다.

개발자 커뮤니티에 바로 맞춰 쓸 수 있는 홍보 초안은 [COMMUNITY_POSTS.md](COMMUNITY_POSTS.md)에 있습니다.

<details>
<summary>저장소 구조와 로컬 검증</summary>

```text
.codex-plugin/plugin.json             플러그인 매니페스트
.agents/plugins/marketplace.json      GitHub 마켓플레이스 항목
skills/click/                         One-shot 설계·구현 Skill
skills/click/references/modes.md      영구 모드와 코드 리뷰 동작
skills/click/references/capability-protocol.md  구조화 runner schema
skills/fix/                           축약 수정 Skill
hooks/click_gate.py                   계약·capability·anti-loop·예산 안전망
hooks/hooks.json                      라이프사이클 Hook 설정
evals/                                golden case·A/B runner·의미 grader
tests/                                Hook·grader·정책 결정적 테스트
scripts/validate_distribution.py     저장소 자체 release validator
COMMUNITY_POSTS.md                    영문·국문 커뮤니티 홍보 초안
LICENSE                               MIT 라이선스
```

```bash
python3 scripts/validate_distribution.py
python3 -m compileall -q hooks evals scripts tests
python3 -m unittest discover -s tests -v
git diff --check
```

A/B runner는 실행자가 다음처럼 유료 실행을 명시적으로 확인하지 않으면 model call을 시작하지 않습니다.

```bash
python3 evals/run_ab.py --results /path/to/results --execute-paid-runs
```

</details>

<details>
<summary>비슷한 접근</summary>

| 프로젝트 | 겹치는 부분 | Click이 더 좁게 집중하는 부분 |
| --- | --- | --- |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | 명세·계획·작업·구현 | 지속적인 다중 명령 명세 대신 축약 계약 하나와 승인 한 번 |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | AI 코딩 전 합의 | 프로젝트 로컬 명세 저장소 없이 대상 저장소 밖에 digest만 보관 |
| [Kiro Specs](https://kiro.dev/docs/cli/v3/specs/) | 요구사항·설계·작업·검증 실행 | 전체 계약 한 번 검토 뒤 One-shot 구현 |
| [Agentic SDLC Codex Plugin](https://github.com/aantenore/agentic-sdlc-codex-plugin) | hash로 묶인 제안과 승인 | 더 넓은 SDLC 거버넌스보다 작은 구현 전 경계 |

이 표는 제한된 비교이며 신규성에 대한 전수 조사가 아닙니다.

</details>

## 라이선스

Click은 [MIT 라이선스](LICENSE)로 배포됩니다.
