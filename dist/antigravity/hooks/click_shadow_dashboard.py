#!/usr/bin/env python3
"""Authenticated loopback viewer for non-authoritative Shadow telemetry."""

from __future__ import annotations

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from typing import Any, Callable
from urllib.parse import urlsplit

if __package__:
    from . import (
        click_contract_state,
        click_dashboard_projection,
        click_process,
        click_runtime_state,
        click_state,
    )
else:  # Executed directly from the bundled hooks directory.
    import click_contract_state
    import click_dashboard_projection
    import click_process
    import click_runtime_state
    import click_state


DASHBOARD_FIELD = "shadow_dashboard"
DASHBOARD_STATE_VERSION = 1
DASHBOARD_STATUSES = frozenset(
    {"idle", "starting", "running", "stopping", "stopped", "failed"}
)
DASHBOARD_ACTIONS = frozenset({"start", "stop", "status"})
START_TIMEOUT_SECONDS = 8
STOP_TIMEOUT_SECONDS = 8
MAX_LIFETIME_SECONDS = 2 * 60 * 60
POLL_SECONDS = 0.1

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_INSTANCE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_DASHBOARD_FIELDS = frozenset(
    {
        "version",
        "status",
        "instance_id",
        "runner_token_digest",
        "runner_claimed_at",
        "access_token_digest",
        "port",
        "pid",
        "started_at",
        "stop_requested",
        "last_error",
    }
)

RenderCommand = Callable[[list[str]], str]


HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Click Incremental Verification</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <a class="skip" href="#main">대시보드로 건너뛰기</a>
  <header>
    <div class="brand"><span class="mark" aria-hidden="true">C</span><div><b>Click</b><span>Incremental Verification</span></div></div>
    <div class="live"><i aria-hidden="true"></i><span id="connection">연결 중</span></div>
  </header>
  <main id="main">
    <section class="hero" aria-labelledby="title">
      <div><p class="eyebrow">INCREMENTAL VERIFICATION</p><h1 id="title">이번 변경에서<br>무엇만 다시 검사했나요?</h1><p id="taskline">현재 Click 상태를 불러오는 중…</p></div>
      <div class="notice"><strong id="observerTitle">Observer 확인 중</strong><span id="observerBody">Dashboard와 Observer는 서로 독립적으로 동작합니다.</span></div>
    </section>
    <section class="metrics" aria-label="실제 증분 검증 결과">
      <article><span>현재 유효한 검사</span><strong id="currentChecks">—</strong><small>현재 revision에서 통과 상태</small></article>
      <article><span>실제로 실행한 검사</span><strong id="executedChecks">—</strong><small>불확실한 검사는 실행에 포함</small></article>
      <article><span>안전하게 재사용</span><strong id="reusedChecks">—</strong><small>Click 권한 규칙을 통과한 결과</small></article>
      <article><span>최근 실행 기준 추정 회피</span><strong id="estimatedAvoided">—</strong><small>실측 절약 시간이 아닌 추정값</small></article>
    </section>
    <section class="metric-split" aria-label="실제 결과와 Shadow 텔레메트리">
      <article class="panel compact"><p class="eyebrow">실제 증분 검증</p><h2>Authoritative reuse</h2><div class="statline"><span>Exact / Dependency / Safe change</span><strong id="reuseBreakdown">—</strong></div><div class="statline"><span>실제 실행 시간</span><strong id="executedDuration">—</strong></div></article>
      <article class="panel compact shadow-card"><p class="eyebrow">SHADOW TELEMETRY · 권한 없음</p><h2>잠재 재사용 관찰</h2><div class="statline"><span>후보 / 확인 / 모순</span><strong id="shadowBreakdown">—</strong></div><div class="statline"><span>잠재 시간 / Observer overhead</span><strong id="shadowTiming">—</strong></div></article>
    </section>
    <section class="workspace">
      <article class="panel checks"><div class="panel-title"><div><p class="eyebrow">검사 목록</p><h2>실행 또는 재사용 결과</h2></div><span id="sourceCount" class="count">0</span></div><div id="sources" class="source-list"></div></article>
      <article class="panel map-panel"><div class="panel-title"><div><p class="eyebrow">EVIDENCE MAP</p><h2>선택한 검사가 읽은 입력</h2></div><span id="mapMeta" class="muted"></span></div><div id="emptyMap" class="empty">검사를 선택하면 현재 입력과 이전 baseline의 관계를 보여줍니다.</div><svg id="map" role="img" aria-label="선택한 검사의 Evidence Map"></svg></article>
    </section>
    <section class="panel explanation" aria-live="polite"><p class="eyebrow">판정 이유</p><h2 id="whyTitle">검사를 선택하세요</h2><p id="whyBody">왜 실행했거나 재사용했는지 사람말로 설명합니다.</p><div id="limits"></div></section>
  </main>
  <footer><span>로컬 전용 · 읽기 전용 · 파일 내용 미노출</span><span id="updated">아직 갱신되지 않음</span></footer>
  <script src="/app.js" defer></script>
</body>
</html>
"""

CSS = """:root{color-scheme:dark;--bg:#0b0d12;--panel:#121722;--line:#253044;--text:#f5f7fb;--muted:#8e9bb0;--green:#73e6a2;--amber:#ffca6a;--red:#ff7b82;--blue:#79b8ff;--violet:#ad8cff;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 12% -8%,#1d2940 0,transparent 32%),var(--bg);color:var(--text);min-height:100vh}.skip{position:absolute;left:-999px}.skip:focus{left:16px;top:12px;z-index:9;background:#fff;color:#000;padding:8px}header,footer{height:72px;padding:0 max(24px,calc((100vw - 1320px)/2));display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}footer{height:auto;min-height:56px;border:0;border-top:1px solid var(--line);color:var(--muted);font-size:12px}.brand{display:flex;gap:12px;align-items:center}.brand div{display:grid}.brand span{color:var(--muted);font-size:12px}.mark{display:grid;place-items:center;width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,var(--violet),var(--blue));color:#080a0e!important;font-weight:900;font-size:20px!important}.live{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px}.live i{width:8px;height:8px;border-radius:50%;background:var(--amber);box-shadow:0 0 14px var(--amber)}.live.ok i{background:var(--green);box-shadow:0 0 14px var(--green)}main{max-width:1320px;margin:auto;padding:44px 24px 56px}.hero{display:flex;justify-content:space-between;align-items:end;gap:32px;margin-bottom:28px}.eyebrow{margin:0 0 8px;color:var(--blue);font-size:10px;font-weight:800;letter-spacing:.16em}h1{margin:0;font-size:clamp(34px,5vw,64px);line-height:1;letter-spacing:-.055em}h2{font-size:18px;margin:0}#taskline{color:var(--muted);margin:14px 0 0}.notice{max-width:330px;border:1px solid #4f4128;background:#1c1811;border-radius:14px;padding:14px 16px;display:grid;gap:4px}.notice strong{color:var(--amber)}.notice span{color:#c7b991;font-size:12px;line-height:1.5}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}.metrics article,.panel{background:linear-gradient(180deg,rgba(24,31,45,.96),rgba(15,20,29,.96));border:1px solid var(--line);border-radius:18px}.metrics article{padding:20px;display:grid;gap:8px}.metrics span,.metrics small{color:var(--muted);font-size:11px}.metrics strong{font-size:28px;letter-spacing:-.04em}.workspace{display:grid;grid-template-columns:380px 1fr;gap:12px}.panel{padding:22px}.panel-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}.count{display:grid;place-items:center;min-width:28px;height:28px;border-radius:9px;background:#202a3a;color:var(--blue);font-weight:800}.muted{color:var(--muted);font-size:11px}.source-list{display:grid;gap:9px;max-height:490px;overflow:auto}.source{appearance:none;width:100%;text-align:left;color:inherit;background:#0f141e;border:1px solid #263146;border-radius:13px;padding:14px;cursor:pointer}.source:hover,.source:focus-visible,.source.active{border-color:var(--blue);outline:none}.source-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}.source strong{font-size:14px}.pill{font-size:10px;padding:4px 7px;border-radius:999px;background:#202a3a;color:var(--muted)}.pill.reuse-candidate,.pill.confirmed-candidate{color:var(--green);background:#14291e}.pill.rerun-required,.pill.contradicted-candidate{color:var(--red);background:#31191d}.source p{margin:0;color:var(--muted);font-size:11px}.map-panel{min-height:550px;overflow:hidden;position:relative}.empty{height:420px;display:grid;place-items:center;text-align:center;color:var(--muted);padding:40px}svg{width:100%;height:440px;display:none}.edge{stroke:#34435d;stroke-width:1.2}.node text{fill:var(--text);font-size:11px}.node rect{fill:#101722;stroke:#31405a;rx:9}.node.source rect{stroke:var(--blue);fill:#132033}.node.changed rect{stroke:var(--red);fill:#2b171b}.explanation{margin-top:12px;min-height:138px}.explanation p:not(.eyebrow){color:var(--muted);line-height:1.6;margin-bottom:0}.tag{display:inline-block;margin:12px 6px 0 0;padding:5px 8px;border-radius:8px;background:#292319;color:var(--amber);font-size:11px}@media(max-width:900px){.metrics{grid-template-columns:repeat(2,1fr)}.workspace{grid-template-columns:1fr}.hero{align-items:start;flex-direction:column}.notice{max-width:none;width:100%}}@media(max-width:520px){main{padding:30px 14px}.metrics{grid-template-columns:1fr 1fr}.metrics article{padding:15px}.metrics strong{font-size:22px}header,footer{padding-left:14px;padding-right:14px}.panel{padding:16px}}@media(prefers-reduced-motion:no-preference){.live i{animation:pulse 2s infinite}@keyframes pulse{50%{opacity:.45}}}
"""

CSS += """.metric-split{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}.compact{padding:18px 20px}.compact h2{margin-bottom:14px}.statline{display:flex;justify-content:space-between;gap:18px;padding-top:10px;margin-top:10px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}.statline strong{color:var(--text);text-align:right}.shadow-card{border-color:#3d3459}.pill.reused{color:var(--green);background:#14291e}.pill.rerun{color:var(--red);background:#31191d}.pill.pending{color:var(--amber);background:#292319}.source .reason{margin-top:7px;color:#c3ccda}.node.changed rect{stroke:var(--red);fill:#2b171b}.node.baseline-only rect{stroke:var(--amber);fill:#292319}.node.newly-observed rect{stroke:var(--violet);fill:#211a32}@media(max-width:900px){.metric-split{grid-template-columns:1fr}}"""

JS = r"""(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const fmt = ms => ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)}초`;
  const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
  history.replaceState(null, '', location.pathname);
  let selected = '';
  let snapshot = null;

  const executionLabels = {
    'run': ['재실행', 'rerun'],
    'not-evaluable': ['재실행', 'rerun'],
    'reuse-exact': ['재사용', 'reused'],
    'reuse-dependency': ['재사용', 'reused'],
    'reuse-safe-change': ['재사용', 'reused'],
    'not-planned': ['대기', 'pending']
  };
  const reasonText = {
    'same-revision-receipt-current': '같은 revision의 검사 결과가 현재 작업트리와 정확히 일치해 재사용했습니다.',
    'observed-dependencies-unchanged': '이 검사가 실제로 읽었던 입력이 바뀌지 않아 이전 통과 결과를 재사용했습니다.',
    'safe-change-policy-covered': '저장소 소유자가 미리 허용한 안전 변경 범위 안이라 이전 결과를 재사용했습니다.',
    'no-passing-evidence': '재사용할 수 있는 이전 통과 결과가 없어 실제 검사를 실행했습니다.',
    'previous-verification-failed': '이전 검사가 통과하지 않아 실제 검사를 다시 실행했습니다.',
    'observed-input-changed': '이 검사가 읽었던 입력이 변경되어 실제 검사를 다시 실행했습니다.',
    'check-binding-changed': '검사 명령의 결합 정보가 달라져 실제 검사를 실행했습니다.',
    'contract-binding-changed': '승인 계약의 결합 정보가 달라져 실제 검사를 실행했습니다.',
    'environment-binding-changed': '검사 환경이 달라져 실제 검사를 실행했습니다.',
    'executable-binding-changed': '검사 실행 파일이 달라져 실제 검사를 실행했습니다.',
    'host-coverage-binding-changed': '호스트 Hook 관찰 범위가 달라져 실제 검사를 실행했습니다.',
    'workspace-ambiguous': '현재 작업트리를 확실히 식별할 수 없어 안전하게 실제 검사를 실행했습니다.',
    'mutation-boundary-ambiguous': '변경 전후 경계를 확실히 묶을 수 없어 실제 검사를 실행했습니다.',
    'observer-incomplete': '의존성 관찰이 완전하지 않아 실제 검사를 실행했습니다.',
    'external-input-unmodeled': '저장소 밖 입력이 관찰되어 실제 검사를 실행했습니다.',
    'policy-unavailable': '적용할 수 있는 재사용 정책이 없어 실제 검사를 실행했습니다.',
    'safe-change-policy-not-covered': '변경이 안전 변경 정책 범위를 벗어나 실제 검사를 실행했습니다.',
    'receipt-invalid': '이전 영수증을 현재 상태에 유효하게 결합할 수 없어 실제 검사를 실행했습니다.',
    '': '아직 이 검사에 대한 실행 계획이 없습니다.'
  };
  const inputStatus = {
    'current-observed': '현재 관찰됨',
    'changed': '변경됨',
    'baseline-only': '이전 baseline에만 존재',
    'newly-observed': '현재 새로 관찰됨'
  };

  function reasonFor(source) {
    if (source.reason_code === 'observed-input-changed' && source.changed_inputs.length) {
      return `${source.changed_inputs[0]} 변경 때문에 다시 실행했습니다.`;
    }
    return reasonText[source.reason_code] || '안전한 기본값으로 실제 검사를 실행했습니다.';
  }

  function explain(source) {
    selected = source.id;
    const [label] = executionLabels[source.execution_decision];
    $('whyTitle').textContent = `${source.label} · ${label}`;
    $('whyBody').textContent = reasonFor(source);
    const tags = [
      `현재 revision ${source.current_revision}`,
      source.previous_revision >= 0 ? `이전 성공 revision ${source.previous_revision}` : '이전 성공 없음',
      `근거 ${source.authority_source}`,
      ...source.shadow_limitations.map(item => `Shadow: ${item}`)
    ];
    $('limits').replaceChildren(...tags.map(text => {
      const element = document.createElement('span');
      element.className = 'tag';
      element.textContent = text;
      return element;
    }));
    document.querySelectorAll('.source').forEach(element => {
      element.classList.toggle('active', element.dataset.id === selected);
    });
    renderMap(snapshot, source);
  }

  function renderSources(data) {
    const root = $('sources');
    root.replaceChildren();
    data.sources.forEach(source => {
      const button = document.createElement('button');
      button.className = 'source';
      button.dataset.id = source.id;
      button.type = 'button';
      const head = document.createElement('div');
      head.className = 'source-head';
      const name = document.createElement('strong');
      name.textContent = source.label;
      const [label, className] = executionLabels[source.execution_decision];
      const pill = document.createElement('span');
      pill.className = `pill ${className}`;
      pill.textContent = label;
      head.append(name, pill);
      const meta = document.createElement('p');
      meta.textContent = `상태 ${source.status} · 입력 ${source.input_count}개 · Observer ${source.observer_status}`;
      const reason = document.createElement('p');
      reason.className = 'reason';
      reason.textContent = reasonFor(source);
      button.append(head, meta, reason);
      button.onclick = () => explain(source);
      root.append(button);
    });
    $('sourceCount').textContent = String(data.sources.length);
    const current = data.sources.find(source => source.id === selected) || data.sources[0];
    if (current) {
      explain(current);
    } else {
      selected = '';
      $('whyTitle').textContent = '아직 계획된 검사가 없습니다';
      $('whyBody').textContent = '검증 계획이 생성되면 실행과 재사용 이유가 여기에 표시됩니다.';
      renderMap(data, null);
    }
  }

  function svgElement(name, attributes = {}) {
    const element = document.createElementNS('http://www.w3.org/2000/svg', name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }

  function renderMap(data, selectedSource) {
    const svg = $('map');
    const empty = $('emptyMap');
    svg.replaceChildren();
    if (!selectedSource) {
      svg.style.display = 'none';
      empty.style.display = 'grid';
      $('mapMeta').textContent = '';
      return;
    }
    const sourceNode = data.map.nodes.find(node => node.id === selectedSource.id);
    const selectedEdges = data.map.edges.filter(edge => edge.source === selectedSource.id);
    const targetIds = new Set(selectedEdges.map(edge => edge.target));
    const inputNodes = data.map.nodes.filter(node => targetIds.has(node.id)).slice(0, 48);
    const visibleIds = new Set(inputNodes.map(node => node.id));
    const edges = selectedEdges.filter(edge => visibleIds.has(edge.target));
    if (!sourceNode) {
      svg.style.display = 'none';
      empty.style.display = 'grid';
      return;
    }
    empty.style.display = 'none';
    svg.style.display = 'block';
    const positions = new Map();
    positions.set(sourceNode.id, {x: 20, y: 28, w: 160, h: 48});
    inputNodes.forEach((node, index) => {
      positions.set(node.id, {x: 260 + (index % 2) * 225, y: 12 + Math.floor(index / 2) * 58, w: 195, h: 42});
    });
    const height = Math.max(440, Math.ceil(inputNodes.length / 2) * 58 + 30);
    svg.setAttribute('viewBox', `0 0 700 ${height}`);
    edges.forEach(edge => {
      const from = positions.get(edge.source);
      const to = positions.get(edge.target);
      if (from && to) {
        svg.append(svgElement('line', {class: 'edge', x1: from.x + from.w, y1: from.y + from.h / 2, x2: to.x, y2: to.y + to.h / 2}));
      }
    });
    [sourceNode, ...inputNodes].forEach(node => {
      const position = positions.get(node.id);
      const group = svgElement('g', {class: `node ${node.type} ${node.status}`});
      group.append(svgElement('rect', {x: position.x, y: position.y, width: position.w, height: position.h}));
      const text = svgElement('text', {x: position.x + 10, y: position.y + 18});
      const label = node.label.length > 25 ? `${node.label.slice(0, 22)}…` : node.label;
      text.textContent = label;
      group.append(text);
      if (node.type === 'input') {
        const status = svgElement('text', {x: position.x + 10, y: position.y + 33, class: 'muted'});
        status.textContent = inputStatus[node.status];
        group.append(status);
      }
      svg.append(group);
    });
    const hidden = selectedSource.input_count - selectedSource.visible_input_count;
    $('mapMeta').textContent = hidden > 0 ? `입력 ${selectedSource.visible_input_count}개 표시 · ${hidden}개 생략` : `입력 ${selectedSource.input_count}개`;
  }

  function render(data) {
    snapshot = data;
    $('connection').textContent = '연결됨';
    document.querySelector('.live').classList.add('ok');
    $('taskline').textContent = `${data.task.runtime_mode} 모드 · revision ${data.task.mutation_revision} · ${data.task.status}`;
    const incremental = data.summary.incremental;
    const shadow = data.summary.shadow;
    $('currentChecks').textContent = String(incremental.current_source_count);
    $('executedChecks').textContent = String(incremental.executed_source_count);
    $('reusedChecks').textContent = String(incremental.authoritative_reuse_count);
    $('estimatedAvoided').textContent = fmt(incremental.estimated_avoided_ms);
    $('reuseBreakdown').textContent = `${incremental.exact_reuse_count} / ${incremental.dependency_reuse_count} / ${incremental.safe_change_reuse_count}`;
    $('executedDuration').textContent = fmt(incremental.executed_duration_ms);
    $('shadowBreakdown').textContent = `${shadow.candidate_count} / ${shadow.confirmed_candidate_count} / ${shadow.contradiction_count}`;
    $('shadowTiming').textContent = `${fmt(shadow.potential_ms)} / ${fmt(shadow.observer_overhead_ms)}`;
    $('observerTitle').textContent = data.task.observer_enabled ? 'Observer: Shadow 켜짐' : 'Observer: 꺼짐';
    $('observerBody').textContent = data.task.observer_enabled
      ? '예측 정확도를 측정하지만 검사 생략 권한은 만들지 않습니다.'
      : 'Dashboard는 계속 볼 수 있으며 기존 exact·policy reuse는 정상 동작합니다.';
    $('updated').textContent = `${new Date(data.generated_at * 1000).toLocaleTimeString()} 갱신`;
    renderSources(data);
  }

  async function refresh() {
    if (!token) {
      $('connection').textContent = '접근 토큰 없음';
      return;
    }
    try {
      const response = await fetch('/api/v1/snapshot', {
        headers: {Authorization: `Bearer ${token}`},
        cache: 'no-store'
      });
      if (!response.ok) throw new Error(String(response.status));
      render(await response.json());
    } catch (_) {
      $('connection').textContent = '연결 끊김';
      document.querySelector('.live').classList.remove('ok');
    }
  }
  refresh();
  setInterval(refresh, 1500);
})();
"""


def fresh_state() -> dict[str, Any]:
    return {
        "version": DASHBOARD_STATE_VERSION,
        "status": "idle",
        "instance_id": "",
        "runner_token_digest": "",
        "runner_claimed_at": 0,
        "access_token_digest": "",
        "port": 0,
        "pid": 0,
        "started_at": 0,
        "stop_requested": False,
        "last_error": "",
    }


def state_is_valid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _DASHBOARD_FIELDS:
        return False
    status = value.get("status")
    instance_id = value.get("instance_id")
    runner_digest = value.get("runner_token_digest")
    access_digest = value.get("access_token_digest")
    integers = [
        value.get("runner_claimed_at"),
        value.get("port"),
        value.get("pid"),
        value.get("started_at"),
    ]
    if (
        value.get("version") != DASHBOARD_STATE_VERSION
        or status not in DASHBOARD_STATUSES
        or not isinstance(instance_id, str)
        or not isinstance(runner_digest, str)
        or not isinstance(access_digest, str)
        or any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in integers)
        or not isinstance(value.get("stop_requested"), bool)
        or not isinstance(value.get("last_error"), str)
        or len(value["last_error"]) > 256
    ):
        return False
    if status == "idle":
        return value == fresh_state()
    return bool(
        _INSTANCE.fullmatch(instance_id)
        and _DIGEST.fullmatch(access_digest)
        and (not runner_digest or _DIGEST.fullmatch(runner_digest))
        and 0 <= value["port"] <= 65535
    )


def _dashboard_state(state: Any) -> dict[str, Any]:
    value = state.get(DASHBOARD_FIELD) if isinstance(state, dict) else None
    return dict(value) if state_is_valid(value) else fresh_state()


def _managed_state_path(path: Path) -> bool:
    return click_state.managed_state_path(path, ("session-contract-",))


def _runner_prefix(action: str, runner_script: Path) -> list[str]:
    return [
        sys.executable,
        str(runner_script.resolve()),
        "--state-root",
        str(click_state.state_root().resolve()),
        action,
    ]


def runner_command(
    event: dict[str, Any],
    action: str,
    arguments: list[str],
    *,
    runner_script: Path,
    render_command: RenderCommand,
) -> str:
    return render_command(
        [
            *_runner_prefix(action, runner_script),
            str(click_state.contract_path(event).resolve()),
            *arguments,
        ]
    )


def prepare(
    event: dict[str, Any],
    action: str,
    *,
    runner_script: Path,
    render_command: RenderCommand,
) -> tuple[str, str]:
    if action not in DASHBOARD_ACTIONS:
        return "", "Click dashboard action must be start, stop, or status."
    state = click_contract_state.read_contract_state(event)
    runtime = click_runtime_state.view(state)
    if not runtime.execution_authorized:
        return "", "Start Guarded or Evidence runtime state before opening its dashboard."
    dashboard = _dashboard_state(state)
    state_path = str(click_state.contract_path(event).resolve())
    if action == "status":
        return runner_command(
            event,
            "run-dashboard-status",
            [],
            runner_script=runner_script,
            render_command=render_command,
        ), ""
    if action == "stop":
        if dashboard["status"] not in {"starting", "running", "stopping"}:
            return runner_command(
                event,
                "run-dashboard-status",
                [],
                runner_script=runner_script,
                render_command=render_command,
            ), ""
        dashboard["status"] = "stopping"
        dashboard["stop_requested"] = True
        state[DASHBOARD_FIELD] = dashboard
        click_contract_state.save_contract_state(event, state)
        return runner_command(
            event,
            "run-dashboard-stop",
            [dashboard["instance_id"]],
            runner_script=runner_script,
            render_command=render_command,
        ), ""

    if dashboard["status"] in {"starting", "running", "stopping"}:
        return "", "The Click Shadow dashboard is already active. Stop it first."
    instance_id = secrets.token_urlsafe(24)
    runner_token = secrets.token_urlsafe(24)
    access_token = secrets.token_urlsafe(32)
    dashboard = {
        "version": DASHBOARD_STATE_VERSION,
        "status": "starting",
        "instance_id": instance_id,
        "runner_token_digest": hashlib.sha256(runner_token.encode()).hexdigest(),
        "runner_claimed_at": 0,
        "access_token_digest": hashlib.sha256(access_token.encode()).hexdigest(),
        "port": 0,
        "pid": 0,
        "started_at": int(time.time()) or 1,
        "stop_requested": False,
        "last_error": "",
    }
    state[DASHBOARD_FIELD] = dashboard
    click_contract_state.save_contract_state(event, state)
    return runner_command(
        event,
        "run-dashboard-start",
        [instance_id, runner_token, access_token],
        runner_script=runner_script,
        render_command=render_command,
    ), ""


def request_stop(event: dict[str, Any]) -> bool:
    state = click_contract_state.read_contract_state(event)
    dashboard = _dashboard_state(state)
    if dashboard["status"] not in {"starting", "running", "stopping"}:
        return False
    dashboard["status"] = "stopping"
    dashboard["stop_requested"] = True
    state[DASHBOARD_FIELD] = dashboard
    click_contract_state.save_contract_state(event, state)
    return True


def _read_state(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _write_dashboard_fields(
    path: Path, instance_id: str, **fields: Any
) -> bool:
    state = _read_state(path)
    if state is None:
        return False
    dashboard = _dashboard_state(state)
    if dashboard.get("instance_id") != instance_id:
        return False
    dashboard.update(fields)
    if not state_is_valid(dashboard):
        return False
    state[DASHBOARD_FIELD] = dashboard
    click_state.write_json(path, state)
    return True


def _snapshot(path: Path, instance_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    state = _read_state(path)
    if state is None:
        return None, fresh_state()
    dashboard = _dashboard_state(state)
    if dashboard.get("instance_id") != instance_id:
        return None, dashboard
    return state, dashboard


def run_start(
    arguments: list[str],
    *,
    runner_script: Path,
    spawn: Callable[..., subprocess.Popen[Any]] = click_process.spawn_argv,
) -> int:
    if len(arguments) != 4:
        sys.stderr.write("usage: run-dashboard-start <state> <id> <runner-token> <access-token>\n")
        return 2
    state_path = Path(arguments[0])
    instance_id, runner_token, access_token = arguments[1:]
    if not _managed_state_path(state_path):
        sys.stderr.write("Click dashboard runner received an unmanaged state path.\n")
        return 2
    with click_state.state_lock():
        state, dashboard = _snapshot(state_path, instance_id)
        runner_digest = hashlib.sha256(runner_token.encode()).hexdigest()
        access_digest = hashlib.sha256(access_token.encode()).hexdigest()
        if (
            state is None
            or not click_runtime_state.view(state).execution_authorized
            or dashboard.get("status") != "starting"
            or dashboard.get("stop_requested") is True
            or dashboard.get("runner_claimed_at") != 0
            or not hmac.compare_digest(str(dashboard.get("runner_token_digest", "")), runner_digest)
            or not hmac.compare_digest(str(dashboard.get("access_token_digest", "")), access_digest)
            or time.time() - int(dashboard.get("started_at", 0)) > START_TIMEOUT_SECONDS * 2
        ):
            sys.stderr.write("Click dashboard start authorization is stale or invalid.\n")
            return 2
        if not _write_dashboard_fields(
            state_path,
            instance_id,
            runner_claimed_at=int(time.time()) or 1,
            runner_token_digest="",
        ):
            return 2
    try:
        spawn(
            [
                *_runner_prefix("run-dashboard-server", runner_script),
                str(state_path),
                instance_id,
                access_token,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        with click_state.state_lock():
            _write_dashboard_fields(
                state_path,
                instance_id,
                status="failed",
                last_error=str(exc)[:256],
            )
        sys.stderr.write("Click dashboard process could not start.\n")
        return 2
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        with click_state.state_lock():
            _, current = _snapshot(state_path, instance_id)
        if current.get("status") == "running" and int(current.get("port", 0)) > 0:
            sys.stdout.write(
                f"http://127.0.0.1:{current['port']}/#token={access_token}\n"
            )
            return 0
        if current.get("status") == "failed":
            sys.stderr.write("Click dashboard exited during startup.\n")
            return 2
        time.sleep(POLL_SECONDS)
    with click_state.state_lock():
        _write_dashboard_fields(
            state_path,
            instance_id,
            status="stopping",
            stop_requested=True,
            last_error="startup-timeout",
        )
    sys.stderr.write("Click dashboard did not start within its bounded timeout.\n")
    return 2


def run_stop(arguments: list[str]) -> int:
    if len(arguments) != 2:
        sys.stderr.write("usage: run-dashboard-stop <state> <id>\n")
        return 2
    state_path = Path(arguments[0])
    instance_id = arguments[1]
    if not _managed_state_path(state_path):
        return 2
    deadline = time.monotonic() + STOP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        with click_state.state_lock():
            _, dashboard = _snapshot(state_path, instance_id)
        if dashboard.get("status") in {"stopped", "failed", "idle"}:
            sys.stdout.write("Click Shadow dashboard stopped\n")
            return 0
        time.sleep(POLL_SECONDS)
    sys.stderr.write("Click Shadow dashboard did not stop within its bounded timeout.\n")
    return 2


def run_status(arguments: list[str]) -> int:
    if len(arguments) != 1:
        sys.stderr.write("usage: run-dashboard-status <state>\n")
        return 2
    state_path = Path(arguments[0])
    if not _managed_state_path(state_path):
        return 2
    with click_state.state_lock():
        state = _read_state(state_path)
        dashboard = _dashboard_state(state)
    sys.stdout.write(
        json.dumps(
            {
                "status": dashboard["status"],
                "port": dashboard["port"],
                "started_at": dashboard["started_at"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


class _DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, state_path: Path, instance_id: str, access_token: str):
        self.state_path = state_path
        self.instance_id = instance_id
        self.access_token = access_token
        super().__init__(("127.0.0.1", 0), _DashboardHandler)


class _DashboardHandler(BaseHTTPRequestHandler):
    server: _DashboardServer

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'none'",
        )
        self.end_headers()

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self._headers(status, content_type, len(body))
        if self.command != "HEAD":
            self.wfile.write(body)

    def _host_is_valid(self) -> bool:
        expected = f"127.0.0.1:{self.server.server_port}"
        return hmac.compare_digest(self.headers.get("Host", ""), expected)

    def _authorized(self) -> bool:
        value = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.access_token}"
        return hmac.compare_digest(value, expected)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._host_is_valid():
            self._send(421, "text/plain; charset=utf-8", b"Misdirected Request\n")
            return
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", HTML.encode())
            return
        if path == "/styles.css":
            self._send(200, "text/css; charset=utf-8", CSS.encode())
            return
        if path == "/app.js":
            self._send(200, "text/javascript; charset=utf-8", JS.encode())
            return
        if path == "/api/v1/snapshot":
            if not self._authorized():
                self._send(401, "application/json", b'{"error":"unauthorized"}\n')
                return
            with click_state.state_lock():
                state, dashboard = _snapshot(
                    self.server.state_path, self.server.instance_id
                )
                if (
                    state is None
                    or dashboard.get("status") not in {"running", "stopping"}
                ):
                    self._send(410, "application/json", b'{"error":"stale"}\n')
                    return
                projection = click_dashboard_projection.dashboard_projection(state)
                if not click_dashboard_projection.projection_is_valid(projection):
                    self._send(500, "application/json", b'{"error":"invalid-projection"}\n')
                    return
            body = json.dumps(
                projection,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8") + b"\n"
            self._send(200, "application/json; charset=utf-8", body)
            return
        self._send(404, "text/plain; charset=utf-8", b"Not Found\n")

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.do_GET()

    def _method_not_allowed(self) -> None:
        self._send(405, "text/plain; charset=utf-8", b"Method Not Allowed\n")

    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed


def run_server(arguments: list[str]) -> int:
    if len(arguments) != 3:
        return 2
    state_path = Path(arguments[0])
    instance_id, access_token = arguments[1:]
    if not _managed_state_path(state_path):
        return 2
    access_digest = hashlib.sha256(access_token.encode()).hexdigest()
    with click_state.state_lock():
        state, dashboard = _snapshot(state_path, instance_id)
        if (
            state is None
            or not click_runtime_state.view(state).execution_authorized
            or dashboard.get("status") != "starting"
            or dashboard.get("stop_requested") is True
            or not hmac.compare_digest(
                str(dashboard.get("access_token_digest", "")), access_digest
            )
        ):
            return 2
    try:
        server = _DashboardServer(state_path, instance_id, access_token)
    except OSError as exc:
        with click_state.state_lock():
            _write_dashboard_fields(
                state_path,
                instance_id,
                status="failed",
                last_error=str(exc)[:256],
            )
        return 2
    server.timeout = 0.4
    with click_state.state_lock():
        if not _write_dashboard_fields(
            state_path,
            instance_id,
            status="running",
            port=int(server.server_port),
            pid=os.getpid(),
        ):
            server.server_close()
            return 2
    deadline = time.monotonic() + MAX_LIFETIME_SECONDS
    result = 0
    try:
        while time.monotonic() < deadline:
            with click_state.state_lock():
                state, dashboard = _snapshot(state_path, instance_id)
            if (
                state is None
                or dashboard.get("stop_requested") is True
                or dashboard.get("status") != "running"
                or not hmac.compare_digest(
                    str(dashboard.get("access_token_digest", "")), access_digest
                )
            ):
                break
            server.handle_request()
        else:
            result = 124
    finally:
        server.server_close()
        with click_state.state_lock():
            _write_dashboard_fields(
                state_path,
                instance_id,
                status="stopped" if result == 0 else "failed",
                stop_requested=True,
                port=0,
                pid=0,
                last_error="" if result == 0 else "lifetime-expired",
            )
    return result
