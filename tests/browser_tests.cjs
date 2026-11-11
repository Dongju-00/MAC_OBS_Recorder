const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../browser.js'), 'utf8');

function fixture({href='https://media.example/watch/1', labels=['Next video'], count=1,
  disabled=false, blank=false, nested=false, inaccessible=false, frame=false, shadow=false}={}) {
  const calls = [];
  let document;
  class Element {
    constructor(tag, text='', attrs={}) {
      this.tagName=tag; this.innerText=text; this.attrs=attrs; this.ownerDocument=document;
      this.children=[]; this.hidden=false; this.disabled=false;
    }
    getAttribute(name) { return this.attrs[name] ?? null; }
    setAttribute(name,value) { this.attrs[name]=value; }
    removeAttribute(name) { delete this.attrs[name]; }
    getBoundingClientRect() { return {width:this.hidden?0:500,height:300}; }
    contains(el) { return this.children.includes(el); }
    querySelectorAll(selector) { return this.children.filter(el => matches(el,selector)); }
    click() { calls.push(this.innerText); }
    focus() { this.ownerDocument.activeElement=this; }
  }
  function matches(el, selector) {
    return selector.split(',').some(s => {
      s=s.trim();
      if(s==='*') return true;
      if(s==='video') return el.tagName==='VIDEO';
      if(s==='#player') return el.attrs.id==='player';
      if(s==='#advance') return el.attrs.id==='advance';
      if(s==='[bad') throw new Error('invalid selector');
      if(s==='button') return el.tagName==='BUTTON';
      if(s==='a' || s==='a[href]') return el.tagName==='A' && (s==='a' || !!el.attrs.href);
      if(s==='[role="button"]') return el.attrs.role==='button';
      if(s==='[rel~="next"]' || s==='a[rel~="next"]') return (el.attrs.rel||'').split(' ').includes('next');
      return false;
    });
  }
  const roots=[];
  document={title:'Example video',defaultView:{getComputedStyle:()=>({visibility:'visible',display:'block'})},
    querySelectorAll(selector) { return roots.filter(el=>matches(el,selector)); }};
  function newVideo() {
    const video=new Element('VIDEO','',{id:'player'});
    video.listeners={};
    Object.assign(video,{duration:60,currentTime:5,paused:true,ended:false,seeking:false,readyState:4,error:null,
      addEventListener(name,fn) {(this.listeners[name] ||= []).push(fn);},
      pause() { this.paused=true; calls.push('pause'); },
      play() { this.paused=false; calls.push('play'); return Promise.resolve(); },
      requestFullscreen() { document.fullscreenElement=this; return Promise.resolve(); },
      emit(name) { for(const fn of this.listeners[name]||[]) fn(); }});
    return video;
  }
  let video=newVideo();
  for(let i=0;i<count;i++) roots.push(i===0?video:newVideo());
  const buttons=labels.map(label=>new Element('BUTTON',label));
  buttons.forEach(button=>{button.disabled=disabled;button.attrs.id='advance';});
  if(blank && buttons.length) {buttons[0].tagName='A';buttons[0].attrs.href='https://other.example/2';buttons[0].attrs.target='_blank';}
  roots.push(...buttons);
  if(nested) {
    const parent=new Element('DIV','Next video',{role:'button'});
    parent.children.push(buttons[0]);roots.push(parent);
  }
  if(inaccessible) roots.push(Object.assign(new Element('IFRAME'),{contentDocument:null}));
  if(frame || shadow) {
    const inner={defaultView:document.defaultView,querySelectorAll:selector=>[video,...buttons].filter(el=>matches(el,selector))};
    roots.splice(0,roots.length);
    if(frame) roots.push(Object.assign(new Element('IFRAME'),{contentDocument:inner}));
    else roots.push(Object.assign(new Element('DIV'),{shadowRoot:inner}));
  }
  const context=vm.createContext({document,window:{},URL,location:{href},console});
  const fn=vm.runInContext('('+source+')',context);
  return {calls,buttons,get video(){return video;},context,
    replaceVideo() { const index=roots.indexOf(video); video=newVideo(); roots[index]=video; },
    call(action='inspect',selector='',playerSelector='') {return JSON.parse(fn(action,selector,playerSelector));}};
}

(async () => {
  let f=fixture();
  assert.equal(f.call().nextCount,1);
  assert.equal(f.call().videoCount,1);
  f.call('prepare');assert.equal(f.video.currentTime,0);assert.equal(f.video.paused,true);
  f.call('play');assert.equal(f.video.paused,false);
  assert.equal(f.call('focus-player').playerHasFocus,true);
  f.video.emit('ended');assert.equal(f.call().ended,true);
  f.call('prepare');assert.equal(f.call().ended,false);

  for(const href of ['https://one.example/video','http://localhost:8000/video','file:///tmp/video.html']) {
    f=fixture({href});f.call('play');assert.equal(f.video.paused,false);
    f.call('next');assert.equal(f.calls.at(-1),'Next video');
  }
  f=fixture({labels:['Continue watching']});
  assert.equal(f.call().nextCount,0);
  assert.equal(f.call('inspect','#advance').nextCount,1);
  f.call('next','#advance');assert.equal(f.calls.at(-1),'Continue watching');
  assert.ok(f.call('inspect','[bad').failure);

  for(const labels of [['다음 영상'],['다음'],['Next'],['Next video']]) {
    f=fixture({labels});assert.equal(f.call().nextCount,1);
  }
  f=fixture({labels:['Pay now']});assert.equal(f.call().nextCount,0);
  assert.ok(f.call('next').failure);assert.deepEqual(f.calls,[]);
  f=fixture({labels:['Continue']});f.buttons[0].attrs.rel='nofollow next';
  assert.equal(f.call().nextCount,1);

  f=fixture({labels:['Next video','Next video']});
  assert.equal(f.call().nextCount,2);assert.ok(f.call('next').failure);assert.deepEqual(f.calls,[]);
  f=fixture({nested:true});assert.equal(f.call().nextCount,1);
  f=fixture({disabled:true});assert.equal(f.call().nextCount,0);
  assert.equal(f.call().nextDisabledCount,1);assert.ok(f.call('next').failure);
  f=fixture({blank:true});assert.ok(f.call('next').failure);assert.deepEqual(f.calls,[]);
  f=fixture();f.buttons[0].tagName='A';f.buttons[0].attrs.href='javascript:alert(1)';
  assert.ok(f.call('next').failure);assert.deepEqual(f.calls,[]);

  f=fixture({count:2});assert.ok(f.call('play').failure);
  f.video.attrs.id='chosen';assert.equal(f.call('inspect','','#player').videoCount,1);
  f=fixture({inaccessible:true,count:0});assert.equal(f.call().inaccessibleFrames,1);
  assert.ok(f.call('prepare').failure);
  f=fixture({frame:true});assert.equal(f.call().videoCount,1);
  f=fixture({shadow:true});assert.equal(f.call().videoCount,1);

  f=fixture();const first=f.call().videoId;
  f.context.location.href='https://media.example/watch/2';
  assert.equal(f.call().videoId,first,'URL만 바뀌어도 이전 플레이어를 새 영상으로 인식하면 안 됨');
  f.video.emit('loadstart');assert.equal(f.call().playerReady,false);
  f.video.emit('loadedmetadata');assert.notEqual(f.call().videoId,first);
  assert.equal(f.call().playerReady,true);
  const second=f.call().videoId;f.replaceVideo();assert.notEqual(f.call().videoId,second);
  const other=fixture();assert.notEqual(other.call().videoId,fixture().call().videoId);

  f=fixture();f.call();f.video.play=()=>Promise.reject(new Error('Playback blocked'));
  f.call('play');await new Promise(resolve=>setImmediate(resolve));
  assert.match(f.call().playError,/Playback blocked/);
  f=fixture();const details=f.call('diagnose');assert.ok(details.nextCandidates);
  assert.deepEqual(f.calls,[]);
  console.log('video 브라우저: 일반 URL, 재생, 버튼, iframe, shadow root, 미디어 교체, 오류 시나리오 통과');
})().catch(error=>{console.error(error);process.exitCode=1;});
