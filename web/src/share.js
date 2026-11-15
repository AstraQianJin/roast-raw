// Daily share card, 1080x1440, ported from the old project's TopSet-style Day renderer.
// Plates are solved from the day's final main-lift load; collars count only when the venue switch asks for them.

const W = 1080, H = 1440, M = 72, CW = W - M * 2;
const PLATES = [
  [25, '#E53935', 96, 30], [20, '#1E88E5', 96, 26], [15, '#FFB300', 84, 24],
  [10, '#43A047', 70, 20], [5, '#E7ECF3', 54, 17], [2.5, '#181C22', 44, 12],
  [1.25, '#7C8084', 36, 10], [1, '#8E9196', 32, 9], [0.75, '#A0A3A7', 30, 8],
  [0.5, '#B4B6BA', 28, 7], [0.25, '#C8CACE', 26, 6],
];

export function solvePlates(total, barKg = 20, collarPair = 0) {
  let perSide = Math.round(((total - barKg - collarPair) / 2) * 1000) / 1000;
  const plates = [];
  if (!(perSide > 0)) return plates;
  for (const [kg, color, h, w] of PLATES) {
    while (perSide >= kg - 1e-9) {
      plates.push({ kg, color, h, w });
      perSide = Math.round((perSide - kg) * 1000) / 1000;
    }
  }
  return plates;
}

export function dayShareData(plan, logs, date) {
  const rows = plan.workouts.filter(row => row.date === date);
  const logged = rows.map(row => ({ row, log: logs[`${row.week}|${row.day}|${row.seq}`] }))
    .filter(item => item.log && item.log.sets > 0);
  const volume = logged.reduce((sum, item) => sum + (item.log.load || 0) * item.log.sets * item.log.reps, 0);
  const mains = logged.filter(item => item.row.bucket === 'main');
  const finalMain = mains.length ? mains[mains.length - 1] : null;
  const byLift = {};
  for (const item of logged) {
    const lift = item.row.lift || 'OTHER';
    byLift[lift] = (byLift[lift] || 0) + (item.log.load || 0) * item.log.sets * item.log.reps;
  }
  const plannedSets = rows.reduce((sum, row) => sum + row.sets, 0);
  const doneSets = logged.reduce((sum, item) => sum + item.log.sets, 0);
  const week = rows[0]?.week ?? null;
  const day = rows[0]?.day ?? null;
  return {
    date, week, day, volume: logged.length ? volume : null,
    topSet: finalMain ? { name: finalMain.row.nameEn, load: finalMain.log.load, reps: finalMain.log.reps, rpe: finalMain.log.rpe } : null,
    byLift: Object.entries(byLift).sort((a, b) => b[1] - a[1]),
    plannedSets, doneSets,
    completion: plannedSets > 0 ? doneSets / plannedSets : null,
    loggedCount: logged.length,
  };
}

function fitText(g, text, maxWidth, startPx, minPx, weight, family) {
  let size = startPx;
  while (size > minPx) {
    g.font = `${weight} ${size}px ${family}`;
    if (g.measureText(text).width <= maxWidth) break;
    size -= 2;
  }
  g.font = `${weight} ${size}px ${family}`;
  return size;
}

function drawBarbell(g, x, y, width, height, load, theme, collarPair = 0) {
  const plates = solvePlates(load, 20, collarPair);
  const shaftY = y + height / 2;
  const grad = g.createLinearGradient(0, shaftY - 5, 0, shaftY + 5);
  grad.addColorStop(0, '#525B69'); grad.addColorStop(.4, '#C7CFDA'); grad.addColorStop(1, '#3B424E');
  g.fillStyle = grad;
  g.fillRect(x, shaftY - 5, width, 10);
  let cursor = x + 26;
  const scale = height / 96;
  for (const plate of plates) {
    const ph = plate.h * scale, pw = plate.w * scale;
    if (cursor + pw > x + width - 40) break;
    g.fillStyle = plate.color;
    g.beginPath();
    g.roundRect(cursor, shaftY - ph / 2, pw, ph, 4 * scale);
    g.fill();
    g.fillStyle = 'rgba(255,255,255,.35)';
    g.fillRect(cursor + 2 * scale, shaftY - ph / 2 + 3 * scale, pw - 4 * scale, 3 * scale);
    if (plate.kg >= 5) {
      g.fillStyle = plate.kg === 15 ? '#1A1200' : plate.kg === 5 ? '#111111' : '#FFFFFF';
      g.font = `700 ${Math.max(12, 15 * scale)}px 'Roboto Mono', Consolas, monospace`;
      g.textAlign = 'center'; g.textBaseline = 'middle';
      g.save();
      g.translate(cursor + pw / 2, shaftY);
      g.rotate(-Math.PI / 2);
      g.fillText(String(plate.kg), 0, 0);
      g.restore();
    }
    cursor += pw + 4 * scale;
  }
  g.fillStyle = '#9AA3AF';
  g.fillRect(cursor + 2, shaftY - 14 * scale, 10 * scale, 28 * scale);
  g.textAlign = 'left'; g.textBaseline = 'alphabetic';
}

export function renderShareCard(canvas, data, plan, theme = 'light', collarPair = 0) {
  canvas.width = W; canvas.height = H;
  const g = canvas.getContext('2d');
  const dark = theme === 'dark';
  const bg = dark ? '#07090D' : '#F1F0EB';
  const ink = dark ? '#F2F5F9' : '#111111';
  const muted = dark ? '#A0ACBC' : '#5A5A56';
  const gold = dark ? '#E0A83A' : '#8A5F0B';
  const line = dark ? 'rgba(242,245,249,.22)' : 'rgba(17,17,17,.28)';
  const mono = "'Roboto Mono', Consolas, monospace";
  const display = "'Roboto Condensed', 'Arial Narrow', sans-serif";
  g.fillStyle = bg; g.fillRect(0, 0, W, H);
  g.fillStyle = dark ? 'rgba(242,245,249,.07)' : 'rgba(17,17,17,.08)';
  g.font = `800 180px ${display}`;
  g.fillText(data.date.replaceAll('-', '.'), M, 168);
  g.fillStyle = muted;
  g.font = `700 22px ${mono}`;
  g.fillText(data.week ? `WEEK ${String(data.week).padStart(2, '0')} · DAY ${data.day || '—'}` : 'TRAINING JOURNAL', M, 232);
  g.textAlign = 'right';
  g.fillText(data.date, W - M, 232);
  g.textAlign = 'left';
  g.fillStyle = ink;
  fitText(g, (plan.meta.name || 'ROAST RAW').toUpperCase(), CW, 30, 20, 800, display);
  g.fillText((plan.meta.name || 'ROAST RAW').toUpperCase(), M, 268);
  g.fillStyle = gold;
  g.font = `800 22px ${mono}`;
  g.fillText('SESSION VOLUME', M, 336);
  g.textAlign = 'right';
  g.fillStyle = muted;
  g.fillText('ACTUAL LOGGED WORK', W - M, 336);
  g.textAlign = 'left';
  g.fillStyle = ink;
  const volumeText = data.volume === null ? '—' : Math.round(data.volume).toLocaleString('en-US');
  fitText(g, volumeText, CW - 140, 220, 140, 800, mono);
  g.fillText(volumeText, M, 560);
  g.fillStyle = gold;
  g.font = `800 62px ${mono}`;
  g.textAlign = 'right';
  g.fillText('KG', W - M, 560);
  g.textAlign = 'left';
  if (data.volume === null) {
    g.fillStyle = muted;
    g.font = `700 26px ${mono}`;
    g.fillText('NO SESSION LOG', M, 600);
  }
  g.strokeStyle = line; g.lineWidth = 2;
  g.beginPath(); g.moveTo(M, 624); g.lineTo(W - M, 624); g.stroke();
  g.fillStyle = gold;
  g.font = `800 22px ${mono}`;
  g.fillText('TOP SET · FINAL MAIN LIFT', M, 680);
  if (data.topSet) {
    g.textAlign = 'right'; g.fillStyle = muted;
    g.fillText(data.topSet.rpe !== null && data.topSet.rpe !== undefined ? `RPE ${data.topSet.rpe}` : 'RPE —', W - M, 680);
    g.textAlign = 'left';
    drawBarbell(g, M, 700, 300, 110, data.topSet.load, theme, collarPair);
    g.fillStyle = ink;
    g.font = `800 92px ${mono}`;
    g.fillText(`${data.topSet.load} × ${data.topSet.reps}`, M + 330, 800);
    g.fillStyle = muted;
    fitText(g, data.topSet.name.toUpperCase(), CW, 34, 22, 800, display);
    g.fillText(data.topSet.name.toUpperCase(), M, 852);
    g.fillStyle = muted;
    g.font = `700 18px ${mono}`;
    g.fillText(collarPair > 0 ? '20 KG BAR + 5 KG COMPETITION COLLARS INCLUDED' : '20 KG BAR ONLY · NO COLLARS COUNTED', M, 880);
  } else {
    g.fillStyle = muted;
    g.font = `800 64px ${mono}`;
    g.fillText('—', M, 800);
    g.font = `700 24px ${mono}`;
    g.fillText('NO MAIN-LIFT LOG', M, 852);
  }
  g.strokeStyle = line;
  g.beginPath(); g.moveTo(M, 908); g.lineTo(W - M, 908); g.stroke();
  g.fillStyle = gold;
  g.font = `800 22px ${mono}`;
  g.fillText('VOLUME BY LIFT', M, 956);
  const entries = data.byLift.slice(0, 4);
  const maxVolume = entries.length ? entries[0][1] : 1;
  const pitch = entries.length >= 4 ? 46 : 56;
  let y = 996;
  const names = { S: 'SQUAT', B: 'BENCH', D: 'DEADLIFT', OTHER: 'OTHER' };
  for (const [lift, value] of entries) {
    g.fillStyle = ink;
    fitText(g, names[lift] || lift, 232, 24, 16, 800, display);
    g.fillText(names[lift] || lift, M, y + 8);
    g.fillStyle = dark ? 'rgba(242,245,249,.12)' : 'rgba(17,17,17,.10)';
    g.fillRect(M + 264, y, 528, 10);
    g.fillStyle = gold;
    g.fillRect(M + 264, y, Math.max(4, 528 * value / maxVolume), 10);
    g.fillStyle = ink;
    g.font = `700 22px ${mono}`;
    g.textAlign = 'right';
    g.fillText(Math.round(value).toLocaleString('en-US'), W - M, y + 10);
    g.textAlign = 'left';
    y += pitch;
  }
  if (!entries.length) {
    g.fillStyle = muted;
    g.font = `700 22px ${mono}`;
    g.fillText('NO LOGGED VOLUME', M, y + 8);
  }
  g.strokeStyle = line;
  g.beginPath(); g.moveTo(M, 1196); g.lineTo(W - M, 1196); g.stroke();
  g.fillStyle = ink;
  g.font = `800 26px ${mono}`;
  g.fillText(`${data.doneSets} / ${data.plannedSets} SETS`, M, 1240);
  g.fillStyle = muted;
  g.font = `700 20px ${mono}`;
  const completion = data.completion === null ? '—' : `${Math.round(data.completion * 100)}%`;
  g.fillText(`COMPLETION ${completion} · DONE ÷ PLANNED`, M, 1274);
  g.fillStyle = gold;
  g.font = `800 24px ${display}`;
  g.fillText('ROAST RAW', M, 1330);
  g.fillStyle = muted;
  g.font = `700 20px ${mono}`;
  g.textAlign = 'right';
  g.fillText(data.date, W - M, 1330);
  g.textAlign = 'left';
  return canvas;
}