# Click community launch posts

These drafts deliberately describe implemented behavior, not unmeasured gains in accuracy, speed, or token use.

## English — Reddit, Discord, forum

### Title

**I built a Codex plugin that binds AI execution to approved intent and evidence**

### Post

Powerful coding models can finish difficult work, but they can also spend too much time rewriting the plan, rereading the same files, rescanning the repository, and running one more test suite.

I built **Click**, an MIT-licensed Codex plugin with a deliberately small workflow:

> Approve the intent once. Bind execution to it. Return evidence for what actually ran.

On first use, you choose **Always ON** or **Manual**.

- Always ON applies Click only to software-changing requests.
- Manual applies it when you mention `@Click`.
- Questions, explanations, and simple read-only inspection stay normal.
- Code review needs no build contract. The read-only guard keeps mutation blocked while fresh repeated observations and distinct broad inventories remain available with non-blocking reuse or narrowing guidance.

For a code change, Click turns the request and repository context into one compact contract: outcome, boundary, must-hold behavior, build approach, verification scale, and a plain-language explanation. It stages and shows that contract, then requires a later user turn for the one approval. After that, the Hook rejects replacement contracts and unauthorized mutations, binds one-use runners to exact requests, and records revision-bound evidence. Plan tools remain available as non-blocking, non-authoritative guidance.

Click v0.21 binds each approved completion source to current-revision Hook state. Every local argv check names the exact evidence ID it proves; Browser work is observed and then explicitly finalized; hosted, manual, and existing sources remain explicit attestations rather than independently proven external events. Once every declared source is current and no managed service remains active, Click stops. A contract with no argv source no longer runs an unrelated local test merely for ceremony. This is a local workflow guard—not a security sandbox or a measured claim of faster or more accurate results.

This is not a claim that Click invents better architecture than the model. The model already knows how to design software. Click's job is narrower: bind observable execution to one approved boundary and return evidence without treating model workflow strategy as authority.

I built it for:

- users who need approval, side-effect authority, and completion evidence to survive long autonomous runs;
- MVPs, internal tools, automations, and clearly bounded features where minimum design followed by continuous implementation matters more than a large spec process.

What is verified: deterministic Hook behavior, contract structure, and the repository test suite. What is not yet proven: that Click improves accuracy, total time, or token use across real projects. Those product-level effects require independent measurement on unrelated real repositories.

Install:

```bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

Already using Click? v0.21 requires an explicit refresh and reinstall:

```bash
codex plugin marketplace upgrade click
codex plugin add click@click
```

Restart the ChatGPT desktop app and start a new task after reviewing the updated Hook.

Repository: https://github.com/grapefruit0205/click

I would especially value feedback from people who need to leave an agent running after one approval. Which authorization or evidence guarantee is still missing, and which advisory feels too opinionated?

## English — Show HN

### Title

**Show HN: Click – bind AI execution to approved intent and return evidence**

### Opening

I built Click, an MIT-licensed Codex plugin for a narrower runtime problem: a capable model can implement the feature, but approval, side-effect authority, and completion evidence still need guarantees outside the model.

Click asks for one compact, plain-language approval before code changes, then uses local lifecycle Hooks to bind a short opaque `contract_id` to the staged digest, reject replacement contracts and unauthorized mutations, and record only the approved completion evidence needed for the current revision. The later approval sends only that id instead of reconstructing the contract JSON. Versioned argv-based inspect, mutate, service, and verify runners make supported command intent explicit and run without a shell. Plan tools remain non-blocking and non-authoritative. Its Always ON mode applies only to software mutations; questions and simple inspection remain normal, while code review gets a separate read-only guard without a build contract.

It is intentionally smaller than a full spec-driven workflow. I am not claiming measured accuracy or token improvements yet; the current evidence is deterministic enforcement and tests. I would like feedback on whether this boundary-first, anti-loop workflow solves a real problem or merely moves prompt ceremony into a plugin.

Repository: https://github.com/grapefruit0205/click

## 한국어 — 개발자 커뮤니티

### 제목

**승인한 의도에 AI 실행을 결속하고 증거를 돌려주는 Codex 플러그인을 만들었습니다**

### 본문

성능 좋은 코딩 모델은 어려운 기능도 구현할 수 있지만, 이미 정한 계획을 다시 만들고 같은 파일을 다시 읽고 저장소 전체를 다시 훑고 테스트를 하나 더 돌리느라 오래 걸릴 때가 있습니다.

그래서 **Click**이라는 MIT 라이선스 Codex 플러그인을 만들었습니다.

> 의도를 한 번 승인하고, 실행을 그 의도에 결속하고, 실제 수행 증거를 돌려받습니다.

처음 사용할 때 **Always ON** 또는 **Manual**을 한 번 선택합니다.

- Always ON은 소프트웨어를 실제로 바꾸는 요청에만 적용됩니다.
- Manual은 `@Click`을 멘션했을 때만 적용됩니다.
- 질문·설명·단순 조회는 평소처럼 처리합니다.
- 코드 리뷰는 구현 계약 없이 진행합니다. 읽기 전용 안전망은 mutation을 막고 동일 관찰을 재사용하며, 서로 다른 broad inventory에는 비차단 범위 축소 안내를 제공합니다.

코드 변경 요청에서는 저장소 맥락을 바탕으로 결과, 범위, 반드시 지킬 동작, 최소 구현 경로, 검증 규모, 쉬운 설명을 하나의 축약 계약으로 만듭니다. 계약을 stage해 보여준 뒤 다음 사용자 turn의 승인 한 번을 기다립니다. 승인하면 Hook이 대체 계약과 무권한 mutation을 막고, one-use runner를 정확한 요청에 결속하며, revision에 결속된 evidence를 기록합니다. plan tool은 비차단·비권한 advisory로 계속 사용할 수 있습니다.

Click v0.21은 승인한 완료 근거를 현재 코드 revision의 Hook 상태와 각각 연결합니다. local argv check는 자신이 증명하는 evidence ID를 정확히 지정하고, Browser 작업은 관찰된 뒤 명시적으로 finalize합니다. hosted·manual·existing은 외부 사실을 독립적으로 증명하는 장치가 아니라 명시적인 attestation으로 남습니다. 선언된 근거가 모두 current이고 관리 서비스가 활성 상태가 아니면 즉시 멈추며, argv 근거가 없는 계약에 형식적인 local test를 추가하지 않습니다. 모든 도구를 완벽히 막는 보안 샌드박스나 더 빠르고 정확하다는 측정된 주장은 아닙니다.

Click이 모델보다 더 좋은 아키텍처를 발명한다고 주장하지는 않습니다. 모델은 이미 소프트웨어 설계를 할 수 있습니다. Click의 역할은 더 좁습니다. **사용자가 승인한 경계에 관찰 가능한 실행을 결속하고 실제 수행 evidence를 돌려주는 것**입니다.

주요 대상은 다음과 같습니다.

- 승인 한 번 후에도 권한·side effect·완료 evidence가 보존되는 장시간 자율 실행이 필요한 사용자
- 큰 명세 절차보다 최소설계 뒤 바로 구현하는 MVP·내부 도구·자동화·명확한 기능 추가가 중요한 사용자

현재 결정적 Hook 동작, 계약 구조, 저장소 테스트는 검증했습니다. 하지만 실제 프로젝트 전반에서 정확도·전체 시간·토큰이 개선되는지는 아직 증명하지 않았으며, 서로 관련 없는 실제 저장소에서 독립적으로 측정해야 합니다.

설치:

```bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
```

기존 Click 사용자는 v0.21을 사용하려면 명시적으로 마켓플레이스를 갱신하고 플러그인을 다시 설치해야 합니다.

```bash
codex plugin marketplace upgrade click
codex plugin add click@click
```

갱신된 Hook을 검토한 뒤 ChatGPT 데스크톱 앱을 다시 시작하고 새 작업을 시작하세요.

저장소: https://github.com/grapefruit0205/click

비슷한 문제를 겪어 보셨다면 어떤 안전망은 유용하고 어떤 부분은 지나치게 제한적인지 솔직한 의견을 듣고 싶습니다.
