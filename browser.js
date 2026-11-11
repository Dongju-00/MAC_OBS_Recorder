function (action, nextSelector = '', playerSelector = '') {
  // Ordinary DOM playback controls for authorized, non-DRM browser testing.
  // No key extraction, DRM configuration changes, or capture-protection bypass.
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
  const hostname = new URL(location.href).hostname;
  const youtube = hostname === 'youtube.com' || hostname.endsWith('.youtube.com');
  const nextScore = el => {
    // YouTube also labels unrelated page/carousel arrows "Next". Only its
    // player controls may advance media; a missing control uses the tested shortcut.
    if (youtube && !(el.getAttribute('class') || '').split(/\s+/).includes('ytp-next-button')
        && !(el.closest && el.closest('#movie_player, .html5-video-player'))) return 0;
    let score = 0;
    for (const raw of [el.innerText, el.getAttribute('aria-label'), el.getAttribute('title')]) {
      const text = (raw || '').replace(/\s*\((?:shift|ctrl|control|alt|option|command)[^)]*\)\s*$/i, '').trim();
      if (/^(?:next\s+(?:video|lesson|lecture|episode|clip)|다음\s*(?:영상|동영상|강의|수업))\s*[›»→]*$/i.test(text)) score = 100;
      else if (/^(?:next|다음)\s*[›»→]*$/i.test(text)) score = Math.max(score, 60);
    }
    if ((el.getAttribute('rel') || '').split(/\s+/).includes('next')) score = Math.max(score, 80);
    for (const attr of ['id', 'class', 'data-testid', 'data-test']) {
      const value = el.getAttribute(attr) || '';
      if (/(?:^|[\s_-])(?:next[-_](?:video|lesson|lecture|episode|button)|(?:video|player)[-_]next)(?:$|[\s_-])/i.test(value)) {
        score = Math.max(score, 90);
      }
    }
    return score;
  };
  const selectorFor = el => {
    const tag = el.tagName.toLowerCase();
    const selectors = ['id', 'data-testid', 'data-test', 'aria-label', 'title', 'rel']
      .filter(attr => el.getAttribute(attr))
      .map(attr => `${tag}[${attr}=${JSON.stringify(el.getAttribute(attr))}]`);
    for (const token of (el.getAttribute('class') || '').split(/\s+/).filter(Boolean)) {
      selectors.push(`${tag}[class~=${JSON.stringify(token)}]`);
    }
    for (const selector of selectors) {
      try {
        const found = all(selector).filter(visible);
        if (found.length === 1 && found[0] === el) return selector;
      } catch (_) { /* Try another stable attribute. */ }
    }
    return null; // Keep semantic discovery when no unique attribute exists.
  };
  let videos, matches;
  try {
    videos = all(playerSelector || 'video').filter(el => el.tagName === 'VIDEO' && visible(el));
    matches = nextSelector ? all(nextSelector).filter(visible) :
      all('button, a, [role="button"]').filter(el => visible(el) && nextScore(el) > 0);
  } catch (error) { return JSON.stringify({failure: 'Invalid video CSS selector: ' + error.message}); }
  matches = matches.filter(el => !matches.some(other => el !== other && el.contains(other)));
  const disabled = el => el.disabled || el.getAttribute('aria-disabled') === 'true';
  if (!nextSelector) {
    const best = Math.max(0, ...matches.map(nextScore));
    matches = matches.filter(el => nextScore(el) === best);
  }
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
    return JSON.stringify({failure: 'Exactly one controllable video is required. Specify it with --video-selector.'});
  }
  if (['prepare', 'play'].includes(action) && !ready()) {
    return JSON.stringify({failure: 'Wait for the new video to finish loading.'});
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
      if (nextCandidates.length !== 1) throw new Error('Exactly one next-video control is required. Check --video-next-selector.');
      const next = nextCandidates[0];
      const target = next.getAttribute('target');
      if (target && target.toLowerCase() !== '_self') throw new Error('The next video must open in the current tab.');
      const href = next.getAttribute('href');
      if (href && !['http:', 'https:', 'file:'].includes(new URL(href, location.href).protocol)) {
        throw new Error('Unsupported next-video link protocol.');
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
    result.nextSelector = nextCandidates.length === 1 ? selectorFor(nextCandidates[0]) : null;
    result.nextCandidates = matches.map(el => ({tag: el.tagName, text: label(el),
      id: el.getAttribute('id'), class: el.getAttribute('class'),
      disabled: !!disabled(el), href: el.getAttribute('href')}));
  }
  return JSON.stringify(result);
}
