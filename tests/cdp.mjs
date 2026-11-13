import { spawn } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

export async function openBrowser() {
  const profile = await mkdtemp(join(tmpdir(), 'roastraw-cdp-'));
  const chrome = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  const child = spawn(chrome, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', 'about:blank'], { stdio: 'ignore' });
  let failure;
  child.on('error', error => { failure = error; });
  let port;
  for (let i = 0; i < 200; i++) {
    if (failure) throw failure;
    try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break; } catch { await delay(50); }
  }
  if (!port) { child.kill(); throw new Error('Chrome debugging endpoint did not start'); }
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const ws = new WebSocket(pages.find(p => p.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0;
  const pending = new Map();
  const events = new Map();
  const errors = [];
  function nextEvent(method) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { events.delete(method); reject(new Error(`CDP event timeout: ${method}`)); }, 15000);
      events.set(method, params => { clearTimeout(timer); events.delete(method); resolve(params); });
    });
  }
  ws.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    events.get(message.method)?.(message.params);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
    if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') errors.push(message.params);
    if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') errors.push(message.params.entry);
    const entry = pending.get(message.id);
    if (!entry) return;
    pending.delete(message.id);
    clearTimeout(entry.timer);
    if (message.error) entry.reject(new Error(message.error.message)); else entry.resolve(message.result);
  };
  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const key = ++id;
      const timer = setTimeout(() => { pending.delete(key); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
      pending.set(key, { resolve, reject, timer });
      ws.send(JSON.stringify({ id: key, method, params }));
    });
  }
  async function evaluate(expression) {
    const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  async function waitFor(expression) {
    for (let i = 0; i < 100; i++) { if (await evaluate(expression)) return; await delay(50); }
    throw new Error(`Browser condition timed out: ${expression}`);
  }
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Log.enable');
  return {
    send, evaluate, waitFor, errors,
    async viewport(width, height = 844) {
      await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: true });
    },
    async navigate(url) {
      const loaded = nextEvent('Page.loadEventFired');
      await send('Page.navigate', { url });
      await loaded;
      await waitFor('document.readyState === "complete"');
    },
    async screenshot(path, clip) {
      const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, ...(clip ? { clip } : {}) });
      await writeFile(path, Buffer.from(data, 'base64'));
    },
    async close() {
      await send('Browser.close').catch(() => {});
      ws.close();
      if (child.exitCode === null) await Promise.race([new Promise(resolve => child.once('exit', resolve)), delay(3000)]);
      if (child.exitCode === null) child.kill();
      await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }).catch(() => {});
    },
  };
}
