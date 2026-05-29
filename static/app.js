document.addEventListener('alpine:init', () => {
  Alpine.store('progress', { pct: 0, status: '\u5f85\u547d', dotColor: 'var(--dim)', output: '', done: false, file_i: 0, file_n: 0, eta: '', startTime: 0 })

  const evt = new EventSource('/progress')
  evt.onopen = () => {
    const ld = document.getElementById('ld')
    if (ld) { ld.style.opacity = '0'; setTimeout(() => ld.remove(), 300) }
  }
  evt.onmessage = e => {
    const d = JSON.parse(e.data), s = Alpine.store('progress')
    s.pct = Math.min(d.pct || 0, 100); s.status = d.status || ''
    if (d.file_i != null) s.file_i = d.file_i
    if (d.file_n != null) s.file_n = d.file_n
    if (d.output) s.output = d.output
    if (d.pct > 1 && s.startTime) {
      const elapsed = (Date.now() - s.startTime) / 1000
      const total = elapsed / (d.pct / 100), remaining = Math.max(0, total - elapsed)
      s.eta = remaining > 60 ? Math.round(remaining / 60) + '\u5206 \u5269\u4f59' : Math.round(remaining) + '\u79d2 \u5269\u4f59'
    }
    const ok = d.status && d.status.includes('\u2714'), err = d.status && (d.status.includes('\u5931') || d.status.includes('\u53d6\u6d88'))
    s.dotColor = ok ? 'var(--success)' : err ? 'var(--primary)' : 'var(--primary)'
    if (d.done) { s.done = true; s.eta = ''; notify(d.status, d.output) }
  }
})

function notify(s, o) {
  if (!('Notification' in window) || Notification.permission === 'denied') return
  if (s && s.includes('\u2714') && o) new Notification('AudioExtract', { body: '\u5b8c\u6210: ' + o.split('\\').pop() })
}

function app() {
  return {
    tab: 'local', batchMode: false, batchFiles: [], dragOver: false,
    filePath: '', tStart: '', tEnd: '', showPlayer: false,
    localFmt: 'mp3', localQual: 'medium', localOut: '',
    urlFmt: 'mp3', urlQual: 'medium', urlDir: '', urlText: '',
    convPath: '', convFmt: 'mp3', convQual: 'medium', convOut: '',
    working: false, history: [], toast: '', toastError: false, toastAnim: false,
    theme: 'dark', usePlaylist: false,
    showShortcuts: false, showOnboarding: false, onboardStep: 0,

    async init() {
      this.$watch('$store.progress.done', v => { if (v) { this.working = false; Alpine.store('progress').done = false; this.loadHistory() } })
      this.loadHistory()
      if ('Notification' in window) Notification.requestPermission()
      this.theme = localStorage.getItem('ae-theme') || 'dark'
      if (this.theme === 'dark' && window.matchMedia('(prefers-color-scheme: dark)').matches === false) this.theme = 'light'
      if (this.theme === 'light') document.body.classList.add('light')
      try { const r = await fetch('/api/config'); const c = await r.json(); if (c.fmt) this.localFmt = this.urlFmt = c.fmt; if (c.qual) this.localQual = this.urlQual = c.qual; if (c.dir) this.urlDir = c.dir } catch (e) { }
      if (!localStorage.getItem('ae-onboarded')) { this.showOnboarding = true; localStorage.setItem('ae-onboarded', '1') }
    },
    async loadHistory() { try { const r = await fetch('/api/history'); this.history = await r.json() } catch (e) { } },
    async clearHistory() { await fetch('/api/history/clear', { method: 'POST' }); this.history = [] },
    toggleTheme() { this.theme = this.theme === 'dark' ? 'light' : 'dark'; document.body.classList.toggle('light', this.theme === 'light'); localStorage.setItem('ae-theme', this.theme) },
    async savePrefs() { await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ fmt: this.localFmt, qual: this.localQual, dir: this.urlDir }) }) },

    openFile() { if (this.tab === 'local') this.selectFile(); else if (this.tab === 'convert') this.selectConvFile() },

    async selectFile() { const r = await fetch('/api/select-file'); const d = await r.json(); if (d.path) this.setFile(d.path) },
    setFile(p) { this.filePath = p; this.localOut = p.split('\\').pop().replace(/\.[^.]+$/, '') + '.' + this.localFmt },
    handleDrop(e) { this.dragOver = false; const f = e.dataTransfer.files; if (f.length && f[0].path) this.setFile(f[0].path); else this.showToast('\u8bf7\u4ece\u6587\u4ef6\u7ba1\u7406\u5668\u62d6\u62fd', true) },
    async addBatchFile() { const r = await fetch('/api/select-file'); const d = await r.json(); if (d.path && !this.batchFiles.includes(d.path)) this.batchFiles.push(d.path); this.localOut = '' },
    handleBatchDrop(e) { this.dragOver = false; for (const f of Array.from(e.dataTransfer.files)) { if (f.path && !this.batchFiles.includes(f.path)) this.batchFiles.push(f.path) } },
    async selectDir() { const r = await fetch('/api/select-dir'); const d = await r.json(); if (d.path) { this.urlDir = d.path; this.savePrefs() } },
    async selectOutput() { const r = await fetch('/api/select-save'); const d = await r.json(); if (d.path) this.localOut = d.path },
    onPaste(e) { const t = (e.clipboardData || window.clipboardData).getData('text'); if (t && t.includes('http') && !this.urlText) setTimeout(() => { if (this.urlText.includes('http')) this.showToast('\u68c0\u6d4b\u5230\u94fe\u63a5\uff0cCtrl+Enter \u5f00\u59cb') }, 100) },

    // Convert tab
    async selectConvFile() { const r = await fetch('/api/select-file'); const d = await r.json(); if (d.path) { this.convPath = d.path; this.convOut = d.path.replace(/\.[^.]+$/, '') + '.' + this.convFmt } },
    handleConvDrop(e) { this.dragOver = false; const f = e.dataTransfer.files; if (f.length && f[0].path) { this.convPath = f[0].path; this.convOut = f[0].path.replace(/\.[^.]+$/, '') + '.' + this.convFmt } },
    async selectConvOutput() { const r = await fetch('/api/select-save'); const d = await r.json(); if (d.path) this.convOut = d.path },

    async doExtract() {
      if (this.tab === 'convert') {
        if (!this.convPath) { this.showToast('\u8bf7\u9009\u62e9\u97f3\u9891\u6587\u4ef6', true); return }
        this.working = true; this.resetProgress(); this.showPlayer = false
        fetch('/api/convert-audio', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ input: this.convPath, output: this.convOut, format: this.convFmt, quality: this.convQual }) })
      } else if (this.tab === 'local') {
        if (this.batchMode) { if (!this.batchFiles.length) { this.showToast('\u8bf7\u6dfb\u52a0\u6587\u4ef6', true); return } }
        else { if (!this.filePath) { this.showToast('\u8bf7\u5148\u9009\u62e9\u89c6\u9891\u6587\u4ef6', true); return } }
        this.working = true; this.resetProgress(); this.showPlayer = false
        const body = this.batchMode ? { files: this.batchFiles, format: this.localFmt, quality: this.localQual } : { input: this.filePath, output: this.localOut, format: this.localFmt, quality: this.localQual, start: this.tStart, end: this.tEnd }
        fetch('/api/extract-file', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      } else {
        if (!this.urlText.trim()) { this.showToast('\u8bf7\u8f93\u5165\u94fe\u63a5', true); return }
        this.working = true; this.resetProgress(); this.savePrefs()
        fetch('/api/extract-url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: this.urlText, output_dir: this.urlDir, format: this.urlFmt, quality: this.urlQual, playlist: this.usePlaylist }) })
      }
    },
    resetProgress() { const s = Alpine.store('progress'); s.pct = 0; s.dotColor = 'var(--primary)'; s.status = '\u51c6\u5907\u4e2d...'; s.output = ''; s.file_i = 0; s.file_n = 0; s.eta = ''; s.startTime = Date.now() },
    async cancel() { await fetch('/api/cancel', { method: 'POST' }); this.working = false; this.showToast('\u5df2\u53d6\u6d88') },
    openFolder() { fetch('/api/open-folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: Alpine.store('progress').output }) }) },
    openPath(p) { fetch('/api/open-folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: p }) }) },
    playAudio() { this.showPlayer = !this.showPlayer },
    showToast(msg, err) { this.toast = msg; this.toastError = !!err; this.toastAnim = true; setTimeout(() => { this.toast = ''; this.toastAnim = false }, err ? 3000 : 2000) },
    fmtTime(s) { const m = Math.floor(s / 60), sec = Math.floor(s % 60); return m + ':' + (sec < 10 ? '0' : '') + sec },
    onVideoLoad() { },
    setStart() { const v = document.getElementById('player'); if (v) this.tStart = this.fmtTime(v.currentTime) },
    setEnd() { const v = document.getElementById('player'); if (v) this.tEnd = this.fmtTime(v.currentTime) },
    resetTrim() { this.tStart = ''; this.tEnd = ''; const v = document.getElementById('player'); if (v) v.currentTime = 0 },
    previewTrim() { const v = document.getElementById('player'); if (!v || !this.tStart) return; const ss = this._parseTime(this.tStart); v.currentTime = ss; v.play(); if (this.tEnd) { setTimeout(() => v.pause(), (this._parseTime(this.tEnd) - ss) * 1000) } },
    _parseTime(t) { const p = t.split(':'); return p.length === 2 ? +p[0] * 60 + +p[1] : +p[0] * 3600 + +p[1] * 60 + +p[2] },
  }
}
