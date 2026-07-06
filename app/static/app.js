// === DOM ===
const messagesEl       = document.getElementById('messages');
const searchAreaEl     = document.getElementById('search-area');
const searchResultsEl  = document.getElementById('search-results');
const inputEl          = document.getElementById('input');
const sendBtn          = document.getElementById('send-btn');
const loginScreen      = document.getElementById('login-screen');
const appEl            = document.getElementById('app');
const usernameInput    = document.getElementById('username-input');
const passwordInput    = document.getElementById('password-input');
const loginBtn         = document.getElementById('login-btn');
const loginError       = document.getElementById('login-error');
const newChatBtn       = document.getElementById('new-chat-btn');
const chatListEl       = document.getElementById('chat-list');
const topbarTitle      = document.getElementById('topbar-title');
const deleteChatBtn    = document.getElementById('delete-chat-btn');
const sidebarOpenBtn   = document.getElementById('sidebar-open-btn');
const sidebarCollapse  = document.getElementById('sidebar-toggle-collapse');
const sidebar          = document.getElementById('sidebar');
const modeToggleEl     = document.getElementById('mode-toggle');
const askCounterEl     = document.getElementById('ask-counter');
const cooldownBar      = document.getElementById('cooldown-bar');
const cooldownText     = document.getElementById('cooldown-text');
const modeSelectEl     = document.getElementById('mode-select');
const loginBoxEl       = document.getElementById('login-box');
const sidebarModeIcon  = document.getElementById('sidebar-mode-icon');
const sidebarModeName  = document.getElementById('sidebar-mode-name');
const sidebarSwitchBtn = document.getElementById('sidebar-switch-btn');
const sendIconAsk      = document.getElementById('send-icon-ask');
const sendIconSearch   = document.getElementById('send-icon-search');
const topbarSwitchBtn  = document.getElementById('topbar-switch-btn');
const topbarModeIcon   = document.getElementById('topbar-mode-icon');
const topbarModeName   = document.getElementById('topbar-mode-name');
const logoutBtn        = document.getElementById('logout-btn');
const dashboardBtn     = document.getElementById('dashboard-btn');
const dashboardScreen  = document.getElementById('dashboard-screen');

// === State ===
let sessionUsername  = '';
let sessionPassword  = '';
let sessionIsAdmin   = false;
let currentChatId    = null;
let currentMode      = 'search';
let askRemaining     = 5;
let askDailyLimit    = 5;
let cooldownInterval = null;
let cooldownSeconds  = 0;
let APP_NAME         = 'DocuRAG';

const thinkingWords = [
    'Thinking', 'Considering', 'Reasoning', 'Analyzing', 'Reflecting',
    'Planning', 'Searching', 'Reviewing', 'Evaluating', 'Working',
    'Processing', 'Cross-checking', 'Weighing', 'Connecting', 'Summarizing'
];

marked.setOptions({ breaks: true, gfm: true });

// === Helpers ===
function escapeHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// === Storage ===
function storageKey() {
    return currentMode === 'ask' ? 'docurag_chats_ask' : 'docurag_chats_search';
}

function getChats() {
    try { return JSON.parse(localStorage.getItem(storageKey()) || '{}'); }
    catch { return {}; }
}

function saveChats(chats) {
    localStorage.setItem(storageKey(), JSON.stringify(chats));
}

function getChat(id) { return getChats()[id] || null; }

function saveChatMessages(id, messages, title) {
    const chats = getChats();
    if (!chats[id]) {
        chats[id] = { id, title: title || 'New chat', created: Date.now(), messages: [] };
    }
    chats[id].messages = messages;
    if (title) chats[id].title = title;
    chats[id].updated = Date.now();
    saveChats(chats);
}

function saveSearchQuery(id, query) {
    const chats = getChats();
    if (!chats[id]) {
        chats[id] = { id, title: deriveTitle(query), created: Date.now(), messages: [], query };
    } else {
        chats[id].query = query;
        chats[id].title = deriveTitle(query);
    }
    chats[id].updated = Date.now();
    saveChats(chats);
}

function deleteChat(id) {
    const chats = getChats();
    delete chats[id];
    saveChats(chats);
}

function generateId() {
    return (currentMode === 'ask' ? 'ask_' : 'srch_') + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
}

function deriveTitle(text) {
    const clean = text.replace(/\n/g, ' ').trim();
    return clean.length > 45 ? clean.slice(0, 42) + '...' : clean;
}

// === Display sync ===
function syncContentDisplay() {
    const isAsk = currentMode === 'ask';
    messagesEl.style.display   = isAsk ? 'flex' : 'none';
    searchAreaEl.style.display = isAsk ? 'none' : 'flex';
    if (isAsk) messagesEl.style.flexDirection = 'column';
}

// === Mode management ===
function setMode(mode) {
    if (currentMode === mode) return;
    if (mode === 'search') stopCooldown();

    const fromEl = currentMode === 'ask' ? messagesEl : searchAreaEl;
    const toEl   = mode === 'ask'        ? messagesEl : searchAreaEl;

    fromEl.style.transition = 'opacity 0.15s ease, transform 0.15s ease';
    fromEl.style.opacity    = '0';
    fromEl.style.transform  = 'translateY(3px)';

    setTimeout(() => {
        fromEl.style.transition = '';
        fromEl.style.opacity    = '';
        fromEl.style.transform  = '';
        fromEl.style.display    = 'none';

        currentMode = mode;
        updateModeUI();

        toEl.style.display        = 'flex';
        toEl.style.flexDirection  = 'column';
        toEl.style.opacity        = '0';
        toEl.style.transform      = 'translateY(-3px)';
        toEl.style.transition     = '';

        const chats  = getChats();
        const sorted = Object.values(chats).sort((a, b) => (b.updated || b.created) - (a.updated || a.created));
        if (sorted.length > 0) loadChat(sorted[0].id);
        else createNewChat();

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                toEl.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
                toEl.style.opacity    = '1';
                toEl.style.transform  = '';
                setTimeout(() => {
                    toEl.style.transition = '';
                    toEl.style.opacity    = '';
                    toEl.style.transform  = '';
                }, 220);
            });
        });
    }, 160);
}

function updateModeUI() {
    const isAsk = currentMode === 'ask';
    const isSearch = currentMode === 'search';

    appEl.classList.toggle('search-mode', isSearch);

    modeToggleEl.classList.toggle('mode-ask',    isAsk);
    modeToggleEl.classList.toggle('mode-search', isSearch);
    askCounterEl.style.display = isAsk ? 'inline' : 'none';
    if (isAsk) askCounterEl.textContent = `${askRemaining}/${askDailyLimit}`;

    const sidebarHeader = document.getElementById('sidebar-header');
    sidebarHeader.classList.toggle('mode-ask',    isAsk);
    sidebarHeader.classList.toggle('mode-search', isSearch);
    if (sidebarModeIcon) sidebarModeIcon.textContent = isAsk ? '◈' : '⌕';
    if (sidebarModeName) sidebarModeName.textContent = isAsk ? 'Ask' : 'Search';

    if (topbarModeIcon) topbarModeIcon.textContent = '⌕';
    if (topbarModeName) topbarModeName.textContent = 'Search';

    if (sendIconAsk)    sendIconAsk.style.display    = isAsk ? 'flex' : 'none';
    if (sendIconSearch) sendIconSearch.style.display = isAsk ? 'none' : 'flex';

    inputEl.placeholder = isAsk ? 'Ask a question' : 'Search the knowledge base';

    newChatBtn.textContent = isAsk ? '+ New chat' : '+ New search';

    renderChatList();
}

async function fetchAskStatus() {
    try {
        const res = await fetch(`/ask-status?username=${encodeURIComponent(sessionUsername)}&password=${encodeURIComponent(sessionPassword)}`);
        if (!res.ok) return;
        const data = await res.json();
        askRemaining  = data.remaining ?? 5;
        askDailyLimit = data.daily_limit ?? 5;
        if (data.seconds_until_next > 0) startCooldown(data.seconds_until_next);
        askCounterEl.textContent = `${askRemaining}/${askDailyLimit}`;
    } catch { /* silent */ }
}

function startCooldown(seconds) {
    stopCooldown();
    cooldownSeconds = seconds;
    updateCooldownUI();
    cooldownBar.style.display = 'flex';
    sendBtn.disabled  = true;
    inputEl.disabled  = true;

    cooldownInterval = setInterval(() => {
        cooldownSeconds--;
        if (cooldownSeconds <= 0) {
            stopCooldown();
            fetchAskStatus();
        } else {
            updateCooldownUI();
        }
    }, 1000);
}

function stopCooldown() {
    if (cooldownInterval) { clearInterval(cooldownInterval); cooldownInterval = null; }
    cooldownSeconds = 0;
    cooldownBar.style.display = 'none';
    sendBtn.disabled = false;
    inputEl.disabled = false;
}

function updateCooldownUI() {
    const m = Math.floor(cooldownSeconds / 60);
    const s = cooldownSeconds % 60;
    cooldownText.textContent = `Next question in ${m}:${String(s).padStart(2, '0')}`;
}

async function showModeSelectFromApp() {
    stopCooldown();
    try {
        const res = await fetch(`/ask-status?username=${encodeURIComponent(sessionUsername)}&password=${encodeURIComponent(sessionPassword)}`);
        if (res.ok) {
            const data = await res.json();
            askRemaining  = data.remaining ?? 5;
            askDailyLimit = data.daily_limit ?? 5;
            const badge = document.getElementById('ask-count-badge');
            if (badge) badge.textContent = `${askRemaining}/${askDailyLimit} today`;
        }
    } catch {}
    appEl.style.display       = 'none';
    loginScreen.style.display = 'flex';
    loginBoxEl.style.display  = 'none';
    modeSelectEl.style.display = 'flex';
    modeSelectEl.style.opacity = '1';
}

function toggleMode() {
    showModeSelectFromApp();
}

sidebarSwitchBtn && sidebarSwitchBtn.addEventListener('click', toggleMode);
topbarSwitchBtn  && topbarSwitchBtn.addEventListener('click', toggleMode);

// === Sidebar ===
function renderChatList() {
    const chats  = getChats();
    const sorted = Object.values(chats).sort((a, b) => (b.updated || b.created) - (a.updated || a.created));
    chatListEl.innerHTML = '';
    sorted.forEach(chat => {
        const div = document.createElement('div');
        div.className = 'chat-item' + (chat.id === currentChatId ? ' active' : '');
        div.textContent = chat.title || (currentMode === 'search' ? 'New search' : 'New chat');
        div.title = chat.title || '';
        div.addEventListener('click', () => loadChat(chat.id));
        chatListEl.appendChild(div);
    });
}

sidebarCollapse.addEventListener('click', () => sidebar.classList.add('collapsed'));
sidebarOpenBtn.addEventListener('click', () => sidebar.classList.remove('collapsed'));

function closeSidebarOnMobile() {
    if (window.innerWidth <= 768) sidebar.classList.add('collapsed');
}

// === Chat management ===
function createNewChat() {
    const id = generateId();
    currentChatId = id;

    if (currentMode === 'search') {
        saveChatMessages(id, [], 'New search');
        inputEl.value = '';
        inputEl.style.height = 'auto';
        showSearchWelcome();
        topbarTitle.textContent = 'New search';
        renderChatList();
    } else {
        clearMessages();
        showWelcome();
        topbarTitle.textContent = 'New chat';
    }
    inputEl.focus();
    closeSidebarOnMobile();
}

function loadChat(id) {
    currentChatId = id;
    const chat = getChat(id);
    if (!chat) return createNewChat();

    topbarTitle.textContent = chat.title || (currentMode === 'search' ? 'New search' : 'New chat');

    if (currentMode === 'search') {
        if (chat.query) {
            inputEl.value = chat.query;
            inputEl.style.height = 'auto';
            runSearch(chat.query);
        } else {
            showSearchWelcome();
        }
        renderChatList();
        closeSidebarOnMobile();
        return;
    }

    clearMessages();
    if (chat.messages.length === 0) {
        showWelcome();
    } else {
        hideWelcome();
        chat.messages.forEach(msg => addMessageToDOM(msg.role, msg.content, msg.filesRead || []));
    }
    renderChatList();
    scrollToBottom();
    inputEl.focus();
    closeSidebarOnMobile();
}

function getCurrentMessages() {
    const chat = getChat(currentChatId);
    return chat ? chat.messages : [];
}

// === Ask mode UI helpers ===
function scrollToBottom() { messagesEl.scrollTop = messagesEl.scrollHeight; }

function showWelcome() {
    let w = document.getElementById('welcome');
    if (!w) {
        w = document.createElement('div');
        w.id = 'welcome';
        w.innerHTML = `
            <div id="welcome-icon">&gt;_</div>
            <div id="welcome-title">Ask ${escapeHtml(APP_NAME)}</div>
            <div id="welcome-sub">Ask a question — answers are grounded in the knowledge base.</div>
        `;
        messagesEl.appendChild(w);
    }
    w.style.display = 'flex';
}

function hideWelcome() {
    const w = document.getElementById('welcome');
    if (w) w.style.display = 'none';
}

function clearMessages() { messagesEl.innerHTML = ''; }

// Wrap tables for horizontal scroll, tint row groups, open links in new tabs.
function postProcessMessage(div) {
    div.querySelectorAll('table').forEach(table => {
        if (table.parentElement.classList.contains('table-scroll')) return;
        const wrapper = document.createElement('div');
        wrapper.className = 'table-scroll';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });

    div.querySelectorAll('table').forEach(table => {
        const rows = table.querySelectorAll('tbody tr');
        if (rows.length < 2) return;
        let groupIdx = 0, lastKey = null;
        rows.forEach(row => {
            const cell = row.cells[0];
            if (!cell) return;
            const text = cell.textContent.trim();
            const key = text.slice(0, 10);
            if (key !== lastKey) { if (lastKey !== null) groupIdx++; lastKey = key; }
            row.classList.add(`row-tint-${groupIdx % 4}`);
        });
    });

    div.querySelectorAll('a').forEach(a => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
}

function addMessageToDOM(role, content, filesRead = []) {
    hideWelcome();
    const div = document.createElement('div');
    div.className = `message ${role}`;

    if (role === 'assistant') {
        div.innerHTML = marked.parse(content);
        postProcessMessage(div);
        if (filesRead.length > 0) {
            const src = document.createElement('div');
            src.className = 'sources';
            const names = filesRead.map(f => f.split('/').pop().replace(/\.md$/, ''));
            src.textContent = `articles read: ${names.join(' · ')}`;
            div.appendChild(src);
        }
    } else {
        div.textContent = content;
    }

    messagesEl.appendChild(div);
    scrollToBottom();
    return div;
}

// === Search mode UI helpers ===
function showSearchWelcome() {
    const welcomeEl = document.getElementById('search-welcome');
    const outputEl  = document.getElementById('search-output');
    const loadingEl = document.getElementById('search-loading');
    if (welcomeEl) welcomeEl.style.display = 'flex';
    if (outputEl)  outputEl.style.display  = 'none';
    if (loadingEl) loadingEl.remove();
}

function hideSearchWelcome() {
    const welcomeEl = document.getElementById('search-welcome');
    if (welcomeEl) welcomeEl.style.display = 'none';
}

function showSearchLoading() {
    hideSearchWelcome();
    document.getElementById('search-loading')?.remove();
    const el = document.createElement('div');
    el.id = 'search-loading';
    el.className = 'search-loading';
    el.innerHTML = '<span></span><span></span><span></span>';
    const outputEl = document.getElementById('search-output');
    searchResultsEl.insertBefore(el, outputEl);
}

function hideSearchLoading() {
    document.getElementById('search-loading')?.remove();
}

async function runSearch(query) {
    sendBtn.disabled = true;
    showSearchLoading();

    try {
        const url = `/search?q=${encodeURIComponent(query)}&username=${encodeURIComponent(sessionUsername)}&password=${encodeURIComponent(sessionPassword)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        hideSearchLoading();
        renderSearchResults(data.results, query);
    } catch (err) {
        hideSearchLoading();
        hideSearchWelcome();
        const outputEl = document.getElementById('search-output');
        const metaEl   = document.getElementById('search-meta');
        const listEl   = document.getElementById('result-list');
        metaEl.textContent = 'Search error';
        listEl.innerHTML = `<div class="search-no-results">
            <div>${escapeHtml(err.message)}</div>
            <div class="search-no-results-hint">Try again or reload the page</div>
        </div>`;
        outputEl.style.display = 'block';
    }

    sendBtn.disabled = false;
    inputEl.focus();
}

function renderSearchResults(results, query) {
    hideSearchWelcome();
    const outputEl = document.getElementById('search-output');
    const metaEl   = document.getElementById('search-meta');
    const listEl   = document.getElementById('result-list');

    listEl.innerHTML = '';

    if (!results || results.length === 0) {
        metaEl.textContent = `No results for "${query}"`;
        listEl.innerHTML = `<div class="search-no-results">
            <div>No articles matched your search.</div>
            <div class="search-no-results-hint">Try shorter keywords or check the spelling</div>
        </div>`;
        outputEl.style.display = 'block';
        return;
    }

    const count = results.length;
    metaEl.textContent = `${count} ${count === 1 ? 'result' : 'results'} for "${query}"`;

    results.forEach((r, i) => {
        const a = document.createElement('a');
        a.className = 'result-card';
        a.href      = r.url || '#';
        a.style.animationDelay = `${i * 55}ms`;

        a.innerHTML = `
            <div class="result-card-top">
                <span class="result-card-title">${escapeHtml(r.title)}</span>
                ${r.category ? `<span class="result-card-category">${escapeHtml(r.category)}</span>` : ''}
            </div>
            <div class="result-card-summary">${escapeHtml(r.summary)}</div>
        `;

        if (r.url) {
            a.target = '_blank';
            a.rel    = 'noopener noreferrer';
        }

        listEl.appendChild(a);
    });

    outputEl.style.display = 'block';
}

// === Thinking animation (ask mode) ===
let thinkingInterval = null;

function showThinking() {
    const div = document.createElement('div');
    div.className = 'thinking';
    div.id = 'thinking-indicator';

    const word = document.createElement('span');
    word.className = 'thinking-word';
    word.textContent = thinkingWords[Math.floor(Math.random() * thinkingWords.length)];

    const dots = document.createElement('span');
    dots.className = 'thinking-dots';
    dots.innerHTML = '<span></span><span></span><span></span>';

    div.appendChild(word);
    div.appendChild(dots);
    messagesEl.appendChild(div);
    scrollToBottom();

    thinkingInterval = setInterval(() => {
        word.style.transition = 'opacity 0.4s ease';
        word.style.opacity = '0';
        setTimeout(() => {
            let next;
            do { next = thinkingWords[Math.floor(Math.random() * thinkingWords.length)]; }
            while (next === word.textContent && thinkingWords.length > 1);
            word.textContent = next;
            word.style.opacity = '1';
        }, 420);
    }, 7000);
}

function hideThinking() {
    if (thinkingInterval) { clearInterval(thinkingInterval); thinkingInterval = null; }
    document.getElementById('thinking-indicator')?.remove();
}

// === Login ===
async function login() {
    const un = usernameInput.value.trim();
    const pw = passwordInput.value.trim();
    if (!un || !pw) { loginError.textContent = 'Enter username and password'; return; }

    loginBtn.disabled = true;
    loginError.textContent = '';

    try {
        const res = await fetch('/verify-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: un, password: pw })
        });

        if (res.status === 401) {
            loginError.textContent = 'Wrong username or password';
            loginBtn.disabled = false;
            passwordInput.value = '';
            passwordInput.focus();
            return;
        }

        const data = await res.json();
        sessionUsername = un;
        sessionPassword = pw;
        sessionIsAdmin  = !!data.is_admin;
        localStorage.setItem('docurag_credentials', JSON.stringify({ username: un, password: pw }));
        showModeSelect();
    } catch {
        loginError.textContent = 'Could not connect to the server.';
        loginBtn.disabled = false;
    }
}

async function showModeSelect() {
    try {
        const res = await fetch(`/ask-status?username=${encodeURIComponent(sessionUsername)}&password=${encodeURIComponent(sessionPassword)}`);
        if (res.ok) {
            const data = await res.json();
            askRemaining  = data.remaining ?? 5;
            askDailyLimit = data.daily_limit ?? 5;
            const badge = document.getElementById('ask-count-badge');
            if (badge) badge.textContent = `${askRemaining}/${askDailyLimit} today`;
        }
    } catch { /* silent */ }

    if (loginBoxEl.style.display !== 'none') {
        loginBoxEl.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
        loginBoxEl.style.opacity = '0';
        loginBoxEl.style.transform = 'translateY(-8px)';
        setTimeout(showModeCards, 250);
    } else {
        showModeCards();
    }

    function showModeCards() {
        loginBoxEl.style.display = 'none';
        logoutBtn.style.display = '';
        if (sessionIsAdmin) dashboardBtn.style.display = '';
        modeSelectEl.style.display = 'flex';
        modeSelectEl.style.opacity = '0';
        modeSelectEl.style.transition = 'opacity 0.3s ease';
        requestAnimationFrame(() => { modeSelectEl.style.opacity = '1'; });
    }
}

document.getElementById('mode-card-search').addEventListener('click', () => enterApp('search'));
document.getElementById('mode-card-ask').addEventListener('click', () => enterApp('ask'));

function enterApp(mode) {
    currentMode = mode;
    syncContentDisplay();
    loginScreen.style.display = 'none';
    appEl.style.display = 'flex';
    updateModeUI();
    if (mode === 'ask') {
        fetchAskStatus();
        createNewChat();
    } else {
        createNewChat();
    }
}

loginBtn.addEventListener('click', login);
usernameInput.addEventListener('keydown', e => { if (e.key === 'Enter') passwordInput.focus(); });
passwordInput.addEventListener('keydown', e => { if (e.key === 'Enter') login(); });

// === Send ===
async function send() {
    const message = inputEl.value.trim();
    if (!message || sendBtn.disabled) return;

    if (currentMode === 'search') {
        inputEl.style.height = 'auto';

        if (!currentChatId) currentChatId = generateId();
        saveSearchQuery(currentChatId, message);
        topbarTitle.textContent = deriveTitle(message);
        renderChatList();

        await runSearch(message);
        return;
    }

    if (cooldownSeconds > 0) return;

    inputEl.value = '';
    inputEl.style.height = 'auto';
    sendBtn.disabled = true;

    addMessageToDOM('user', message);
    showThinking();

    const chatMessages  = getCurrentMessages();
    const historyForAPI = chatMessages.slice(-10).map(m => ({ role: m.role, content: m.content }));

    let assistantDiv    = null;
    let thinkingTexts   = [];
    let thinkingDiv     = null;
    let fullText        = '';
    let twTimer         = null;
    let pendingSources  = null;

    // Typewriter animation for the final answer, with correct styling from char 1.
    function runTypewriter(text) {
        let revealed = '';
        let queue    = text;
        assistantDiv = document.createElement('div');
        assistantDiv.className = 'message assistant streaming';
        messagesEl.appendChild(assistantDiv);

        twTimer = setInterval(() => {
            if (!queue) {
                clearInterval(twTimer);
                twTimer = null;
                assistantDiv.innerHTML = marked.parse(text);
                postProcessMessage(assistantDiv);
                assistantDiv.classList.remove('streaming');
                if (pendingSources) {
                    assistantDiv.appendChild(pendingSources);
                    pendingSources = null;
                }
                scrollToBottom();
                return;
            }
            const n = queue.length > 80 ? 6 : queue.length > 20 ? 2 : 1;
            revealed += queue.slice(0, n);
            queue = queue.slice(n);
            assistantDiv.innerHTML = marked.parse(revealed);
            postProcessMessage(assistantDiv);
            scrollToBottom();
        }, 16);
    }

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                history: historyForAPI,
                username: sessionUsername,
                password: sessionPassword,
                mode: currentMode
            })
        });

        if (!res.ok) {
            const err    = await res.json().catch(() => ({}));
            const detail = err.detail;

            if (res.status === 429 && detail?.reason === 'daily_limit') {
                hideThinking();
                sendBtn.disabled = false;
                addMessageToDOM('assistant', `❌ ${detail.message || 'Daily limit reached. Try again tomorrow, or switch to Search mode.'}`);
                return;
            }

            throw new Error(typeof detail === 'string' ? detail : `HTTP ${res.status}`);
        }

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                let event;
                try { event = JSON.parse(line.slice(6)); } catch { continue; }

                if (event.type === 'promote_to_thinking' || event.type === 'tool_activity') {
                    thinkingTexts.push(event.text);
                    if (!thinkingDiv) {
                        thinkingDiv = document.createElement('div');
                        thinkingDiv.className = 'thinking-text-block';
                        messagesEl.appendChild(thinkingDiv);
                    }
                    thinkingDiv.textContent = thinkingTexts.join('\n\n');
                    scrollToBottom();

                } else if (event.type === 'commit_stream') {
                    hideThinking();
                    fullText = event.text;
                    runTypewriter(event.text);

                } else if (event.type === 'thinking_clear') {
                    if (thinkingDiv && thinkingTexts.length > 0) {
                        const allText = thinkingTexts.join('\n\n');
                        thinkingDiv.innerHTML = '';
                        thinkingDiv.className = 'thinking-collapsed';

                        const toggle = document.createElement('button');
                        toggle.className = 'thinking-toggle';
                        toggle.innerHTML = '<span class="tw-dot">◌</span> Show process';
                        thinkingDiv.appendChild(toggle);

                        const body = document.createElement('div');
                        body.className = 'thinking-body';
                        body.textContent = allText;
                        body.hidden = true;
                        thinkingDiv.appendChild(body);

                        toggle.addEventListener('click', () => {
                            const expand = body.hidden;
                            body.hidden = !expand;
                            toggle.innerHTML = `<span class="tw-dot">${expand ? '◉' : '◌'}</span> ${expand ? 'Hide' : 'Show'} process`;
                        });
                    }
                    thinkingTexts = [];
                    thinkingDiv   = null;
                    hideThinking();

                } else if (event.type === 'done') {
                    if (event.files_read?.length > 0) {
                        const src = document.createElement('div');
                        src.className = 'sources';
                        const names = event.files_read.map(f => f.split('/').pop().replace(/\.md$/, ''));
                        src.textContent = `articles read: ${names.join(' · ')}`;
                        if (twTimer) {
                            pendingSources = src;
                        } else if (assistantDiv) {
                            assistantDiv.appendChild(src);
                        }
                    }
                    const msgs  = getCurrentMessages();
                    msgs.push({ role: 'user', content: message });
                    msgs.push({ role: 'assistant', content: fullText, filesRead: event.files_read || [] });
                    const chat  = getChat(currentChatId);
                    const title = (!chat || chat.title === 'New chat') ? deriveTitle(message) : chat.title;
                    saveChatMessages(currentChatId, msgs, title);
                    topbarTitle.textContent = title || 'New chat';
                    renderChatList();

                    if (currentMode === 'ask') {
                        fetchAskStatus();
                    }

                } else if (event.type === 'error') {
                    throw new Error(event.message || 'Unknown error');
                }
            }
        }

        if (!assistantDiv) {
            hideThinking();
            addMessageToDOM('assistant', fullText || 'No answer received.');
        }

    } catch (err) {
        if (twTimer) { clearInterval(twTimer); twTimer = null; }
        hideThinking();
        if (assistantDiv) {
            assistantDiv.textContent = `Error: ${err.message}`;
        } else {
            addMessageToDOM('assistant', `Error: ${err.message}`);
        }
    }

    sendBtn.disabled = false;
    inputEl.focus();
}

// === Event listeners ===
sendBtn.addEventListener('click', send);

inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});

inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + 'px';
    if (currentMode === 'search' && !inputEl.value.trim()) {
        showSearchWelcome();
    }
});

newChatBtn.addEventListener('click', createNewChat);

deleteChatBtn.addEventListener('click', () => {
    if (!currentChatId) return;
    deleteChat(currentChatId);
    const chats  = getChats();
    const sorted = Object.values(chats).sort((a, b) => (b.updated || b.created) - (a.updated || a.created));
    if (sorted.length > 0) { loadChat(sorted[0].id); } else { createNewChat(); }
});

const style = document.createElement('style');
style.textContent = '.thinking-word { transition: opacity 0.2s ease; }';
document.head.appendChild(style);

// === Dashboard ===
let dashChart = null;

dashboardBtn && dashboardBtn.addEventListener('click', openDashboard);
dashboardScreen && dashboardScreen.querySelector('#dashboard-close-btn') &&
    dashboardScreen.querySelector('#dashboard-close-btn').addEventListener('click', closeDashboard);

dashboardScreen && dashboardScreen.querySelectorAll('.dash-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        dashboardScreen.querySelectorAll('.dash-tab-btn').forEach(b => b.classList.remove('active'));
        dashboardScreen.querySelectorAll('.dash-panel').forEach(p => p.style.display = 'none');
        btn.classList.add('active');
        const panel = dashboardScreen.querySelector(`#dash-panel-${btn.dataset.tab}`);
        if (panel) panel.style.display = '';
    });
});

function openDashboard() {
    dashboardScreen.style.display = 'flex';
    loadDashboard();
}
function closeDashboard() {
    dashboardScreen.style.display = 'none';
}

async function loadDashboard() {
    document.getElementById('dash-stats').innerHTML =
        '<div style="color:var(--text-tertiary);font-family:var(--font-mono);font-size:12px">Loading...</div>';
    try {
        const res = await fetch(
            `/admin/dashboard-data?admin_username=${encodeURIComponent(sessionUsername)}&admin_password=${encodeURIComponent(sessionPassword)}&days=30`
        );
        if (!res.ok) { document.getElementById('dash-stats').textContent = 'Access denied.'; return; }
        renderDashboard(await res.json());
    } catch { document.getElementById('dash-stats').textContent = 'Could not load data.'; }
}

function renderDashboard(data) {
    const totals = data.totals || {};
    const searches = totals['search'] || 0;
    const asks     = totals['ask']    || 0;
    const tokens   = data.total_tokens || 0;

    document.getElementById('dash-stats').innerHTML = `
        <div class="dash-stat"><div class="dash-stat-value">${searches}</div><div class="dash-stat-label">Searches</div></div>
        <div class="dash-stat"><div class="dash-stat-value">${asks}</div><div class="dash-stat-label">Questions</div></div>
        <div class="dash-stat"><div class="dash-stat-value">${tokens >= 1000 ? (tokens/1000).toFixed(1)+'K' : tokens}</div><div class="dash-stat-label">Tokens used</div></div>
    `;

    renderDashChart(data.daily || []);
    renderSearchTable(data.searches || []);
    renderAskTable(data.asks || []);
}

function renderDashChart(daily) {
    const daySet = [...new Set(daily.map(d => d.day))].sort();
    const get = (type) => daySet.map(d => { const e = daily.find(x => x.day === d && x.event_type === type); return e ? e.count : 0; });

    const ctx = document.getElementById('dash-chart').getContext('2d');
    if (dashChart) dashChart.destroy();
    dashChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: daySet,
            datasets: [
                { label: 'Searches',  data: get('search'), backgroundColor: 'rgba(93,184,122,0.55)', borderColor: '#5db87a', borderWidth: 1 },
                { label: 'Questions', data: get('ask'),    backgroundColor: 'rgba(201,100,66,0.55)', borderColor: '#c96442', borderWidth: 1 },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#888', font: { family: 'JetBrains Mono', size: 10 }, boxWidth: 10 } } },
            scales: {
                x: { ticks: { color: '#555', font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 45 }, grid: { color: '#222' } },
                y: { beginAtZero: true, ticks: { color: '#555', font: { family: 'JetBrains Mono', size: 10 }, precision: 0 }, grid: { color: '#222' } }
            }
        }
    });
}

function fmtTs(ts) {
    if (!ts) return '—';
    try { return new Date(ts.endsWith('Z') ? ts : ts + 'Z').toLocaleString('en-GB', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' }); }
    catch { return ts.slice(0, 16); }
}

function renderSearchTable(rows) {
    const tbody = rows.map(r => `<tr>
        <td class="mono-dim">${fmtTs(r.timestamp)}</td>
        <td>${escapeHtml(r.username || '—')}</td>
        <td>${escapeHtml(r.query || '—')}</td>
    </tr>`).join('') || '<tr><td colspan="3" style="color:var(--text-tertiary);text-align:center;padding:20px">No searches yet</td></tr>';
    document.getElementById('dash-panel-searches').innerHTML = `
        <table class="dash-table">
            <thead><tr><th>Time</th><th>User</th><th>Search</th></tr></thead>
            <tbody>${tbody}</tbody>
        </table>`;
}

function renderAskTable(rows) {
    const panel = document.getElementById('dash-panel-asks');
    if (!rows.length) {
        panel.innerHTML = '<p style="color:var(--text-tertiary);font-family:var(--font-mono);font-size:12px;padding:20px 0;text-align:center">No questions yet</p>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'dash-table';
    table.innerHTML = `<thead><tr>
        <th>Time</th><th>User</th><th>Question</th><th>Answer</th>
        <th style="text-align:right">Tokens in</th><th style="text-align:right">Tokens out</th>
    </tr></thead>`;
    const tbody = document.createElement('tbody');

    rows.forEach(r => {
        const hasMore = (r.response || '').length > 0;
        const preview = (r.response || '').slice(0, 120) + ((r.response || '').length > 120 ? '…' : '');

        const row = document.createElement('tr');
        row.style.cursor = hasMore ? 'pointer' : '';
        row.innerHTML = `
            <td class="mono-dim">${fmtTs(r.timestamp)}</td>
            <td>${escapeHtml(r.username || '—')}</td>
            <td class="wrap">${escapeHtml((r.query || '').slice(0, 120))}${(r.query||'').length > 120 ? '…' : ''}</td>
            <td class="wrap">${escapeHtml(preview)}</td>
            <td class="mono-dim" style="text-align:right">${r.tokens_input || 0}</td>
            <td class="mono-dim" style="text-align:right">${r.tokens_output || 0}</td>
        `;

        const expandRow = document.createElement('tr');
        expandRow.className = 'dash-expand-row';
        expandRow.style.display = 'none';
        expandRow.innerHTML = `<td colspan="6" class="dash-expand-cell">${escapeHtml(r.response || '')}</td>`;

        if (hasMore) {
            row.addEventListener('click', () => {
                const open = expandRow.style.display !== 'none';
                expandRow.style.display = open ? 'none' : '';
                row.classList.toggle('dash-row-active', !open);
            });
        }

        tbody.appendChild(row);
        tbody.appendChild(expandRow);
    });

    table.appendChild(tbody);
    panel.innerHTML = '';
    panel.appendChild(table);
}

// === Logout ===
function logout() {
    localStorage.removeItem('docurag_credentials');
    sessionUsername = '';
    sessionPassword = '';
    sessionIsAdmin = false;
    logoutBtn.style.display = 'none';
    dashboardBtn.style.display = 'none';
    modeSelectEl.style.display = 'none';
    loginBoxEl.style.opacity = '0';
    loginBoxEl.style.transform = 'none';
    loginBoxEl.style.transition = 'none';
    loginBoxEl.style.display = 'flex';
    requestAnimationFrame(() => {
        loginBoxEl.style.transition = 'opacity 0.25s ease';
        loginBoxEl.style.opacity = '1';
    });
    usernameInput.value = '';
    passwordInput.value = '';
    usernameInput.focus();
}
logoutBtn && logoutBtn.addEventListener('click', logout);

// === Auto-login on page load ===
function showLoginBox() {
    loginBoxEl.style.opacity = '0';
    loginBoxEl.style.display = 'flex';
    requestAnimationFrame(() => {
        loginBoxEl.style.transition = 'opacity 0.3s ease';
        loginBoxEl.style.opacity = '1';
    });
}

(async function tryAutoLogin() {
    const stored = localStorage.getItem('docurag_credentials');
    if (!stored) { showLoginBox(); return; }
    try {
        const { username, password } = JSON.parse(stored);
        if (!username || !password) { showLoginBox(); return; }
        const res = await fetch('/verify-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (res.ok) {
            const data = await res.json();
            sessionUsername = username;
            sessionPassword = password;
            sessionIsAdmin  = !!data.is_admin;
            showModeSelect();
        } else {
            localStorage.removeItem('docurag_credentials');
            showLoginBox();
        }
    } catch { showLoginBox(); }
})();

// === Branding + animated logo ===
// Renders APP_NAME as individual interactive characters with a drop-in
// animation and a ripple effect driven by typing in the login fields.
const Logo = (function () {
    const el      = document.getElementById('ascii-art');
    const tagline = document.getElementById('login-tagline');
    const pwInput = document.getElementById('password-input');
    const unInput = document.getElementById('username-input');

    let chars = [], ripples = [], rafId = null, interactive = false;

    function build(text) {
        if (!el) return;
        stop();
        el.innerHTML = '';
        tagline.classList.remove('show');
        tagline.style.opacity = '0';
        el.classList.remove('live');
        chars = []; ripples = [];

        const spans = [];
        [...text].forEach(ch => {
            const span = document.createElement('span');
            span.className = 'ch';
            span.textContent = ch === ' ' ? ' ' : ch;
            const fx = (Math.random() * 40 - 20).toFixed(0);
            const fr = (Math.random() * 20 - 10).toFixed(1);
            span.style.setProperty('--fx', fx + 'px');
            span.style.setProperty('--fr', fr + 'deg');
            spans.push({ span, isSpace: ch === ' ' });
            el.appendChild(span);
        });

        spans.forEach(s => {
            if (s.isSpace) { s.span.style.opacity = '1'; return; }
            s.span.classList.add('dropping');
            s.span.style.animationDelay = (Math.random() * 0.15).toFixed(3) + 's';
        });

        setTimeout(() => {
            tagline.classList.add('show');
            startInteractive(spans);
        }, 1400);
    }

    function startInteractive(spans) {
        spans.forEach(s => {
            if (s.isSpace) return;
            s.span.classList.remove('dropping');
            s.span.style.animationName = 'none';
            s.span.style.animationDelay = '';
        });
        el.classList.add('live');
        requestAnimationFrame(() => {
            const rect = el.getBoundingClientRect();
            chars = spans.filter(s => !s.isSpace).map(s => {
                const r = s.span.getBoundingClientRect();
                return { span: s.span, x: r.left - rect.left + r.width / 2, y: r.top - rect.top + r.height / 2, cx: 0, cy: 0 };
            });
            interactive = true;
            loop();
        });
    }

    function stop() {
        interactive = false;
        if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
        chars = []; ripples = [];
    }

    function triggerRipple() {
        if (!chars.length) return;
        const rect = el.getBoundingClientRect();
        ripples.push({
            x: Math.random() * rect.width,
            y: rect.height / 2 + (Math.random() - 0.5) * rect.height * 0.6,
            born: performance.now(), life: 900
        });
    }

    function loop() {
        if (!interactive) { rafId = null; return; }
        const now = performance.now();
        ripples = ripples.filter(r => now - r.born < r.life);
        for (let i = 0; i < chars.length; i++) {
            const c = chars[i];
            let tx = 0, ty = 0;
            for (let j = 0; j < ripples.length; j++) {
                const r = ripples[j];
                const age  = (now - r.born) / r.life;
                const ring = age * 180;
                const dx   = c.x - r.x, dy = c.y - r.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const off  = Math.abs(dist - ring);
                if (off < 35 && dist > 0.1) {
                    const push = (1 - off / 35) ** 2 * (1 - age) * 6;
                    tx += (dx / dist) * push;
                    ty += (dy / dist) * push;
                }
            }
            c.cx += (tx - c.cx) * 0.25;
            c.cy += (ty - c.cy) * 0.25;
            c.span.style.setProperty('--rx', c.cx.toFixed(2) + 'px');
            c.span.style.setProperty('--ry', c.cy.toFixed(2) + 'px');
        }
        rafId = requestAnimationFrame(loop);
    }

    pwInput && pwInput.addEventListener('input', () => triggerRipple());
    unInput && unInput.addEventListener('input', () => { if (Math.random() < 0.6) triggerRipple(); });

    return { build };
}());

// Fetch branding, then build the logo once fonts are ready.
(async function initBranding() {
    try {
        const res = await fetch('/app-config');
        if (res.ok) {
            const cfg = await res.json();
            if (cfg.app_name) APP_NAME = cfg.app_name;
            if (cfg.tagline) {
                const t = document.getElementById('login-tagline');
                if (t) t.textContent = cfg.tagline;
            }
            document.title = APP_NAME;
        }
    } catch { /* keep defaults */ }

    const ready = document.fonts ? document.fonts.ready : Promise.resolve();
    ready.then(() => Logo.build(APP_NAME));
})();
