(() => {
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d', { alpha: false });
  const shell = document.getElementById('canvasShell');
  const statusEl = document.getElementById('status');
  const documentNameEl = document.getElementById('documentName');
  const pencilButton = document.getElementById('pencilButton');
  const eraserButton = document.getElementById('eraserButton');
  const widthInput = document.getElementById('widthInput');
  const widthValue = document.getElementById('widthValue');
  const colorInput = document.getElementById('colorInput');
  const undoButton = document.getElementById('undoButton');
  const redoButton = document.getElementById('redoButton');
  const clearButton = document.getElementById('clearButton');

  let socket = null;
  let currentPath = '';
  let baseImage = null;
  let strokes = [];
  let redoStack = [];
  let activeStroke = null;
  let tool = 'pencil';
  let revision = 0;
  let saveTimer = null;
  let loadingRemote = false;

  const params = new URLSearchParams(location.search);
  let token = params.get('token') || localStorage.getItem('ndGraphicToken') || '';
  if (params.has('token')) localStorage.setItem('ndGraphicToken', token);

  function setStatus(text) { statusEl.textContent = text; }

  function normalizePressure(ev) {
    let p = Number(ev.pressure);
    if (!Number.isFinite(p) || p <= 0) p = ev.pointerType === 'mouse' ? 0.5 : 0.25;
    return Math.max(0.04, Math.min(1, p));
  }

  function hexToRgb(hex) {
    const value = String(hex).replace('#', '');
    const full = value.length === 3 ? value.split('').map(x => x + x).join('') : value;
    return {
      r: parseInt(full.slice(0, 2), 16) || 0,
      g: parseInt(full.slice(2, 4), 16) || 0,
      b: parseInt(full.slice(4, 6), 16) || 0,
    };
  }

  function pointFromEvent(ev) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (ev.clientX - rect.left) * canvas.width / rect.width,
      y: (ev.clientY - rect.top) * canvas.height / rect.height,
      pressure: normalizePressure(ev),
    };
  }

  function drawSegment(a, b, stroke) {
    const avgPressure = (a.pressure + b.pressure) / 2;
    const baseWidth = Number(stroke.width || 6);
    const width = baseWidth * (0.55 + avgPressure * 0.95);
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineWidth = width;
    if (stroke.tool === 'eraser') {
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = '#ffffff';
      ctx.globalAlpha = 1;
    } else {
      const rgb = hexToRgb(stroke.color || '#202020');
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = `rgb(${rgb.r},${rgb.g},${rgb.b})`;
      ctx.globalAlpha = 0.45 + avgPressure * 0.55;
    }
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    ctx.restore();
  }

  function drawStroke(stroke) {
    const points = stroke.points || [];
    if (points.length === 1) {
      const p = points[0];
      drawSegment({x:p.x-0.1,y:p.y,pressure:p.pressure}, p, stroke);
      return;
    }
    for (let i = 1; i < points.length; i += 1) drawSegment(points[i - 1], points[i], stroke);
  }

  function repaint() {
    ctx.save();
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (baseImage) ctx.drawImage(baseImage, 0, 0, canvas.width, canvas.height);
    ctx.restore();
    for (const stroke of strokes) drawStroke(stroke);
    if (activeStroke) drawStroke(activeStroke);
  }

  function fitCanvas() {
    const ratio = canvas.width / canvas.height;
    const shellRect = shell.getBoundingClientRect();
    const availableW = Math.max(shellRect.width - 20, 100);
    const availableH = Math.max(shellRect.height - 20, 100);
    let w = availableW;
    let h = w / ratio;
    if (h > availableH) { h = availableH; w = h * ratio; }
    canvas.style.width = `${Math.floor(w)}px`;
    canvas.style.height = `${Math.floor(h)}px`;
  }

  function chooseTool(next) {
    tool = next;
    pencilButton.classList.toggle('active', tool === 'pencil');
    eraserButton.classList.toggle('active', tool === 'eraser');
  }

  function beginStroke(ev) {
    if (!currentPath) return;
    if (ev.pointerType === 'touch') return; // fingers can still operate the UI/scrolling
    ev.preventDefault();
    canvas.setPointerCapture(ev.pointerId);
    redoStack = [];
    activeStroke = {
      tool,
      width: Number(widthInput.value),
      color: colorInput.value,
      points: [pointFromEvent(ev)],
    };
    repaint();
  }

  function continueStroke(ev) {
    if (!activeStroke) return;
    ev.preventDefault();
    const batch = typeof ev.getCoalescedEvents === 'function' ? ev.getCoalescedEvents() : [ev];
    for (const sample of batch.length ? batch : [ev]) {
      const point = pointFromEvent(sample);
      const last = activeStroke.points[activeStroke.points.length - 1];
      activeStroke.points.push(point);
      drawSegment(last, point, activeStroke);
    }
  }

  function endStroke(ev) {
    if (!activeStroke) return;
    ev.preventDefault();
    strokes.push(activeStroke);
    activeStroke = null;
    revision += 1;
    repaint();
    scheduleSave();
  }

  function scheduleSave() {
    if (loadingRemote || !currentPath) return;
    clearTimeout(saveTimer);
    setStatus('Editing…');
    saveTimer = setTimeout(sendUpdate, 250);
  }

  function sendUpdate() {
    if (!socket || socket.readyState !== WebSocket.OPEN || !currentPath) {
      setStatus('Offline — changes kept on iPad');
      return;
    }
    const pngDataUrl = canvas.toDataURL('image/png');
    socket.send(JSON.stringify({
      type: 'update_graphic',
      path: currentPath,
      png_base64: pngDataUrl.split(',', 2)[1],
      canvas_width: canvas.width,
      canvas_height: canvas.height,
      web_strokes: strokes,
      pencil: { width: Number(widthInput.value), color: colorInput.value },
      client_revision: revision,
    }));
    setStatus('Saving…');
  }

  async function loadRemote(payload) {
    if (!payload || !payload.path || !payload.document) return;
    loadingRemote = true;
    currentPath = payload.path;
    documentNameEl.textContent = currentPath;
    const doc = payload.document;
    canvas.width = Number(doc.canvas_width || 1600);
    canvas.height = Number(doc.canvas_height || 1000);
    if (doc.pencil) {
      if (doc.pencil.width) widthInput.value = doc.pencil.width;
      if (doc.pencil.color) colorInput.value = doc.pencil.color;
      widthValue.textContent = widthInput.value;
    }
    strokes = Array.isArray(doc.web_strokes) ? doc.web_strokes : [];
    redoStack = [];
    baseImage = null;
    if ((!strokes.length) && payload.png_base64) {
      const img = new Image();
      await new Promise((resolve) => {
        img.onload = resolve;
        img.onerror = resolve;
        img.src = `data:image/png;base64,${payload.png_base64}`;
      });
      if (img.complete && img.naturalWidth > 0) baseImage = img;
    }
    repaint();
    fitCanvas();
    loadingRemote = false;
    setStatus('Saved');
  }

  function connect() {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${scheme}://${location.host}/ws${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    socket = new WebSocket(url);
    socket.onopen = () => {
      setStatus('Connected');
      socket.send(JSON.stringify({type: 'request_current'}));
    };
    socket.onmessage = (event) => {
      let payload;
      try { payload = JSON.parse(event.data); } catch { return; }
      if (payload.type === 'open_graphic') loadRemote(payload);
      else if (payload.type === 'graphic_updated') {
        if (Number(payload.client_revision || 0) === revision && payload.path === currentPath) {
          setStatus('Saved');
          return;
        }
        loadRemote(payload);
      } else if (payload.type === 'error') setStatus(`Error: ${payload.message}`);
    };
    socket.onclose = () => {
      setStatus('Disconnected — retrying…');
      setTimeout(connect, 1200);
    };
    socket.onerror = () => setStatus('Connection error');
  }

  pencilButton.addEventListener('click', () => chooseTool('pencil'));
  eraserButton.addEventListener('click', () => chooseTool('eraser'));
  widthInput.addEventListener('input', () => { widthValue.textContent = widthInput.value; });
  widthInput.addEventListener('change', scheduleSave);
  colorInput.addEventListener('change', scheduleSave);
  undoButton.addEventListener('click', () => {
    if (!strokes.length) return;
    redoStack.push(strokes.pop());
    repaint(); revision += 1; scheduleSave();
  });
  redoButton.addEventListener('click', () => {
    if (!redoStack.length) return;
    strokes.push(redoStack.pop());
    repaint(); revision += 1; scheduleSave();
  });
  clearButton.addEventListener('click', () => {
    if (!confirm('Clear this graphic?')) return;
    strokes = []; redoStack = []; baseImage = null;
    repaint(); revision += 1; scheduleSave();
  });

  canvas.addEventListener('pointerdown', beginStroke, {passive:false});
  canvas.addEventListener('pointermove', continueStroke, {passive:false});
  canvas.addEventListener('pointerup', endStroke, {passive:false});
  canvas.addEventListener('pointercancel', endStroke, {passive:false});
  window.addEventListener('resize', fitCanvas);
  document.addEventListener('contextmenu', ev => { if (ev.target === canvas) ev.preventDefault(); });

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  fitCanvas();
  connect();
})();
