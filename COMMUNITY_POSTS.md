# Click community launch posts

These drafts deliberately describe implemented behavior, not unmeasured gains in accuracy, speed, or token use.

## English — Reddit, Discord, forum

### Title

**I built a Codex plugin for people tired of agents replanning, rereading, and over-verifying**

### Post

Powerful coding models can finish difficult work, but they can also spend too much time rewriting the plan, rereading the same files, rescanning the repository, and running one more test suite.

I built **Click**, an MIT-licensed Codex plugin with a deliberately small workflow:

> Approve the boundary once. Build without replanning. Verify once.

On first use, you choose **Always ON** or **Manual**.

- Always ON applies Click only to software-changing requests.
- Manual applies it when you mention `@Click`.
- Questions, explanations, and simple read-only inspection stay normal.
- Code review needs no build contract, but a read-only guard blocks repeated successful reads and repeat repository-wide inventory.

For a code change, Click turns the request and repository context into one compact contract: outcome, boundary, must-hold behavior, build approach, verification scale, and a plain-language explanation. It stages and shows that contract, then requires a later user turn for the one approval. After that, the Hook rejects replacement contracts, matched replanning, repeated successful observations, repository-wide rescans, and verification outside the approved budget.

The v0.16 candidate tightens the places where a guard can become either too loose or too annoying. An activated Manual contract now remains mutation-locked across later turns until the exact contract is passed. Verification cost uses runner kind and actual scope, so broad filters and many files cannot masquerade as one targeted test, while one exact integration test is no longer forced to deep. Common Windows, uv, lint, build, typecheck, Cargo, and Go checks are recognized. Git-backed checks warn about every new non-ignored path and fail stale for obvious new source, configuration, or migration paths. The versioned argv-based `inspect`, `mutate`, and `verify` requests still execute accepted commands without a shell. This is a local workflow guard—not a security sandbox or a claim of perfect tool coverage.

This is not a claim that Click invents better architecture than the model. The model already knows how to design software. Click's job is narrower: keep the agent inside one visible boundary and stop observable execution loops after approval.

I built it for:

- users of high-capability models who are tired of planning and verification churn;
- MVPs, internal tools, automations, and clearly bounded features where minimum design followed by continuous implementation matters more than a large spec process.

What is verified: deterministic Hook behavior, contract structure, and the repository test suite. What is not yet proven: that Click improves accuracy, total time, or token use across real projects. Those product-level effects require independent measurement on unrelated real repositories.

Install:

```bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

Repository: https://github.com/grapefruit0205/click

I would especially value feedback from people who have seen strong reasoning models get stuck in re-planning, repeated repository exploration, or excessive verification. Which guard feels useful, and which one feels too restrictive?

## English — Show HN

### Title

**Show HN: Click – approve a coding boundary once, then block replanning and repeated exploration**

### Opening

I built Click, an MIT-licensed Codex plugin for a specific failure mode I keep seeing with capable coding agents: the model can implement the feature, but keeps revisiting the plan, rereading the same evidence, rescanning the repository, and expanding verification.

Click asks for one compact, plain-language approval before code changes, then uses local lifecycle Hooks to hold the staged contract digest, reject replacement plans, deduplicate successful structured observations, block repository-wide rescans, and meter one final verification batch. Versioned argv-based inspect, mutate, and verify runners make supported command intent explicit and run without a shell. Its Always ON mode applies only to software mutations; questions and simple inspection remain normal, while code review gets a separate read-only anti-loop guard without a build contract.

It is intentionally smaller than a full spec-driven workflow. I am not claiming measured accuracy or token improvements yet; the current evidence is deterministic enforcement and tests. I would like feedback on whether this boundary-first, anti-loop workflow solves a real problem or merely moves prompt ceremony into a plugin.

Repository: https://github.com/grapefruit0205/click

## 한국어 — 개발자 커뮤니티

### 제목

**성능 좋은 코딩 모델의 재계획·반복 탐색·과도한 검증을 막는 Codex 플러그인을 만들었습니다**

### 본문

성능 좋은 코딩 모델은 어려운 기능도 구현할 수 있지만, 이미 정한 계획을 다시 만들고 같은 파일을 다시 읽고 저장소 전체를 다시 훑고 테스트를 하나 더 돌리느라 오래 걸릴 때가 있습니다.

그래서 **Click**이라는 MIT 라이선스 Codex 플러그인을 만들었습니다.

> 구현 경계를 한 번 승인하고, 다시 계획하지 않고, 한 번만 검증합니다.

처음 사용할 때 **Always ON** 또는 **Manual**을 한 번 선택합니다.

- Always ON은 소프트웨어를 실제로 바꾸는 요청에만 적용됩니다.
- Manual은 `@Click`을 멘션했을 때만 적용됩니다.
- 질문·설명·단순 조회는 평소처럼 처리합니다.
- 코드 리뷰는 구현 계약 없이 진행하지만, 읽기 전용 안전망으로 성공한 동일 조회와 저장소 전체 재탐색 반복을 막습니다.

코드 변경 요청에서는 저장소 맥락을 바탕으로 결과, 범위, 반드시 지킬 동작, 최소 구현 경로, 검증 규모, 쉬운 설명을 하나의 축약 계약으로 만듭니다. 계약을 stage해 보여준 뒤 다음 사용자 turn의 승인 한 번을 기다립니다. 승인하면 Hook이 대체 계약, 일치하는 재계획, 성공한 동일 조회, 저장소 전체 재탐색, 검증 예산 밖의 광범위 테스트를 제한합니다.

v0.16 후보는 안전망이 너무 느슨하거나 지나치게 답답해지는 지점을 함께 줄였습니다. 한 번 활성화한 Manual 계약은 정확한 계약을 pass할 때까지 다음 turn에서도 mutation을 막습니다. 검증 비용은 runner 종류와 실제 범위를 나눠 보므로 넓은 filter나 여러 파일을 targeted 하나로 속일 수 없고, 정확한 integration test 하나를 무조건 deep으로 과차단하지도 않습니다. Windows·uv·lint·build·typecheck·Cargo·Go의 일반 검사 형식을 지원합니다. Git 기반 검증은 새 non-ignored 경로를 모두 경고하고 명백한 source·config·migration 신규 경로는 stale 실패시킵니다. argv 기반 `inspect`·`mutate`·`verify`는 계속 허용 명령을 shell 없이 실행합니다. 모든 도구를 완벽히 막는 보안 샌드박스는 아닙니다.

Click이 모델보다 더 좋은 아키텍처를 발명한다고 주장하지는 않습니다. 모델은 이미 소프트웨어 설계를 할 수 있습니다. Click의 역할은 더 좁습니다. **승인한 경계를 눈에 보이게 고정하고, 승인 뒤 관찰 가능한 실행 루프를 줄이는 것**입니다.

주요 대상은 다음과 같습니다.

- 성능 좋은 모델의 재계획·반복 탐색·과도한 검증에 피로를 느끼는 사용자
- 큰 명세 절차보다 최소설계 뒤 바로 구현하는 MVP·내부 도구·자동화·명확한 기능 추가가 중요한 사용자

현재 결정적 Hook 동작, 계약 구조, 저장소 테스트는 검증했습니다. 하지만 실제 프로젝트 전반에서 정확도·전체 시간·토큰이 개선되는지는 아직 증명하지 않았으며, 서로 관련 없는 실제 저장소에서 독립적으로 측정해야 합니다.

설치:

```bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

저장소: https://github.com/grapefruit0205/click

비슷한 문제를 겪어 보셨다면 어떤 안전망은 유용하고 어떤 부분은 지나치게 제한적인지 솔직한 의견을 듣고 싶습니다.
