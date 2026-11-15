import { ref } from 'vue';

// Competition collars are a venue fact, not a prescription: the pair weighs 5 kg
// and either both are on the bar or neither is. The switch is device-local, the
// same way the old journal kept venue stock on the phone, and it defaults to off
// so a session that never asked for collars is never quietly 5 kg heavier.
const KEY = 'rr.gear.collars';
export const COLLAR_PAIR_KG = 5;

const read = () => {
  try { return globalThis.localStorage?.getItem(KEY) === '1'; } catch { return false; }
};

export const useCollars = ref(read());
export const collarPairOf = value => (value ? COLLAR_PAIR_KG : 0);

export function setUseCollars(value) {
  useCollars.value = Boolean(value);
  try { globalThis.localStorage?.setItem(KEY, value ? '1' : '0'); } catch { /* private mode keeps the in-memory value */ }
}
