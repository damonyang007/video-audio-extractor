function fmtTime(s) {
  const m = Math.floor(s / 60), sec = Math.floor(s % 60)
  return m + ':' + (sec < 10 ? '0' : '') + sec
}

function parseTime(t) {
  const p = t.split(':')
  if (p.length === 2) return parseInt(p[0]) * 60 + parseInt(p[1])
  return parseInt(p[0]) * 3600 + parseInt(p[1]) * 60 + parseInt(p[2])
}
