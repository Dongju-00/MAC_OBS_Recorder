function (action, nextSelector = '', playerSelector = '') {
  // Runs inside the selected Chrome tab. No site-specific routes or APIs.
  const visible = el => {
    const rect = el.getBoundingClientRect();
    const style = el.ownerDocument.defaultView.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const roots = [document];
  const seen = new Set(roots);
  let inaccessibleFrames = 0;
  for (let index = 0; index < roots.length; index++) {
    for (const element of roots[index].querySelectorAll('*')) {
      if (element.shadowRoot && !seen.has(element.shadowRoot)) {
        seen.add(element.shadowRoot);
        roots.push(element.shadowRoot);
      }
      if (element.tagName === 'IFRAME' && visible(element)) {
        try {
          const frame = element.contentDocument;
          if (frame && !seen.has(frame)) { seen.add(frame); roots.push(frame); }
          else if (!frame) inaccessibleFrames++;
        } catch (_) { inaccessibleFrames++; }
      }
    }
  }
  const all = selector => [...new Set(roots.flatMap(root => [...root.querySelectorAll(selector)]))];
  const label = el => [el.innerText, el.getAttribute('aria-label'), el.getAttribute('title')]
    .filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  let videos, matches;
  try {
    videos = all(playerSelector || 'video').filter(el => el.tagName === 'VIDEO' && visible(el));
    matches = nextSelector ? all(nextSelector).filter(visible) :
      all('button, a, [role="button"]').filter(el => visible(el) &&
        ((el.getAttribute('rel') || '').split(/\s+/).includes('next') ||
         [el.innerText, el.getAttribute('aria-label'), el.getAttribute('title')].some(text =>
           /^(?:다음(?:\s*영상)?|next(?:\s+video)?)[\s›»→]*$/i.test((text || '').trim()))));
  } catch (error) { return JSON.stringify({failure: 'video CSS 선택자 오류: ' + error.message}); }
  matches = matches.filter(el => !matches.some(other => el !== other && el.contains(other)));
  const disabled = el => el.disabled || el.getAttribute('aria-disabled') === 'true';
  const nextCandidates = matches.filter(el => !disabled(el));
  const video = videos.length === 1 ? videos[0] : null;
  const memory = window.__videoRecorderState || (window.__videoRecorderState = {
    documentId: Date.now().toString(36) + '-' + Math.random().toString(36).slice(2),
    sequence: 0, players: new WeakMap()
  });
  let player = video && memory.players.get(video);
  if (video && !player) {
    player = {id: ++memory.sequence, generation: 0, loading: false, ended: false, playError: null};
    memory.players.set(video, player);
    const state = player;
    video.addEventListener('ended', () => { state.ended = true; });
    for (const event of ['emptied', 'loadstart']) video.addEventListener(event, () => {
      state.loading = true;
      state.ended = false;
    });
    video.addEventListener('loadedmetadata', () => {
      state.generation++;
      state.loading = false;
      state.ended = false;
      state.playError = null;
    });
  }
  const ready = () => !!video && !player.loading && video.readyState >= 2;
  if (['prepare', 'play', 'pause', 'focus-player', 'fullscreen'].includes(action) && !video) {
    return JSON.stringify({failure: '제어 가능한 video가 정확히 1개여야 합니다. --video-selector로 대상을 지정하세요.'});
  }
  if (['prepare', 'play'].includes(action) && !ready()) {
    return JSON.stringify({failure: '새 영상의 로딩 완료를 기다려야 합니다.'});
  }
  try {
    if (action === 'prepare') {
      video.pause();
      video.currentTime = 0;
      player.ended = false;
      player.playError = null;
    }
    if (action === 'play') {
      player.playError = null;
      const state = player;
      const result = video.play();
      if (result && result.catch) result.catch(error => { state.playError = error.message; });
    }
    if (action === 'pause') video.pause();
    if (action === 'focus-player') {
      video.setAttribute('tabindex', '0');
      video.focus({preventScroll: true});
    }
    if (action === 'fullscreen' && !video.ownerDocument.fullscreenElement) {
      const result = video.requestFullscreen();
      if (result && result.catch) result.catch(() => {});
    }
    if (action === 'exit-fullscreen') {
      for (const root of roots) {
        if (root.fullscreenElement && root.exitFullscreen) root.exitFullscreen();
      }
    }
    if (action === 'next') {
      if (nextCandidates.length !== 1) throw new Error('다음 영상 버튼이 정확히 1개여야 합니다. --video-next-selector를 확인하세요.');
      const next = nextCandidates[0];
      const target = next.getAttribute('target');
      if (target && target.toLowerCase() !== '_self') throw new Error('다음 영상은 현재 탭에서 열려야 합니다.');
      const href = next.getAttribute('href');
      if (href && !['http:', 'https:', 'file:'].includes(new URL(href, location.href).protocol)) {
        throw new Error('다음 영상 링크의 프로토콜을 지원하지 않습니다.');
      }
      next.click();
    }
  } catch (error) { return JSON.stringify({failure: error.message}); }
  const result = {
    url: location.href, title: document.title, videoCount: videos.length,
    videoId: video ? memory.documentId + ':' + player.id + ':' + player.generation : null,
    duration: video && Number.isFinite(video.duration) ? video.duration : null,
    time: video ? video.currentTime : null, paused: video ? video.paused : null,
    ended: !!video && (video.ended || player.ended), seeking: !!video && video.seeking,
    readyState: video ? video.readyState : 0, playerReady: ready(),
    error: video && video.error ? video.error.code : null,
    playError: player ? player.playError : null,
    userActivated: typeof navigator === 'undefined' || !navigator.userActivation ? null : navigator.userActivation.hasBeenActive,
    fullscreen: !!video && !!video.ownerDocument.fullscreenElement,
    playerHasFocus: !!video && video.ownerDocument.activeElement === video,
    nextCount: nextCandidates.length, nextDisabledCount: matches.filter(disabled).length,
    inaccessibleFrames
  };
  if (action === 'diagnose') {
    result.nextCandidates = matches.map(el => ({tag: el.tagName, text: label(el),
      id: el.getAttribute('id'), class: el.getAttribute('class'),
      disabled: !!disabled(el), href: el.getAttribute('href')}));
  }
  return JSON.stringify(result);
}
