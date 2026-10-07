// Controlled scheduler probe: hold only the installed Gradio component flush.
// Mouse events, backend work, guard arguments/returns and other RAF callbacks run normally.
function install() {
  const raf = window.requestAnimationFrame.bind(window);
  const pending = [];
  const gate = window.ownedSelectorFlush = {armed: false, held: 0, released: 0};
  const record = (phase, values) => window.ownedRecordFramework?.(phase, values);
  window.requestAnimationFrame = callback => raf(time => {
    const source = Function.prototype.toString.call(callback);
    if (gate.armed && source.startsWith('function w(){_.update(h=>{for(let k=0;k<Vt.length;') &&
        source.includes('$.props[y.prop]=E')) {
      pending.push(callback); gate.held += 1;
      record('controlled_flush_held', {held: gate.held, source});
    } else callback(time);
  });
  gate.release = (all = false) => {
    if (all) gate.armed = false;
    if (!pending.length) throw Error('No controlled component flush is held');
    const callback = pending.shift();
    return new Promise(resolve => raf(time => {
      callback(time); gate.released += 1;
      record('controlled_flush_released', {released: gate.released}); resolve();
    }));
  };
  gate.close = () => { gate.armed = false; for (const callback of pending.splice(0)) raf(callback); };
}
module.exports = {install};
