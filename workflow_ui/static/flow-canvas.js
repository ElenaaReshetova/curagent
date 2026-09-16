/**
 * DEPRECATED — replaced by React Flow + ELK (react-dist/designer.js + react-flow-bridge.js).
 * Kept for reference / emergency fallback. Not loaded from index.html.
 *
 * FlowCanvas — vanilla port of React Flow (xyflow) interaction model.
 *
 * Key behaviors from @xyflow/system XYHandle:
 * - document-level pointermove/up while connecting
 * - geometric getClosestHandle(connectionRadius) — not elementFromPoint
 * - reconnect endpoints sit ON the edge path (not stacked on the port)
 * - parallel edges are offset so paths don't overlap
 * - handles always hittable (large hit target)
 * - palette drag-and-drop onto canvas; drop on edge inserts node into the link
 */
(function (global) {
  'use strict';

  const ZOOM_MIN = 0.25;
  const ZOOM_MAX = 2.5;
  const DEFAULT_NODE = { w: 220, h: 76 };
  const START_END = { w: 96, h: 48 };
  const NODE_MIN = { w: 160, h: 56 };
  const NODE_MAX_W = 360;
  const CONNECTION_RADIUS = 28; // flow-space px, like xyflow connectionRadius
  const EDGE_DROP_RADIUS = 26; // flow-space px — highlight / insert on edge
  const DRAG_THRESHOLD = 4;
  const HISTORY_LIMIT = 50;
  const PALETTE_MIME = 'application/x-fc-palette';
  const BRANCH_TYPES = new Set([
    'CONTROL_GATE', 'CONDITIONAL_BRANCH', 'CONDITION',
  ]);
  const HUMAN_DECISION_TYPES = new Set([
    'HUMAN_CHECKPOINT', 'HUMAN_DECISION',
  ]);

  let instanceSeq = 0;
  /** @type {Array<{ mount: HTMLElement, readOnly: () => boolean, hoverPalette: Function, dropPalette: Function, clearPaletteHover: Function }>} */
  const liveInstances = [];
  let paletteSession = null;

  function uid(prefix) {
    return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
  }

  function clamp(n, min, max) {
    return Math.min(max, Math.max(min, n));
  }

  function dist(a, b) {
    const dx = a.x - b.x;
    const dy = a.y - b.y;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function pointToSegmentDist(p, a, b) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    if (dx === 0 && dy === 0) return dist(p, a);
    let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy);
    t = Math.max(0, Math.min(1, t));
    return dist(p, { x: a.x + t * dx, y: a.y + t * dy });
  }

  function parsePalettePayload(dt) {
    if (!dt) return null;
    try {
      const raw = dt.getData(PALETTE_MIME) || dt.getData('text/plain');
      if (!raw) return null;
      if (raw.charAt(0) === '{') return JSON.parse(raw);
      return { type: raw };
    } catch (_) {
      return null;
    }
  }

  function instanceFromPoint(clientX, clientY) {
    const stack = typeof document.elementsFromPoint === 'function'
      ? document.elementsFromPoint(clientX, clientY)
      : [document.elementFromPoint(clientX, clientY)].filter(Boolean);
    for (let i = 0; i < stack.length; i += 1) {
      const root = stack[i] && stack[i].closest && stack[i].closest('.fc-root');
      if (!root) continue;
      const found = liveInstances.find((inst) => inst.mount === root);
      if (found) return found;
    }
    return null;
  }

  function ensurePaletteGhost(label) {
    let ghost = document.getElementById('fc-palette-ghost');
    if (!ghost) {
      ghost = document.createElement('div');
      ghost.id = 'fc-palette-ghost';
      ghost.className = 'fc-palette-ghost';
      document.body.appendChild(ghost);
    }
    ghost.textContent = label || 'Node';
    ghost.classList.remove('fc-hidden');
    return ghost;
  }

  function movePaletteGhost(clientX, clientY) {
    const ghost = document.getElementById('fc-palette-ghost');
    if (!ghost) return;
    ghost.style.transform = `translate(${clientX + 12}px, ${clientY + 12}px)`;
  }

  function hidePaletteGhost() {
    const ghost = document.getElementById('fc-palette-ghost');
    if (ghost) ghost.classList.add('fc-hidden');
  }

  function endPaletteSession(commit, clientX, clientY) {
    const session = paletteSession;
    paletteSession = null;
    document.body.classList.remove('fc-palette-dragging');
    hidePaletteGhost();
    liveInstances.forEach((inst) => inst.clearPaletteHover());
    if (!session) return;
    if (session.sourceEl) session.sourceEl.classList.remove('is-dragging');
    document.removeEventListener('pointermove', onPalettePointerMove);
    document.removeEventListener('pointerup', onPalettePointerUp);
    document.removeEventListener('pointercancel', onPalettePointerUp);
    if (!commit || !session.moved) return;
    const sourceEl = session.sourceEl;
    if (sourceEl) {
      // Suppress the click that follows a drag ending on the same element.
      // If pointerup was outside the button (drop on canvas), no click fires —
      // clear the flag on the next tick so the next real click still works.
      sourceEl.dataset.fcDidDrag = '1';
      setTimeout(() => {
        if (sourceEl.dataset.fcDidDrag === '1') sourceEl.dataset.fcDidDrag = '0';
      }, 0);
    }
    const inst = instanceFromPoint(clientX, clientY);
    if (inst) inst.dropPalette(session.payload, clientX, clientY);
  }

  function onPalettePointerMove(ev) {
    if (!paletteSession) return;
    const dx = ev.clientX - paletteSession.startX;
    const dy = ev.clientY - paletteSession.startY;
    if (!paletteSession.moved) {
      if (Math.abs(dx) < DRAG_THRESHOLD && Math.abs(dy) < DRAG_THRESHOLD) return;
      paletteSession.moved = true;
      if (paletteSession.sourceEl) paletteSession.sourceEl.classList.add('is-dragging');
      document.body.classList.add('fc-palette-dragging');
      ensurePaletteGhost(paletteSession.label);
    }
    movePaletteGhost(ev.clientX, ev.clientY);
    const inst = instanceFromPoint(ev.clientX, ev.clientY);
    liveInstances.forEach((other) => {
      if (other === inst) other.hoverPalette(ev.clientX, ev.clientY);
      else other.clearPaletteHover();
    });
  }

  function onPalettePointerUp(ev) {
    endPaletteSession(true, ev.clientX, ev.clientY);
  }

  function isTerminalType(type) {
    return type === 'START' || type === 'END' || type === 'end' || type === 'start';
  }

  function defaultSize(node) {
    if (isTerminalType(node.type)) {
      if (typeof node.width === 'number' && typeof node.height === 'number') {
        return { w: node.width, h: node.height };
      }
      return START_END;
    }
    if (typeof node.width === 'number' && typeof node.height === 'number') {
      return { w: node.width, h: node.height };
    }
    return DEFAULT_NODE;
  }

  function minSize(node) {
    if (isTerminalType(node && node.type)) return START_END;
    return NODE_MIN;
  }

  /**
   * True when nodes carry distinct saved coordinates (user or previous auto-layout).
   * Empty / all-zero / fully overlapping positions mean layout still needs to run.
   */
  function hasUserLayout(nodes) {
    const list = nodes || [];
    if (!list.length) return true;
    if (list.length === 1) {
      const p = list[0].position || {};
      return typeof p.x === 'number' && typeof p.y === 'number';
    }
    let missing = 0;
    const keys = new Set();
    list.forEach((n) => {
      const p = n.position || {};
      if (typeof p.x !== 'number' || typeof p.y !== 'number' || Number.isNaN(p.x) || Number.isNaN(p.y)) {
        missing += 1;
        return;
      }
      keys.add(`${Math.round(p.x)},${Math.round(p.y)}`);
    });
    if (missing > 0) return false;
    if (keys.size === 1) return false;
    const allOrigin = list.every((n) => {
      const p = n.position || {};
      return (p.x || 0) === 0 && (p.y || 0) === 0;
    });
    return !allOrigin;
  }

  function isBranchNode(node) {
    const t = String(node.type || '');
    const upper = t.toUpperCase();
    return BRANCH_TYPES.has(t) || BRANCH_TYPES.has(upper)
      || HUMAN_DECISION_TYPES.has(t) || HUMAN_DECISION_TYPES.has(upper);
  }

  function isHumanDecisionNode(node) {
    const t = String((node && node.type) || '').toUpperCase();
    return HUMAN_DECISION_TYPES.has(t);
  }

  /**
   * Orthogonal lane routing. Lane slots are precomputed once per render
   * so drag updates stay O(edges), not O(edges² · sort).
   */
  function laneSlot(index, count) {
    if (count <= 1) return 0.5;
    return (index + 1) / (count + 1);
  }

  function buildLaneTable(edges) {
    const incoming = {};
    const outgoing = {};
    edges.forEach((e) => {
      if (!incoming[e.target]) incoming[e.target] = [];
      incoming[e.target].push(e);
      const key = `${e.source}::${e.sourceHandle || 'source'}`;
      if (!outgoing[key]) outgoing[key] = [];
      outgoing[key].push(e);
    });
    const inMeta = {};
    const outMeta = {};
    Object.keys(incoming).forEach((t) => {
      const list = incoming[t].slice().sort((a, b) =>
        String(a.source).localeCompare(String(b.source)) || String(a.id).localeCompare(String(b.id))
      );
      list.forEach((e, i) => {
        inMeta[e.id] = { index: i, count: list.length, slot: laneSlot(i, list.length) };
      });
    });
    Object.keys(outgoing).forEach((k) => {
      const list = outgoing[k].slice().sort((a, b) =>
        String(a.target).localeCompare(String(b.target)) || String(a.id).localeCompare(String(b.id))
      );
      list.forEach((e, i) => {
        outMeta[e.id] = { index: i, count: list.length, slot: laneSlot(i, list.length) };
      });
    });
    return { inMeta, outMeta };
  }

  function portPoint(node, handleId, slot) {
    const pos = node.position || { x: 0, y: 0 };
    const size = defaultSize(node);
    const h = String(handleId || 'source');
    const t = slot == null ? 0.5 : slot;
    const y = pos.y + size.h * Math.min(0.92, Math.max(0.08, t));
    if (h === 'target' || h === 'in') {
      return { x: pos.x, y, position: 'left' };
    }
    if (h === 'yes' || h === 'pass' || h === 'true' || h === 'approve') {
      return { x: pos.x + size.w, y: pos.y + size.h * (slot == null ? (isHumanDecisionNode(node) ? 0.22 : 0.28) : t), position: 'right' };
    }
    if (h === 'changes' || h === 'clarify' || h === 'request_changes') {
      return { x: pos.x + size.w, y: pos.y + size.h * (slot == null ? 0.5 : t), position: 'right' };
    }
    if (h === 'no' || h === 'fail' || h === 'false' || h === 'reject') {
      return { x: pos.x + size.w, y: pos.y + size.h * (slot == null ? (isHumanDecisionNode(node) ? 0.78 : 0.72) : t), position: 'right' };
    }
    return { x: pos.x + size.w, y, position: 'right' };
  }

  function listHandles(node) {
    const handles = [
      { id: 'target', type: 'target', ...portPoint(node, 'target') },
    ];
    if (isHumanDecisionNode(node)) {
      handles.push(
        { id: 'approve', type: 'source', ...portPoint(node, 'approve') },
        { id: 'changes', type: 'source', ...portPoint(node, 'changes') },
        { id: 'reject', type: 'source', ...portPoint(node, 'reject') }
      );
    } else if (isBranchNode(node)) {
      handles.push(
        { id: 'yes', type: 'source', ...portPoint(node, 'yes') },
        { id: 'no', type: 'source', ...portPoint(node, 'no') }
      );
    } else {
      handles.push({ id: 'source', type: 'source', ...portPoint(node, 'source') });
    }
    return handles;
  }

  function getClosestHandle(flowPos, nodes, from, radius) {
    let best = null;
    let bestDist = radius;
    nodes.forEach((node) => {
      listHandles(node).forEach((handle) => {
        if (from.nodeId === node.id && from.handleId === handle.id && from.handleType === handle.type) {
          return;
        }
        if (from.handleType === 'source' && handle.type !== 'target') return;
        if (from.handleType === 'target' && handle.type !== 'source') return;
        const d = dist(flowPos, handle);
        if (d <= bestDist) {
          bestDist = d;
          best = {
            nodeId: node.id,
            handleId: handle.id,
            handleType: handle.type,
            x: handle.x,
            y: handle.y,
            position: handle.position,
          };
        }
      });
    });
    return best;
  }

  function routeEdge(edge, nodeMap, lanes) {
    const src = nodeMap[edge.source];
    const tgt = nodeMap[edge.target];
    if (!src || !tgt) return null;

    const srcHandle = edge.sourceHandle || (isBranchNode(src) ? 'yes' : 'source');
    const inM = (lanes && lanes.inMeta[edge.id]) || { index: 0, count: 1, slot: 0.5 };
    const outM = (lanes && lanes.outMeta[edge.id]) || { index: 0, count: 1, slot: 0.5 };
    const outSlot = isHumanDecisionNode(src)
      && (srcHandle === 'approve' || srcHandle === 'yes' || srcHandle === 'changes' || srcHandle === 'reject' || srcHandle === 'no')
      ? (srcHandle === 'approve' || srcHandle === 'yes' ? 0.22
        : srcHandle === 'changes' ? 0.5 : 0.78)
      : (isBranchNode(src) && (srcHandle === 'yes' || srcHandle === 'no')
        ? (srcHandle === 'yes' ? 0.28 : 0.72)
        : outM.slot);

    const a = portPoint(src, srcHandle, outSlot);
    const b = portPoint(tgt, edge.targetHandle || 'target', inM.slot);

    const laneSpread = 24;
    const lane = (inM.index - (inM.count - 1) / 2) * laneSpread
      + (outM.index - (outM.count - 1) / 2) * (laneSpread * 0.3);

    const forward = b.x >= a.x - 8;
    let points;
    if (forward) {
      const gap = Math.max(48, (b.x - a.x) * 0.5);
      const midX = a.x + gap + lane;
      points = [
        { x: a.x, y: a.y },
        { x: midX, y: a.y },
        { x: midX, y: b.y },
        { x: b.x, y: b.y },
      ];
    } else {
      const srcSize = defaultSize(src);
      const tgtSize = defaultSize(tgt);
      const top = Math.min(a.y, b.y) - 48 - Math.abs(lane);
      const bottom = Math.max(a.y + srcSize.h, b.y + tgtSize.h) + 48 + Math.abs(lane);
      const bypassY = inM.index % 2 === 0 ? top : bottom;
      const outStub = a.x + 32;
      const inStub = b.x - 32;
      points = [
        { x: a.x, y: a.y },
        { x: outStub, y: a.y },
        { x: outStub, y: bypassY },
        { x: inStub, y: bypassY },
        { x: inStub, y: b.y },
        { x: b.x, y: b.y },
      ];
    }

    const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

    function at(t) {
      const segs = [];
      let total = 0;
      for (let i = 0; i < points.length - 1; i += 1) {
        const len = dist(points[i], points[i + 1]);
        segs.push({ a: points[i], b: points[i + 1], len });
        total += len;
      }
      if (!total) return points[0];
      let remain = Math.max(0, Math.min(1, t)) * total;
      for (let i = 0; i < segs.length; i += 1) {
        if (remain <= segs[i].len || i === segs.length - 1) {
          const r = segs[i].len ? remain / segs[i].len : 0;
          return {
            x: segs[i].a.x + (segs[i].b.x - segs[i].a.x) * r,
            y: segs[i].a.y + (segs[i].b.y - segs[i].a.y) * r,
          };
        }
        remain -= segs[i].len;
      }
      return points[points.length - 1];
    }

    return { d, at, a, b, points };
  }

  function previewPath(x1, y1, x2, y2) {
    const midX = (x1 + x2) / 2;
    return `M ${x1} ${y1} L ${midX} ${y1} L ${midX} ${y2} L ${x2} ${y2}`;
  }

  function edgeLabelText(edge) {
    const d = edge.data || {};
    if (d.label != null && String(d.label).trim() !== '') return String(d.label);
    if (d.condition != null && String(d.condition).trim() !== '') return String(d.condition);
    const sh = String(edge.sourceHandle || '');
    if (sh === 'approve' || sh === 'yes' || sh === 'pass' || sh === 'true') return sh === 'approve' ? 'Approve' : 'Yes';
    if (sh === 'changes' || sh === 'clarify' || sh === 'request_changes') return 'Changes';
    if (sh === 'reject') return 'Reject';
    if (sh === 'no' || sh === 'fail' || sh === 'false') return 'No';
    return '';
  }

  function labelFromHandle(handleId) {
    const h = String(handleId || '').toLowerCase();
    if (h === 'approve') return { label: 'Approve', condition: 'approve' };
    if (h === 'changes' || h === 'clarify' || h === 'request_changes') {
      return { label: 'Request changes', condition: 'request_changes' };
    }
    if (h === 'reject') return { label: 'Reject', condition: 'reject' };
    if (h === 'yes' || h === 'pass' || h === 'true') return { label: 'Yes', condition: 'yes' };
    if (h === 'no' || h === 'fail' || h === 'false') return { label: 'No', condition: 'no' };
    return { label: '', condition: null };
  }

  function create(options) {
    const opts = options || {};
    const mount = typeof opts.mount === 'string' ? document.querySelector(opts.mount) : opts.mount;
    if (!mount) throw new Error('FlowCanvas: mount element required');

    const iid = ++instanceSeq;
    const markerId = `fc-arrow-${iid}`;
    const markerActiveId = `fc-arrow-active-${iid}`;

    const state = {
      nodes: [],
      edges: [],
      selectedNodeId: null,
      selectedEdgeId: null,
      panX: 40,
      panY: 40,
      zoom: 1,
      readOnly: !!opts.readOnly,
      snap: opts.snap == null ? false : opts.snap,
      interaction: null,
      connection: null,
      pendingGraph: null,
      emitting: false,
      laneTable: null,
      dropEdgeId: null,
      destroyed: false,
      past: [],
      future: [],
      historyBefore: null,
      applyingHistory: false,
    };

    const callbacks = {
      onChange: typeof opts.onChange === 'function' ? opts.onChange : null,
      onSelect: typeof opts.onSelect === 'function' ? opts.onSelect : null,
      renderNode: typeof opts.renderNode === 'function' ? opts.renderNode : null,
      createDroppedNode: typeof opts.createDroppedNode === 'function' ? opts.createDroppedNode : null,
      isNodeLocked: typeof opts.isNodeLocked === 'function' ? opts.isNodeLocked : null,
      canConnect: typeof opts.canConnect === 'function' ? opts.canConnect : null,
      canInsertIntoEdge: typeof opts.canInsertIntoEdge === 'function' ? opts.canInsertIntoEdge : null,
    };

    function nodeIsLocked(node) {
      if (!node) return true;
      if (node.type === 'START') return true;
      if (callbacks.isNodeLocked) {
        try {
          return !!callbacks.isNodeLocked(node);
        } catch (_err) {
          return false;
        }
      }
      const data = node.data || {};
      const gateKind = data.config && data.config.gate_kind;
      return !!(
        data.immutable
        || node.type === 'LOCKED_STEP'
        || node.id === 'stage-artifact-gate'
        || gateKind === 'stage_artifact'
      );
    }

    function connectionAllowed(sourceId, targetId, sourceHandle) {
      if (!callbacks.canConnect) return true;
      try {
        return callbacks.canConnect(sourceId, targetId, sourceHandle) !== false;
      } catch (_err) {
        return true;
      }
    }

    mount.classList.add('fc-root');
    mount.innerHTML = `
      <div class="fc-controls" aria-label="Canvas controls">
        <button type="button" class="fc-ctrl" data-act="zoom-in" title="Zoom in">+</button>
        <button type="button" class="fc-ctrl" data-act="zoom-out" title="Zoom out">−</button>
        <button type="button" class="fc-ctrl" data-act="fit" title="Fit view">⊡</button>
        <button type="button" class="fc-ctrl" data-act="layout" title="Auto layout">▤</button>
        <span class="fc-zoom-label">100%</span>
      </div>
      <div class="fc-hint">${opts.hint || 'Palette → canvas: drag block · Drop on arrow to insert · Pan / wheel zoom · Connect from handle · Del: delete · Ctrl/⌘Z: undo'}</div>
      <div class="fc-viewport" tabindex="0">
        <div class="fc-stage">
          <svg class="fc-edges" aria-hidden="true">
            <defs>
              <marker id="${markerId}" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"></path>
              </marker>
              <marker id="${markerActiveId}" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#2563eb"></path>
              </marker>
            </defs>
            <g class="fc-edges-layer"></g>
            <path class="fc-link-preview fc-hidden" d=""></path>
          </svg>
          <div class="fc-nodes"></div>
        </div>
      </div>`;

    const viewport = mount.querySelector('.fc-viewport');
    const stage = mount.querySelector('.fc-stage');
    const nodesEl = mount.querySelector('.fc-nodes');
    const edgesLayer = mount.querySelector('.fc-edges-layer');
    const preview = mount.querySelector('.fc-link-preview');
    const zoomLabel = mount.querySelector('.fc-zoom-label');

    function takeSnapshot() {
      return {
        nodes: state.nodes.map(cloneNode),
        edges: state.edges.map(cloneEdge),
        selectedNodeId: state.selectedNodeId,
        selectedEdgeId: state.selectedEdgeId,
      };
    }

    function clearHistory() {
      state.past = [];
      state.future = [];
      state.historyBefore = null;
    }

    /** Capture graph before a mutation; coalesces nested edits into one undo step. */
    function beginHistory() {
      if (state.readOnly || state.applyingHistory || state.historyBefore) return;
      state.historyBefore = takeSnapshot();
    }

    function discardHistoryCapture() {
      state.historyBefore = null;
    }

    function commitHistory() {
      if (state.applyingHistory || !state.historyBefore) return;
      const before = state.historyBefore;
      state.historyBefore = null;
      state.past.push(before);
      if (state.past.length > HISTORY_LIMIT) state.past.shift();
      state.future = [];
    }

    function applySnapshot(snap) {
      state.nodes = (snap.nodes || []).map(cloneNode);
      state.edges = (snap.edges || []).map(cloneEdge);
      state.selectedNodeId = snap.selectedNodeId || null;
      state.selectedEdgeId = snap.selectedEdgeId || null;
      state.historyBefore = null;
      render();
      emitChange();
      emitSelect();
    }

    function undo() {
      if (state.readOnly || !state.past.length) return false;
      state.applyingHistory = true;
      try {
        state.future.push(takeSnapshot());
        if (state.future.length > HISTORY_LIMIT) state.future.shift();
        applySnapshot(state.past.pop());
      } finally {
        state.applyingHistory = false;
      }
      return true;
    }

    function redo() {
      if (state.readOnly || !state.future.length) return false;
      state.applyingHistory = true;
      try {
        state.past.push(takeSnapshot());
        if (state.past.length > HISTORY_LIMIT) state.past.shift();
        applySnapshot(state.future.pop());
      } finally {
        state.applyingHistory = false;
      }
      return true;
    }

    function emitChange() {
      commitHistory();
      if (!callbacks.onChange || state.emitting) return;
      state.emitting = true;
      try {
        callbacks.onChange({
          nodes: state.nodes.map(cloneNode),
          edges: state.edges.map(cloneEdge),
        });
      } finally {
        state.emitting = false;
      }
    }

    function emitSelect() {
      if (!callbacks.onSelect) return;
      callbacks.onSelect({
        nodeId: state.selectedNodeId,
        edgeId: state.selectedEdgeId,
        node: state.nodes.find((n) => n.id === state.selectedNodeId) || null,
        edge: state.edges.find((e) => e.id === state.selectedEdgeId) || null,
      });
    }

    function cloneNode(n) {
      return {
        id: n.id,
        type: n.type,
        position: { x: n.position.x, y: n.position.y },
        data: n.data ? JSON.parse(JSON.stringify(n.data)) : {},
        width: n.width,
        height: n.height,
      };
    }

    function cloneEdge(e) {
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle || null,
        targetHandle: e.targetHandle || 'target',
        data: e.data ? JSON.parse(JSON.stringify(e.data)) : {},
      };
    }

    function applyTransform() {
      stage.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
      if (zoomLabel) zoomLabel.textContent = `${Math.round(state.zoom * 100)}%`;
    }

    function clientToFlow(clientX, clientY) {
      const rect = viewport.getBoundingClientRect();
      return {
        x: (clientX - rect.left - state.panX) / state.zoom,
        y: (clientY - rect.top - state.panY) / state.zoom,
      };
    }

    function snap(v) {
      if (!state.snap) return v;
      return Math.round(v / state.snap) * state.snap;
    }

    function byId() {
      return Object.fromEntries(state.nodes.map((n) => [n.id, n]));
    }

    function escAttr(v) {
      return String(v == null ? '' : v)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;');
    }

    function escHtml(v) {
      const d = document.createElement('div');
      d.textContent = v == null ? '' : String(v);
      return d.innerHTML;
    }

    function sourceHandleOf(edge, srcNode) {
      if (edge.sourceHandle) return edge.sourceHandle;
      if (isBranchNode(srcNode)) return 'yes';
      return 'source';
    }

    function renderEdges() {
      const map = byId();
      state.laneTable = buildLaneTable(state.edges);
      edgesLayer.innerHTML = state.edges.map((e) => {
        const path = routeEdge(e, map, state.laneTable);
        if (!path) return '';
        const mid = path.at(0.5);
        const selected = state.selectedEdgeId === e.id ? ' selected' : '';
        const dropTarget = state.dropEdgeId === e.id ? ' is-drop-target' : '';
        const marker = (selected || dropTarget)
          ? `url(#${markerActiveId})`
          : `url(#${markerId})`;
        const label = edgeLabelText(e);
        const labelW = Math.max(36, label.length * 7 + 16);
        const labelHtml = label
          ? `<g class="fc-edge-label" transform="translate(${mid.x}, ${mid.y})">
              <rect class="fc-edge-label-bg" x="${-labelW / 2}" y="-10" width="${labelW}" height="20" rx="6"></rect>
              <text class="fc-edge-label-text" text-anchor="middle" dominant-baseline="middle">${escHtml(label)}</text>
            </g>`
          : '';
        let endpoints = '';
        if (selected && !state.readOnly) {
          const pSrc = path.at(0.18);
          const pTgt = path.at(0.82);
          endpoints = `
            <circle class="fc-edge-updater" data-end="source" data-id="${escAttr(e.id)}" cx="${pSrc.x}" cy="${pSrc.y}" r="6"></circle>
            <circle class="fc-edge-updater" data-end="target" data-id="${escAttr(e.id)}" cx="${pTgt.x}" cy="${pTgt.y}" r="6"></circle>`;
        }
        return `<g class="fc-edge${selected}${dropTarget}" data-id="${escAttr(e.id)}">
          <path class="fc-edge-hit" d="${path.d}"></path>
          <path class="fc-edge-path" d="${path.d}" marker-end="${marker}"></path>
          ${labelHtml}
          ${endpoints}
        </g>`;
      }).join('');

      edgesLayer.querySelectorAll('.fc-edge-hit').forEach((el) => {
        el.addEventListener('pointerdown', onEdgePointerDown);
      });
      edgesLayer.querySelectorAll('.fc-edge-updater').forEach((el) => {
        el.addEventListener('pointerdown', onEdgeUpdaterPointerDown);
      });
    }

    function nodeHtml(node) {
      if (callbacks.renderNode) {
        return callbacks.renderNode(node, {
          selected: state.selectedNodeId === node.id,
          readOnly: state.readOnly,
        });
      }
      const selected = state.selectedNodeId === node.id ? ' selected' : '';
      const title = (node.data && (node.data.label || node.data.name)) || node.id;
      const sub = (node.data && node.data.subtitle) || node.type || '';
      return {
        className: `fc-node${selected}`,
        body: `<div class="fc-node-label">${escHtml(title)}</div><div class="fc-node-sub">${escHtml(sub)}</div>`,
      };
    }

    function handlesHtml(node) {
      if (state.readOnly) return '';
      const id = escAttr(node.id);
      if (isHumanDecisionNode(node)) {
        return `
          <div class="fc-handle fc-handle-target" data-nodeid="${id}" data-handleid="target" data-handletype="target" title="target">
            <span class="fc-handle-dot"></span>
          </div>
          <div class="fc-handle fc-handle-source fc-handle-yes" data-nodeid="${id}" data-handleid="approve" data-handletype="source" title="Утвердить (Approve)">
            <span class="fc-handle-dot"></span><span class="fc-handle-tag">Y</span>
          </div>
          <div class="fc-handle fc-handle-source fc-handle-changes" data-nodeid="${id}" data-handleid="changes" data-handletype="source" title="Уточнить / перегенерация (Request changes)">
            <span class="fc-handle-dot"></span><span class="fc-handle-tag">~</span>
          </div>
          <div class="fc-handle fc-handle-source fc-handle-no" data-nodeid="${id}" data-handleid="reject" data-handletype="source" title="Отклонить (Reject)">
            <span class="fc-handle-dot"></span><span class="fc-handle-tag">N</span>
          </div>`;
      }
      if (isBranchNode(node)) {
        return `
          <div class="fc-handle fc-handle-target" data-nodeid="${id}" data-handleid="target" data-handletype="target" title="target">
            <span class="fc-handle-dot"></span>
          </div>
          <div class="fc-handle fc-handle-source fc-handle-yes" data-nodeid="${id}" data-handleid="yes" data-handletype="source" title="Yes / Pass">
            <span class="fc-handle-dot"></span><span class="fc-handle-tag">Y</span>
          </div>
          <div class="fc-handle fc-handle-source fc-handle-no" data-nodeid="${id}" data-handleid="no" data-handletype="source" title="No / Fail">
            <span class="fc-handle-dot"></span><span class="fc-handle-tag">N</span>
          </div>`;
      }
      return `
        <div class="fc-handle fc-handle-target" data-nodeid="${id}" data-handleid="target" data-handletype="target" title="target">
          <span class="fc-handle-dot"></span>
        </div>
        <div class="fc-handle fc-handle-source" data-nodeid="${id}" data-handleid="source" data-handletype="source" title="source">
          <span class="fc-handle-dot"></span>
        </div>`;
    }

    function syncNodeSizesFromDom() {
      let changed = false;
      nodesEl.querySelectorAll('.fc-node').forEach((el) => {
        const id = el.dataset.id;
        const node = state.nodes.find((n) => n.id === id);
        if (!node) return;
        const mins = minSize(node);
        el.style.width = 'max-content';
        el.style.height = 'auto';
        el.style.maxWidth = `${NODE_MAX_W}px`;
        el.style.minWidth = `${mins.w}px`;
        el.style.minHeight = `${mins.h}px`;
        let w = Math.ceil(Math.max(mins.w, el.offsetWidth));
        w = Math.min(NODE_MAX_W, w);
        el.style.width = `${w}px`;
        el.style.height = 'auto';
        const h = Math.ceil(Math.max(mins.h, el.offsetHeight));
        el.style.maxWidth = '';
        el.style.minWidth = '';
        el.style.minHeight = '';
        el.style.width = `${w}px`;
        el.style.height = `${h}px`;
        if (node.width !== w || node.height !== h) {
          node.width = w;
          node.height = h;
          changed = true;
        }
      });
      return changed;
    }

    function renderNodes() {
      nodesEl.innerHTML = state.nodes.map((node) => {
        const size = defaultSize(node);
        const pos = node.position || { x: 0, y: 0 };
        const rendered = nodeHtml(node);
        const cls = typeof rendered === 'string'
          ? `fc-node${state.selectedNodeId === node.id ? ' selected' : ''}`
          : (rendered.className || 'fc-node');
        const body = typeof rendered === 'string' ? rendered : (rendered.body || '');
        const extraStyle = typeof rendered === 'object' && rendered.style ? rendered.style : '';
        const branchCls = isBranchNode(node) ? ' fc-branch' : '';
        return `<div class="${cls}${branchCls}" data-id="${escAttr(node.id)}" style="left:${pos.x}px;top:${pos.y}px;width:${size.w}px;height:${size.h}px;${extraStyle}">
          ${body}${handlesHtml(node)}
        </div>`;
      }).join('');

      nodesEl.querySelectorAll('.fc-node').forEach((el) => {
        el.addEventListener('pointerdown', onNodePointerDown);
      });
      // ALL handles can start a connection (source → target strict)
      nodesEl.querySelectorAll('.fc-handle').forEach((el) => {
        el.addEventListener('pointerdown', onHandlePointerDown);
      });
    }

    function render() {
      if (state.destroyed) return;
      mount.classList.toggle('fc-readonly', state.readOnly);
      mount.classList.toggle('fc-connecting', !!state.connection);
      renderNodes();
      syncNodeSizesFromDom();
      renderEdges();
      applyTransform();
      sizeStage();
    }

    function sizeStage() {
      let maxX = 1200;
      let maxY = 800;
      state.nodes.forEach((n) => {
        const s = defaultSize(n);
        const p = n.position || { x: 0, y: 0 };
        maxX = Math.max(maxX, p.x + s.w + 200);
        maxY = Math.max(maxY, p.y + s.h + 200);
      });
      stage.style.width = `${maxX}px`;
      stage.style.height = `${maxY}px`;
    }

    function selectOnly(nodeId, edgeId, opts) {
      state.selectedNodeId = nodeId;
      state.selectedEdgeId = edgeId;
      const light = opts && opts.light;
      if (light) {
        nodesEl.querySelectorAll('.fc-node').forEach((el) => {
          el.classList.toggle('selected', el.dataset.id === nodeId);
        });
        renderEdges();
        emitSelect();
      } else {
        render();
        emitSelect();
      }
      try { viewport.focus({ preventScroll: true }); } catch (_) { /* */ }
    }

    function onEdgePointerDown(ev) {
      if (ev.button !== 0) return;
      if (state.connection) return;
      ev.preventDefault();
      ev.stopPropagation();
      const id = ev.currentTarget.closest('[data-id]')?.dataset.id;
      if (!id) return;
      selectOnly(null, id);
    }

    // —— Connect / Reconnect (xyflow XYHandle.onPointerDown model) ——

    function beginConnection(ev, optsConn) {
      if (state.readOnly) return;
      const startX = ev.clientX;
      const startY = ev.clientY;
      const from = {
        nodeId: optsConn.nodeId,
        handleId: optsConn.handleId,
        handleType: optsConn.handleType, // 'source' | 'target'
      };
      const reconnect = optsConn.reconnect || null; // { edgeId, end: 'source'|'target' }

      let started = false;
      let closest = null;

      const fromNode = state.nodes.find((n) => n.id === from.nodeId);
      if (!fromNode) return;
      const fromPos = portPoint(fromNode, from.handleId);

      function paintPreview(toX, toY, snapHandle) {
        const to = snapHandle
          ? { x: snapHandle.x, y: snapHandle.y }
          : { x: toX, y: toY };
        let x1; let y1; let x2; let y2;
        if (reconnect && reconnect.end === 'source') {
          // dragging source end: free → fixed target
          const edge = state.edges.find((e) => e.id === reconnect.edgeId);
          const tgt = state.nodes.find((n) => n.id === edge.target);
          const b = portPoint(tgt, edge.targetHandle || 'target');
          x1 = to.x; y1 = to.y; x2 = b.x; y2 = b.y;
        } else if (reconnect && reconnect.end === 'target') {
          const edge = state.edges.find((e) => e.id === reconnect.edgeId);
          const src = state.nodes.find((n) => n.id === edge.source);
          const a = portPoint(src, sourceHandleOf(edge, src));
          x1 = a.x; y1 = a.y; x2 = to.x; y2 = to.y;
        } else if (from.handleType === 'target') {
          // dragging from target handle → connect to a source
          x1 = to.x; y1 = to.y; x2 = fromPos.x; y2 = fromPos.y;
        } else {
          x1 = fromPos.x; y1 = fromPos.y; x2 = to.x; y2 = to.y;
        }
        preview.classList.remove('fc-hidden');
        preview.setAttribute('d', previewPath(x1, y1, x2, y2));
        preview.setAttribute('marker-end', `url(#${markerActiveId})`);
        preview.classList.toggle('is-valid', !!snapHandle);
        preview.classList.toggle('is-invalid', !snapHandle && started);
      }

      function clearHighlight() {
        mount.querySelectorAll('.is-drop, .is-drop-node').forEach((el) => {
          el.classList.remove('is-drop', 'is-drop-node');
        });
      }

      function highlight(handle) {
        clearHighlight();
        if (!handle) return;
        const nodeEl = nodesEl.querySelector(`.fc-node[data-id="${CSS.escape(handle.nodeId)}"]`);
        const handleEl = nodesEl.querySelector(
          `.fc-handle[data-nodeid="${CSS.escape(handle.nodeId)}"][data-handleid="${CSS.escape(handle.handleId)}"]`
        );
        nodeEl?.classList.add('is-drop-node');
        handleEl?.classList.add('is-drop');
      }

      function onMove(e) {
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        if (!started && dx * dx + dy * dy < DRAG_THRESHOLD * DRAG_THRESHOLD) return;
        if (!started) {
          started = true;
          state.connection = { from, reconnect };
          mount.classList.add('fc-connecting');
        }
        const flow = clientToFlow(e.clientX, e.clientY);
        // xyflow: connectionRadius in flow/renderer space
        closest = getClosestHandle(
          flow,
          state.nodes,
          from,
          CONNECTION_RADIUS / Math.max(state.zoom, 0.01)
        );
        // exclude self-node for reconnect target changes appropriately
        if (closest && reconnect) {
          const edge = state.edges.find((ed) => ed.id === reconnect.edgeId);
          if (reconnect.end === 'target' && closest.nodeId === edge.source) closest = null;
          if (reconnect.end === 'source' && closest.nodeId === edge.target) closest = null;
        }
        highlight(closest);
        paintPreview(flow.x, flow.y, closest);
      }

      function onUp(e) {
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        document.removeEventListener('pointercancel', onUp);
        clearHighlight();
        preview.classList.add('fc-hidden');
        preview.classList.remove('is-valid', 'is-invalid');
        mount.classList.remove('fc-connecting');
        state.connection = null;

        if (!started) {
          // click without drag — just select node
          if (!reconnect) selectOnly(from.nodeId, null);
          return;
        }

        const flow = clientToFlow(e.clientX, e.clientY);
        closest = getClosestHandle(flow, state.nodes, from, CONNECTION_RADIUS / Math.max(state.zoom, 0.01));

        if (reconnect) {
          finishReconnect(reconnect, closest);
        } else if (closest) {
          finishConnect(from, closest);
        } else {
          render();
        }
      }

      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
      document.addEventListener('pointercancel', onUp);
      ev.preventDefault();
      ev.stopPropagation();
    }

    function finishConnect(from, to) {
      let source; let target; let sourceHandle; let targetHandle;
      if (from.handleType === 'source') {
        source = from.nodeId;
        sourceHandle = from.handleId;
        target = to.nodeId;
        targetHandle = to.handleId;
      } else {
        source = to.nodeId;
        sourceHandle = to.handleId;
        target = from.nodeId;
        targetHandle = from.handleId;
      }
      if (source === target) { render(); return; }
      if (!connectionAllowed(source, target, sourceHandle)) { render(); return; }
      addEdge(source, target, { sourceHandle, targetHandle });
    }

    function finishReconnect(reconnect, closest) {
      const edge = state.edges.find((e) => e.id === reconnect.edgeId);
      if (!edge || !closest) { render(); return; }
      const nextSource = reconnect.end === 'source' ? closest.nodeId : edge.source;
      const nextTarget = reconnect.end === 'target' ? closest.nodeId : edge.target;
      const nextHandle = reconnect.end === 'source'
        ? (closest.handleId || 'source')
        : (edge.sourceHandle || 'source');
      if (!connectionAllowed(nextSource, nextTarget, nextHandle)) { render(); return; }
      beginHistory();
      if (reconnect.end === 'target') {
        edge.target = closest.nodeId;
        edge.targetHandle = closest.handleId || 'target';
      } else {
        edge.source = closest.nodeId;
        edge.sourceHandle = closest.handleId || 'source';
        const meta = labelFromHandle(edge.sourceHandle);
        edge.data = Object.assign({}, edge.data || {}, {
          label: meta.label || (edge.data && edge.data.label) || '',
          condition: meta.condition != null ? meta.condition : (edge.data && edge.data.condition),
        });
      }
      // drop duplicate
      const dup = state.edges.find((e) =>
        e.id !== edge.id
        && e.source === edge.source
        && e.target === edge.target
        && (e.sourceHandle || 'source') === (edge.sourceHandle || 'source')
      );
      if (dup) {
        state.edges = state.edges.filter((e) => e.id !== dup.id);
      }
      render();
      emitChange();
      emitSelect();
    }

    function onHandlePointerDown(ev) {
      if (ev.button !== 0 || state.readOnly) return;
      const el = ev.currentTarget;
      beginConnection(ev, {
        nodeId: el.dataset.nodeid,
        handleId: el.dataset.handleid,
        handleType: el.dataset.handletype,
      });
    }

    function onEdgeUpdaterPointerDown(ev) {
      if (ev.button !== 0 || state.readOnly) return;
      const edgeId = ev.currentTarget.dataset.id;
      const end = ev.currentTarget.dataset.end;
      const edge = state.edges.find((e) => e.id === edgeId);
      if (!edge) return;
      const map = byId();
      if (end === 'target') {
        // drag target end: from = current source (fixed conceptually), updater acts as target-type drag from source? 
        // xyflow: edgeUpdaterType = 'target' means you're updating the target, starting from target side.
        // We model: from = the FIXED end, reconnect moves the other.
        // For target updater: from is source handle, reconnect end is target.
        const src = map[edge.source];
        beginConnection(ev, {
          nodeId: edge.source,
          handleId: sourceHandleOf(edge, src),
          handleType: 'source',
          reconnect: { edgeId, end: 'target' },
        });
      } else {
        beginConnection(ev, {
          nodeId: edge.target,
          handleId: edge.targetHandle || 'target',
          handleType: 'target',
          reconnect: { edgeId, end: 'source' },
        });
      }
    }

    function addEdge(source, target, meta) {
      const sourceHandle = (meta && meta.sourceHandle) || 'source';
      const targetHandle = (meta && meta.targetHandle) || 'target';
      if (!connectionAllowed(source, target, sourceHandle)) {
        render();
        return false;
      }
      if (state.edges.some((e) =>
        e.source === source && e.target === target
        && (e.sourceHandle || 'source') === sourceHandle
      )) {
        render();
        return false;
      }
      beginHistory();
      const labels = labelFromHandle(sourceHandle);
      const data = (meta && meta.data)
        ? Object.assign({}, meta.data)
        : { label: labels.label, condition: labels.condition };
      state.edges.push({
        id: (meta && meta.id) || uid('e'),
        source,
        target,
        sourceHandle,
        targetHandle,
        data,
      });
      render();
      emitChange();
      return true;
    }

    function findClosestEdge(flowPos, radius) {
      const map = byId();
      if (!state.laneTable) state.laneTable = buildLaneTable(state.edges);
      let best = null;
      let bestDist = radius;
      state.edges.forEach((e) => {
        const path = routeEdge(e, map, state.laneTable);
        if (!path || !path.points || path.points.length < 2) return;
        for (let i = 0; i < path.points.length - 1; i += 1) {
          const d = pointToSegmentDist(flowPos, path.points[i], path.points[i + 1]);
          if (d <= bestDist) {
            bestDist = d;
            best = e;
          }
        }
      });
      return best;
    }

    function clearDropHighlight() {
      if (!state.dropEdgeId) {
        mount.classList.remove('fc-palette-over');
        return;
      }
      state.dropEdgeId = null;
      edgesLayer.querySelectorAll('.fc-edge.is-drop-target').forEach((el) => {
        el.classList.remove('is-drop-target');
      });
      mount.classList.remove('fc-palette-over');
    }

    function setDropHighlight(edgeId) {
      mount.classList.add('fc-palette-over');
      if (state.dropEdgeId === edgeId) return;
      state.dropEdgeId = edgeId;
      edgesLayer.querySelectorAll('.fc-edge').forEach((el) => {
        el.classList.toggle('is-drop-target', !!edgeId && el.dataset.id === edgeId);
      });
    }

    function insertNodeIntoEdge(edgeId, node) {
      const edge = state.edges.find((e) => e.id === edgeId);
      if (!edge) {
        beginHistory();
        state.nodes.push(node);
        selectOnly(node.id, null);
        emitChange();
        return node;
      }
      if (callbacks.canInsertIntoEdge) {
        try {
          if (callbacks.canInsertIntoEdge(edge, node) === false) {
            return null;
          }
        } catch (_err) {
          return null;
        }
      }
      beginHistory();
      state.nodes.push(node);
      state.edges = state.edges.filter((e) => e.id !== edgeId);

      const inData = edge.data ? JSON.parse(JSON.stringify(edge.data)) : {};
      state.edges.push({
        id: uid('e'),
        source: edge.source,
        target: node.id,
        sourceHandle: edge.sourceHandle || null,
        targetHandle: 'target',
        data: inData,
      });

      const outHandle = isBranchNode(node) ? 'yes' : 'source';
      const outMeta = labelFromHandle(outHandle);
      state.edges.push({
        id: uid('e'),
        source: node.id,
        target: edge.target,
        sourceHandle: outHandle,
        targetHandle: edge.targetHandle || 'target',
        data: {
          label: outMeta.label || '',
          condition: outMeta.condition,
        },
      });

      selectOnly(node.id, null);
      emitChange();
      return node;
    }

    function hasPalettePayload(dt) {
      if (document.body.classList.contains('fc-palette-dragging')) return true;
      if (paletteSession) return true;
      if (!dt) return false;
      if (typeof dt.types !== 'undefined') {
        const types = Array.from(dt.types || []);
        if (types.includes(PALETTE_MIME)) return true;
      }
      return false;
    }

    function applyPaletteDrop(payload, clientX, clientY) {
      if (state.readOnly || !callbacks.createDroppedNode || !payload) return null;
      if (!(payload.type || payload.kind || payload.add)) return null;

      const flowPos = clientToFlow(clientX, clientY);
      const edge = findClosestEdge(flowPos, EDGE_DROP_RADIUS);
      const draft = {
        type: payload.type || payload.kind || payload.add,
        kind: payload.kind || payload.add || payload.type,
        position: { x: flowPos.x, y: flowPos.y },
        insertEdgeId: edge ? edge.id : null,
        payload,
      };
      const created = callbacks.createDroppedNode(draft);
      if (!created) return null;

      const size = defaultSize(created);
      const node = {
        id: String(created.id || uid('n')),
        type: created.type || draft.type || 'default',
        position: created.position || {
          x: snap(flowPos.x - size.w / 2),
          y: snap(flowPos.y - size.h / 2),
        },
        data: created.data || {},
        width: created.width,
        height: created.height,
      };
      if (!created.position) {
        node.position = {
          x: snap(flowPos.x - defaultSize(node).w / 2),
          y: snap(flowPos.y - defaultSize(node).h / 2),
        };
      }

      clearDropHighlight();
      if (edge) {
        const inserted = insertNodeIntoEdge(edge.id, node);
        if (!inserted) return null;
        return inserted;
      }
      beginHistory();
      state.nodes.push(node);
      selectOnly(node.id, null);
      emitChange();
      return node;
    }

    function hoverPalette(clientX, clientY) {
      if (state.readOnly || !callbacks.createDroppedNode) return;
      const flowPos = clientToFlow(clientX, clientY);
      const edge = findClosestEdge(flowPos, EDGE_DROP_RADIUS);
      setDropHighlight(edge ? edge.id : null);
    }

    function dropPalette(payload, clientX, clientY) {
      return applyPaletteDrop(payload, clientX, clientY);
    }

    function onPaletteDragOver(ev) {
      if (state.readOnly || !callbacks.createDroppedNode) return;
      if (!hasPalettePayload(ev.dataTransfer)) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'copy';
      hoverPalette(ev.clientX, ev.clientY);
    }

    function onPaletteDragLeave(ev) {
      const rect = viewport.getBoundingClientRect();
      const x = ev.clientX;
      const y = ev.clientY;
      if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) return;
      clearDropHighlight();
    }

    function onPaletteDrop(ev) {
      if (state.readOnly || !callbacks.createDroppedNode) return;
      const payload = parsePalettePayload(ev.dataTransfer);
      clearDropHighlight();
      if (!payload) return;
      ev.preventDefault();
      ev.stopPropagation();
      applyPaletteDrop(payload, ev.clientX, ev.clientY);
    }

    function onPaletteDragEndGlobal() {
      clearDropHighlight();
    }

    function onNodePointerDown(ev) {
      if (ev.button !== 0) return;
      if (ev.target.closest('.fc-handle')) return;
      if (state.connection) return;
      const id = ev.currentTarget.dataset.id;
      const node = state.nodes.find((n) => n.id === id);
      if (!node) return;
      // Light select — do NOT destroy DOM mid-gesture (prevents rubber-band)
      selectOnly(id, null, { light: true });
      if (state.readOnly) return;

      const pt = clientToFlow(ev.clientX, ev.clientY);
      beginHistory();
      state.interaction = {
        type: 'node',
        node,
        offsetX: pt.x - node.position.x,
        offsetY: pt.y - node.position.y,
        moved: false,
        originX: node.position.x,
        originY: node.position.y,
      };
      mount.classList.add('fc-dragging');
      ev.preventDefault();
      ev.stopPropagation();
    }

    function onViewportPointerDown(ev) {
      if (ev.button !== 0 && ev.button !== 1) return;
      if (ev.target.closest('.fc-node')
        || ev.target.closest('.fc-edge-hit')
        || ev.target.closest('.fc-edge-updater')
        || ev.target.closest('.fc-handle')) {
        return;
      }
      if (state.selectedNodeId || state.selectedEdgeId) selectOnly(null, null);
      state.interaction = {
        type: 'pan',
        startX: ev.clientX,
        startY: ev.clientY,
        panX: state.panX,
        panY: state.panY,
      };
      viewport.classList.add('is-panning');
      ev.preventDefault();
    }

    function redrawLiveEdges() {
      const map = byId();
      if (!state.laneTable) state.laneTable = buildLaneTable(state.edges);
      state.edges.forEach((e) => {
        const g = edgesLayer.querySelector(`g[data-id="${CSS.escape(e.id)}"]`);
        if (!g) return;
        const path = routeEdge(e, map, state.laneTable);
        if (!path) return;
        g.querySelectorAll('path').forEach((p) => p.setAttribute('d', path.d));
        const mid = path.at(0.5);
        const label = g.querySelector('.fc-edge-label');
        if (label) label.setAttribute('transform', `translate(${mid.x}, ${mid.y})`);
        const ends = g.querySelectorAll('.fc-edge-updater');
        ends.forEach((c) => {
          const pt = c.dataset.end === 'source' ? path.at(0.18) : path.at(0.82);
          c.setAttribute('cx', pt.x);
          c.setAttribute('cy', pt.y);
        });
      });
    }

    function onDocMove(ev) {
      const action = state.interaction;
      if (!action || state.connection) return;
      if (action.type === 'pan') {
        state.panX = action.panX + (ev.clientX - action.startX);
        state.panY = action.panY + (ev.clientY - action.startY);
        applyTransform();
        return;
      }
      if (action.type === 'node' && !state.readOnly) {
        const pt = clientToFlow(ev.clientX, ev.clientY);
        // No grid snap while dragging — snap only on drop (avoids "magnet" fights)
        action.node.position = {
          x: Math.max(0, pt.x - action.offsetX),
          y: Math.max(0, pt.y - action.offsetY),
        };
        action.moved = true;
        const el = nodesEl.querySelector(`[data-id="${CSS.escape(action.node.id)}"]`);
        if (el) {
          el.style.left = `${action.node.position.x}px`;
          el.style.top = `${action.node.position.y}px`;
        }
        redrawLiveEdges();
      }
    }

    function onDocUp() {
      const action = state.interaction;
      viewport.classList.remove('is-panning');
      mount.classList.remove('fc-dragging');
      if (action && action.type === 'node' && action.moved) {
        if (state.snap) {
          action.node.position = {
            x: snap(action.node.position.x),
            y: snap(action.node.position.y),
          };
          const el = nodesEl.querySelector(`[data-id="${CSS.escape(action.node.id)}"]`);
          if (el) {
            el.style.left = `${action.node.position.x}px`;
            el.style.top = `${action.node.position.y}px`;
          }
          redrawLiveEdges();
        }
        sizeStage();
        emitChange();
      } else if (action && action.type === 'node') {
        discardHistoryCapture();
      }
      state.interaction = null;
      if (state.pendingGraph) {
        const g = state.pendingGraph;
        state.pendingGraph = null;
        setGraph(g);
      }
    }

    function onWheel(ev) {
      ev.preventDefault();
      zoomAt(ev.deltaY < 0 ? 1 : -1, ev.clientX, ev.clientY);
    }

    function zoomAt(dir, clientX, clientY) {
      const rect = viewport.getBoundingClientRect();
      const mx = clientX != null ? clientX - rect.left : rect.width / 2;
      const my = clientY != null ? clientY - rect.top : rect.height / 2;
      const prev = state.zoom;
      const next = clamp(prev * (dir > 0 ? 1.12 : 0.89), ZOOM_MIN, ZOOM_MAX);
      const scale = next / prev;
      state.panX = mx - scale * (mx - state.panX);
      state.panY = my - scale * (my - state.panY);
      state.zoom = next;
      applyTransform();
    }

    function fitView() {
      if (!state.nodes.length) {
        state.panX = 40; state.panY = 40; state.zoom = 1;
        applyTransform();
        return true;
      }
      let minX = Infinity; let minY = Infinity; let maxX = -Infinity; let maxY = -Infinity;
      state.nodes.forEach((n) => {
        const s = defaultSize(n);
        const p = n.position || { x: 0, y: 0 };
        minX = Math.min(minX, p.x); minY = Math.min(minY, p.y);
        maxX = Math.max(maxX, p.x + s.w); maxY = Math.max(maxY, p.y + s.h);
      });
      const pad = 48;
      const rect = viewport.getBoundingClientRect();
      if (rect.width < 40 || rect.height < 40) return false;
      const scaleX = (rect.width - pad * 2) / Math.max(1, maxX - minX);
      const scaleY = (rect.height - pad * 2) / Math.max(1, maxY - minY);
      state.zoom = clamp(Math.min(scaleX, scaleY, 1), ZOOM_MIN, ZOOM_MAX);
      state.panX = pad - minX * state.zoom;
      state.panY = pad - minY * state.zoom;
      applyTransform();
      return true;
    }

    function fitViewWhenReady(attempts) {
      const left = attempts == null ? 16 : attempts;
      if (fitView()) return;
      if (left <= 0) {
        fitView();
        return;
      }
      requestAnimationFrame(() => fitViewWhenReady(left - 1));
    }

    function autoLayout(opts) {
      const options = opts || {};
      if (!state.nodes.length) return;
      if (!options.silent) beginHistory();
      // Cycle-safe BFS layering (longest-path re-queue hangs on cycles / Yes-No merges).
      const start = state.nodes.find((n) => n.type === 'START' || n.type === 'start') || state.nodes[0];
      const succs = {};
      state.nodes.forEach((n) => { succs[n.id] = []; });
      state.edges.forEach((e) => {
        if (succs[e.source] && e.target !== e.source) succs[e.source].push(e.target);
      });

      const layer = {};
      const queue = [start.id];
      layer[start.id] = 0;
      let guard = 0;
      const guardMax = state.nodes.length * state.nodes.length + 8;
      while (queue.length && guard < guardMax) {
        guard += 1;
        const cur = queue.shift();
        (succs[cur] || []).forEach((next) => {
          // Visit once — never re-queue (prevents infinite loop on cycles)
          if (layer[next] != null) return;
          layer[next] = layer[cur] + 1;
          queue.push(next);
        });
      }

      let maxLayer = 0;
      state.nodes.forEach((n) => {
        if (layer[n.id] == null) {
          maxLayer = Math.max(maxLayer, ...Object.values(layer), 0);
          layer[n.id] = maxLayer + 1;
        }
        maxLayer = Math.max(maxLayer, layer[n.id]);
      });
      state.nodes.forEach((n) => {
        if (n.type === 'END' || n.type === 'end') layer[n.id] = maxLayer;
      });

      const columns = {};
      state.nodes.forEach((n) => {
        const col = layer[n.id] || 0;
        if (!columns[col]) columns[col] = [];
        columns[col].push(n);
      });

      Object.keys(columns).forEach((c) => {
        columns[c].sort((a, b) => {
          const aNo = state.edges.some((e) => e.target === a.id && (e.sourceHandle === 'no' || (e.data && e.data.condition === 'no')));
          const bNo = state.edges.some((e) => e.target === b.id && (e.sourceHandle === 'no' || (e.data && e.data.condition === 'no')));
          if (aNo !== bNo) return aNo ? 1 : -1;
          return String(a.id).localeCompare(String(b.id));
        });
      });

      // Measure content sizes before placing so gaps account for tall/wide labels.
      renderNodes();
      syncNodeSizesFromDom();

      const sortedCols = Object.keys(columns).map(Number).sort((a, b) => a - b);
      const colWidths = {};
      sortedCols.forEach((col) => {
        colWidths[col] = Math.max(
          DEFAULT_NODE.w,
          ...columns[col].map((n) => defaultSize(n).w)
        );
      });
      const colGap = 80;
      const rowPad = 48;
      let x = 80;
      const colX = {};
      sortedCols.forEach((col) => {
        colX[col] = x;
        x += colWidths[col] + colGap;
      });

      const colHeights = {};
      sortedCols.forEach((col) => {
        const list = columns[col];
        let total = 0;
        list.forEach((n, idx) => {
          total += defaultSize(n).h;
          if (idx < list.length - 1) total += rowPad;
        });
        colHeights[col] = total;
      });
      const maxBlock = Math.max(0, ...Object.values(colHeights));
      const midY = 80 + maxBlock / 2;

      sortedCols.forEach((col) => {
        const list = columns[col];
        const blockH = colHeights[col] || 0;
        let y = midY - blockH / 2;
        list.forEach((n) => {
          const s = defaultSize(n);
          n.position = { x: colX[col], y };
          y += s.h + rowPad;
        });
      });
      render();
      if (!options.skipFit) fitViewWhenReady();
      if (!options.silent) emitChange();
    }

    /**
     * On first open: run layered auto-layout when positions are missing/broken.
     * Otherwise keep the saved user layout and only fit the viewport.
     */
    function ensureLayout(opts) {
      const options = opts || {};
      if (!hasUserLayout(state.nodes)) {
        autoLayout({ silent: options.silent !== false, skipFit: false });
        return 'auto';
      }
      fitViewWhenReady();
      return 'kept';
    }

    function isStageGateNode(node) {
      if (!node) return false;
      if (node.id === 'stage-artifact-gate') return true;
      const gateKind = node.data && node.data.config && node.data.config.gate_kind;
      return gateKind === 'stage_artifact';
    }

    function isEndType(type) {
      return type === 'END' || type === 'end';
    }

    function isFailLikeHandle(handleId, data) {
      const h = String(handleId || '').trim().toLowerCase();
      const c = String((data && data.condition) || '').trim().toLowerCase();
      const fail = new Set(['no', 'fail', 'false', 'block', 'error', 'reject']);
      return fail.has(h) || fail.has(c);
    }

    /**
     * Normalize unlabeled outs from decision nodes onto the happy-path handle
     * so bridged / healed edges attach to Yes/Approve — not a phantom mid handle.
     */
    function normalizeBridgeHandle(sourceId, sourceHandle, data) {
      const src = state.nodes.find((n) => n.id === sourceId);
      const raw = sourceHandle || '';
      const fail = isFailLikeHandle(raw, data);
      if (raw && raw !== 'source' && raw !== 'out') return raw;
      if (!src) return raw || 'source';
      if (isHumanDecisionNode(src)) return fail ? 'reject' : 'approve';
      if (isBranchNode(src)) return fail ? 'no' : 'yes';
      return raw || 'source';
    }

    function reachableNodeIds(originId) {
      const adj = {};
      state.nodes.forEach((n) => { adj[n.id] = []; });
      state.edges.forEach((e) => {
        if (adj[e.source]) adj[e.source].push(e.target);
      });
      const seen = new Set();
      const stack = [originId];
      while (stack.length) {
        const cur = stack.pop();
        if (seen.has(cur)) continue;
        seen.add(cur);
        (adj[cur] || []).forEach((nxt) => stack.push(nxt));
      }
      return seen;
    }

    function edgeExists(source, target, sourceHandle) {
      const sh = sourceHandle || 'source';
      return state.edges.some((e) =>
        e.source === source
        && e.target === target
        && (e.sourceHandle || 'source') === sh
      );
    }

    function pushEdge(source, target, meta) {
      if (!source || !target || source === target) return false;
      const sourceHandle = (meta && meta.sourceHandle) || 'source';
      const targetHandle = (meta && meta.targetHandle) || 'target';
      if (!connectionAllowed(source, target, sourceHandle)) return false;
      if (edgeExists(source, target, sourceHandle)) return false;
      const labels = labelFromHandle(sourceHandle);
      const data = (meta && meta.data)
        ? Object.assign({}, meta.data)
        : { label: labels.label, condition: labels.condition };
      state.edges.push({
        id: (meta && meta.id) || uid('e'),
        source,
        target,
        sourceHandle,
        targetHandle,
        data,
      });
      return true;
    }

    /**
     * If the mandatory artifact gate can no longer reach END, restore gate → END
     * on the Yes/Pass handle only (never auto-wire No/fail to completion).
     */
    function ensureStageGateBoundToEnd() {
      const gate = state.nodes.find(isStageGateNode);
      const ends = state.nodes.filter((n) => isEndType(n.type));
      if (!gate || !ends.length) return false;
      const reach = reachableNodeIds(gate.id);
      if (ends.some((end) => reach.has(end.id))) return false;
      // Prefer a stable primary END key when present.
      const preferred = ends.find((n) => n.id === 'end') || ends[0];
      return pushEdge(gate.id, preferred.id, {
        sourceHandle: 'yes',
        targetHandle: 'target',
        data: { label: 'Yes', condition: 'yes', locked_spine: true },
      });
    }

    /**
     * When removing a node from a chain A → X → B, reconnect A → B so mandatory
     * spine links (e.g. gate → END) are not silently dropped.
     *
     * Fail/No/Reject edges are never auto-bridged onto END — only the happy path
     * may reattach to stage completion. An unwired fail port stays open and must
     * be connected explicitly (validated on save / simulate / publish).
     */
    function bridgeAroundRemovedNode(nodeId, incoming, outgoing) {
      incoming.forEach((inn) => {
        const fail = isFailLikeHandle(inn.sourceHandle, inn.data);
        const sourceHandle = normalizeBridgeHandle(inn.source, inn.sourceHandle, inn.data);
        outgoing.forEach((out) => {
          if (inn.source === out.target) return;
          const tgt = state.nodes.find((n) => n.id === out.target);
          if (fail && tgt && isEndType(tgt.type)) return;
          const labels = labelFromHandle(sourceHandle);
          const data = Object.assign({}, inn.data || {}, { bridged_from: nodeId });
          if (labels.condition && data.condition == null) data.condition = labels.condition;
          if (labels.label && !data.label) data.label = labels.label;
          pushEdge(inn.source, out.target, {
            sourceHandle,
            targetHandle: out.targetHandle || 'target',
            data,
          });
        });
      });
    }

    function deleteSelection() {
      if (state.readOnly) return false;
      if (state.selectedEdgeId) {
        const edge = state.edges.find((e) => e.id === state.selectedEdgeId);
        if (edge) {
          const src = state.nodes.find((n) => n.id === edge.source);
          const tgt = state.nodes.find((n) => n.id === edge.target);
          // Keep mandatory spine wiring: do not cut edges that only serve locked control points.
          if (nodeIsLocked(src) && nodeIsLocked(tgt)) return false;
          if (nodeIsLocked(src) || nodeIsLocked(tgt)) {
            const touchesGate = !!(isStageGateNode(src) || isStageGateNode(tgt));
            const failEdge = !!(
              (edge.sourceHandle || '') === 'no'
              || (edge.data && ['no', 'fail', 'false', 'block'].includes(String(edge.data.condition || '').toLowerCase()))
            );
            // Pass/Yes spine edges are undeleteable; No/fail remediation may be rewired.
            if (touchesGate && !failEdge) return false;
          }
        }
        beginHistory();
        state.edges = state.edges.filter((e) => e.id !== state.selectedEdgeId);
        state.selectedEdgeId = null;
        ensureStageGateBoundToEnd();
        render(); emitChange(); emitSelect();
        return true;
      }
      if (state.selectedNodeId) {
        const node = state.nodes.find((n) => n.id === state.selectedNodeId);
        if (!node || nodeIsLocked(node)) return false;
        const ends = state.nodes.filter((n) => n.type === 'END' || n.type === 'end');
        if ((node.type === 'END' || node.type === 'end') && ends.length <= 1) return false;
        const id = node.id;
        const incoming = state.edges.filter((e) => e.target === id);
        const outgoing = state.edges.filter((e) => e.source === id);
        beginHistory();
        state.nodes = state.nodes.filter((n) => n.id !== id);
        state.edges = state.edges.filter((e) => e.source !== id && e.target !== id);
        bridgeAroundRemovedNode(id, incoming, outgoing);
        ensureStageGateBoundToEnd();
        state.selectedNodeId = null;
        render(); emitChange(); emitSelect();
        return true;
      }
      return false;
    }

    function detachSelected() {
      if (state.readOnly || !state.selectedNodeId) return 0;
      const node = state.nodes.find((n) => n.id === state.selectedNodeId);
      if (nodeIsLocked(node)) return 0;
      const id = state.selectedNodeId;
      const incoming = state.edges.filter((e) => e.target === id);
      const outgoing = state.edges.filter((e) => e.source === id);
      if (!incoming.length && !outgoing.length) return 0;
      beginHistory();
      state.edges = state.edges.filter((e) => e.source !== id && e.target !== id);
      bridgeAroundRemovedNode(id, incoming, outgoing);
      ensureStageGateBoundToEnd();
      render(); emitChange(); emitSelect();
      return incoming.length + outgoing.length;
    }

    function updateEdgeData(id, dataPatch) {
      const edge = state.edges.find((e) => e.id === id);
      if (!edge) return;
      edge.data = Object.assign({}, edge.data || {}, dataPatch || {});
      if (dataPatch && (dataPatch.condition === 'yes' || dataPatch.condition === 'pass' || dataPatch.condition === 'approve')) {
        edge.sourceHandle = dataPatch.condition === 'approve' ? 'approve' : 'yes';
        if (!edge.data.label) edge.data.label = dataPatch.condition === 'approve' ? 'Approve' : 'Yes';
      }
      if (dataPatch && (dataPatch.condition === 'request_changes' || dataPatch.condition === 'changes' || dataPatch.condition === 'clarify')) {
        edge.sourceHandle = 'changes';
        if (!edge.data.label) edge.data.label = 'Request changes';
      }
      if (dataPatch && (dataPatch.condition === 'reject')) {
        edge.sourceHandle = 'reject';
        if (!edge.data.label) edge.data.label = 'Reject';
      }
      if (dataPatch && (dataPatch.condition === 'no' || dataPatch.condition === 'fail')) {
        edge.sourceHandle = 'no';
        if (!edge.data.label) edge.data.label = 'No';
      }
      render(); emitChange(); emitSelect();
    }

    function onKeyDown(ev) {
      const t = ev.target;
      if (t) {
        const tag = (t.tagName || '').toUpperCase();
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
        if (t.isContentEditable) return;
        if (typeof t.closest === 'function' && t.closest('input, textarea, select, [contenteditable="true"]')) return;
      }
      // Hidden / inactive mount must not steal Backspace while editing DSL
      if (!mount.getClientRects().length || mount.classList.contains('hidden') || mount.classList.contains('pb-hidden')) return;
      if (mount.classList.contains('de-surface-panel') && !mount.classList.contains('is-active')) return;
      if (mount.classList.contains('pb-surface-panel') && !mount.classList.contains('is-active')) return;
      if (!(mount.offsetWidth || mount.offsetHeight)) return;
      const mod = ev.metaKey || ev.ctrlKey;
      if (mod && (ev.key === 'z' || ev.key === 'Z')) {
        if (ev.shiftKey) {
          if (redo()) ev.preventDefault();
        } else if (undo()) {
          ev.preventDefault();
        }
        return;
      }
      if (mod && (ev.key === 'y' || ev.key === 'Y')) {
        if (redo()) ev.preventDefault();
        return;
      }
      if (ev.key === 'Delete' || ev.key === 'Backspace') {
        if (deleteSelection()) ev.preventDefault();
      }
      if (ev.key === 'Escape') {
        state.connection = null;
        mount.classList.remove('fc-connecting');
        preview.classList.add('fc-hidden');
        selectOnly(null, null);
      }
      if ((ev.key === 'f' || ev.key === 'F') && !ev.metaKey && !ev.ctrlKey) fitView();
    }

    mount.querySelectorAll('.fc-ctrl').forEach((btn) => {
      btn.addEventListener('click', () => {
        const act = btn.dataset.act;
        if (act === 'zoom-in') zoomAt(1);
        if (act === 'zoom-out') zoomAt(-1);
        if (act === 'fit') fitView();
        if (act === 'layout') autoLayout();
      });
    });

    viewport.addEventListener('pointerdown', onViewportPointerDown);
    viewport.addEventListener('wheel', onWheel, { passive: false });
    viewport.addEventListener('dragover', onPaletteDragOver);
    viewport.addEventListener('dragleave', onPaletteDragLeave);
    viewport.addEventListener('drop', onPaletteDrop);
    document.addEventListener('pointermove', onDocMove);
    document.addEventListener('pointerup', onDocUp);
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('fc-palette-dragend', onPaletteDragEndGlobal);

    function setGraph(graph) {
      // Never clobber an in-progress node drag (autosave race → rubber-band)
      if (state.interaction && state.interaction.type === 'node') {
        state.pendingGraph = graph;
        return;
      }
      clearHistory();
      const g = graph || {};
      state.nodes = (g.nodes || []).map((n) => ({
        id: String(n.id || n.key),
        type: n.type || 'default',
        position: {
          x: (n.position && n.position.x) != null ? n.position.x : (n.x || 0),
          y: (n.position && n.position.y) != null ? n.position.y : (n.y || 0),
        },
        data: n.data || {},
        width: n.width,
        height: n.height,
      }));
      state.edges = (g.edges || []).map((e) => {
        const data = e.data ? JSON.parse(JSON.stringify(e.data)) : {};
        let sourceHandle = e.sourceHandle || null;
        if (!sourceHandle && data.condition) {
          const c = String(data.condition).toLowerCase();
          if (c === 'yes' || c === 'pass' || c === 'true') sourceHandle = 'yes';
          if (c === 'no' || c === 'fail' || c === 'false') sourceHandle = 'no';
        }
        if (sourceHandle === 'out') sourceHandle = 'source';
        let targetHandle = e.targetHandle || 'target';
        if (targetHandle === 'in') targetHandle = 'target';
        if (!data.label && data.condition) {
          const c = String(data.condition).toLowerCase();
          if (c === 'yes' || c === 'pass' || c === 'true') data.label = 'Yes';
          if (c === 'no' || c === 'fail' || c === 'false') data.label = 'No';
        }
        return {
          id: String(e.id || e.key || uid('e')),
          source: String(e.source),
          target: String(e.target),
          sourceHandle,
          targetHandle,
          data,
        };
      });
      render();
      if (ensureStageGateBoundToEnd()) {
        // Spine heal may add edges; keep local graph in sync without looping autosave.
        render();
      }
    }

    function getGraph() {
      return { nodes: state.nodes.map(cloneNode), edges: state.edges.map(cloneEdge) };
    }

    function setReadOnly(v) { state.readOnly = !!v; render(); }
    function selectNode(id) { selectOnly(id, null); }
    function selectEdge(id) { selectOnly(null, id); }

    function addNode(node, opts) {
      if (state.readOnly) return null;
      const n = {
        id: String(node.id || uid('n')),
        type: node.type || 'default',
        position: node.position || { x: 120, y: 120 },
        data: node.data || {},
        width: node.width,
        height: node.height,
      };
      const insertEdgeId = (opts && opts.insertEdgeId) || node.insertEdgeId || null;
      if (insertEdgeId) {
        return insertNodeIntoEdge(insertEdgeId, n);
      }
      beginHistory();
      state.nodes.push(n);
      selectOnly(n.id, null);
      emitChange();
      return n;
    }

    function updateNodeData(id, dataPatch) {
      const node = state.nodes.find((n) => n.id === id);
      if (!node) return;
      node.data = Object.assign({}, node.data || {}, dataPatch || {});
      render();
      emitChange();
    }

    function bindPalette(elements, options) {
      return bindPaletteElements(elements, Object.assign({}, options || {}, {
        isDisabled: () => state.readOnly || (options && options.isDisabled && options.isDisabled()),
      }));
    }

    function destroy() {
      state.destroyed = true;
      const idx = liveInstances.indexOf(instanceApi);
      if (idx >= 0) liveInstances.splice(idx, 1);
      document.removeEventListener('pointermove', onDocMove);
      document.removeEventListener('pointerup', onDocUp);
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('fc-palette-dragend', onPaletteDragEndGlobal);
      viewport.removeEventListener('dragover', onPaletteDragOver);
      viewport.removeEventListener('dragleave', onPaletteDragLeave);
      viewport.removeEventListener('drop', onPaletteDrop);
      clearDropHighlight();
      mount.innerHTML = '';
      mount.classList.remove('fc-root', 'fc-readonly', 'fc-connecting', 'fc-palette-over');
    }

    applyTransform();

    const instanceApi = {
      mount,
      readOnly: () => state.readOnly,
      hoverPalette,
      dropPalette,
      clearPaletteHover: clearDropHighlight,
      setGraph, getGraph, setReadOnly, selectNode, selectEdge,
      addNode, addEdge, updateNodeData, updateEdgeData, bindPalette,
      deleteSelection, detachSelected, undo, redo, fitView, fitViewWhenReady, autoLayout, ensureLayout, render, destroy,
      get selectedNodeId() { return state.selectedNodeId; },
      get selectedEdgeId() { return state.selectedEdgeId; },
    };
    liveInstances.push(instanceApi);
    return instanceApi;
  }

  function bindPaletteElements(elements, options) {
    const opts = options || {};
    const list = typeof elements === 'string'
      ? Array.from(document.querySelectorAll(elements))
      : Array.from(elements || []);
    list.forEach((el) => {
      if (!el || el.dataset.fcPaletteBound === '1') return;
      el.dataset.fcPaletteBound = '1';
      el.classList.add('fc-palette-draggable');
      el.setAttribute('draggable', 'false');

      el.addEventListener('click', (ev) => {
        if (el.dataset.fcDidDrag === '1') {
          el.dataset.fcDidDrag = '0';
          ev.preventDefault();
          ev.stopImmediatePropagation();
        }
      }, true);

      el.addEventListener('pointerdown', (ev) => {
        if (ev.button != null && ev.button !== 0) return;
        if (opts.isDisabled && opts.isDisabled()) return;
        el.dataset.fcDidDrag = '0';
        const payload = opts.getPayload
          ? opts.getPayload(el)
          : {
            type: el.dataset.type || el.dataset.add || el.dataset.kind,
            kind: el.dataset.add || el.dataset.kind || el.dataset.type,
          };
        if (!payload || !(payload.type || payload.kind)) return;
        if (paletteSession) endPaletteSession(false, ev.clientX, ev.clientY);
        paletteSession = {
          payload,
          label: (el.textContent || payload.type || 'Node').replace(/\s+/g, ' ').trim(),
          sourceEl: el,
          startX: ev.clientX,
          startY: ev.clientY,
          moved: false,
        };
        document.addEventListener('pointermove', onPalettePointerMove);
        document.addEventListener('pointerup', onPalettePointerUp);
        document.addEventListener('pointercancel', onPalettePointerUp);
      });

      // Keep HTML5 DnD as a secondary path (some environments still use it)
      el.addEventListener('dragstart', (ev) => {
        if (opts.isDisabled && opts.isDisabled()) {
          ev.preventDefault();
          return;
        }
        const payload = opts.getPayload
          ? opts.getPayload(el)
          : {
            type: el.dataset.type || el.dataset.add || el.dataset.kind,
            kind: el.dataset.add || el.dataset.kind || el.dataset.type,
          };
        if (!payload || !(payload.type || payload.kind)) {
          ev.preventDefault();
          return;
        }
        const json = JSON.stringify(payload);
        try {
          ev.dataTransfer.setData(PALETTE_MIME, json);
          ev.dataTransfer.setData('text/plain', json);
          ev.dataTransfer.effectAllowed = 'copy';
        } catch (_) { /* ignore */ }
        el.classList.add('is-dragging');
        document.body.classList.add('fc-palette-dragging');
      });
      el.addEventListener('dragend', () => {
        el.classList.remove('is-dragging');
        document.body.classList.remove('fc-palette-dragging');
        document.dispatchEvent(new CustomEvent('fc-palette-dragend'));
      });
    });
    return list.length;
  }

  global.FlowCanvas = {
    create,
    bindPalette: bindPaletteElements,
    hasUserLayout,
    PALETTE_MIME,
  };
})(window);
