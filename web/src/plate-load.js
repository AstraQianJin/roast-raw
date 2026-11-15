// One place for plate arithmetic. Both the strip under an attempt and the GEAR
// cabinet read this, so the screen can never disagree with itself about what sits
// on the bar. Only the existing prescribed load is solved; no new load policy here.

export const PLATE_STACK = [
  { kg: 25, token: '--plate-25', ink: '--on-accent', h: 30, w: 13, micro: false },
  { kg: 20, token: '--plate-20', ink: '--on-accent', h: 30, w: 11, micro: false },
  { kg: 15, token: '--plate-15', ink: '--plate-15-ink', h: 26, w: 10, micro: false },
  { kg: 10, token: '--plate-10', ink: '--on-accent', h: 22, w: 8.5, micro: false },
  { kg: 5, token: '--plate-5', ink: '--plate-5-ink', h: 17, w: 7, micro: false },
  { kg: 2.5, token: '--plate-2p5', ink: '--on-accent', h: 14, w: 5, micro: true },
  { kg: 1.25, token: '--plate-1p25', ink: '--on-accent', h: 12, w: 4, micro: true },
  { kg: 1, token: '--plate-1', ink: '--on-accent', h: 11, w: 3.6, micro: true },
  { kg: 0.75, token: '--plate-0p75', ink: '--on-accent', h: 10.5, w: 3.3, micro: true },
  { kg: 0.5, token: '--plate-0p5', ink: '--on-accent', h: 10, w: 3 },
  { kg: 0.25, token: '--plate-0p25', ink: '--on-accent', h: 9.5, w: 2.7 },
];

// Micro plates are the ones a lifter has to physically hunt for; the cabinet
// names them by weight so they can never be confused with a standard plate.
export const MICRO_SIZES = [1.25, 1, 0.75, 0.5, 0.25];

const EPS = 1e-6;
const round3 = value => Math.round(value * 1000) / 1000;
const near = (a, b) => Math.abs(a - b) < EPS;

export const plateLabel = kg => {
  const text = round3(kg).toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
  return text === '' ? '0' : text;
};

// Greedy per-side stack. Remaining millimetres of a gram stay in `rest` so a
// load that cannot be built is reported instead of silently rounded away.
export function solveStack(kg) {
  let rest = round3(Math.max(0, kg));
  const plates = [];
  for (const plate of PLATE_STACK) {
    while (rest >= plate.kg - EPS) {
      plates.push(plate);
      rest = round3(rest - plate.kg);
    }
  }
  return { plates, rest: round3(rest), loaded: round3(Math.max(0, kg) - rest) };
}

const signature = stack => stack.plates.map(plate => plate.kg).join('+');

// solveLoad returns both sides. A symmetric load reports equal sides; a load
// whose half cannot be built with stock plates is split unevenly, which is the
// single-side case (one side carries the odd micro plate).
export function solveLoad(total, barKg = 20, collarPair = 0) {
  if (total === null || total === undefined || !Number.isFinite(Number(total))) return null;
  const load = round3(Number(total));
  const plateTotal = round3(load - barKg - collarPair);
  if (plateTotal <= EPS) {
    return {
      load, barKg, collarPair, plateTotal: Math.max(0, plateTotal),
      sideA: { plates: [], loaded: 0 },
      sideB: { plates: [], loaded: 0 },
      asymmetric: false, microUsed: [], shortKg: round3(Math.max(0, -plateTotal)),
    };
  }
  const half = solveStack(plateTotal / 2);
  const other = solveStack(plateTotal - half.loaded);
  const loaded = round3(half.loaded + other.loaded);
  const shortKg = round3(plateTotal - loaded);
  const asymmetric = !near(half.loaded, other.loaded) || signature(half) !== signature(other);
  // Heavier side first, so the heavier stack is the one a lifter loads first.
  const sideA = other.loaded >= half.loaded ? other : half;
  const sideB = other.loaded >= half.loaded ? half : other;
  const used = new Set();
  for (const plate of [...sideA.plates, ...sideB.plates]) {
    if (plate.kg <= 1.25 + EPS) used.add(plate.kg);
  }
  return {
    load, barKg, collarPair,
    plateTotal: round3(Math.max(0, plateTotal)),
    sideA: { plates: sideA.plates, loaded: round3(sideA.loaded) },
    sideB: { plates: sideB.plates, loaded: round3(sideB.loaded) },
    asymmetric,
    microUsed: [...used].sort((a, b) => b - a),
    shortKg,
  };
}

export function sideText(side) {
  if (!side || !side.plates.length) return 'empty bar side';
  const counts = {};
  for (const plate of side.plates) counts[plate.kg] = (counts[plate.kg] || 0) + 1;
  return Object.entries(counts)
    .sort((a, b) => Number(b[0]) - Number(a[0]))
    .map(([kg, count]) => `${count}×${plateLabel(kg)} kg`)
    .join(' + ');
}
