const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={Intl,Date,window:{},document:{readyState:'loading',addEventListener(){}}};
vm.runInNewContext(fs.readFileSync('static/jalali-picker.js','utf8'),context);
const p=context.window.ServiceDatePicker;
assert.equal(p.days(1399,12),30);assert.equal(p.days(1400,12),29);assert.equal(p.days(1403,12),30);
assert.equal(p.days(1405,1),31);assert.equal(p.days(1405,7),30);
assert.equal(JSON.stringify(p.parse('۱۴۰۵/۰۱/۰۱')),'[1405,1,1]');
assert.equal(JSON.stringify(p.parse('2026-03-21')),'[1405,1,1]');
console.log('Jalali picker: 7 checks passed');
