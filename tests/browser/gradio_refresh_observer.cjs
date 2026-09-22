// Read-only logpoints in the locked, actually served Gradio 4.39.0 bundle.
// No callback return, trigger mode, concurrency limit or production file changes.
const fs = require('node:fs');
const crypto = require('node:crypto');

function installTrace(ids) {
  const trace = window.ownedFrameworkTrace = {records: [], errors: [], ids};
  const clone = value => JSON.parse(JSON.stringify(value));
  window.ownedRecordFramework = (phase, value) => {
    try {
      trace.records.push({sequence: trace.records.length, action: window.ownedWebAction,
        time: performance.now(), phase, ...clone(value)});
    } catch (error) { trace.errors.push({phase, error: String(error)}); }
  };
  window.ownedRecordUpdates = (phase, updates) => {
    try {
      const values = (updates || []).filter(item => ids.components.includes(item.id) && ids.props.includes(item.prop));
      if (values.length) window.ownedRecordFramework(phase, {updates: values});
    } catch (error) { trace.errors.push({phase, error: String(error)}); }
  };
  window.ownedRecordData = (phase, fn, data) => {
    if (ids.functions.includes(fn)) window.ownedRecordFramework(phase, {fn, data});
  };
  const scheduledChanges = [];
  let currentChange;
  const waiting = new WeakMap();
  window.ownedChangeSchedule = (fn, id) => {
    if (fn !== ids.applyFn || id !== ids.resultId) return;
    const flush = trace.records.findLast(row => row.phase === 'flush_end');
    const value = flush?.updates.find(row => row.id === id)?.value;
    const scheduled = trace.records.length;
    scheduledChanges.push(scheduled);
    window.ownedRecordFramework('change_schedule', {fn, id, scheduled, stamp: value?.stamp});
  };
  window.ownedChangeCallback = (fn, id) => {
    if (fn === ids.applyFn && id === ids.resultId) {
      currentChange = scheduledChanges.shift();
      window.ownedRecordFramework('change_callback', {fn, id, scheduled: currentChange});
    }
  };
  window.ownedWaitForFlush = (fn, id, pending, invocation) => {
    if (fn !== ids.applyFn || id !== ids.resultId) return;
    const wait = trace.records.length;
    waiting.set(invocation, wait);
    window.ownedRecordFramework('wait_for_flush', {fn, id, pending, wait, scheduled: currentChange});
  };
  window.ownedResumeFlush = (fn, id, invocation) => {
    if (fn === ids.applyFn && id === ids.resultId) {
      window.ownedRecordFramework('wait_resumed', {fn, id, wait: waiting.get(invocation)});
    }
  };
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    const url = String(args[0]?.url || args[0]);
    if (new URL(url, location.href).pathname.endsWith('/queue/data')) {
      (async () => {
        const reader = response.clone().body.getReader(), decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const item = await reader.read();
          if (item.done) break;
          buffer += decoder.decode(item.value, {stream:true}).replaceAll('\r\n','\n');
          let boundary;
          while ((boundary = buffer.indexOf('\n\n')) >= 0) {
            const frame = buffer.slice(0,boundary); buffer = buffer.slice(boundary+2);
            const data = frame.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trim()).join('\n');
            if (!data) continue;
            const message = JSON.parse(data), payload = message.output?.data?.[0];
            if (payload?.stamp?.fileRequest || ids.conversation) window.ownedRecordFramework('transport',{url,message});
          }
        }
      })().catch(error=>{
        if (error.name==='AbortError') window.ownedRecordFramework('transport_end',{url,reason:'client_abort',error:String(error)});
        else trace.errors.push({phase:'transport',error:String(error)});
      });
    }
    return response;
  };
  document.addEventListener('gradio', event => {
    if (ids.components.includes(event.detail?.id) && event.detail?.event === 'change') {
      window.ownedRecordFramework('change', {detail: event.detail});
    }
  }, true);
  window.ownedRecordFramework('installed', {ids});
}

async function attach(page, ready, base, {conversation = false} = {}) {
  if (ready.gradio !== '4.39.0') throw Error('Unexpected Gradio version');
  const filename = 'Blocks-BPGBf-rO.js';
  const bundle = fs.readFileSync(ready.frontend.path);
  const hash = crypto.createHash('sha256').update(bundle).digest('hex');
  if (hash !== ready.frontend.sha256 || hash !== '0742ee7d0374cdd5f1b0aa66c562570fb86280f13c86ad02bb9efda5c6e251b1') throw Error('Unexpected installed Gradio bundle');
  const definitions = Object.entries(ready.functions);
  const refresh = definitions.filter(([, value]) => value.name === 'refresh_chat_file_list');
  const resultId = refresh[0][1].outputs[0];
  const [applyId, apply] = definitions.find(([, value]) => value.targets.some(([id, event]) => id === resultId && event === 'change'));
  const ids = {resultId, applyFn: Number(applyId), components: [resultId, ...apply.outputs],
    functions: [...refresh.map(([id]) => Number(id)), Number(applyId)], props: ['value'], conversation};
  if (conversation) {
    for (const [id, definition] of definitions) {
      if (['new_conv', 'reload_conv', 'rename_conv', 'select_conv'].includes(definition.name) ||
          definition.js?.includes('#chat-input textarea')) {
        ids.functions.push(Number(id));
      }
    }
    const selection = ready.functions[ready.roles.conversation_select];
    ids.components.push(...selection.outputs.slice(0, 2));
    ids.components = [...new Set(ids.components)];
    ids.props.push('choices');
  }
  await page.addInitScript(installTrace, ids);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Debugger.enable');
  const code = bundle.toString('utf8');
  const definitionsToTrace = [
    ['update_value', 'h&&(Vt.push(h)', "window.ownedRecordUpdates?.('queued',h)"],
    ['assignment', '$.props[y.prop]=E', "window.ownedRecordUpdates?.('assignment',[{id:y.id,prop:y.prop,value:E,previous:$.props[y.prop]}])"],
    ['flush_end', 'Vt=[],v=!1,p.set(!1)', "window.ownedRecordUpdates?.('flush_end',window.ownedFrameworkTrace.ids.components.flatMap(id=>window.ownedFrameworkTrace.ids.props.map(prop=>({id,prop,value:s[id]?.props[prop]}))))"],
    ['handle_update', 'const W=u.find(X=>X.id==ee).outputs', "window.ownedRecordData?.('handle_update',ee,A)"],
    ['js_schedule', 'B.frontend_fn?B.frontend_fn(X.data.concat', "window.ownedRecordData?.('js_schedule',A,X.data)"],
    ['js_result', 'Dl(x,A)}):B.types.cancel', "window.ownedFrameworkTrace?.ids.functions.includes(A)&&window.ownedRecordFramework('js_result',{fn:A,input:X.data,outputs:x})"],
    ['handle_data', 'const{data:$e,fn_index:le}=he;B.pending_request', "window.ownedRecordData?.('handle_data',he.fn_index,he.data)"],
    ['change_schedule', 'requestAnimationFrame(()=>{Dt(x,B,X)})', "window.ownedChangeSchedule?.(x,B)"],
    ['change_callback', 'Dt(x,B,X)', "window.ownedChangeCallback?.(x,B)"],
    ['wait_for_flush', 'o?B=V.subscribe(X=>{X||(Nl(A,ee,W),ne())}):Nl(A,ee,W)', "window.ownedWaitForFlush?.(A,ee,o,ne)"],
    ['wait_resumed', 'Nl(A,ee,W),ne()', "window.ownedResumeFlush?.(A,ee,ne)"],
  ];
  const points = [];
  for (const [name, needle, expression] of definitionsToTrace) {
    const offset = code.indexOf(needle);
    if (offset < 0 || code.indexOf(needle, offset + 1) >= 0) throw Error('Nonunique logpoint: ' + name);
    const before = code.slice(0, offset).split('\n');
    const position = {lineNumber: before.length - 1, columnNumber: before.at(-1).length};
    const receipt = await cdp.send('Debugger.setBreakpointByUrl', {
      url: base + '/assets/' + filename, ...position,
      condition: '(' + expression + ',false)',
    });
    points.push({name, needle, ...position, ...receipt});
  }
  const resolved = [];
  cdp.on('Debugger.breakpointResolved', record => resolved.push(record));
  const served = [];
  page.on('response', response => {
    if (new URL(response.url()).pathname.endsWith('/' + filename)) {
      served.push(response.body().then(value => ({url: response.url(), sha256: crypto.createHash('sha256').update(value).digest('hex')})));
    }
  });
  return {ids, async snapshot() {
    const responses = await Promise.allSettled(served);
    return {bundleSha256: hash, points, resolved, served: responses,
      state: await page.evaluate(() => window.ownedFrameworkTrace)};
  }};
}
module.exports = {attach, installTrace};
