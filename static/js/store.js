document.addEventListener('alpine:init', () => {
  Alpine.store('progress', {
    pct: 0, status: '待命', dotColor: 'var(--dim)',
    output: '', done: false, file_i: 0, file_n: 0, eta: '', startTime: 0
  })

  const evt = new EventSource('/progress')
  evt.onopen = () => {
    const ld = document.getElementById('ld')
    if (ld) { ld.style.opacity = '0'; setTimeout(() => ld.remove(), 300) }
  }
  evt.onmessage = (e) => {
    const d = JSON.parse(e.data), s = Alpine.store('progress')
    s.pct = Math.min(d.pct || 0, 100)
    s.status = d.status || ''
    if (d.file_i != null) s.file_i = d.file_i
    if (d.file_n != null) s.file_n = d.file_n
    if (d.output) s.output = d.output
    if (d.pct > 1 && s.startTime) {
      const elapsed = (Date.now() - s.startTime) / 1000
      const total = elapsed / (d.pct / 100)
      const remaining = Math.max(0, total - elapsed)
      s.eta = remaining > 60
        ? Math.round(remaining / 60) + '分 剩余'
        : Math.round(remaining) + '秒 剩余'
    }
    const ok = d.status && d.status.includes('\u2714')
    const err = d.status && (d.status.includes('\u5931') || d.status.includes('\u53d6\u6d88'))
    s.dotColor = ok ? 'var(--success)' : err ? 'var(--primary)' : 'var(--primary)'
    if (d.done) { s.done = true; s.eta = ''; notify(d.status, d.output) }
  }
})

function notify(s, o) {
  if (!('Notification' in window) || Notification.permission === 'denied') return
  if (s && s.includes('\u2714') && o) {
    new Notification('AudioExtract', { body: '完成: ' + o.split('\\').pop() })
  }
}
