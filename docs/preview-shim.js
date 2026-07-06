/*
 * DocuRAG — static preview shim.
 *
 * Loaded BEFORE app.js on the GitHub Pages build. It makes the unmodified
 * frontend run with no backend by:
 *   1. showing a demo login (any credentials work; "admin" unlocks the
 *      analytics dashboard), and
 *   2. patching window.fetch to answer the backend routes locally:
 *        /verify-password       -> OK; is_admin when username is "admin"
 *        /app-config            -> branding from data/app-config.json
 *        /ask-status            -> a canned quota
 *        /search                -> client-side keyword scoring (ported from rag.py)
 *        /chat                  -> canned demo answers streamed as SSE
 *        /admin/dashboard-data  -> sample analytics from data/demo-dashboard.json
 *
 * The search scoring here is a faithful port of app/rag.py + app/search_config.py.
 * Its tuning is exported to data/search-index.json at build time, so the two
 * never drift.
 */
(function () {
  'use strict';

  var _fetch = window.fetch.bind(window);

  // Username that unlocks the admin analytics dashboard in the demo.
  var ADMIN_USER = 'admin';

  // ---- Data (loaded once, before app.js needs it) ----
  var DATA = null;
  var dataReady = Promise.all([
    _fetch('data/search-index.json').then(function (r) { return r.json(); }),
    _fetch('data/demo-answers.json').then(function (r) { return r.json(); }),
    _fetch('data/app-config.json').then(function (r) { return r.json(); }),
    _fetch('data/demo-dashboard.json').then(function (r) { return r.json(); })
  ]).then(function (parts) {
    DATA = { index: parts[0], demo: parts[1], cfg: parts[2], dashboard: parts[3] };
    return DATA;
  });

  function isAdmin(username) {
    return (username || '').trim().toLowerCase() === ADMIN_USER;
  }

  // =====================================================================
  // Search engine — port of app/rag.py (search path only)
  // =====================================================================
  function cfg() { return DATA.index.config; }

  function stem(word) {
    var suffixes = cfg().SUFFIXES, minStem = cfg().MIN_STEM;
    for (var i = 0; i < suffixes.length; i++) {
      var suf = suffixes[i];
      if (word.length > suf.length && word.slice(-suf.length) === suf) {
        var s = word.slice(0, word.length - suf.length);
        if (s.length >= minStem) return s;
      }
    }
    return word;
  }

  function extractKeywords(query) {
    var stop = new Set(cfg().STOP_WORDS);
    var tech = new Set(cfg().TECH_TERMS);
    var words = query.toLowerCase().split(/[\s,?.!:;()\[\]\/]+/);
    var out = [];
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (!w || stop.has(w)) continue;
      if (tech.has(w) || w.length >= 4) out.push(w);
    }
    return out;
  }

  function keywordVariants(kw) {
    var syn = cfg().SYNONYMS;
    var variants = [kw];
    function add(v) { if (variants.indexOf(v) === -1) variants.push(v); }
    var st = stem(kw);
    if (st !== kw) add(st);
    if (kw.length >= 6) add(kw.slice(0, -2));
    if (kw.length >= 8) add(kw.slice(0, -3));
    var list = syn[kw] || [];
    for (var i = 0; i < list.length; i++) {
      add(list[i]);
      var ss = stem(list[i]);
      if (ss !== list[i]) add(ss);
    }
    return variants;
  }

  function categoryBoost(entry, keywords) {
    var map = cfg().CATEGORY_BOOST;
    var pathL = entry.path.replace(/\\/g, '/').toLowerCase();
    var boost = 0;
    for (var i = 0; i < keywords.length; i++) {
      var frags = map[keywords[i]] || [];
      for (var j = 0; j < frags.length; j++) {
        if (pathL.indexOf(frags[j].toLowerCase()) !== -1) { boost += 2.0; break; }
      }
    }
    return boost;
  }

  function scoreEntry(entry, keywords, queryLower) {
    var titleL = entry.title.toLowerCase();
    var summaryL = (entry.summary || '').toLowerCase();
    var tagsL = (entry.tags || '').toLowerCase();
    var score = 0, matched = 0;

    if (queryLower) {
      var phrases = cfg().KNOWN_PHRASES;
      for (var p = 0; p < phrases.length; p++) {
        if (queryLower.indexOf(phrases[p]) !== -1 && titleL.indexOf(phrases[p]) !== -1) {
          score += 8.0;
        }
      }
    }
    score += categoryBoost(entry, keywords);

    for (var k = 0; k < keywords.length; k++) {
      var variants = keywordVariants(keywords[k]);
      var hit = false;
      for (var v = 0; v < variants.length; v++) {
        var vv = variants[v];
        if (titleL.indexOf(vv) !== -1) { score += 4.0; hit = true; break; }
        else if (tagsL.indexOf(vv) !== -1) { score += 1.0; hit = true; break; }
        else if (summaryL.indexOf(vv) !== -1) { score += 1.0; hit = true; break; }
      }
      if (hit) matched++;
    }
    return matched > 0 ? [score, matched] : [0, 0];
  }

  function occurrences(hay, needle) {
    if (!needle) return 0;
    return hay.split(needle).length - 1;
  }

  // Port of rag.search_wiki — full-text scan over article bodies.
  function searchWiki(query) {
    var keywords = query.split(/\s+/).filter(function (k) { return k; })
      .map(function (k) { return k.toLowerCase(); });
    if (!keywords.length) return [];
    var scored = [];
    var entries = DATA.index.entries;
    for (var i = 0; i < entries.length; i++) {
      var content = entries[i].text || '';
      var docScore = 0, hits = 0;
      for (var k = 0; k < keywords.length; k++) {
        var c = occurrences(content, keywords[k]);
        if (c > 0) { docScore += 1 + Math.log(c); hits++; }
      }
      var required = Math.max(1, Math.floor((keywords.length + 1) / 2));
      if (hits >= required) scored.push([docScore, entries[i].path]);
    }
    scored.sort(function (a, b) { return b[0] - a[0]; });
    return scored.slice(0, 10).map(function (x) { return x[1]; });
  }

  // Port of rag.search_index_entries.
  function searchIndex(query) {
    var keywords = extractKeywords(query);
    if (!keywords.length) return [];
    var required = Math.max(1, keywords.length - 1);
    var entries = DATA.index.entries;
    var queryLower = query.toLowerCase();

    var scored = [];
    for (var i = 0; i < entries.length; i++) {
      var res = scoreEntry(entries[i], keywords, queryLower);
      if (res[0] >= 2.0 && res[1] >= required) scored.push([res[0], entries[i]]);
    }
    scored.sort(function (a, b) { return b[0] - a[0]; });
    var results = scored.slice(0, 5).map(function (x) { return x[1]; });

    // Phase 2 — full-text fallback when the index gives too few hits.
    if (results.length < 3) {
      var specific = keywords.slice().sort(function (a, b) { return b.length - a.length; }).slice(0, 2);
      var paths = searchWiki(specific.join(' '));
      var existing = {};
      results.forEach(function (r) { existing[r.path] = true; });
      var byPath = {};
      entries.forEach(function (e) { byPath[e.path.replace(/\\/g, '/')] = e; });
      for (var p = 0; p < paths.length && p < 4; p++) {
        var cp = paths[p].replace(/\\/g, '/');
        if (!existing[cp] && byPath[cp]) results.push(byPath[cp]);
      }
    }
    return results.slice(0, 5).map(function (e) {
      return { path: e.path, title: e.title, summary: e.summary, url: e.url, category: e.category };
    });
  }

  // =====================================================================
  // Canned Ask answers
  // =====================================================================
  var DEMO_LABEL = '\n\n*Demo response — in a live deployment this is generated by Claude, grounded in your own articles.*';

  function pickAnswer(message) {
    var msg = message.toLowerCase();
    var best = null, bestScore = 0;
    var list = DATA.demo.answers || [];
    for (var i = 0; i < list.length; i++) {
      var hits = 0;
      var kws = list[i].keywords || [];
      for (var k = 0; k < kws.length; k++) {
        if (msg.indexOf(kws[k].toLowerCase()) !== -1) hits++;
      }
      if (hits > bestScore) { bestScore = hits; best = list[i]; }
    }
    if (best && bestScore > 0) {
      return { answer: best.answer + DEMO_LABEL, files_read: best.files_read || [] };
    }
    return { answer: DATA.demo.fallback.answer, files_read: [] };
  }

  // =====================================================================
  // Response helpers
  // =====================================================================
  function jsonResponse(obj, status) {
    return new Response(JSON.stringify(obj), {
      status: status || 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  function sseResponse(message) {
    var picked = pickAnswer(message);
    var events = [
      { type: 'commit_stream', text: picked.answer },
      { type: 'done', files_read: picked.files_read }
    ];
    var payload = events.map(function (e) { return 'data: ' + JSON.stringify(e) + '\n'; }).join('');
    var stream = new ReadableStream({
      start: function (controller) {
        controller.enqueue(new TextEncoder().encode(payload));
        controller.close();
      }
    });
    return new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' }
    });
  }

  // =====================================================================
  // fetch interceptor
  // =====================================================================
  window.fetch = function (input, init) {
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    var path;
    try { path = new URL(url, location.href).pathname; } catch (e) { path = url; }

    if (path.endsWith('/verify-password')) {
      var username = '';
      try { username = JSON.parse(init && init.body).username || ''; } catch (e) {}
      return Promise.resolve(jsonResponse({ ok: true, is_admin: isAdmin(username) }));
    }
    if (path.endsWith('/app-config')) {
      return dataReady.then(function () { return jsonResponse(DATA.cfg); });
    }
    if (path.endsWith('/ask-status')) {
      return jsonResponse({ remaining: 20, daily_limit: 20, seconds_until_next: 0 });
    }
    if (path.endsWith('/search')) {
      return dataReady.then(function () {
        var q = '';
        try { q = new URL(url, location.href).searchParams.get('q') || ''; } catch (e) {}
        q = q.trim();
        var results = q ? searchIndex(q) : [];
        return jsonResponse({ results: results, count: results.length });
      });
    }
    if (path.endsWith('/chat')) {
      return dataReady.then(function () {
        var message = '';
        try { message = JSON.parse(init && init.body).message || ''; } catch (e) {}
        return sseResponse(message);
      });
    }
    if (path.endsWith('/admin/dashboard-data')) {
      return dataReady.then(function () { return jsonResponse(DATA.dashboard); });
    }
    if (path.indexOf('/admin/') !== -1) {
      return Promise.resolve(jsonResponse({ detail: 'Not available in preview' }, 403));
    }
    return _fetch(input, init);
  };

  // =====================================================================
  // Preview chrome — a "Preview" badge + demo-credentials hint on the login
  // =====================================================================
  function injectChrome() {
    var style = document.createElement('style');
    style.textContent =
      '#docurag-preview-badge{position:fixed;left:14px;bottom:12px;z-index:9999;' +
      'font-family:"JetBrains Mono",monospace;font-size:10px;letter-spacing:0.12em;' +
      'text-transform:uppercase;color:#c96442;border:1px solid rgba(201,100,66,0.4);' +
      'background:rgba(201,100,66,0.08);padding:4px 9px;border-radius:6px;' +
      'pointer-events:none;user-select:none;}' +
      '#docurag-demo-hint{margin-top:14px;font-family:"JetBrains Mono",monospace;' +
      'font-size:11px;line-height:1.6;color:#8a8a8a;text-align:center;}' +
      '#docurag-demo-hint b{color:#c9c9c9;font-weight:600;}' +
      '#docurag-demo-hint .accent{color:#c96442;}';
    document.head.appendChild(style);

    var badge = document.createElement('div');
    badge.id = 'docurag-preview-badge';
    badge.textContent = 'Preview';
    document.body.appendChild(badge);

    // Demo login hint — any credentials work; "admin" reveals the dashboard.
    var box = document.getElementById('login-box');
    if (box) {
      var hint = document.createElement('div');
      hint.id = 'docurag-demo-hint';
      hint.innerHTML =
        'Demo preview — any login works.<br>' +
        'User: <b>demo</b> / <b>demo</b> &nbsp;·&nbsp; ' +
        'Admin: <b class="accent">admin</b> / <b class="accent">admin</b>';
      box.appendChild(hint);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectChrome);
  } else {
    injectChrome();
  }
})();
