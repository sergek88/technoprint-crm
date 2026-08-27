// ═══════════════════════════════════════════════════════════════════
// offline.js — оффлайн-режим ТехноПринт CRM
// • Очередь записей (IndexedDB outbox) с временными отрицательными id
// • Автосинхронизация при восстановлении связи (по порядку, с подстановкой temp→real id)
// • Устойчивость к частичной синхронизации (persistent idmap) и к потере ответа (X-Op-Id идемпотентность)
// • Оптимистичный UI — патч кэша карточек (тот же кэш, что наполняет Service Worker)
// ═══════════════════════════════════════════════════════════════════
window.TP = (function () {
    const API = location.origin;
    const TOKEN_KEY = 'tp_token';
    const API_CACHE = 'tp-api';
    const DB_NAME = 'tp-offline', DB_VER = 1;
    const STORE_OUT = 'outbox', STORE_MAP = 'idmap';

    let _db = null;
    let _pending = 0, _syncing = false, _failed = [];
    let _map = {};   // idmap в памяти: temp(отрицательный) → real id (персистится в IndexedDB)
    const _listeners = [];

    function emit() { _listeners.forEach(fn => { try { fn(state()); } catch (e) {} }); }
    function state() { return { online: navigator.onLine, pending: _pending, syncing: _syncing, failed: _failed.slice() }; }

    // ───────── IndexedDB ─────────
    function openDB() {
        return new Promise((resolve, reject) => {
            if (_db) return resolve(_db);
            const req = indexedDB.open(DB_NAME, DB_VER);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE_OUT)) db.createObjectStore(STORE_OUT, { keyPath: 'seq', autoIncrement: true });
                if (!db.objectStoreNames.contains(STORE_MAP)) db.createObjectStore(STORE_MAP, { keyPath: 'temp' });
            };
            req.onsuccess = () => { _db = req.result; resolve(_db); };
            req.onerror = () => reject(req.error);
        });
    }
    async function tx(store, mode, fn) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const t = db.transaction(store, mode);
            const s = t.objectStore(store);
            let out;
            const r = fn(s);
            if (r) r.onsuccess = () => { out = r.result; };
            t.oncomplete = () => resolve(out);
            t.onerror = () => reject(t.error);
            t.onabort = () => reject(t.error);
        });
    }
    const outAdd = (op) => tx(STORE_OUT, 'readwrite', s => s.add(op));
    const outAll = () => tx(STORE_OUT, 'readonly', s => s.getAll());
    const outDel = (seq) => tx(STORE_OUT, 'readwrite', s => s.delete(seq));
    const outPut = (op) => tx(STORE_OUT, 'readwrite', s => s.put(op));
    const outCount = () => tx(STORE_OUT, 'readonly', s => s.count());
    const mapAll = () => tx(STORE_MAP, 'readonly', s => s.getAll());
    const mapPut = (temp, real) => tx(STORE_MAP, 'readwrite', s => s.put({ temp, real }));

    // ───────── helpers ─────────
    function uuid() { return 'op-' + Math.random().toString(36).slice(2) + '-' + Math.random().toString(36).slice(2); }
    function nextTempId() {
        let n = Number(localStorage.getItem('tp_tempseq') || '0') - 1;
        localStorage.setItem('tp_tempseq', String(n));
        return n; // отрицательное
    }
    const isTemp = (v) => typeof v === 'number' && v < 0;
    function resolveUrl(url, map) {
        return url.replace(/-\d+/g, m => { const t = Number(m); return (map[t] != null) ? String(map[t]) : m; });
    }
    const urlHasTemp = (url) => /\/-\d+(\/|$|\?)/.test(url);
    // temp-id в телах встречаются ТОЛЬКО в полях-ссылках (массивы id выписываемых позиций).
    // Цены/кол-во не трогаем — отрицательная цена не должна считаться temp-id или подменяться.
    const ID_FIELDS = ['refill_ids', 'work_ids', 'sale_ids'];
    function resolveBody(obj, map) {
        if (!obj || typeof obj !== 'object') return obj;
        const o = { ...obj };
        for (const f of ID_FIELDS) {
            if (Array.isArray(o[f])) o[f] = o[f].map(v => (isTemp(v) && map[v] != null) ? map[v] : v);
        }
        return o;
    }
    function bodyHasTemp(obj) {
        if (!obj || typeof obj !== 'object') return false;
        return ID_FIELDS.some(f => Array.isArray(obj[f]) && obj[f].some(isTemp));
    }
    // ссылается ли операция на конкретный temp-id (как producer, в URL или в полях-ссылках тела)
    function opRefs(op, tempId) {
        if (op.produces === tempId) return true;
        if (new RegExp('/' + tempId + '(/|$|\\?)').test(op.url)) return true;
        if (op.body) { try { const b = JSON.parse(op.body); return ID_FIELDS.some(f => Array.isArray(b[f]) && b[f].includes(tempId)); } catch (e) {} }
        return false;
    }
    function authHeaders(opId) {
        const h = { 'Content-Type': 'application/json' };
        const t = localStorage.getItem(TOKEN_KEY);
        if (t) h['Authorization'] = 'Bearer ' + t;
        if (opId) h['X-Op-Id'] = opId;
        return h;
    }
    // fetch с таймаутом — при «зависшем TLS» (ТСПУ) не виснем, а уходим в офлайн/кэш
    function fetchT(url, opts, ms) {
        return new Promise((resolve, reject) => {
            const t = setTimeout(() => reject(new TypeError('timeout')), ms || 9000);
            fetch(url, opts).then(r => { clearTimeout(t); resolve(r); }, e => { clearTimeout(t); reject(e); });
        });
    }
    function pushFailed(item) {
        if (_failed.some(f => f.url === item.url && f.detail === item.detail)) return;
        _failed.push(item);
        if (_failed.length > 50) _failed = _failed.slice(-50);
    }

    // ───────── cache (тот же, что у Service Worker) ─────────
    async function cacheGet(path) {
        try {
            const c = await caches.open(API_CACHE);
            const res = await c.match(API + path);
            if (!res) return null;
            return await res.json();
        } catch (e) { return null; }
    }
    async function cachePut(path, obj) {
        try {
            const c = await caches.open(API_CACHE);
            await c.put(API + path, new Response(JSON.stringify(obj), { headers: { 'Content-Type': 'application/json' } }));
        } catch (e) {}
    }

    const todayStr = () => new Date().toISOString().slice(0, 10);

    // ───────── построение строк документа из карточки ─────────
    function refillItem(r) {
        let model = (r.model || ''); if (model.toLowerCase().startsWith('картридж')) model = model.slice('картридж'.length).trim();
        let base = r.spec_type || 'Заправка'; if (!base.toLowerCase().includes('картридж')) base += ' картриджа';
        let name = (base + ' ' + model).trim(); if (r.barcode) name += ' (' + r.barcode + ')';
        const price = Number(r.price) || 0;
        return { id: nextTempId(), kind: 'work', name, unit: 'шт', qty: 1, price, total: price };
    }
    function workItem(w) {
        const name = (w.title || '') + (w.device_label ? ' — ' + w.device_label : '');
        const price = Number(w.price) || 0;
        return { id: nextTempId(), kind: 'repair', name, unit: 'шт', qty: 1, price, total: price };
    }
    function saleItem(s) {
        const qty = Number(s.qty) || 1, price = Number(s.price) || 0;
        return { id: nextTempId(), kind: 'goods', name: s.name, unit: 'шт', qty, price, total: qty * price };
    }

    // пометить позиции выписанными в карточке + пересчитать unbilled
    function markBilled(card, listKey, ids) {
        (card[listKey] || []).forEach(x => { if (ids.includes(x.id)) x.is_billed = true; });
        card.unbilled = (card[listKey] || []).filter(x => !x.is_billed).length;
    }

    // ───────── оптимистичный патч кэша по типу операции ─────────
    async function applyOptimistic(meta, body, tempId, resp) {
        if (!meta || !meta.kind) return;
        const k = meta.kind;
        const cartPath = (id) => '/api/cartridges/client/' + id;
        const workPath = (id) => '/api/works/client/' + id;
        const goodsPath = (id) => '/api/goods/client/' + id;
        const docsPath = (id) => '/api/documents?client_id=' + id;

        // refill-операции патчат И карточку клиента, И карточку картриджа (если открыта)
        const refillPaths = [cartPath(meta.clientId), meta.cartCardId ? ('/api/cartridges/card/' + meta.cartCardId) : null].filter(Boolean);
        const eachRefillCard = async (mutate) => {
            for (const p of refillPaths) {
                const card = await cacheGet(p); if (!card) continue;
                mutate(card);
                card.unbilled = (card.refills || []).filter(r => !r.is_billed).length;
                await cachePut(p, card);
            }
        };

        if (k === 'refill_add') {
            await eachRefillCard(card => (card.refills = card.refills || []).unshift({
                id: tempId, cartridge_id: body.__cid, barcode: meta.barcode || '', model: meta.model || '',
                date: (body.date || todayStr()), worker: meta.workerName || null, defect: null,
                worker_id: body.worker_id || null, defect_id: body.defect_id || null,
                spec_type: meta.specName || 'Заправка', spec_type_id: body.spec_type_id || 1,
                advice: body.advice || null, remark: body.remark || null,
                price: (body.price == null ? null : Number(body.price)), is_billed: false, _offline: true,
            }));
        } else if (k === 'refill_edit') {
            await eachRefillCard(card => {
                const r = (card.refills || []).find(x => x.id === meta.id); if (!r) return;
                if (body.date) r.date = body.date;
                if (body.spec_type_id != null) { r.spec_type_id = body.spec_type_id; r.spec_type = meta.specName || r.spec_type; }
                r.worker_id = body.worker_id || null; r.worker = meta.workerName || null;
                r.remark = body.remark || null; r.price = (body.price == null ? null : Number(body.price)); r._offline = true;
            });
        } else if (k === 'refill_del') {
            await eachRefillCard(card => { card.refills = (card.refills || []).filter(x => x.id !== meta.id); });
        } else if (k === 'cart_add') {
            const card = await cacheGet(cartPath(meta.clientId)); if (!card) return;
            (card.cartridges = card.cartridges || []).push({ id: tempId, barcode: meta.barcode || 'черновик', model: meta.model || '', model_id: meta.model_id || null, last_price: null, _offline: true });
            await cachePut(cartPath(meta.clientId), card);
        } else if (k === 'work_add') {
            const card = await cacheGet(workPath(meta.clientId)); if (!card) return;
            (card.jobs = card.jobs || []).unshift({
                id: tempId, title: body.title, device_label: body.device_label || null, date: body.date || todayStr(),
                worker: meta.workerName || null, worker_id: body.worker_id || null,
                price: (body.price == null ? null : Number(body.price)), remark: body.remark || null, is_billed: false, _offline: true,
            });
            card.unbilled = (card.jobs || []).filter(j => !j.is_billed).length;
            await cachePut(workPath(meta.clientId), card);
        } else if (k === 'work_edit') {
            const card = await cacheGet(workPath(meta.clientId)); if (!card) return;
            const w = (card.jobs || []).find(x => x.id === meta.id); if (!w) return;
            w.title = body.title; w.device_label = body.device_label || null; if (body.date) w.date = body.date;
            w.worker_id = body.worker_id || null; w.worker = meta.workerName || null;
            w.price = (body.price == null ? null : Number(body.price)); w.remark = body.remark || null; w._offline = true;
            await cachePut(workPath(meta.clientId), card);
        } else if (k === 'work_del') {
            const card = await cacheGet(workPath(meta.clientId)); if (!card) return;
            card.jobs = (card.jobs || []).filter(x => x.id !== meta.id);
            card.unbilled = (card.jobs || []).filter(j => !j.is_billed).length;
            await cachePut(workPath(meta.clientId), card);
        } else if (k === 'sale_add') {
            const card = await cacheGet(goodsPath(meta.clientId)); if (!card) return;
            (card.sales = card.sales || []).unshift({
                id: tempId, name: body.name, good_id: body.good_id || null, qty: Number(body.qty) || 1,
                price: (body.price == null ? null : Number(body.price)), date: body.date || todayStr(),
                remark: body.remark || null, is_billed: false, _offline: true,
            });
            card.unbilled = (card.sales || []).filter(s => !s.is_billed).length;
            await cachePut(goodsPath(meta.clientId), card);
        } else if (k === 'sale_edit') {
            const card = await cacheGet(goodsPath(meta.clientId)); if (!card) return;
            const s = (card.sales || []).find(x => x.id === meta.id); if (!s) return;
            s.name = body.name; s.qty = Number(body.qty) || 1; s.price = (body.price == null ? null : Number(body.price));
            if (body.date) s.date = body.date; s.remark = body.remark || null; s._offline = true;
            await cachePut(goodsPath(meta.clientId), card);
        } else if (k === 'sale_del') {
            const card = await cacheGet(goodsPath(meta.clientId)); if (!card) return;
            card.sales = (card.sales || []).filter(x => x.id !== meta.id);
            card.unbilled = (card.sales || []).filter(s => !s.is_billed).length;
            await cachePut(goodsPath(meta.clientId), card);
        } else if (k === 'cash' || k === 'invoice') {
            // пометить позиции выписанными в нужной карточке
            const cp = meta.client === 'work' ? workPath(meta.clientId) : meta.client === 'goods' ? goodsPath(meta.clientId) : cartPath(meta.clientId);
            const listKey = meta.client === 'work' ? 'jobs' : meta.client === 'goods' ? 'sales' : 'refills';
            const card = await cacheGet(cp);
            let items = [];
            if (card) {
                const chosen = (card[listKey] || []).filter(x => meta.ids.includes(x.id));
                items = chosen.map(meta.client === 'work' ? workItem : meta.client === 'goods' ? saleItem : refillItem);
                markBilled(card, listKey, meta.ids);
                await cachePut(cp, card);
            }
            if (k === 'invoice') {
                const total = items.reduce((sm, it) => sm + (Number(it.total) || 0), 0);
                let creq = {};
                const cl = (await cacheGet('/api/clients') || []).find(c => c.id === meta.clientId);
                if (cl) creq = { full_name: cl.full_name, inn: cl.inn, kpp: cl.kpp, address: cl.address };
                const doc = {
                    id: tempId, doc_type: 'invoice', type_label: 'Счёт на оплату', number: null,
                    date: (body.date || todayStr()), client_id: meta.clientId, client: (card && card.client) || '',
                    total, is_paid: false, parent_id: null, order_id: null, note: null,
                    items, client_req: creq, children: [], _offline: true,
                };
                await cachePut('/api/documents/' + tempId, doc);
                const list = (await cacheGet(docsPath(meta.clientId))) || [];
                list.unshift({ id: tempId, doc_type: 'invoice', type_label: 'Счёт на оплату', number: null, date: doc.date, total, is_paid: false, order_id: null, _offline: true });
                await cachePut(docsPath(meta.clientId), list);
            }
        } else if (k === 'derive') {
            // акт/накладная/чек «на основании» счёта — копия позиций родителя
            const labels = { act: 'Акт выполненных работ', waybill: 'Товарная накладная', receipt: 'Товарный чек' };
            const parent = await cacheGet('/api/documents/' + meta.parentId);
            const items = parent ? (parent.items || []).map(it => ({ ...it, id: nextTempId() })) : [];
            const total = parent ? parent.total : items.reduce((s, it) => s + (Number(it.total) || 0), 0);
            const doc = {
                id: tempId, doc_type: meta.doc_type, type_label: labels[meta.doc_type] || meta.doc_type,
                number: null, date: (body.date || todayStr()),
                client_id: meta.clientId, client: parent ? parent.client : '',
                total, is_paid: parent ? parent.is_paid : false, parent_id: meta.parentId, order_id: null, note: null,
                items, client_req: parent ? (parent.client_req || {}) : {}, children: [], _offline: true,
            };
            await cachePut('/api/documents/' + tempId, doc);
            if (parent) {
                (parent.children = parent.children || []).push({ id: tempId, doc_type: meta.doc_type, type_label: doc.type_label, number: null });
                await cachePut('/api/documents/' + meta.parentId, parent);
            }
            const list = (await cacheGet('/api/documents?client_id=' + meta.clientId)) || [];
            list.unshift({ id: tempId, doc_type: meta.doc_type, type_label: doc.type_label, number: null, date: doc.date, total, is_paid: doc.is_paid, order_id: null, _offline: true });
            await cachePut('/api/documents?client_id=' + meta.clientId, list);
        }
    }

    // ───────── публичное: записать (онлайн-попытка или очередь) ─────────
    // opts: { method, body(JSON string), offline: {kind, ...meta} }
    async function write(path, opts) {
        const method = (opts.method || 'POST').toUpperCase();
        const opId = uuid();
        // подставить уже известные temp→real (idmap) — на случай действий с офлайн-сущностью
        const rurl = resolveUrl(path, _map);
        const rbodyObj = opts.body ? resolveBody(JSON.parse(opts.body), _map) : null;
        const stillTemp = urlHasTemp(rurl) || (rbodyObj && bodyHasTemp(rbodyObj));
        // онлайн-путь только если очередь ПУСТА — иначе нарушим FIFO-порядок по этой же сущности
        const queueEmpty = (await outCount()) === 0;
        if (navigator.onLine && !stillTemp && queueEmpty) {
            try {
                const res = await fetchT(API + rurl, { method, headers: authHeaders(opId), body: rbodyObj != null ? JSON.stringify(rbodyObj) : opts.body });
                if (res.status === 401) { localStorage.removeItem(TOKEN_KEY); location.href = '/login.html'; return null; }
                if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || 'Ошибка сервера'); }
                flush();   // онлайн прошло — заодно дослать очередь
                if (res.status === 204) return null;
                return await res.json().catch(() => ({}));
            } catch (e) {
                if (!isNetworkError(e)) throw e;   // настоящая ошибка сервера — наверх
                // сеть отвалилась/зависла → в очередь
            }
        }
        return await queue(path, opts, opId);
    }

    function isNetworkError(e) {
        return e instanceof TypeError || /Failed to fetch|NetworkError|Load failed|timeout/i.test(e && e.message || '');
    }

    async function queue(path, opts, opId) {
        const meta = opts.offline || null;
        const body = opts.body ? JSON.parse(opts.body) : null;

        // Удаление temp-сущности ДО синхронизации → отменяем парную add-операцию (и все ссылки на неё)
        // локально, на сервер ничего не шлём.
        if (meta && /_del$/.test(meta.kind) && isTemp(meta.id)) {
            let removed = 0;
            try {
                for (const o of await outAll()) { if (opRefs(o, meta.id)) { await outDel(o.seq); removed++; } }
            } catch (e) {}
            if (removed > 0 || _map[meta.id] == null) {
                // отменили очередь по этой temp-сущности (или это фантом без producer/маппинга) → просто убрать из кэша
                try { await applyOptimistic(meta, body || {}, null, null); } catch (e) {}
                _pending = await outCount(); emit();
                return { ok: true, _offline: true, cancelled: true };
            }
            // _map[meta.id] есть → add уже синхронизирован, это реальное удаление: падаем в обычную очередь (URL резолвится при flush)
        }

        // finalize одного и того же документа не дублируем в очереди (сервер всё равно идемпотентен)
        if (meta && meta.kind === 'finalize') {
            try {
                const ops = await outAll();
                if (ops.some(o => o.url === path && o.method === method0(opts))) return { ok: true, already: true, _offline: true };
            } catch (e) {}
        }

        const creates = meta && ['refill_add', 'work_add', 'sale_add', 'cart_add', 'invoice', 'derive'].includes(meta.kind);
        const tempId = creates ? nextTempId() : null;
        // для add-операций сохраним cartridge_id в body (для патча карточки)
        if (meta && meta.kind === 'refill_add' && body) body.__cid = meta.cartridgeId;
        const op = { method: method0(opts), url: path, body: body ? JSON.stringify(stripPrivate(body)) : null, opId, produces: tempId, ts: Date.now() };
        await outAdd(op);
        _pending = await outCount(); emit();
        try { await applyOptimistic(meta, body || {}, tempId, null); } catch (e) { console.warn('optimistic', e); }
        if (navigator.onLine) flush();   // онлайн, но писали в очередь (был backlog) → сразу дослать
        return synthetic(meta, tempId, body || {});
    }
    const method0 = (opts) => (opts.method || 'POST').toUpperCase();
    function stripPrivate(body) { const b = { ...body }; delete b.__cid; return b; }

    function synthetic(meta, tempId, body) {
        const k = meta && meta.kind;
        if (k === 'cash') {
            // приблизительный итог из тела не знаем — посчитан в UI; вернём ok
            return { ok: true, order_id: tempId, _offline: true };
        }
        if (k === 'invoice' || k === 'derive' || k === 'refill_add' || k === 'work_add' || k === 'sale_add') return { ok: true, id: tempId, _offline: true };
        if (k === 'cart_add') return { ok: true, id: tempId, barcode: (meta && meta.barcode) || 'черновик', _offline: true };
        if (k === 'finalize') return { ok: true, already: false, _offline: true };
        return { ok: true, _offline: true };
    }

    // ───────── синхронизация очереди ─────────
    async function flush() {
        if (_syncing || !navigator.onLine) return;
        if ((await outCount()) === 0) return;
        _syncing = true; emit();
        const resolved = {};   // temp→real, разрешённые в этом проходе (для afterSync)
        try {
            const ops = await outAll(); // по возрастанию seq
            for (const op of ops) {
                const url = resolveUrl(op.url, _map);
                const bodyObj = op.body ? resolveBody(JSON.parse(op.body), _map) : undefined;
                // «Мёртвая» зависимость: temp остался неразрешённым, хотя producer (раньше по seq)
                // уже обработан и ОТКЛОНЁН сервером навсегда (4xx). НЕ виснем (break), а убиваем операцию.
                if (urlHasTemp(url) || (bodyObj && bodyHasTemp(bodyObj))) {
                    await outDel(op.seq);
                    pushFailed({ url: op.url, detail: 'Родительская операция отклонена сервером — действие отменено', ts: Date.now() });
                    _pending = await outCount(); emit();
                    continue;
                }
                const body = bodyObj !== undefined ? JSON.stringify(bodyObj) : undefined;
                let res;
                try {
                    res = await fetchT(API + url, { method: op.method, headers: authHeaders(op.opId), body });
                } catch (e) { break; } // сеть снова пропала/зависла → стоп, очередь сохранится
                if (res.status === 401) { _syncing = false; emit(); localStorage.removeItem(TOKEN_KEY); location.href = '/login.html'; return; }
                let data = {}; try { data = await res.json(); } catch (e) {}
                if (res.ok) {
                    if (op.produces != null) {
                        const real = data && (data.id != null ? data.id : data.order_id);
                        if (real != null) { _map[op.produces] = real; resolved[op.produces] = real; await mapPut(op.produces, real); }
                    }
                    await outDel(op.seq);
                } else if (res.status >= 500) {
                    // 5xx/502/504 — ВРЕМЕННЫЙ сбой (рестарт/деплой/ТСПУ). НЕ теряем: повторим
                    // позже с тем же X-Op-Id (идемпотентность защитит от задвоения).
                    op.tries = (op.tries || 0) + 1;
                    if (op.tries >= 6) {  // «ядовитая» операция — не виснем вечно, отбраковываем
                        await outDel(op.seq);
                        pushFailed({ url, detail: 'Сервер не принял после нескольких попыток: ' + ((data && data.detail) || ('HTTP ' + res.status)), ts: Date.now() });
                        _pending = await outCount(); emit();
                        continue;
                    }
                    await outPut(op);  // сохранить счётчик попыток
                    break;             // временный сбой — остановимся, повторим позже
                } else {
                    // 4xx — постоянный отказ: операция мертва, убираем, чтобы не зациклить.
                    // Зависимые от неё (по temp-id) на своём шаге попадут в ветку «мёртвой зависимости».
                    await outDel(op.seq);
                    pushFailed({ url, detail: (data && data.detail) || ('HTTP ' + res.status), ts: Date.now() });
                }
                _pending = await outCount(); emit();
            }
            _pending = await outCount();
        } finally {
            _syncing = false; emit();
            window.dispatchEvent(new CustomEvent('tp-synced', { detail: { resolved } }));
        }
    }

    // ───────── init ─────────
    async function init() {
        try { _pending = await outCount(); } catch (e) { _pending = 0; }
        try { (await mapAll()).forEach(r => { _map[r.temp] = r.real; }); } catch (e) {}
        window.addEventListener('online', () => { emit(); flush(); });
        window.addEventListener('offline', () => emit());
        emit();
        if (navigator.onLine && _pending > 0) flush();
    }

    return {
        init, write, flush,
        state, onChange: (fn) => { _listeners.push(fn); },
        isTemp, clearFailed: () => { _failed = []; emit(); },
        pendingCount: () => _pending,
    };
})();
