const test=require('node:test'),assert=require('node:assert/strict');
const {ChartNavigator}=require('./navigator.js');
test('navigation clamps first/last, arrow and segment positions',()=>{
 const n=new ChartNavigator(100); assert.equal(n.move(-1),0); assert.equal(n.move(1),1);
 assert.equal(n.seek(99),99); assert.equal(n.move(1),99); assert.equal(n.move(-10),89);
 n.reset(1); assert.equal(n.move(100),0);
});
test('playback ranges and custom validation',()=>{
 const n=new ChartNavigator(100); n.seek(50);
 assert.deepEqual(n.range('current'),[50,99]); assert.deepEqual(n.range('previous',10),[40,49]);
 assert.deepEqual(n.range('next',10),[51,60]); assert.deepEqual(n.range('custom',10,2,5),[1,4]);
 assert.throws(()=>n.range('custom',10,0,101));
});
