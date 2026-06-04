function app() {
  return {
    // ---- State ----
    tab: 'local',
    batchFiles: [], dragOver: false, previewFile: '',
    tStart: '', tEnd: '', showPlayer: false,
    localFmt: 'mp3', localQual: 'medium', localOut: '',
    urlFmt: 'mp3', urlQual: 'medium', urlDir: '', urlText: '',
    convPath: '', convFmt: 'mp3', convQual: 'medium', convOut: '',
    working: false, history: [], usePlaylist: false, useSubs: false, loudnorm: false,
    urlBatchMode: false, urlBatchText: '',
    toast: '', toastError: false, toastAnim: false,
    theme: 'dark', showShortcuts: false, showOnboarding: false, onboardStep: 0,

    // ---- Lifecycle ----
    async init() {
      this.$watch('$store.progress.done', v => {
        if (v) { this.working = false; Alpine.store('progress').done = false; this.loadHistory() }
      })
      this.loadHistory()
      if ('Notification' in window) Notification.requestPermission()
      // Theme: manual preference > system preference > dark default
      const saved = localStorage.getItem('ae-theme')
      if (saved) {
        this.theme = saved
      } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
        this.theme = 'light'
      }
      if (this.theme === 'light') document.body.classList.add('light')
      window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', e => {
        if (!localStorage.getItem('ae-theme')) {
          this.theme = e.matches ? 'light' : 'dark'
          document.body.classList.toggle('light', this.theme === 'light')
        }
      })
      try {
        const r = await fetch('/api/config'), c = await r.json()
        if (c.fmt) { this.localFmt = this.urlFmt = c.fmt }
        if (c.qual) { this.localQual = this.urlQual = c.qual }
        if (c.dir) this.urlDir = c.dir
      } catch (e) { /* ok */ }
      if (!localStorage.getItem('ae-onboarded')) {
        this.showOnboarding = true; localStorage.setItem('ae-onboarded', '1')
      }
    },

    async loadHistory() { try { const r = await fetch('/api/history'); this.history = await r.json() } catch (e) { } },
    async clearHistory() { if (confirm('确定清除所有记录？')) { await fetch('/api/history/clear', { method: 'POST' }); this.history = [] } },
    retryExtract(h) { if (h.kind === 'url') { this.tab = 'url'; this.urlText = h.source; this.urlBatchMode = false } },
    async deleteHistoryItem(i) { await fetch('/api/history/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ index: i }) }); this.history.splice(i, 1) },
    toggleTheme() { this.theme = this.theme === 'dark' ? 'light' : 'dark'; document.body.classList.toggle('light', this.theme === 'light'); localStorage.setItem('ae-theme', this.theme) },
    async savePrefs() { await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ fmt: this.localFmt, qual: this.localQual, dir: this.urlDir }) }) },

    openFile() { this.tab === 'local' && this.addBatchFile() || this.tab === 'convert' && this.selectConvFile() },

    // ---- File management (always batch-capable) ----
    async addBatchFile() {
      const r = await fetch('/api/select-files'); const d = await r.json()
      for (const p of (d.paths || [])) {
        if (!this.batchFiles.includes(p)) this.batchFiles.push(p)
      }
      if (this.batchFiles.length === 1) {
        this.localOut = this.batchFiles[0].split('\\').pop().replace(/\.[^.]+$/, '') + '.' + this.localFmt
        this.previewFile = this.batchFiles[0]
      } else {
        this.localOut = ''
      }
    },
    handleBatchDrop(e) {
      this.dragOver = false
      for (const f of e.dataTransfer.files) {
        if (f.path && !this.batchFiles.includes(f.path)) this.batchFiles.push(f.path)
      }
      if (this.batchFiles.length === 1) {
        this.localOut = this.batchFiles[0].split('\\').pop().replace(/\.[^.]+$/, '') + '.' + this.localFmt
      }
    },

    async selectDir() {
      const r = await fetch('/api/select-dir'); const d = await r.json()
      if (d.path) { this.urlDir = d.path; this.savePrefs() }
    },
    async selectOutput() {
      const r = await fetch('/api/select-dir'); const d = await r.json()
      if (d.path) {
        const name = (this.batchFiles[0] || '').split('\\').pop().replace(/\.[^.]+$/, '') || 'audio'
        this.localOut = d.path + '\\' + name + '.' + this.localFmt
      }
    },
    onPaste(e) {
      const t = (e.clipboardData || window.clipboardData).getData('text')
      if (t && t.includes('http') && !this.urlText) {
        setTimeout(() => this.urlText.includes('http') && this.showToast('检测到链接，Ctrl+Enter 开始'), 100)
      }
    },

    // ---- Convert Tab ----
    async selectConvFile() {
      const r = await fetch('/api/select-file'); const d = await r.json()
      if (d.path) { this.convPath = d.path; this.convOut = d.path.replace(/\.[^.]+$/, '') + '.' + this.convFmt }
    },
    clearConv() { this.convPath = ''; this.convOut = '' },
    handleConvDrop(e) {
      this.dragOver = false
      const f = e.dataTransfer.files
      if (f.length && f[0].path) { this.convPath = f[0].path; this.convOut = f[0].path.replace(/\.[^.]+$/, '') + '.' + this.convFmt }
    },
    async selectConvOutput() {
      const r = await fetch('/api/select-dir'); const d = await r.json()
      if (d.path) {
        const name = (this.convPath || '').split('\\').pop().replace(/\.[^.]+$/, '') || 'audio'
        this.convOut = d.path + '\\' + name + '.' + this.convFmt
      }
    },

    // ---- Extraction ----
    async doExtract() {
      let endpoint, body
      if (this.tab === 'convert') {
        if (!this.convPath) return this.showToast('请选择音频文件', true)
        endpoint = '/api/convert-audio'
        body = { input: this.convPath, output: this.convOut, format: this.convFmt, quality: this.convQual, loudnorm: this.loudnorm }
      } else if (this.tab === 'local') {
        if (!this.batchFiles.length) return this.showToast('请添加文件', true)
        endpoint = '/api/extract-file'
        body = this.batchFiles.length === 1 && (this.tStart || this.tEnd)
          ? { input: this.batchFiles[0], output: this.localOut, format: this.localFmt, quality: this.localQual, start: this.tStart, end: this.tEnd, loudnorm: this.loudnorm }
          : { files: this.batchFiles, format: this.localFmt, quality: this.localQual, loudnorm: this.loudnorm }
      } else {
        if (this.urlBatchMode) {
          if (!this.urlBatchText.trim()) return this.showToast('请先输入链接', true)
          endpoint = '/api/extract-urls-batch'
          body = { urls: this.urlBatchText, output_dir: this.urlDir, format: this.urlFmt, quality: this.urlQual, playlist: this.usePlaylist, subs: this.useSubs }
        } else {
          if (!this.urlText.trim()) return this.showToast('请先输入视频链接', true)
          endpoint = '/api/extract-url'
          body = { url: this.urlText, output_dir: this.urlDir, format: this.urlFmt, quality: this.urlQual, playlist: this.usePlaylist, subs: this.useSubs, loudnorm: this.loudnorm }
        }
        this.savePrefs()
      }
      this.working = true; this.resetProgress(); this.showPlayer = false
      fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
        .catch(err => { this.working = false; this.showToast('请求失败: ' + err.message, true) })
    },

    resetProgress() {
      const s = Alpine.store('progress')
      Object.assign(s, { pct: 0, dotColor: 'var(--primary)', status: '准备中...', output: '', file_i: 0, file_n: 0, eta: '', startTime: Date.now() })
    },
    async cancel() { await fetch('/api/cancel', { method: 'POST' }); this.working = false; this.showToast('已取消') },
    openFolder() { fetch('/api/open-folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: Alpine.store('progress').output }) }) },
    openPath(p) { fetch('/api/open-folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: p }) }) },
    playAudio() { this.showPlayer = !this.showPlayer; if (!this.showPlayer) { const a = document.getElementById('audio-player'); if (a) a.pause() } },

    // ---- Trim controls ----
    setStart() { const v = document.getElementById('player'); if (v) this.tStart = fmtTime(v.currentTime) },
    setEnd() { const v = document.getElementById('player'); if (v) this.tEnd = fmtTime(v.currentTime) },
    resetTrim() { this.tStart = ''; this.tEnd = ''; const v = document.getElementById('player'); if (v) v.currentTime = 0 },
    previewTrim() {
      const v = document.getElementById('player')
      if (!v || !this.tStart) return
      const ss = parseTime(this.tStart); v.currentTime = ss; v.play()
      if (this.tEnd) setTimeout(() => v.pause(), (parseTime(this.tEnd) - ss) * 1000)
    },

    // ---- Utilities ----
    showToast(msg, err) {
      this.toast = msg; this.toastError = !!err; this.toastAnim = true
      setTimeout(() => { this.toast = ''; this.toastAnim = false }, err ? 3000 : 2000)
    },
  }
}
