// ═══════════════ API HELPER ═══════════════
const API = location.origin;
const TOKEN_KEY = 'tp_token';

async function api(path, opts = {}) {
    const method = (opts.method || 'GET').toUpperCase();
    // записи с поддержкой офлайна → через движок очереди (онлайн-попытка → иначе очередь + идемпотентность)
    if (method !== 'GET' && opts.offline && window.TP) {
        return await TP.write(path, opts);
    }
    const token = localStorage.getItem(TOKEN_KEY);
    const headers = { ...opts.headers };
    if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API}${path}`, { ...opts, headers });
    if (res.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        location.href = '/login.html';
        return;
    }
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Ошибка сервера');
    }
    if (res.status === 204) return null;
    const ct = res.headers.get('content-type');
    if (ct && ct.includes('json')) return res.json();
    return res;
}

// ═══════════════ ICONS ═══════════════
const ICONS = {
    dashboard: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>',
    orders: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/></svg>',
    clients: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
    expenses: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/></svg>',
    advances: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    debts: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
    reports: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>',
    salary: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/></svg>',
    works: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z"/></svg>',
    org: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
    goods: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>',
    audit: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>',
    pricelist: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5a1.99 1.99 0 011.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.99 1.99 0 013 9V4a1 1 0 011-1z"/></svg>',
};

// ═══════════════ MAIN APP ═══════════════
function app() {
    return {
        // --- Navigation ---
        page: 'dashboard',
        sidebarOpen: false,

        menuItems: [
            { id: 'dashboard', label: 'Дашборд', icon: ICONS.dashboard },
            { id: 'orders', label: 'Журнал заказов', icon: ICONS.orders },
            { id: 'cartridges', label: 'Заправки', icon: ICONS.expenses },
            { id: 'works', label: 'Работы', icon: ICONS.works },
            { id: 'goods', label: 'Товар', icon: ICONS.goods },
            { id: 'pricelist', label: 'Прайс-лист', icon: ICONS.pricelist, admin: true },
            { id: 'clients', label: 'Клиенты', icon: ICONS.clients },
            { id: 'expenses', label: 'Расходы', icon: ICONS.expenses },
            { id: 'salary', label: 'Зарплата', icon: ICONS.salary },
            { id: 'advances', label: 'Авансы', icon: ICONS.advances },
            { id: 'debts', label: 'Долги', icon: ICONS.debts },
            { id: 'reports', label: 'Отчёты', icon: ICONS.reports, admin: true },
            { id: 'org', label: 'Реквизиты', icon: ICONS.org, admin: true },
            { id: 'audit', label: 'Журнал', icon: ICONS.audit, admin: true },
        ],
        mobileMenu: [
            { id: 'dashboard', label: 'Главная', icon: ICONS.dashboard },
            { id: 'orders', label: 'Заказы', icon: ICONS.orders },
            { id: 'debts', label: 'Долги', icon: ICONS.debts },
            { id: 'clients', label: 'Клиенты', icon: ICONS.clients },
            { id: 'reports', label: 'Отчёты', icon: ICONS.reports, admin: true },
        ],

        // --- User ---
        user: null,
        darkMode: localStorage.getItem('darkMode') === 'true',

        // --- Year ---
        year: new Date().getFullYear(),
        availableYears: [new Date().getFullYear()],
        monthNames: ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'],

        // --- Search ---
        searchOpen: false,
        searchQuery: '',
        searchResults: [],

        // --- Toasts ---
        toasts: [],
        toastId: 0,

        // --- Dashboard ---
        daily: null,
        monthly: null,
        yearly: null,
        overdueDebts: [],
        revenueChart: null,
        showCashEdit: false,
        cashEditAmount: 0,

        // --- Orders ---
        orders: [],
        orderDate: new Date().toISOString().split('T')[0],
        showOrderForm: false,
        editingOrder: null,
        orderLoading: false,
        ordersLoading: false,
        orderForm: { service_name: '', client_id: '', amount_cash: 0, amount_bank: 0, amount_card: 0, is_paid: true, invoice_number: '', notes: '' },
        clientPreview: null,
        services: [],
        clients: [],

        // --- Clients ---
        clientsList: [],
        clientSearch: '',
        showClientModal: false,
        editingClient: null,
        showMergeModal: false, mergeSource: null, mergeQuery: '', mergeResults: [],
        clientForm: { name: '', phone: '', client_type: 'org', notes: '', full_name: '', inn: '', kpp: '', address: '', account: '', corr_account: '', bank: '', bik: '', director: '' },
        showClientCard: false,
        selectedClient: null,
        clientOrders: [],

        // --- Expenses ---
        expTab: 'supplies',
        expenses: [],
        expMonth: new Date().getMonth() + 1,
        showExpForm: false,
        expForm: { date: new Date().toISOString().split('T')[0], category: 'parts', description: 'ОЗОН', amount: 0, from_cash_register: false, source: 'ozon' },
        editingExpense: null,
        monthlyCosts: [],

        // --- Salary ---
        salary: null,
        salaryMonth: new Date().getMonth() + 1,
        salaryYear: new Date().getFullYear(),
        salarySettings: null, showSalarySettings: false,
        showSalaryPayForm: false,
        salaryPayForm: { date: new Date().toISOString().split('T')[0], amount: 0, payment_type: 'cash', notes: '' },
        showWorkForm: false,
        salaryWorkForm: { date: new Date().toISOString().split('T')[0], description: '', client: '', amount: 0 },
        // корректировка: перенос выплаты в другой месяц
        showMovePay: false,
        movePay: { id: null, amount: 0, date: '', type: '', fromYear: null, fromMonth: null, year: null, month: null, shift_date: false, years: [] },

        // --- Advances ---
        advances: [],
        advFilter: 'active',
        showAdvForm: false,
        advForm: { client_id: '', date: new Date().toISOString().split('T')[0], amount: 0, notes: '' },
        showDeductionModal: false,
        deductionAdvId: null,
        deductionForm: { date: new Date().toISOString().split('T')[0], amount: 0, description: '' },

        // --- Debts ---
        debts: [],
        debtsByClient: [],
        debtCount: 0,
        debtView: 'list',

        // --- Reports ---
        reportChart: null,
        pieChart: null,
        reportSalary: null,
        sections: null,

        // --- Cartridges (Заправки) — client-centric ---
        cartView: 'search', cartJournal: [], cartJrnQ: '', cartJrnBilled: 'all', cartJrnPeriod: 'all', cartJrnSum: { count: 0, sum: 0 }, cartJrnOff: 0, cartJrnMore: false,
        cartScan: '', cartSearchResults: [], cartSearchDone: false, recentCarts: [], priceSource: '',
        cartQuery: '',
        cartClients: [],
        cartCard: null,                 // { client_id, client, cartridges:[{id,barcode,model,refills:[...]}], unbilled }
        cartRefs: { workers: [], defects: [], models: [], spec_types: [] },
        showRefill: false,
        refillForm: { id: null, cartridge_id: '', date: new Date().toISOString().split('T')[0], spec_type_id: 1, worker_id: '', defect_id: '', remark: '', price: '' },
        showNewCart: false,
        newCart: { model_id: '', barcode: '' },
        showEditCart: false,
        editCartForm: { barcode: '', model_id: '', client_id: null, client_name: '', is_eternal: false, is_china: false, remark: '' },
        editCartClients: [],
        focusedCart: null,              // картридж, найденный по штрих-коду (баннер «Повторить»)
        showLabels: false,              // печать листа штрих-кодов
        labelForm: { count: 36, start: null, text: '', w: 52, h: 22 },  // w/h — размер наклейки, мм
        labelFit: { cols: 3, rows: 12, perPage: 36 },
        labels: [],                     // [{code, text}]
        selectedRefills: [],            // unbilled refill ids selected for an invoice
        cartTransfer: false,            // перевод Коле на карту (заправки)
        cartDocs: [],                   // client's documents
        doc: null,                      // currently opened document
        showDoc: false,
        docNewItem: { name: '', qty: 1, price: '' },   // добавление позиции в документ
        docDateEdit: '',                                // дата счёта для смены (календарь)
        docSearch: '', docSearchResults: [],           // поиск документа по номеру счёта
        // works (Работы — ремонт техники)
        workView: 'new', workJournal: [], workJrnQ: '', workJrnBilled: 'all', workJrnPeriod: 'all', workJrnSum: { count: 0, sum: 0 }, workJrnOff: 0, workJrnMore: false,
        workQuery: '',
        workClients: [],
        workCard: null,
        workRefs: { work_types: [], workers: [] },
        showWork: false,
        workForm: { id: null, client_id: null, client_name: '', title: '', device_label: '', date: new Date().toISOString().split('T')[0], worker_id: '', price: '', remark: '' },
        workTransfer: false,            // перевод Коле на карту (мимо кассы → в зарплату)
        selectedWorks: [],
        workDocs: [],
        org: {},                        // реквизиты организации (для печати + страница Реквизиты)
        printHtml: '',                  // содержимое области печати
        auditLog: [],                   // журнал действий
        // прайс-лист (цены заправок по моделям)
        priceList: [], priceQuery: '', priceModel: null, priceModelLoading: false,
        // оффлайн-режим
        online: navigator.onLine, pending: 0, syncing: false, syncFailed: [],
        // товар (продажа товара)
        goodsView: 'new', goodsJournal: [], goodsJrnQ: '', goodsJrnBilled: 'all', goodsJrnPeriod: 'all', goodsJrnSum: { count: 0, sum: 0 }, goodsJrnOff: 0, goodsJrnMore: false,
        goodsQuery: '',
        goodsClients: [],
        goodsCard: null,
        showSale: false,
        saleForm: { id: null, client_id: null, client_name: '', good_id: null, name: '', qty: 1, price: '', date: new Date().toISOString().split('T')[0], remark: '' },
        goodsCatQuery: '',
        goodsCatalog: [],
        activeGoodsRow: -1,
        selectedSales: [],
        goodsTransfer: false,           // перевод Коле на карту (товар)
        goodsDocs: [],

        // --- WebSocket ---
        ws: null,

        // ═══════════════ INIT ═══════════════
        async init() {
            // Check auth
            const token = localStorage.getItem(TOKEN_KEY);
            if (!token) { location.href = '/login.html'; return; }

            // Dark mode
            if (this.darkMode) document.documentElement.classList.add('dark');

            // Оффлайн-движок: запустить, подписаться на статус очереди
            if (window.TP) {
                await TP.init();
                const apply = (st) => { this.online = st.online; this.pending = st.pending; this.syncing = st.syncing; this.syncFailed = st.failed || []; };
                TP.onChange(apply); apply(TP.state());
                window.addEventListener('online', () => { this.online = true; this.connectWS(); this.syncLabelCounter(); });
                window.addEventListener('offline', () => { this.online = false; });
                window.addEventListener('tp-synced', (ev) => this.afterSync(ev && ev.detail));
            }

            // Load user (офлайн — из кэша localStorage)
            try {
                this.user = await api('/api/auth/me');
                localStorage.setItem('tp_user', JSON.stringify(this.user));
            } catch {
                const cached = localStorage.getItem('tp_user');
                if (!navigator.onLine && cached) {
                    this.user = JSON.parse(cached);
                } else {
                    localStorage.removeItem(TOKEN_KEY);
                    location.href = '/login.html';
                    return;
                }
            }

            // Load reference data
            await this.loadRefData();

            // Load initial page
            await this.loadPage('dashboard');

            // Connect WebSocket
            this.connectWS();

            // Load debt count
            this.loadDebtCount();

            // Догнать серверный счётчик наклеек, если печатали офлайн
            this.syncLabelCounter();
        },

        // если офлайн печатали наклейки (localStorage ушёл вперёд) — догнать серверный счётчик,
        // чтобы авто-код новой карточки не совпал с уже напечатанной наклейкой
        async syncLabelCounter() {
            const last = Number(localStorage.getItem('tp_label_last') || '0');
            if (last > 0 && navigator.onLine) {
                try { await api('/api/cartridges/labels/commit?last=' + last, { method: 'POST' }); } catch (e) {}
            }
        },

        // после автосинхронизации — обновить открытый экран реальными данными
        async afterSync(detail) {
            try {
                if (this.pending === 0 && (this.syncFailed || []).length) {
                    this.toast('Часть изменений отклонена сервером (см. значок офлайна)', 'error');
                }
                // открытый офлайн-документ (temp id<0) переоткрыть под реальным id, иначе закрыть
                let handledDoc = false;
                if (this.showDoc && this.doc && this.doc.id < 0) {
                    const real = detail && detail.resolved && detail.resolved[this.doc.id];
                    if (real) { await this.openDoc(real); }
                    else { this.closeDoc(); }
                    handledDoc = true;
                }
                await this._reloadActiveCard();
                if (!handledDoc && this.showDoc && this.doc && this.doc.id > 0) await this.openDoc(this.doc.id);
                if (this.page === 'dashboard') this.loadDashboard();
                this.loadDebtCount();
            } catch (e) {}
        },

        async loadRefData() {
            try {
                const [services, clients, years] = await Promise.all([
                    api('/api/services'),
                    api('/api/clients'),
                    api('/api/dashboard/available-years'),
                ]);
                this.services = services || [];
                this.clients = clients || [];
                this.availableYears = years && years.length ? years : [new Date().getFullYear()];
            } catch (e) {
                console.error('loadRefData:', e);
            }
        },

        // ═══════════════ NAVIGATION ═══════════════
        goTo(pageId) {
            this.page = pageId;
            this.loadPage(pageId);
        },

        async loadPage(pageId) {
            switch (pageId) {
                case 'dashboard': await this.loadDashboard(); break;
                case 'orders': await this.loadOrders(); break;
                case 'cartridges': await this.loadCartRefs(); this.loadRecentCarts(); this.focusScan(); break;
                case 'works': await this.loadWorkRefs(); this.startWorkNew(); break;
                case 'org': await this.loadOrg(); break;
                case 'goods': this.startSaleNew(); break;
                case 'pricelist': await this.loadPricelist(); break;
                case 'audit': await this.loadAudit(); break;
                case 'clients': await this.loadClients(); break;
                case 'expenses': await this.loadExpenses(); await this.loadMonthlyCosts(); break;
                case 'salary': await this.loadSalary(); break;
                case 'advances': await this.loadAdvances(); break;
                case 'debts': await this.loadDebts(); await this.loadDebtsByClient(); break;
                case 'reports': await this.loadYearly(); await this.loadReportSalary(); await this.loadSections(); break;
            }
        },

        // ═══════════════ DASHBOARD ═══════════════
        async loadDashboard() {
            const now = new Date();
            const month = now.getMonth() + 1;
            try {
                const [daily, monthly, yearly, overdue] = await Promise.all([
                    api('/api/dashboard/daily'),
                    api(`/api/dashboard/monthly?year=${this.year}&month=${month}`),
                    api(`/api/dashboard/yearly?year=${this.year}`),
                    api('/api/debts/overdue?days=14'),
                ]);
                this.daily = daily;
                this.monthly = monthly;
                this.yearly = yearly;
                this.overdueDebts = overdue || [];
                this.$nextTick(() => this.renderRevenueChart());
            } catch (e) {
                console.error('loadDashboard:', e);
            }
        },

        async withdrawCash() {
            const input = prompt('Сумма (пусто = всё):');
            if (input === null) return;
            const amt = input.trim() ? parseFloat(input.trim()) : '';
            const url = amt ? `/api/dashboard/cash-register/withdraw?amount=${amt}` : '/api/dashboard/cash-register/withdraw';
            try {
                const res = await api(url, { method: 'POST' });
                if (res.ok) {
                    let msg = `Забрано ${this.fmt(res.amount)} из кассы`;
                    if (res.added_to_salary) {
                        msg += ' (→ ЗП)';
                        if (res.salary_remaining !== undefined) msg += `. Остаток ЗП: ${this.fmt(res.salary_remaining)}`;
                    }
                    this.toast(msg, 'success');
                    await this.loadDashboard();
                } else {
                    this.toast(res.message || 'Касса пуста', 'info');
                }
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        openCashEdit() {
            this.cashEditAmount = Math.round(Number(this.daily?.cash_register || 0));
            this.showCashEdit = true;
            this.$nextTick(() => this.$refs.cashInput?.focus());
        },

        async saveCashEdit() {
            try {
                const res = await api(`/api/dashboard/cash-register/set?amount=${this.cashEditAmount || 0}`, { method: 'POST' });
                if (res.ok) {
                    this.showCashEdit = false;
                    this.toast('Касса обновлена: ' + this.fmt(res.amount), 'success');
                    await this.loadDashboard();
                } else {
                    this.toast(res.message || 'Ошибка', 'error');
                }
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        renderRevenueChart() {
            const canvas = document.getElementById('revenueChart');
            if (!canvas || !this.yearly) return;
            if (this.revenueChart) this.revenueChart.destroy();

            const months = this.yearly.months || [];
            const isDark = this.darkMode;
            this.revenueChart = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: this.monthNames.map(n => n.substring(0, 3)),
                    datasets: [{
                        label: 'Выручка',
                        data: months.map(m => Number(m.revenue)),
                        backgroundColor: 'rgba(59,130,246,0.5)',
                        borderColor: 'rgb(59,130,246)',
                        borderWidth: 1,
                        borderRadius: 6,
                    }, {
                        label: 'Прибыль',
                        data: months.map(m => Number(m.profit)),
                        backgroundColor: months.map(m => Number(m.profit) >= 0 ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)'),
                        borderColor: months.map(m => Number(m.profit) >= 0 ? 'rgb(34,197,94)' : 'rgb(239,68,68)'),
                        borderWidth: 1,
                        borderRadius: 6,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: isDark ? '#94a3b8' : '#64748b' } } },
                    scales: {
                        y: { ticks: { color: isDark ? '#94a3b8' : '#64748b' }, grid: { color: isDark ? '#334155' : '#e2e8f0' } },
                        x: { ticks: { color: isDark ? '#94a3b8' : '#64748b' }, grid: { display: false } },
                    }
                }
            });
        },

        // ═══════════════ ORDERS ═══════════════
        async loadOrders() {
            this.ordersLoading = true;
            try {
                this.orders = await api(`/api/orders?date=${this.orderDate}`) || [];
            } catch (e) {
                this.toast('Ошибка загрузки заказов', 'error');
            }
            this.ordersLoading = false;
        },

        resetOrderForm() {
            this.orderForm = { service_name: '', client_id: '', amount_cash: 0, amount_bank: 0, amount_card: 0, is_paid: true, invoice_number: '', notes: '', date: this.orderDate || this.todayStr() };
            this.editingOrder = null;
            this.clientPreview = null;
        },

        cancelOrderEdit() {
            this.resetOrderForm();
            this.showOrderForm = false;
        },

        async loadClientPreview(clientId) {
            if (!clientId) { this.clientPreview = null; return; }
            try {
                const orders = await api(`/api/clients/${clientId}/orders?limit=5`);
                const cl = this.clients.find(c => c.id === clientId);
                this.clientPreview = {
                    name: cl?.name || '',
                    totalOrders: cl?.total_orders || 0,
                    totalRevenue: cl?.total_revenue || 0,
                    debt: cl?.debt_amount || 0,
                    orders: orders || [],
                };
            } catch { this.clientPreview = null; }
        },

        editOrder(o) {
            this.editingOrder = o;
            this.orderForm = {
                service_name: o.service_name || '',
                client_id: o.client_id,
                amount_cash: Number(o.amount_cash),
                amount_bank: Number(o.amount_bank),
                amount_card: Number(o.amount_card),
                is_paid: o.is_paid,
                invoice_number: o.invoice_number || '',
                notes: o.notes || '',
                date: (o.date || '').slice(0, 10) || this.todayStr(),
            };
            this.showOrderForm = true;
            this.loadClientPreview(o.client_id);
        },

        repeatOrder(o) {
            this.editingOrder = null;
            this.orderForm = {
                service_name: o.service_name || '',
                client_id: o.client_id,
                amount_cash: Number(o.amount_cash),
                amount_bank: Number(o.amount_bank),
                amount_card: Number(o.amount_card),
                is_paid: o.is_paid,
                invoice_number: '',
                notes: '',
                date: this.orderDate || this.todayStr(),
            };
            this.showOrderForm = true;
            this.loadClientPreview(o.client_id);
            this.toast('Заказ скопирован — проверьте и сохраните', 'info');
        },

        async saveOrder() {
            if (!this.orderForm.service_name?.trim() || !this.orderForm.client_id) {
                this.toast('Введите услугу и выберите клиента', 'error');
                return;
            }
            this.orderLoading = true;
            try {
                const body = {
                    date: this.orderForm.date || this.orderDate,
                    service_name: this.orderForm.service_name.trim(),
                    client_id: this.orderForm.client_id,
                    amount_cash: this.orderForm.amount_cash || 0,
                    amount_bank: this.orderForm.amount_bank || 0,
                    amount_card: this.orderForm.amount_card || 0,
                    is_paid: this.orderForm.is_paid,
                    invoice_number: this.orderForm.invoice_number || null,
                    notes: this.orderForm.notes || null,
                };
                if (this.editingOrder) {
                    await api(`/api/orders/${this.editingOrder.id}`, { method: 'PUT', body: JSON.stringify(body) });
                    this.toast('Заказ обновлён', 'success');
                } else {
                    await api('/api/orders', { method: 'POST', body: JSON.stringify(body) });
                    this.toast('Заказ добавлен', 'success');
                }
                this.resetOrderForm();
                this.showOrderForm = false;
                await this.loadOrders();
            } catch (e) {
                this.toast(e.message, 'error');
            }
            this.orderLoading = false;
        },

        updatePaidStatus() {
            // Безнал → не оплачено, только нал → оплачено
            if (Number(this.orderForm.amount_bank) > 0) {
                this.orderForm.is_paid = false;
            } else {
                this.orderForm.is_paid = true;
            }
        },

        async deleteOrder(id) {
            if (!confirm('Удалить заказ?')) return;
            try {
                await api(`/api/orders/${id}`, { method: 'DELETE' });
                this.toast('Заказ удалён', 'success');
                await this.loadOrders();
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        async markPaid(orderId) {
            try {
                await api(`/api/orders/${orderId}/mark-paid`, { method: 'PUT' });
                this.toast('Оплата отмечена', 'success');
                // Refresh relevant data
                if (this.page === 'orders') await this.loadOrders();
                if (this.page === 'debts') { await this.loadDebts(); await this.loadDebtsByClient(); }
                if (this.page === 'dashboard') await this.loadDashboard();
                this.loadDebtCount();
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        prevDay() {
            const d = new Date(this.orderDate);
            d.setDate(d.getDate() - 1);
            this.orderDate = d.toISOString().split('T')[0];
            this.loadOrders();
        },

        nextDay() {
            const d = new Date(this.orderDate);
            d.setDate(d.getDate() + 1);
            this.orderDate = d.toISOString().split('T')[0];
            this.loadOrders();
        },

        // ═══════════════ CLIENTS ═══════════════
        async loadClients() {
            try {
                const search = this.clientSearch ? `?search=${encodeURIComponent(this.clientSearch)}` : '';
                this.clientsList = await api(`/api/clients${search}`) || [];
            } catch (e) {
                this.toast('Ошибка загрузки клиентов', 'error');
            }
        },

        openNewClientModal() {
            this.editingClient = null;
            this.clientForm = { name: '', phone: '', client_type: 'org', notes: '', full_name: '', inn: '', kpp: '', address: '', account: '', corr_account: '', bank: '', bik: '', director: '' };
            this.showClientModal = true;
        },
        editClient(c) {
            const s = c || this.selectedClient || {};
            this.editingClient = s;
            this.clientForm = {
                name: s.name || '', phone: s.phone || '', client_type: s.client_type || 'org', notes: s.notes || '',
                full_name: s.full_name || '', inn: s.inn || '', kpp: s.kpp || '', address: s.address || '',
                account: s.account || '', corr_account: s.corr_account || '', bank: s.bank || '', bik: s.bik || '', director: s.director || '',
            };
            this.showClientCard = false;
            this.showClientModal = true;
        },

        async saveClient() {
            if (!(this.clientForm.name || '').trim()) { this.toast('Укажите название / ФИО', 'error'); return; }
            try {
                if (this.editingClient) {
                    const cid = this.editingClient.id || this.editingClient.client_id;
                    if (!cid) { this.toast('Не удалось определить клиента', 'error'); return; }
                    const updated = await api(`/api/clients/${cid}`, { method: 'PUT', body: JSON.stringify(this.clientForm) });
                    this.toast('Клиент обновлён', 'success');
                    // сразу отразить изменения в открытой карточке и списках (без «кажется не сохранилось»)
                    if (updated) {
                        if (this.selectedClient && (this.selectedClient.id === cid)) Object.assign(this.selectedClient, updated);
                        for (const arr of [this.clients, this.clientsList]) {
                            const it = (arr || []).find(x => x && x.id === cid);
                            if (it) Object.assign(it, updated);
                        }
                    }
                } else {
                    const newClient = await api('/api/clients', { method: 'POST', body: JSON.stringify(this.clientForm) });
                    this.toast('Клиент создан', 'success');
                    this.clients.push(newClient);
                }
                this.showClientModal = false;
                if (this.page === 'clients') await this.loadClients();
            } catch (e) {
                this.toast(e.message, 'error');   // модалка остаётся открытой — можно повторить
            }
        },

        async openClientCard(client) {
            this.selectedClient = client;
            this.clientOrders = [];
            this.showClientCard = true;
            try {
                this.clientOrders = await api(`/api/clients/${client.id}/orders?year=${this.year}`) || [];
            } catch (e) {
                console.error(e);
            }
        },

        // ═══════════════ EXPENSES ═══════════════
        async loadExpenses() {
            try {
                this.expenses = await api(`/api/expenses?year=${this.year}&month=${this.expMonth}`) || [];
            } catch (e) {
                this.toast('Ошибка загрузки расходов', 'error');
            }
        },

        async saveExpense() {
            try {
                const body = { ...this.expForm };
                if (this.editingExpense) {
                    await api(`/api/expenses/${this.editingExpense.id}`, { method: 'PUT', body: JSON.stringify(body) });
                    this.toast('Расход обновлён', 'success');
                } else {
                    await api('/api/expenses', { method: 'POST', body: JSON.stringify(body) });
                    this.toast('Расход добавлен', 'success');
                }
                this.showExpForm = false;
                this.expForm = { date: new Date().toISOString().split('T')[0], category: 'parts', description: 'ОЗОН', amount: 0, from_cash_register: false, source: 'ozon' };
                this.editingExpense = null;
                await this.loadExpenses();
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        async deleteExpense(id) {
            if (!confirm('Удалить расход?')) return;
            try {
                await api(`/api/expenses/${id}`, { method: 'DELETE' });
                this.toast('Расход удалён', 'success');
                await this.loadExpenses();
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        catName(cat) {
            const map = { toner: 'Тонер', paper: 'Бумага', parts: 'Запчасти', delivery: 'Доставка', other: 'Прочее' };
            return map[cat] || cat || 'Прочее';
        },

        catClass(cat) {
            const map = {
                toner: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
                paper: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
                parts: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400',
                delivery: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
                other: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400',
            };
            return map[cat] || map.other;
        },

        // --- Monthly Costs ---
        async loadMonthlyCosts() {
            try {
                this.monthlyCosts = await api(`/api/monthly-costs?year=${this.year}`) || [];
                // Fill missing months
                for (let m = 1; m <= 12; m++) {
                    if (!this.monthlyCosts.find(c => c.month === m)) {
                        this.monthlyCosts.push({ month: m, year: this.year, salary_admin: 0, salary_master: 0, rent: 0, taxes: 0, other: 0, total: 0, notes: '' });
                    }
                }
                this.monthlyCosts.sort((a, b) => a.month - b.month);
            } catch (e) {
                console.error(e);
            }
        },

        async updateMC(month, field, value) {
            try {
                const body = {};
                body[field] = parseFloat(value) || 0;
                const result = await api(`/api/monthly-costs/${this.year}/${month}`, { method: 'PUT', body: JSON.stringify(body) });
                // Update local
                const idx = this.monthlyCosts.findIndex(c => c.month === month);
                if (idx >= 0 && result) this.monthlyCosts[idx] = result;
                this.toast('Сохранено', 'success');
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        async copyMC(month) {
            try {
                const result = await api(`/api/monthly-costs/${this.year}/${month}/copy-previous`, { method: 'POST' });
                const idx = this.monthlyCosts.findIndex(c => c.month === month);
                if (idx >= 0 && result) this.monthlyCosts[idx] = result;
                this.toast('Скопировано из прошлого месяца', 'success');
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        // ═══════════════ SALARY ═══════════════
        async loadSalary() {
            try {
                this.salary = await api(`/api/salary?year=${this.salaryYear}&month=${this.salaryMonth}`);
                if (this.user?.role === 'admin' && !this.salarySettings) { try { this.salarySettings = await api('/api/salary/settings'); } catch (e) {} }
            } catch (e) {
                this.toast('Ошибка загрузки зарплаты', 'error');
            }
        },
        async saveSalarySettings() {
            try {
                const s = this.salarySettings || {};
                const body = {
                    commission_rate: (Number(s.commission_pct) || 0) / 100,
                    fixed_salary: Number(s.fixed_salary) || 0,
                    fixed_rent: Number(s.fixed_rent) || 0,
                    payroll_tax: Number(s.payroll_tax) || 0,
                };
                this.salarySettings = await api('/api/salary/settings', { method: 'PUT', body: JSON.stringify(body) });
                this.showSalarySettings = false;
                this.toast('Правила зарплаты сохранены', 'success');
                await this.loadSalary();
            } catch (e) { this.toast(e.message, 'error'); }
        },
        openSalarySettings() {
            const s = this.salarySettings || {};
            // в UI процент показываем в %, храним долей
            s.commission_pct = Math.round((Number(s.commission_rate) || 0) * 1000) / 10;
            this.salarySettings = s;
            this.showSalarySettings = true;
        },

        async updateSalaryAmount(field, value) {
            try {
                const v = parseFloat(value) || 0;
                this.salary = await api(`/api/salary/amounts?year=${this.salaryYear}&month=${this.salaryMonth}&${field}=${v}`, { method: 'PUT' });
                this.toast('Сохранено', 'success');
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        async addSalaryPayment() {
            try {
                const body = {
                    year: this.salaryYear,
                    month: this.salaryMonth,
                    ...this.salaryPayForm,
                };
                this.salary = await api('/api/salary/payments', { method: 'POST', body: JSON.stringify(body) });
                this.showSalaryPayForm = false;
                this.salaryPayForm = { date: new Date().toISOString().split('T')[0], amount: 0, payment_type: 'cash', notes: '' };
                this.toast('Выплата добавлена', 'success');
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        async deleteSalaryPayment(id) {
            if (!confirm('Удалить выплату?')) return;
            try {
                this.salary = await api(`/api/salary/payments/${id}`, { method: 'DELETE' });
                this.toast('Выплата удалена', 'success');
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        // ── корректировка месяца выплаты ──
        openMovePayment(p) {
            const y = p.year || this.salaryYear;
            const years = [];
            for (let i = y - 2; i <= y + 1; i++) years.push(i);
            this.movePay = {
                id: p.id, amount: p.amount, date: p.date, type: p.payment_type,
                fromYear: p.year, fromMonth: p.month,
                year: y, month: p.month, shift_date: false, years,
            };
            this.showMovePay = true;
        },

        async submitMovePayment() {
            const m = this.movePay;
            if (m.year === m.fromYear && m.month === m.fromMonth) {
                this.toast('Выберите другой месяц', 'error');
                return;
            }
            try {
                const body = { year: Number(m.year), month: Number(m.month), shift_date: !!m.shift_date };
                this.salary = await api(`/api/salary/payments/${m.id}/move`, { method: 'PUT', body: JSON.stringify(body) });
                this.showMovePay = false;
                this.toast(`Выплата перенесена в ${this.monthNames[m.month - 1]} ${m.year}`, 'success');
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        // выплата отнесена не к тому месяцу, в котором реально сделана (перенесена вручную)
        payYM(p) {
            const [y, m] = String(p.date || '').split('-');
            return [Number(y), Number(m)];
        },

        payMoved(p) {
            if (!p.date) return false;
            const [y, m] = this.payYM(p);
            return y !== p.year || m !== p.month;
        },

        payMovedTitle(p) {
            if (!this.payMoved(p)) return '';
            const [y, m] = this.payYM(p);
            return `Фактически выплачено ${this.monthNames[m - 1]} ${y}, учтено в ${this.monthNames[p.month - 1]} ${p.year}`;
        },

        async addSalaryWork() {
            try {
                const body = {
                    year: this.salaryYear,
                    month: this.salaryMonth,
                    ...this.salaryWorkForm,
                };
                this.salary = await api('/api/salary/works', { method: 'POST', body: JSON.stringify(body) });
                this.showWorkForm = false;
                this.salaryWorkForm = { date: new Date().toISOString().split('T')[0], description: '', client: '', amount: 0 };
                this.toast('Работа добавлена', 'success');
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        async deleteSalaryWork(id) {
            if (!confirm('Удалить запись о работе?')) return;
            try {
                this.salary = await api(`/api/salary/works/${id}`, { method: 'DELETE' });
                this.toast('Запись удалена', 'success');
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        salaryPrevMonth() {
            this.salaryMonth--;
            if (this.salaryMonth < 1) { this.salaryMonth = 12; this.salaryYear--; }
            this.loadSalary();
        },

        salaryNextMonth() {
            this.salaryMonth++;
            if (this.salaryMonth > 12) { this.salaryMonth = 1; this.salaryYear++; }
            this.loadSalary();
        },

        payTypeName(t) {
            return { cash: 'Наличные', bank: 'Офиц. ЗП', card: 'Перевод' }[t] || t;
        },

        payTypeClass(t) {
            return {
                cash: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
                bank: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400',
                card: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
            }[t] || '';
        },

        // ═══════════════ ADVANCES ═══════════════
        async loadAdvances() {
            try {
                const param = this.advFilter === 'active' ? '?active=true' : '';
                this.advances = await api(`/api/advances${param}`) || [];
            } catch (e) {
                this.toast('Ошибка загрузки авансов', 'error');
            }
        },

        async saveAdvance() {
            try {
                await api('/api/advances', { method: 'POST', body: JSON.stringify(this.advForm) });
                this.toast('Аванс создан', 'success');
                this.showAdvForm = false;
                this.advForm = { client_id: '', date: new Date().toISOString().split('T')[0], amount: 0, notes: '' };
                await this.loadAdvances();
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },

        openDeduction(advance) {
            this.deductionAdvId = advance.id;
            this.deductionForm = { date: new Date().toISOString().split('T')[0], amount: 0, description: '' };
            this.showDeductionModal = true;
        },

        async saveDeduction() {
            try {
                await api(`/api/advances/${this.deductionAdvId}/deductions`, { method: 'POST', body: JSON.stringify(this.deductionForm) });
                this.toast('Списание сохранено', 'success');
                this.showDeductionModal = false;
                await this.loadAdvances();
            } catch (e) {
                this.toast(e.message, 'error');
            }
        },
        async deleteClient(c) {
            if (!confirm('Удалить клиента «' + c.name + '»?\n(можно только если у него нет истории — иначе используйте «Объединить»)')) return;
            try {
                await api('/api/clients/' + c.id, { method: 'DELETE' });
                this.toast('Клиент удалён', 'success');
                await this.loadClients();
            } catch (e) { this.toast(e.message, 'error'); }
        },
        openMergeClient(c) {
            this.mergeSource = c; this.mergeQuery = ''; this.mergeResults = []; this.showMergeModal = true;
        },
        async searchMergeTarget() {
            const q = (this.mergeQuery || '').trim();
            if (q.length < 1) { this.mergeResults = []; return; }
            try {
                const r = await api('/api/clients?search=' + encodeURIComponent(q)) || [];
                this.mergeResults = r.filter(x => x.id !== this.mergeSource?.id);
            } catch (e) { this.mergeResults = []; }
        },
        async doMergeClient(target) {
            if (!this.mergeSource) return;
            if (!confirm('Перенести ВСЮ историю (заказы, заправки, счета, авансы) из «' + this.mergeSource.name + '» в «' + target.name + '» и удалить дубль «' + this.mergeSource.name + '»?')) return;
            try {
                await api('/api/clients/' + this.mergeSource.id + '/merge/' + target.id, { method: 'POST' });
                this.toast('Объединено в «' + target.name + '»', 'success');
                this.showMergeModal = false; this.mergeSource = null; this.mergeResults = [];
                await this.loadClients();
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async deleteAdvance(a) {
            if (!confirm('Удалить аванс ' + (a.client_name || '') + ' на ' + this.fmt(a.amount) + ' целиком (со всеми списаниями)?')) return;
            try {
                await api(`/api/advances/${a.id}`, { method: 'DELETE' });
                this.toast('Аванс удалён', 'success');
                await this.loadAdvances();
            } catch (e) { this.toast(e.message, 'error'); }
        },

        // ═══════════════ DEBTS ═══════════════
        async loadDebts() {
            try {
                this.debts = await api('/api/debts') || [];
            } catch (e) {
                console.error(e);
            }
        },

        async loadDebtsByClient() {
            try {
                this.debtsByClient = await api('/api/debts/by-client') || [];
            } catch (e) {
                console.error(e);
            }
        },

        async loadDebtCount() {
            try {
                const debts = await api('/api/debts');
                this.debtCount = debts ? debts.length : 0;
            } catch { this.debtCount = 0; }
        },

        // ═══════════════ REPORTS ═══════════════
        async loadYearly() {
            try {
                this.yearly = await api(`/api/dashboard/yearly?year=${this.year}`);
                this.$nextTick(() => {
                    this.renderReportChart();
                    this.renderPieChart();
                });
            } catch (e) {
                console.error(e);
            }
        },

        async loadReportSalary() {
            try {
                this.reportSalary = await api('/api/salary/prev-month-balance');
            } catch (e) {
                console.error(e);
            }
        },
        async loadSections() {
            try { this.sections = await api(`/api/dashboard/sections?year=${this.year}`); }
            catch (e) { console.error(e); }
        },
        debtAging() {
            const b = { d7: 0, d30: 0, d60: 0, d60p: 0, total: 0 };
            for (const d of (this.debts || [])) {
                const a = Number(d.amount) || 0, o = d.days_overdue || 0;
                b.total += a;
                if (o <= 7) b.d7 += a; else if (o <= 30) b.d30 += a; else if (o <= 60) b.d60 += a; else b.d60p += a;
            }
            return b;
        },

        renderReportChart() {
            const canvas = document.getElementById('reportChart');
            if (!canvas || !this.yearly) return;
            if (this.reportChart) this.reportChart.destroy();
            const months = this.yearly.months || [];
            const isDark = this.darkMode;
            this.reportChart = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: this.monthNames.map(n => n.substring(0, 3)),
                    datasets: [{
                        label: 'Выручка',
                        data: months.map(m => Number(m.revenue)),
                        backgroundColor: 'rgba(59,130,246,0.6)',
                        borderRadius: 4,
                    }, {
                        label: 'Расходы',
                        data: months.map(m => Number(m.expenses_total)),
                        backgroundColor: 'rgba(249,115,22,0.6)',
                        borderRadius: 4,
                    }, {
                        label: 'Прибыль',
                        type: 'line',
                        data: months.map(m => Number(m.profit)),
                        borderColor: 'rgb(34,197,94)',
                        backgroundColor: 'rgba(34,197,94,0.1)',
                        tension: 0.3,
                        fill: true,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: isDark ? '#94a3b8' : '#64748b' } } },
                    scales: {
                        y: { ticks: { color: isDark ? '#94a3b8' : '#64748b' }, grid: { color: isDark ? '#334155' : '#e2e8f0' } },
                        x: { ticks: { color: isDark ? '#94a3b8' : '#64748b' }, grid: { display: false } },
                    }
                }
            });
        },

        renderPieChart() {
            const canvas = document.getElementById('pieChart');
            if (!canvas || !this.yearly) return;
            if (this.pieChart) this.pieChart.destroy();
            const months = this.yearly.months || [];
            const totalCash = months.reduce((s, m) => s + Number(m.cash), 0);
            const totalBank = months.reduce((s, m) => s + Number(m.bank), 0);
            const totalCard = months.reduce((s, m) => s + Number(m.card), 0);
            this.pieChart = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: ['Наличные', 'Безнал', 'Карта'],
                    datasets: [{
                        data: [totalCash, totalBank, totalCard],
                        backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(59,130,246,0.7)', 'rgba(168,85,247,0.7)'],
                        borderWidth: 0,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: this.darkMode ? '#94a3b8' : '#64748b', padding: 16 } },
                    }
                }
            });
        },

        // ═══════════════ CARTRIDGES (Заправки) — client-centric ═══════════════
        async loadCartRefs() {
            try { this.cartRefs = await api('/api/cartridges/refs') || { workers: [], defects: [], models: [], spec_types: [] }; }
            catch (e) { console.error('cartRefs', e); }
        },
        async searchCartClients() {
            try { this.cartClients = await api('/api/cartridges/clients?q=' + encodeURIComponent(this.cartQuery)) || []; }
            catch (e) { this.toast('Ошибка поиска', 'error'); }
        },
        // ───────── ПОИСК КАРТРИДЖЕЙ → КАРТОЧКА КАРТРИДЖА (кабинет) ─────────
        focusScan() { this.$nextTick(() => { const el = document.getElementById('cart-scan'); if (el) { el.focus(); try { el.select(); } catch (e) {} } }); },
        async searchCartridges() {
            const q = (this.cartScan || '').trim();
            if (!q) { this.cartSearchResults = []; this.cartSearchDone = false; return; }
            try {
                this.cartSearchResults = await api('/api/cartridges/search?q=' + encodeURIComponent(q)) || [];
                this.cartSearchDone = true;
            } catch (e) { this.toast(e.message, 'error'); }
        },
        // Enter/скан/кнопка: ровно один картридж → открыть его карточку сразу; иначе показать список
        async findCartridge() {
            const q = (this.cartScan || '').trim();
            if (!q) { this.focusScan(); return; }
            try {
                const res = await api('/api/cartridges/search?q=' + encodeURIComponent(q)) || [];
                this.cartSearchResults = res; this.cartSearchDone = true;
                if (res.length === 1) { await this.openCartridgeCard(res[0].cartridge_id); }
                else { this.cartView = 'search'; if (!res.length) this.focusScan(); }
            } catch (e) { this.toast(e.message, 'error'); }
        },
        loadRecentCarts() { try { this.recentCarts = JSON.parse(localStorage.getItem('tp_recent_carts') || '[]'); } catch (e) { this.recentCarts = []; } },
        addRecentCart(c) {
            try {
                let rec = JSON.parse(localStorage.getItem('tp_recent_carts') || '[]').filter(x => x.cartridge_id !== c.cartridge_id);
                rec.unshift({ cartridge_id: c.cartridge_id, barcode: c.barcode, model: c.model, client: c.client });
                rec = rec.slice(0, 8);
                localStorage.setItem('tp_recent_carts', JSON.stringify(rec));
                this.recentCarts = rec;
            } catch (e) {}
        },
        async openCartridgeCard(cid) {
            try {
                this.cartCard = await api('/api/cartridges/card/' + cid);
                this.cartView = 'card';
                this.showRefill = false; this.showNewCart = false;
                this.selectedRefills = []; this.focusedCart = null; this.priceSource = ''; this.cartTransfer = false;
                if (this.cartCard?.client_id) await this.loadCartDocs(this.cartCard.client_id);
                this.addRecentCart({ cartridge_id: this.cartCard.cartridge_id, barcode: this.cartCard.barcode, model: this.cartCard.model, client: this.cartCard.client });
                this.$nextTick(() => this.renderCardBarcode());
            } catch (e) { this.toast(e.message, 'error'); }
        },
        renderCardBarcode() {
            if (!window.JsBarcode || !this.cartCard?.barcode) return;
            const el = document.getElementById('card-barcode');
            if (el) { try { window.JsBarcode(el, this.cartCard.barcode, { format: 'CODE128', width: 1.4, height: 32, fontSize: 11, margin: 0, displayValue: false }); } catch (e) {} }
        },
        async openCartridgeClientCard(clientId) {
            try {
                this.focusedCart = null;
                this.cartCard = await api('/api/cartridges/client/' + clientId);
                this.cartView = 'clients';
                this.showRefill = false; this.showNewCart = false;
                this.selectedRefills = [];
                await this.loadCartDocs(clientId);
            } catch (e) { this.toast(e.message, 'error'); }
        },
        backFromCard() {
            const wasSingle = this.cartCard?.single;
            this.cartCard = null; this.showRefill = false; this.selectedRefills = [];
            this.cartView = wasSingle ? 'search' : 'clients';
            if (wasSingle) this.focusScan();
        },
        // перезагрузить активную карточку (картриджа или клиента) после правок
        async reloadCard() {
            if (!this.cartCard) return;
            if (this.cartCard.single) await this.openCartridgeCard(this.cartCard.cartridge_id);
            else await this.openCartridgeClientCard(this.cartCard.client_id);
        },
        defaultWorker() { return this.cartRefs?.default_worker_id || ''; },
        openEditCart() {
            if (!this.cartCard?.single) return;
            this.showEditCart = true; this.showRefill = false; this.showNewCart = false;
            this.editCartClients = [];
            this.editCartForm = {
                barcode: this.cartCard.barcode || '',
                model_id: this.cartCard.model_id || '',
                client_id: this.cartCard.client_id || null,
                client_name: this.cartCard.client || '',
                is_eternal: !!this.cartCard.is_eternal,
                is_china: !!this.cartCard.is_china,
                remark: this.cartCard.remark || '',
            };
            this.scrollToForm();
        },
        async ecSearch() {
            this.editCartForm.client_id = null;   // ручной ввод сбрасывает выбор
            const q = (this.editCartForm.client_name || '').trim();
            if (q.length < 1) { this.editCartClients = []; return; }
            try { this.editCartClients = await api('/api/works/clients?q=' + encodeURIComponent(q)) || []; }
            catch (e) { this.editCartClients = []; }
        },
        pickEditCartClient(c) {
            this.editCartForm.client_id = c.client_id; this.editCartForm.client_name = c.client;
            this.editCartClients = [];
        },
        async saveEditCart() {
            if (!this.needOnline()) return;
            // владелец: выбранный из списка, либо найти по имени (как в работах/товаре)
            let clientId = this.editCartForm.client_id;
            if (!clientId && (this.editCartForm.client_name || '').trim()) {
                clientId = await this._resolveClientId(this.editCartForm.client_name);
                if (!clientId) return;
            }
            try {
                const body = {
                    barcode: (this.editCartForm.barcode || '').trim() || null,
                    model_id: this.editCartForm.model_id || null,
                    client_id: clientId || null,
                    is_eternal: !!this.editCartForm.is_eternal,
                    is_china: !!this.editCartForm.is_china,
                    remark: this.editCartForm.remark || null,
                };
                await api('/api/cartridges/' + this.cartCard.cartridge_id, { method: 'PUT', body: JSON.stringify(body) });
                this.toast('Картридж изменён', 'success');
                this.showEditCart = false;
                await this.reloadCard();
            } catch (e) { this.toast(e.message, 'error'); }
        },
        scrollToForm() { this.$nextTick(() => { const el = document.getElementById('refill-form-anchor'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }); },
        // + Заправка на текущем картридже — умный префилл из последней заправки (тип/мастер/цена)
        startRefillCard() {
            const last = (this.cartCard?.refills || [])[0];
            this.showRefill = true; this.showNewCart = false; this.priceSource = '';
            this.refillForm = { id: null, cartridge_id: this.cartCard?.cartridge_id, date: this.todayStr(),
                spec_type_id: last?.spec_type_id || 1, worker_id: last?.worker_id || this.defaultWorker(), defect_id: '', remark: '', price: '' };
            this.prefillRefillPrice(); this.scrollToForm();
        },
        // быстрый повтор по конкретному картриджу (из карточки клиента/баннера)
        quickRepeat(cartId) {
            this.showRefill = true; this.showNewCart = false; this.priceSource = '';
            this.refillForm = { id: null, cartridge_id: cartId, date: this.todayStr(), spec_type_id: 1, worker_id: this.defaultWorker(), defect_id: '', remark: '', price: '' };
            this.prefillRefillPrice(); this.scrollToForm();
        },
        // касса/счёт на ВСЕ невыписанные текущей карточки (без чекбоксов)
        async billAll(kind) {
            const ids = this.unbilledRefills().map(r => r.id);
            if (!ids.length) { this.toast('Нет невыписанных заправок', 'info'); return; }
            this.selectedRefills = ids.slice();
            if (kind === 'cash') await this.createCashRefills();
            else await this.createInvoice();
        },
        // одиночная печать этикетки по штрих-коду (фронт, без сдвига счётчика)
        printOneLabel(barcode) {
            if (!barcode || !window.JsBarcode) { this.toast('Нет штрих-кода', 'error'); return; }
            const root = document.getElementById('label-print-root');
            const w = this.labelForm.w || 52, h = this.labelForm.h || 22;
            const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            root.innerHTML = `<div class="lbl" style="width:${w}mm;height:${h}mm"><svg class="bc" data-code="${esc(barcode)}"></svg></div>`;
            this.renderBarcodes('#label-print-root');
            this.$nextTick(() => window.print());
            setTimeout(() => { root.innerHTML = ''; }, 800);
        },
        startRefill() {
            this.showRefill = true; this.showNewCart = false; this.priceSource = '';
            this.refillForm = { id: null, cartridge_id: '', date: this.todayStr(), spec_type_id: 1, worker_id: this.defaultWorker(), defect_id: '', remark: '', price: '' };
            this.scrollToForm();
        },
        async prefillRefillPrice() {
            if (this.refillForm.id) return;  // при редактировании цену не трогаем
            this.priceSource = '';
            const c = (this.cartCard?.cartridges || []).find(x => x.id === Number(this.refillForm.cartridge_id));
            const spec = Number(this.refillForm.spec_type_id) || 1;
            const srcLabel = { manual: 'из прайса', auto: 'из истории', base: 'базовая заправка' };
            if (c && c.model_id) {
                try {
                    const r = await api(`/api/cartridges/suggest-price?model_id=${c.model_id}&spec_type_id=${spec}`);
                    if (r && r.price != null) { this.refillForm.price = r.price; this.priceSource = (srcLabel[r.source] || '') + ' · ' + this.fmt(r.price); return; }
                } catch {}
            }
            if (c && c.last_price != null) { this.refillForm.price = c.last_price; this.priceSource = 'последняя · ' + this.fmt(c.last_price); }
        },
        // Сохранить заправку И сразу провести: 'cash' (касса) / 'invoice' (счёт)
        async saveRefillAndPay(payKind) {
            if (this.refillForm.id) { await this.saveRefill(); return; }  // редактирование — обычное сохранение
            const cid = Number(this.refillForm.cartridge_id);
            if (!cid) { this.toast('Картридж не выбран', 'error'); return; }
            if (cid < 0) { this.toast('Новый картридж ещё не синхронизирован — сначала онлайн', 'error'); return; }
            const body = {
                date: this.refillForm.date,
                spec_type_id: Number(this.refillForm.spec_type_id) || 1,
                worker_id: this.refillForm.worker_id || null,
                defect_id: this.refillForm.defect_id || null,
                remark: this.refillForm.remark || null,
                price: this.refillForm.price === '' || this.refillForm.price == null ? null : Number(this.refillForm.price),
            };
            const cart = (this.cartCard?.cartridges || []).find(c => c.id === cid) || {};
            const sp = (this.cartRefs?.spec_types || []).find(s => s.id === body.spec_type_id);
            const wk = (this.cartRefs?.workers || []).find(w => w.id === Number(this.refillForm.worker_id));
            const cardId = this.cartCard.single ? this.cartCard.cartridge_id : null;
            try {
                const res = await api('/api/cartridges/' + cid + '/refills', { method: 'POST', body: JSON.stringify(body),
                    offline: { kind: 'refill_add', clientId: this.cartCard.client_id, cartCardId: cardId, cartridgeId: cid, barcode: cart.barcode, model: cart.model, specName: sp ? sp.name : 'Заправка', workerName: wk ? wk.name : null } });
                const newId = res && res.id;
                this.showRefill = false;
                if (newId == null) { await this.reloadCard(); return; }
                const ids = [newId];
                if (payKind === 'invoice') {
                    const r2 = await api('/api/documents', { method: 'POST', body: JSON.stringify({ client_id: this.cartCard.client_id, refill_ids: ids, date: this.todayStr() }),
                        offline: { kind: 'invoice', client: 'cart', clientId: this.cartCard.client_id, ids } });
                    this.toast('Заправка + счёт ✓', 'success');
                    await this.reloadCard();
                    if (r2 && r2.id) await this.openDoc(r2.id);
                    this.focusScan();
                    return;
                }
                const tr = this.cartTransfer;
                const res2 = await api('/api/documents/cash', { method: 'POST', body: JSON.stringify({ client_id: this.cartCard.client_id, refill_ids: ids, date: this.todayStr(), transfer: tr }),
                    offline: { kind: 'cash', client: 'cart', clientId: this.cartCard.client_id, ids } });
                const chek = res2 && res2.doc_number ? ' · чек №' + res2.doc_number : '';
                this.toast((tr ? 'Заправка ✓ перевод Коле' : 'Заправка ✓ в кассу') + chek, 'success');
                this.cartTransfer = false;
                await this.reloadCard();
                this.focusScan();
            } catch (e) { this.toast(e.message, 'error'); }
        },

        // ═══════════════ ПРАЙС-ЛИСТ ═══════════════
        async loadPricelist() {
            try {
                this.priceList = await api('/api/cartridges/pricelist?q=' + encodeURIComponent(this.priceQuery || '') + '&limit=80');
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async saveBasePrice(row) {
            const val = row.base_price === '' || row.base_price == null ? null : Number(row.base_price);
            try {
                await api('/api/cartridges/pricelist', { method: 'PUT', body: JSON.stringify({
                    model_id: row.model_id, spec_type_id: 1, price: val }) });
                row.source = val == null ? null : 'manual';
                this.toast(val == null ? 'Цена очищена' : 'Цена сохранена', 'success');
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async openModelPrices(row) {
            this.priceModel = null; this.priceModelLoading = true;
            try {
                this.priceModel = await api('/api/cartridges/pricelist/' + row.model_id);
            } catch (e) { this.toast(e.message, 'error'); }
            finally { this.priceModelLoading = false; }
        },
        async saveSpecPrice(r) {
            const val = r.price === '' || r.price == null ? null : Number(r.price);
            try {
                await api('/api/cartridges/pricelist', { method: 'PUT', body: JSON.stringify({
                    model_id: this.priceModel.model_id, spec_type_id: r.spec_type_id, price: val }) });
                this.toast(val == null ? 'Очищено' : 'Сохранено', 'success');
                if (r.spec_type_id === 1) this.loadPricelist();  // обновить базовую в списке
            } catch (e) { this.toast(e.message, 'error'); }
        },
        editRefill(r) {
            this.showRefill = true; this.showNewCart = false; this.priceSource = '';
            this.refillForm = {
                id: r.id, cartridge_id: r.cartridge_id, date: (r.date || '').slice(0, 10),
                spec_type_id: r.spec_type_id || 1,
                worker_id: r.worker_id || '', defect_id: r.defect_id || '', remark: r.remark || '',
                price: (r.price ?? ''),
            };
            this.scrollToForm();
        },
        async saveRefill() {
            if (!this.refillForm.cartridge_id) { this.toast('Выберите картридж', 'error'); return; }
            try {
                const body = {
                    date: this.refillForm.date,
                    spec_type_id: Number(this.refillForm.spec_type_id) || 1,
                    worker_id: this.refillForm.worker_id || null,
                    defect_id: this.refillForm.defect_id || null,
                    remark: this.refillForm.remark || null,
                    price: this.refillForm.price === '' || this.refillForm.price == null ? null : Number(this.refillForm.price),
                };
                const cid = Number(this.refillForm.cartridge_id);
                const cart = (this.cartCard?.cartridges || []).find(c => c.id === cid) || {};
                const sp = (this.cartRefs?.spec_types || []).find(s => s.id === (Number(this.refillForm.spec_type_id) || 1));
                const wk = (this.cartRefs?.workers || []).find(w => w.id === Number(this.refillForm.worker_id));
                const specName = sp ? sp.name : 'Заправка', workerName = wk ? wk.name : null;
                const cardId = this.cartCard.single ? this.cartCard.cartridge_id : null;
                if (this.refillForm.id) {
                    await api('/api/cartridges/refills/' + this.refillForm.id, { method: 'PUT', body: JSON.stringify(body),
                        offline: { kind: 'refill_edit', clientId: this.cartCard.client_id, cartCardId: cardId, id: this.refillForm.id, specName, workerName } });
                    this.toast('Заправка изменена', 'success');
                } else {
                    await api('/api/cartridges/' + cid + '/refills', { method: 'POST', body: JSON.stringify(body),
                        offline: { kind: 'refill_add', clientId: this.cartCard.client_id, cartCardId: cardId, cartridgeId: cid, barcode: cart.barcode, model: cart.model, specName, workerName } });
                    this.toast('Заправка добавлена', 'success');
                }
                this.showRefill = false;
                await this.reloadCard();
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async deleteRefill(r) {
            if (!confirm('Удалить заправку от ' + this.formatDate(r.date) + '?')) return;
            try {
                await api('/api/cartridges/refills/' + r.id, { method: 'DELETE',
                    offline: { kind: 'refill_del', clientId: this.cartCard.client_id, cartCardId: (this.cartCard.single ? this.cartCard.cartridge_id : null), id: r.id } });
                this.toast('Заправка удалена', 'success');
                await this.reloadCard();
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async createCartForClient() {
            if (!this.cartCard) return;
            try {
                const mdl = (this.cartRefs?.models || []).find(m => m.id === Number(this.newCart.model_id));
                const bc = (this.newCart.barcode || '').trim();
                const res = await api('/api/cartridges', { method: 'POST', body: JSON.stringify({
                    client_id: this.cartCard.client_id, model_id: this.newCart.model_id || null, barcode: bc || null,
                }), offline: { kind: 'cart_add', clientId: this.cartCard.client_id, model_id: this.newCart.model_id || null, model: mdl ? mdl.name : '', barcode: bc || null } });
                this.toast('Картридж добавлен: ' + res.barcode, 'success');
                this.showNewCart = false;
                this.newCart = { model_id: '', barcode: '' };
                await this.reloadCard();
                // pre-select the new cartridge for an immediate refill
                this.showRefill = true; this.priceSource = '';
                this.refillForm = { id: null, cartridge_id: res.id, date: this.todayStr(), spec_type_id: 1, worker_id: this.defaultWorker(), defect_id: '', remark: '', price: '' };
                this.prefillRefillPrice(); this.scrollToForm();
            } catch (e) { this.toast(e.message, 'error'); }
        },

        // ───────── печать листа штрих-кодов на самоклейку ─────────
        fmtBarcode(n) { return 'TPR' + String(n).padStart(6, '0'); },
        labelNum(code) { return parseInt(String(code).replace(/\D/g, ''), 10) || 0; },
        async openLabels() {
            this.showLabels = true;
            this.labelForm.start = null;   // авто-старт со следующего свободного номера
            this.recalcLabelFit();         // посчитать, сколько влезет на лист
            await this.reloadLabels();
        },
        // A4 за вычетом минимальных полей 5мм = 200×287мм. Колонки делят ширину РОВНО (без остатка справа).
        recalcLabelFit() {
            const USABLE_W = 200, USABLE_H = 287;
            const w = Math.max(20, Math.min(Number(this.labelForm.w) || 52, 200));
            const h = Math.max(10, Math.min(Number(this.labelForm.h) || 22, 140));
            this.labelForm.w = w; this.labelForm.h = h;
            const cols = Math.max(1, Math.round(USABLE_W / w));   // ближайшее число столбцов к желаемой ширине
            const rows = Math.max(1, Math.floor(USABLE_H / h));
            const actualW = Math.round((USABLE_W / cols) * 10) / 10;  // фактическая ширина после деления
            this.labelFit = { cols, rows, perPage: cols * rows, actualW };
        },
        // изменили размер → пересчитать вместимость и заполнить лист целиком
        async onLabelSizeChange() {
            this.recalcLabelFit();
            this.labelForm.count = this.labelFit.perPage;
            await this.reloadLabels();
        },
        labelStyle() { return `width:calc(100% / ${this.labelFit.cols} - 0.1mm);height:${this.labelForm.h}mm`; },
        async reloadLabels() {
            const count = Math.max(1, Math.min(Number(this.labelForm.count) || 24, 200));
            this.labelForm.count = count;
            let base;
            if (this.labelForm.start && this.labelForm.start > 0) {
                base = Math.floor(this.labelForm.start) - 1;
            } else {
                let serverNext = 0;
                try { const r = await api('/api/cartridges/labels/preview?count=1'); serverNext = r.start || 0; } catch (e) {}
                const localNext = (Number(localStorage.getItem('tp_label_last') || '0') || 0) + 1;
                base = Math.max(serverNext, localNext) - 1;
                if (base < 0) base = 0;
                this.labelForm.start = base + 1;
            }
            const text = this.labelForm.text || '';
            this.labels = Array.from({ length: count }, (_, i) => ({ code: this.fmtBarcode(base + 1 + i), text }));
            this.$nextTick(() => this.renderBarcodes());
        },
        applyLabelText() { const t = this.labelForm.text || ''; this.labels.forEach(l => l.text = t); },
        renderBarcodes(root = '#label-area') {
            if (!window.JsBarcode) { this.toast('Библиотека штрих-кодов не загрузилась', 'error'); return; }
            document.querySelectorAll(root + ' .bc').forEach(el => {
                try { window.JsBarcode(el, el.getAttribute('data-code'), { format: 'CODE128', width: 1.6, height: 42, fontSize: 13, margin: 4, displayValue: true }); } catch (e) {}
            });
        },
        async printLabels() {
            if (!this.labels.length) return;
            this.printHtml = '';   // на всякий случай — чтобы рядом не печатался документ
            const cols = this.labelFit.cols, h = this.labelForm.h;
            const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            // строим отдельную область печати в нормальном потоке (надёжно пагинируется на N листов)
            const root = document.getElementById('label-print-root');
            root.innerHTML = this.labels.map(l =>
                `<div class="lbl" style="width:calc(100% / ${cols} - 0.1mm);height:${h}mm"><svg class="bc" data-code="${esc(l.code)}"></svg><div class="lt">${esc(l.text || '')}</div></div>`
            ).join('');
            this.renderBarcodes('#label-print-root');
            await this.$nextTick();
            const last = this.labelNum(this.labels[this.labels.length - 1].code);
            window.print();
            setTimeout(() => { root.innerHTML = ''; }, 800);   // очистить после печати
            if (last) {
                localStorage.setItem('tp_label_last', String(last));
                try { await api('/api/cartridges/labels/commit?last=' + last, { method: 'POST' }); } catch (e) {}
            }
        },

        // ───────── selection → invoice (выписка) ─────────
        toggleRefillSel(r) {
            if (r.is_billed) { this.toast('Заправка уже выписана', 'error'); return; }
            const i = this.selectedRefills.indexOf(r.id);
            if (i >= 0) this.selectedRefills.splice(i, 1);
            else this.selectedRefills.push(r.id);
        },
        unbilledRefills() { return (this.cartCard?.refills || []).filter(r => !r.is_billed); },
        allUnbilledSelected() {
            const u = this.unbilledRefills();
            return u.length > 0 && u.every(r => this.selectedRefills.includes(r.id));
        },
        toggleSelectAllRefills() {
            if (this.allUnbilledSelected()) this.selectedRefills = [];
            else this.selectedRefills = this.unbilledRefills().map(r => r.id);
        },
        async createInvoice() {
            if (!this.selectedRefills.length) { this.toast('Не выбрано ни одной заправки', 'error'); return; }
            try {
                const ids = this.selectedRefills.slice();
                const res = await api('/api/documents', { method: 'POST', body: JSON.stringify({
                    client_id: this.cartCard.client_id, refill_ids: ids, date: this.todayStr(),
                }), offline: { kind: 'invoice', client: 'cart', clientId: this.cartCard.client_id, ids } });
                this.toast(res._offline ? 'Счёт создан (офлайн — номер после синхронизации)' : 'Счёт создан', 'success');
                this.selectedRefills = [];
                await this.reloadCard();
                await this.openDoc(res.id);
            } catch (e) { this.toast(e.message, 'error'); }
        },

        // ───────── documents (счёт/акт/накладная/чек) ─────────
        async loadCartDocs(clientId) {
            try { this.cartDocs = await api('/api/documents?client_id=' + clientId) || []; }
            catch (e) { this.cartDocs = []; }
        },
        async openDoc(docId) {
            try {
                this.doc = await api('/api/documents/' + docId);
                this.docDateEdit = (this.doc.date || '').slice(0, 10);
                this.showDoc = true; this.ensureOrg();
            } catch (e) { this.toast(e.message, 'error'); }
        },
        closeDoc() { this.showDoc = false; this.doc = null; },
        async saveDocItemPrice(item) {
            if (!this.needOnline()) return;
            try {
                const res = await api('/api/documents/' + this.doc.id + '/items/' + item.id,
                    { method: 'PUT', body: JSON.stringify({ name: item.name, price: Number(item.price) || 0, qty: Number(item.qty) || 1 }) });
                item.total = res.item_total;
                this.doc.total = res.doc_total;
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async addDocItem() {
            if (!this.needOnline()) return;
            const name = (this.docNewItem.name || '').trim();
            if (!name) { this.toast('Укажите наименование', 'error'); return; }
            try {
                await api('/api/documents/' + this.doc.id + '/items', { method: 'POST', body: JSON.stringify({
                    name, qty: Number(this.docNewItem.qty) || 1, price: Number(this.docNewItem.price) || 0 }) });
                this.docNewItem = { name: '', qty: 1, price: '' };
                await this.openDoc(this.doc.id);
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async deleteDocItem(item) {
            if (!this.needOnline()) return;
            if (!confirm('Удалить позицию «' + item.name + '»?')) return;
            try {
                await api('/api/documents/' + this.doc.id + '/items/' + item.id, { method: 'DELETE' });
                await this.openDoc(this.doc.id);
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async applyDocDate() {
            if (!this.needOnline()) return;
            const d = (this.docDateEdit || '').slice(0, 10);
            const cur = (this.doc.date || '').slice(0, 10);
            if (!d || d === cur) return;
            if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) { this.toast('Неверная дата', 'error'); return; }
            try {
                await api('/api/documents/' + this.doc.id, { method: 'PUT', body: JSON.stringify({ date: d }) });
                await this.openDoc(this.doc.id);
                this.toast('Дата счёта изменена на ' + this.formatDate(d), 'success');
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async reissueDoc() {
            if (!this.needOnline()) return;
            if (!confirm('Перевыпустить документ? Будет присвоен новый номер и сегодняшняя дата.')) return;
            try {
                const r = await api('/api/documents/' + this.doc.id + '/reissue', { method: 'PUT' });
                await this.openDoc(this.doc.id);
                this.toast('Перевыпущен: №' + (r.number || ''), 'success');
            } catch (e) { this.toast(e.message, 'error'); }
        },
        // поиск документа по номеру счёта
        async searchDocs() {
            const q = (this.docSearch || '').trim();
            if (q.length < 1) { this.docSearchResults = []; return; }
            try { this.docSearchResults = await api('/api/documents/search?q=' + encodeURIComponent(q)) || []; }
            catch (e) { this.docSearchResults = []; }
        },
        openDocFromSearch(d) {
            this.docSearch = ''; this.docSearchResults = [];
            this.openDoc(d.id);
        },

        // ═══════════════ РАБОТЫ (ремонт техники) ═══════════════
        async loadWorkRefs() {
            try { this.workRefs = await api('/api/works/refs') || { work_types: [], workers: [] }; }
            catch (e) { console.error('workRefs', e); }
        },
        // стартовая пустая карточка работы (сразу при открытии раздела) — несколько позиций (строк)
        startWorkNew() {
            this.workView = 'new'; this.workCard = null; this.showWork = false; this.selectedWorks = []; this.workTransfer = false;
            this.workClients = [];
            this.workForm = { id: null, client_id: null, client_name: '', date: this.todayStr(), worker_id: '',
                              rows: [{ title: '', device_label: '', price: '' }] };
        },
        addWorkRow() { this.workForm.rows.push({ title: '', device_label: '', price: '' }); },
        removeWorkRow(i) { if (this.workForm.rows.length > 1) this.workForm.rows.splice(i, 1); },
        workRowsTotal() { return (this.workForm.rows || []).reduce((s, r) => s + (Number(r.price) || 0), 0); },
        // сохранить ВСЕ позиции как отдельные работы клиента, затем открыть карточку
        async saveWorkNew() {
            const rows = (this.workForm.rows || []).filter(r => (r.title || '').trim());
            if (!rows.length) { this.toast('Добавьте хотя бы одну работу', 'error'); return; }
            let clientId = this.workForm.client_id;
            if (!clientId) { clientId = await this._resolveClientId(this.workForm.client_name); if (!clientId) return; }
            const wk = (this.workRefs?.workers || []).find(w => w.id === Number(this.workForm.worker_id));
            const workerName = wk ? wk.name : null;
            try {
                for (const r of rows) {
                    const body = {
                        client_id: clientId, title: r.title.trim(),
                        device_label: (r.device_label || '').trim() || null,
                        date: this.workForm.date,
                        worker_id: this.workForm.worker_id || null,
                        price: r.price === '' || r.price == null ? null : Number(r.price),
                        remark: null,
                    };
                    await api('/api/works', { method: 'POST', body: JSON.stringify(body),
                        offline: { kind: 'work_add', clientId, workerName } });
                }
                this.toast(rows.length > 1 ? ('Добавлено работ: ' + rows.length) : 'Работа добавлена', 'success');
                await this.openWorkCard(clientId);
                this.workView = this.workCard ? 'card' : 'new';
            } catch (e) { this.toast(e.message, 'error'); }
        },
        // автоподбор клиента в стартовой форме
        async wcSearch() {
            this.workForm.client_id = null;   // ручной ввод сбрасывает выбор
            const q = (this.workForm.client_name || '').trim();
            if (q.length < 1) { this.workClients = []; return; }
            try { this.workClients = await api('/api/works/clients?q=' + encodeURIComponent(q)) || []; }
            catch (e) { this.workClients = []; }
        },
        pickWorkClient(c) {
            this.workForm.client_id = c.client_id; this.workForm.client_name = c.client;
            this.workClients = [];
        },
        // найти id клиента по имени или создать нового
        async _resolveClientId(name) {
            name = (name || '').trim();
            if (!name) { this.toast('Укажите клиента', 'error'); return null; }
            try {
                const hits = await api('/api/works/clients?q=' + encodeURIComponent(name)) || [];
                const exact = hits.find(c => (c.client || '').trim().toLowerCase() === name.toLowerCase());
                if (exact) return exact.client_id;
            } catch (e) {}
            if (!this.needOnline()) { this.toast('Новый клиент создаётся только онлайн', 'error'); return null; }
            try { const c = await api('/api/clients', { method: 'POST', body: JSON.stringify({ name }) }); return c.id; }
            catch (e) { this.toast(e.message, 'error'); return null; }
        },
        async openWorkCard(clientId) {
            try {
                this.workCard = await api('/api/works/client/' + clientId);
            } catch (e) { this.toast(e.message, 'error'); return; }
            this.showWork = false; this.selectedWorks = [];
            try { this.workDocs = await api('/api/documents?client_id=' + clientId) || []; }
            catch (e) { this.workDocs = []; }
        },
        startWork() {
            this.showWork = true;
            this.workForm = { id: null, client_id: this.workCard?.client_id || null, client_name: this.workCard?.client || '', title: '', device_label: '', date: this.todayStr(), worker_id: '', price: '', remark: '' };
        },
        editWork(w) {
            this.showWork = true;
            this.workForm = { id: w.id, client_id: this.workCard?.client_id || null, client_name: this.workCard?.client || '', title: w.title || '', device_label: w.device_label || '', date: (w.date || '').slice(0, 10), worker_id: w.worker_id || '', price: (w.price ?? ''), remark: w.remark || '' };
        },
        pickWorkType(name) { if (name && !this.workForm.title) this.workForm.title = name; },
        async saveWork() {
            if (!this.workForm.title) { this.toast('Укажите вид работы', 'error'); return; }
            let clientId = this.workForm.client_id || this.workCard?.client_id;
            if (!clientId) { clientId = await this._resolveClientId(this.workForm.client_name); if (!clientId) return; }
            try {
                const body = {
                    client_id: clientId,
                    title: this.workForm.title,
                    device_label: this.workForm.device_label || null,
                    date: this.workForm.date,
                    worker_id: this.workForm.worker_id || null,
                    price: this.workForm.price === '' ? null : Number(this.workForm.price),
                    remark: this.workForm.remark || null,
                };
                const wk = (this.workRefs?.workers || []).find(w => w.id === Number(this.workForm.worker_id));
                const workerName = wk ? wk.name : null;
                if (this.workForm.id) {
                    await api('/api/works/' + this.workForm.id, { method: 'PUT', body: JSON.stringify(body),
                        offline: { kind: 'work_edit', clientId, id: this.workForm.id, workerName } });
                    this.toast('Работа изменена', 'success');
                } else {
                    await api('/api/works', { method: 'POST', body: JSON.stringify(body),
                        offline: { kind: 'work_add', clientId, workerName } });
                    this.toast('Работа добавлена', 'success');
                }
                this.showWork = false;
                await this.openWorkCard(clientId);     // сначала грузим карточку…
                this.workView = this.workCard ? 'card' : 'new';   // …потом показываем (без пустого экрана)
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async deleteWork(w) {
            if (!confirm('Удалить работу «' + w.title + '»?')) return;
            try {
                await api('/api/works/' + w.id, { method: 'DELETE',
                    offline: { kind: 'work_del', clientId: this.workCard.client_id, id: w.id } });
                this.toast('Работа удалена', 'success');
                await this.openWorkCard(this.workCard.client_id);
            } catch (e) { this.toast(e.message, 'error'); }
        },
        toggleWorkSel(w) {
            if (w.is_billed) { this.toast('Работа уже выписана', 'error'); return; }
            const i = this.selectedWorks.indexOf(w.id);
            if (i >= 0) this.selectedWorks.splice(i, 1); else this.selectedWorks.push(w.id);
        },
        unbilledWorks() { return (this.workCard?.jobs || []).filter(w => !w.is_billed); },
        allUnbilledWorksSelected() { const u = this.unbilledWorks(); return u.length > 0 && u.every(w => this.selectedWorks.includes(w.id)); },
        toggleSelectAllWorks() { if (this.allUnbilledWorksSelected()) this.selectedWorks = []; else this.selectedWorks = this.unbilledWorks().map(w => w.id); },
        async createWorkInvoice() {
            if (!this.selectedWorks.length) { this.toast('Не выбрано ни одной работы', 'error'); return; }
            try {
                const ids = this.selectedWorks.slice();
                const res = await api('/api/documents/works', { method: 'POST', body: JSON.stringify({ client_id: this.workCard.client_id, work_ids: ids, date: this.todayStr() }),
                    offline: { kind: 'invoice', client: 'work', clientId: this.workCard.client_id, ids } });
                this.toast(res._offline ? 'Счёт создан (офлайн — номер после синхронизации)' : 'Счёт создан', 'success');
                this.selectedWorks = [];
                await this.openWorkCard(this.workCard.client_id);
                await this.openDoc(res.id);
            } catch (e) { this.toast(e.message, 'error'); }
        },

        // ───────── документы: на основании / провести / оплата / удаление / печать ─────────
        needOnline() { if (!navigator.onLine) { this.toast('Действие доступно только онлайн', 'error'); return false; } return true; },
        docIsGoods() { const it = this.doc?.items || []; return it.length > 0 && it.every(x => x.kind === 'goods'); },
        async deriveDoc(type) {
            const ex = (this.doc?.children || []).find(c => c.doc_type === type);
            if (ex) { await this.openDoc(ex.id); return; }   // уже создан — просто открыть
            try {
                const r = await api('/api/documents/' + this.doc.id + '/derive', { method: 'POST', body: JSON.stringify({ doc_type: type, date: this.todayStr() }),
                    offline: { kind: 'derive', doc_type: type, parentId: this.doc.id, clientId: this.doc.client_id } });
                this.toast(r._offline ? 'Документ создан (офлайн)' : 'Документ создан', 'success');
                await this.openDoc(this.doc.id);
                await this.openDoc(r.id);   // показать созданный
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async finalizeDoc(silent) {
            try {
                const r = await api('/api/documents/' + this.doc.id + '/finalize', { method: 'PUT',
                    offline: { kind: 'finalize' } });
                // товарный чек проводится наличными — про это говорим всегда, даже при печати
                if (r.cash) this.toast('Проведено в ЦРМ: наличные, оплачено', 'success');
                else if (r.to_cash) this.toast('Счёт переведён в наличные и отмечен оплаченным', 'success');
                else if (!silent) this.toast(r._offline ? 'Будет проведено в ЦРМ после синхронизации' : (r.already ? 'Уже проведено в ЦРМ' : 'Проведено в ЦРМ'), 'success');
                if (!r._offline) await this.openDoc(this.doc.id);
                return true;
            } catch (e) { if (!silent) this.toast(e.message, 'error'); return false; }
        },
        async markDocPaid() {
            if (!this.needOnline()) return;
            try {
                await api('/api/documents/' + this.doc.id + '/mark-paid', { method: 'PUT' });
                this.toast('Отмечено как оплачено', 'success');
                await this.openDoc(this.doc.id);
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async removeDebt() {
            if (!this.needOnline()) return;
            if (!confirm('Убрать запись из ЦРМ по этому счёту? Документ останется, позиции — выписанными.')) return;
            try {
                await api('/api/documents/' + this.doc.id + '/remove-debt', { method: 'PUT' });
                this.toast('Запись убрана из ЦРМ', 'success');
                await this.openDoc(this.doc.id);
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async _reloadActiveCard() {
            if (this.cartCard) await this.reloadCard();
            if (this.workCard) await this.openWorkCard(this.workCard.client_id);
            if (this.goodsCard) await this.openGoodsCard(this.goodsCard.client_id);
        },
        async deleteDoc() {
            if (!this.needOnline()) return;
            const derived = !!this.doc?.parent_id;
            const msg = derived ? 'Удалить этот документ?'
                : 'Удалить счёт и все связанные документы? Позиции (заправки/работы/товар) вернутся в невыписанные, запись из ЦРМ уберётся.';
            if (!confirm(msg)) return;
            try {
                const parentId = this.doc?.parent_id;
                await api('/api/documents/' + this.doc.id, { method: 'DELETE' });
                this.toast('Удалено', 'success');
                if (derived && parentId) { await this.openDoc(parentId); }
                else { this.closeDoc(); }
                await this._reloadActiveCard();
            } catch (e) { this.toast(e.message, 'error'); }
        },

        // ───────── реквизиты организации ─────────
        async ensureOrg() { if (!this.org || !this.org.name) { try { this.org = await api('/api/org') || {}; } catch (e) {} } },
        async loadOrg() { try { this.org = await api('/api/org') || {}; } catch (e) { this.toast(e.message, 'error'); } },
        async loadAudit() { try { this.auditLog = await api('/api/audit?limit=300') || []; } catch (e) { this.toast(e.message, 'error'); } },
        async saveOrg() {
            try { this.org = await api('/api/org', { method: 'PUT', body: JSON.stringify(this.org) }); this.toast('Реквизиты сохранены', 'success'); }
            catch (e) { this.toast(e.message, 'error'); }
        },

        // ───────── печать документа (формат 1С) ─────────
        async printDoc() {
            await this.ensureOrg();
            await this.finalizeDoc(true);   // печать = долг в CRM (один раз, идемпотентно)
            let fresh;
            try { fresh = await api('/api/documents/' + this.doc.id); }
            catch (e) { fresh = this.doc; }   // офлайн — печатаем из текущего (кэш)
            this.printHtml = this.buildDocHtml(fresh, this.org);
            const prevTitle = document.title;
            document.title = (fresh.type_label || 'Документ') + ' №' + (fresh.number || '');
            this.$nextTick(() => { window.onafterprint = () => { this.printHtml = ''; document.title = prevTitle; window.onafterprint = null; }; window.print(); });
        },
        rublesToWords(n) {
            n = Math.round(Number(n) || 0);
            const rub = Math.floor(n), kop = Math.round((n - rub) * 100);
            const ones = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять'];
            const onesF = ['', 'одна', 'две', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять'];
            const teens = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать'];
            const tens = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто'];
            const hund = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот', 'семьсот', 'восемьсот', 'девятьсот'];
            function trio(num, fem) {
                let s = []; const h = Math.floor(num / 100), t = Math.floor((num % 100) / 10), o = num % 10;
                if (h) s.push(hund[h]);
                if (t === 1) s.push(teens[o]);
                else { if (t) s.push(tens[t]); if (o) s.push(fem ? onesF[o] : ones[o]); }
                return s.join(' ');
            }
            function decl(num, forms) { const n100 = num % 100, n10 = num % 10; if (n100 > 10 && n100 < 20) return forms[2]; if (n10 === 1) return forms[0]; if (n10 >= 2 && n10 <= 4) return forms[1]; return forms[2]; }
            let res = [];
            const mil = Math.floor(rub / 1000000), thou = Math.floor((rub % 1000000) / 1000), rest = rub % 1000;
            if (mil) res.push(trio(mil, false) + ' ' + decl(mil, ['миллион', 'миллиона', 'миллионов']));
            if (thou) res.push(trio(thou, true) + ' ' + decl(thou, ['тысяча', 'тысячи', 'тысяч']));
            if (rest) res.push(trio(rest, false));
            let words = res.join(' ').trim();
            if (!words) words = 'ноль';
            words = words.charAt(0).toUpperCase() + words.slice(1);
            return words + ' ' + decl(rub, ['рубль', 'рубля', 'рублей']) + ' ' + String(kop).padStart(2, '0') + ' ' + decl(kop, ['копейка', 'копейки', 'копеек']);
        },
        buildDocHtml(doc, org) {
            if (doc && !doc.number && (doc._offline || doc.id < 0)) doc = { ...doc, number: '(черновик)' };
            const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            const money = v => (Number(v) || 0).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const d = new Date((doc.date || '') + 'T00:00:00');
            const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
            const dateStr = isNaN(d) ? (doc.date || '') : ('«' + d.getDate() + '» ' + months[d.getMonth()] + ' ' + d.getFullYear() + ' г.');
            const t = doc.doc_type, items = doc.items || [];
            const total = items.reduce((s, it) => s + (Number(it.total) || 0), 0);
            const orgReq = [org.inn ? 'ИНН ' + esc(org.inn) : '', org.kpp ? 'КПП ' + esc(org.kpp) : ''].filter(Boolean).join(', ');
            const cr = doc.client_req || {};
            const buyerReq = [cr.inn ? 'ИНН ' + esc(cr.inn) : '', cr.kpp ? 'КПП ' + esc(cr.kpp) : ''].filter(Boolean).join(', ');
            const supplier = `<b>${esc(org.name)}</b>${orgReq ? ', ' + orgReq : ''}${org.address ? ', ' + esc(org.address) : ''}${org.phones ? ', тел.: ' + esc(org.phones) : ''}`;
            const buyerFull = `<b>${esc(cr.full_name || doc.client || '')}</b>${buyerReq ? ', ' + buyerReq : ''}${cr.address ? ', ' + esc(cr.address) : ''}`;
            const rows = items.map((it, i) => `<tr><td class="c">${i + 1}</td><td>${esc(it.name)}</td><td class="c">${Number(it.qty) || 0}</td><td class="c">${esc(it.unit || 'шт')}</td><td class="r">${money(it.price)}</td><td class="r">${money(it.total)}</td></tr>`).join('');
            const itemsTable = `<table class="items"><thead><tr><th style="width:26px">№</th><th>Наименование</th><th style="width:52px">Кол-во</th><th style="width:38px">Ед.</th><th style="width:80px">Цена</th><th style="width:92px">Сумма</th></tr></thead><tbody>${rows}</tbody></table>`;
            const totalsBlock = `<table class="tot"><tr><td>Итого:</td><td class="r">${money(total)}</td></tr><tr><td>Без налога (НДС):</td><td class="r">—</td></tr><tr><td><b>Всего к оплате:</b></td><td class="r"><b>${money(total)}</b></td></tr></table>`;
            const wordsLine = `<div class="words">Всего наименований ${items.length}, на сумму <b>${money(total)}</b> руб.<br><b>${esc(this.rublesToWords(total))}</b></div>`;
            const dir = esc(org.director || '');

            if (t === 'invoice') {
                const bank = `<table class="bank">
                    <tr><td rowspan="2" class="bn"><b>${esc(org.bank_name || '')}</b><div class="sub">Банк получателя</div></td><td class="bl">БИК</td><td class="bv">${esc(org.bank_bik || '')}</td></tr>
                    <tr><td class="bl">Сч. №</td><td class="bv">${esc(org.bank_corr || '')}</td></tr>
                    <tr><td class="bn">ИНН ${esc(org.inn || '')}&nbsp;&nbsp;КПП ${esc(org.kpp || '')}</td><td class="bl" rowspan="2">Сч. №</td><td class="bv" rowspan="2"><b>${esc(org.bank_account || '')}</b></td></tr>
                    <tr><td class="bn"><b>${esc(org.name || '')}</b><div class="sub">Получатель</div></td></tr></table>`;
                return `<div class="doc">${bank}
                    <h1>Счёт на оплату № ${esc(doc.number || '')} от ${dateStr}</h1><div class="rule"></div>
                    <table class="parties"><tr><td class="pl">Поставщик<br>(Исполнитель):</td><td>${supplier}</td></tr>
                    <tr><td class="pl">Покупатель<br>(Заказчик):</td><td>${buyerFull}</td></tr>
                    <tr><td class="pl">Основание:</td><td></td></tr></table>
                    ${itemsTable}${totalsBlock}${wordsLine}
                    <div class="sign"><div>Руководитель _______________ /&nbsp;${dir}&nbsp;/</div><div>Бухгалтер _______________ /&nbsp;${dir}&nbsp;/</div></div>
                    <div class="mp">М.П.</div></div>`;
            }
            if (t === 'act') {
                const itemsAct = `<table class="items"><thead><tr><th style="width:26px">№</th><th>Наименование работ, услуг</th><th style="width:52px">Кол-во</th><th style="width:38px">Ед.</th><th style="width:80px">Цена</th><th style="width:92px">Сумма</th></tr></thead><tbody>${rows}</tbody></table>`;
                return `<div class="doc">
                    <h1 class="actttl">Акт выполненных работ № ${esc(doc.number || '')} от ${dateStr}</h1><div class="rule"></div>
                    <table class="parties"><tr><td class="pl">Исполнитель:</td><td>${supplier}</td></tr><tr><td class="pl">Заказчик:</td><td>${buyerFull}</td></tr></table>
                    ${itemsAct}
                    <div class="words"><b>Всего оказано услуг на сумму: ${money(total)} руб.</b><br>${esc(this.rublesToWords(total))}<br>В том числе НДС: Без НДС</div>
                    <p class="apre">Работы выполнены в полном объёме, в установленные сроки и с надлежащим качеством. Стороны претензий друг к другу не имеют.</p>
                    <table class="asign"><tr><td>Исполнитель _______________ /&nbsp;${dir}&nbsp;/<br><span class="sub">М.П.</span></td><td>Заказчик _______________ /</td></tr></table></div>`;
            }
            const titleMap = { act: 'Акт № ', waybill: 'Товарная накладная № ', receipt: 'Товарный чек № ' };
            let pl1 = 'Исполнитель:', pl2 = 'Заказчик:';
            if (t === 'waybill') { pl1 = 'Поставщик:'; pl2 = 'Грузополучатель:'; }
            if (t === 'receipt') { pl1 = 'Продавец:'; pl2 = 'Покупатель:'; }
            let sign;
            if (t === 'act') sign = `<div class="words">Вышеперечисленные работы выполнены полностью и в срок. Заказчик претензий не имеет.</div><div class="sign"><div>Исполнитель _______________ /&nbsp;${dir}&nbsp;/</div><div>Заказчик _______________ /</div></div>`;
            else if (t === 'waybill') sign = `<div class="sign"><div>Отпустил _______________ /&nbsp;${dir}&nbsp;/</div><div>Получил _______________ /</div></div>`;
            else sign = `<div class="sign"><div>Продавец _______________ /&nbsp;${dir}&nbsp;/</div></div><div class="mp">М.П.</div>`;
            return `<div class="doc"><h1>${(titleMap[t] || esc(doc.type_label) + ' № ')}${esc(doc.number || '')} от ${dateStr}</h1><div class="rule"></div>
                <table class="parties"><tr><td class="pl">${pl1}</td><td>${supplier}</td></tr><tr><td class="pl">${pl2}</td><td>${buyerFull}</td></tr></table>
                ${itemsTable}${totalsBlock}${wordsLine}${sign}</div>`;
        },

        // ═══════════════ ТОВАР (продажа) ═══════════════
        // стартовая пустая карточка продажи товара
        startSaleNew() {
            this.goodsView = 'new'; this.goodsCard = null; this.showSale = false; this.selectedSales = []; this.goodsTransfer = false;
            this.goodsClients = []; this.goodsCatalog = []; this.activeGoodsRow = -1;
            this.saleForm = { id: null, client_id: null, client_name: '', date: this.todayStr(),
                              rows: [{ name: '', good_id: null, qty: 1, price: '' }] };
        },
        addSaleRow() { this.saleForm.rows.push({ name: '', good_id: null, qty: 1, price: '' }); },
        removeSaleRow(i) { if (this.saleForm.rows.length > 1) this.saleForm.rows.splice(i, 1); },
        saleRowsTotal() { return (this.saleForm.rows || []).reduce((s, r) => s + (Number(r.price) || 0) * (Number(r.qty) || 1), 0); },
        // поиск по каталогу 1С для конкретной строки
        async gCatSearch(i) {
            this.activeGoodsRow = i;
            const row = this.saleForm.rows[i];
            row.good_id = null;
            const q = (row.name || '').trim();
            if (q.length < 2) { this.goodsCatalog = []; return; }
            try { this.goodsCatalog = await api('/api/goods/catalog?q=' + encodeURIComponent(q)) || []; }
            catch (e) { this.goodsCatalog = []; }
        },
        pickGoodForRow(i, g) {
            const row = this.saleForm.rows[i];
            row.good_id = g.id; row.name = g.name;
            if (g.last_price != null) row.price = g.last_price;
            this.goodsCatalog = []; this.activeGoodsRow = -1;
        },
        async saveSaleNew() {
            const rows = (this.saleForm.rows || []).filter(r => (r.name || '').trim());
            if (!rows.length) { this.toast('Добавьте хотя бы один товар', 'error'); return; }
            let clientId = this.saleForm.client_id;
            if (!clientId) { clientId = await this._resolveClientId(this.saleForm.client_name); if (!clientId) return; }
            try {
                for (const r of rows) {
                    const body = { client_id: clientId, good_id: r.good_id || null,
                        name: r.name.trim(), qty: Number(r.qty) || 1,
                        price: r.price === '' || r.price == null ? null : Number(r.price),
                        date: this.saleForm.date, remark: null };
                    await api('/api/goods/sale', { method: 'POST', body: JSON.stringify(body),
                        offline: { kind: 'sale_add', clientId } });
                }
                this.toast(rows.length > 1 ? ('Добавлено позиций: ' + rows.length) : 'Товар добавлен', 'success');
                await this.openGoodsCard(clientId);
                this.goodsView = this.goodsCard ? 'card' : 'new';
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async gcSearch() {
            this.saleForm.client_id = null;
            const q = (this.saleForm.client_name || '').trim();
            if (q.length < 1) { this.goodsClients = []; return; }
            try { this.goodsClients = await api('/api/goods/clients?q=' + encodeURIComponent(q)) || []; }
            catch (e) { this.goodsClients = []; }
        },
        pickGoodsClient(c) {
            this.saleForm.client_id = c.client_id; this.saleForm.client_name = c.client;
            this.goodsClients = [];
        },
        async openGoodsCard(id) {
            try {
                this.goodsCard = await api('/api/goods/client/' + id);
            } catch (e) { this.toast(e.message, 'error'); return; }
            this.showSale = false; this.selectedSales = [];
            try { this.goodsDocs = await api('/api/documents?client_id=' + id) || []; }
            catch (e) { this.goodsDocs = []; }
        },
        startSale() {
            this.showSale = true;
            this.saleForm = { id: null, client_id: this.goodsCard?.client_id || null, client_name: this.goodsCard?.client || '', good_id: null, name: '', qty: 1, price: '', date: this.todayStr(), remark: '' };
            this.goodsCatQuery = ''; this.goodsCatalog = [];
        },
        editSale(s) {
            this.showSale = true;
            this.saleForm = { id: s.id, client_id: this.goodsCard?.client_id || null, client_name: this.goodsCard?.client || '', good_id: s.good_id, name: s.name, qty: s.qty || 1, price: (s.price ?? ''), date: (s.date || '').slice(0, 10), remark: s.remark || '' };
            this.goodsCatQuery = ''; this.goodsCatalog = [];
        },
        async searchGoodsCatalog() {
            if (!this.goodsCatQuery || this.goodsCatQuery.length < 2) { this.goodsCatalog = []; return; }
            try { this.goodsCatalog = await api('/api/goods/catalog?q=' + encodeURIComponent(this.goodsCatQuery)) || []; }
            catch (e) {}
        },
        pickGood(g) {
            this.saleForm.good_id = g.id; this.saleForm.name = g.name;
            if (g.last_price != null) this.saleForm.price = g.last_price;
            this.goodsCatQuery = ''; this.goodsCatalog = [];
        },
        async saveSale() {
            if (!this.saleForm.name) { this.toast('Укажите товар', 'error'); return; }
            let clientId = this.saleForm.client_id || this.goodsCard?.client_id;
            if (!clientId) { clientId = await this._resolveClientId(this.saleForm.client_name); if (!clientId) return; }
            try {
                const body = { client_id: clientId, good_id: this.saleForm.good_id || null,
                    name: this.saleForm.name, qty: Number(this.saleForm.qty) || 1,
                    price: this.saleForm.price === '' ? null : Number(this.saleForm.price),
                    date: this.saleForm.date, remark: this.saleForm.remark || null };
                if (this.saleForm.id) { await api('/api/goods/sale/' + this.saleForm.id, { method: 'PUT', body: JSON.stringify(body),
                    offline: { kind: 'sale_edit', clientId, id: this.saleForm.id } }); this.toast('Изменено', 'success'); }
                else { await api('/api/goods/sale', { method: 'POST', body: JSON.stringify(body),
                    offline: { kind: 'sale_add', clientId } }); this.toast('Товар добавлен', 'success'); }
                this.showSale = false;
                await this.openGoodsCard(clientId);
                this.goodsView = this.goodsCard ? 'card' : 'new';
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async deleteSale(s) {
            if (!confirm('Удалить «' + s.name + '»?')) return;
            try { await api('/api/goods/sale/' + s.id, { method: 'DELETE',
                    offline: { kind: 'sale_del', clientId: this.goodsCard.client_id, id: s.id } }); this.toast('Удалено', 'success'); await this.openGoodsCard(this.goodsCard.client_id); }
            catch (e) { this.toast(e.message, 'error'); }
        },
        toggleSaleSel(s) {
            if (s.is_billed) { this.toast('Уже выписано', 'error'); return; }
            const i = this.selectedSales.indexOf(s.id);
            if (i >= 0) this.selectedSales.splice(i, 1); else this.selectedSales.push(s.id);
        },
        unbilledSales() { return (this.goodsCard?.sales || []).filter(s => !s.is_billed); },
        allUnbilledSalesSelected() { const u = this.unbilledSales(); return u.length > 0 && u.every(s => this.selectedSales.includes(s.id)); },
        toggleSelectAllSales() { if (this.allUnbilledSalesSelected()) this.selectedSales = []; else this.selectedSales = this.unbilledSales().map(s => s.id); },
        saleSum(s) { return (Number(s.price) || 0) * (Number(s.qty) || 1); },
        async createCashGoods() {
            if (!this.selectedSales.length) { this.toast('Не выбрано', 'error'); return; }
            const total = (this.goodsCard?.sales || []).filter(s => this.selectedSales.includes(s.id)).reduce((a, s) => a + this.saleSum(s), 0);
            const tr = this.goodsTransfer;
            const msg = tr ? ('Перевод Коле на карту ' + total + ' ₽ — записать в его зарплату?')
                           : ('Внести в кассу (CRM) ' + total + ' ₽ без документа?');
            if (!confirm(msg)) return;
            try {
                const ids = this.selectedSales.slice();
                await api('/api/documents/cash-goods', { method: 'POST', body: JSON.stringify({ client_id: this.goodsCard.client_id, sale_ids: ids, date: this.todayStr(), transfer: tr }),
                    offline: { kind: 'cash', client: 'goods', clientId: this.goodsCard.client_id, ids } });
                this.toast(tr ? ('Перевод записан, в зарплату Коле: ' + total + ' ₽') : ('Внесено в кассу: ' + total + ' ₽'), 'success');
                this.selectedSales = []; this.goodsTransfer = false;
                await this.openGoodsCard(this.goodsCard.client_id);
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async createGoodsInvoice() {
            if (!this.selectedSales.length) { this.toast('Не выбрано', 'error'); return; }
            try {
                const ids = this.selectedSales.slice();
                const res = await api('/api/documents/goods', { method: 'POST', body: JSON.stringify({ client_id: this.goodsCard.client_id, sale_ids: ids, date: this.todayStr() }),
                    offline: { kind: 'invoice', client: 'goods', clientId: this.goodsCard.client_id, ids } });
                this.toast(res._offline ? 'Счёт создан (офлайн — номер после синхронизации)' : 'Счёт создан', 'success');
                this.selectedSales = [];
                await this.openGoodsCard(this.goodsCard.client_id);
                await this.openDoc(res.id);
            } catch (e) { this.toast(e.message, 'error'); }
        },

        // ───────── журналы (плоские списки по дате) ─────────
        async loadCartJournal(reset = true) {
            if (reset) { this.cartJrnOff = 0; this.cartJournal = []; this.cartJrnSum = { count: 0, sum: 0 }; }
            try {
                const qs = `q=${encodeURIComponent(this.cartJrnQ)}&billed=${this.cartJrnBilled}&period=${this.cartJrnPeriod}`;
                const rows = await api(`/api/cartridges/journal?${qs}&limit=100&offset=${this.cartJrnOff}`) || [];
                this.cartJournal = reset ? rows : this.cartJournal.concat(rows);
                this.cartJrnMore = rows.length === 100;
                if (reset) {
                    try { this.cartJrnSum = await api(`/api/cartridges/journal/summary?${qs}`) || { count: 0, sum: 0 }; }
                    catch (e) { this.cartJrnSum = { count: 0, sum: 0 }; }
                }
            } catch (e) { this.toast(e.message, 'error'); }
        },
        moreCartJournal() { this.cartJrnOff += 100; this.loadCartJournal(false); },
        async loadWorkJournal(reset = true) {
            if (reset) { this.workJrnOff = 0; this.workJournal = []; this.workJrnSum = { count: 0, sum: 0 }; }
            try {
                const qs = `q=${encodeURIComponent(this.workJrnQ)}&billed=${this.workJrnBilled}&period=${this.workJrnPeriod}`;
                const rows = await api(`/api/works/journal?${qs}&limit=100&offset=${this.workJrnOff}`) || [];
                this.workJournal = reset ? rows : this.workJournal.concat(rows);
                this.workJrnMore = rows.length === 100;
                if (reset) {
                    try { this.workJrnSum = await api(`/api/works/journal/summary?${qs}`) || { count: 0, sum: 0 }; }
                    catch (e) { this.workJrnSum = { count: 0, sum: 0 }; }
                }
            } catch (e) { this.toast(e.message, 'error'); }
        },
        moreWorkJournal() { this.workJrnOff += 100; this.loadWorkJournal(false); },
        async loadGoodsJournal(reset = true) {
            if (reset) { this.goodsJrnOff = 0; this.goodsJournal = []; this.goodsJrnSum = { count: 0, sum: 0 }; }
            try {
                const qs = `q=${encodeURIComponent(this.goodsJrnQ)}&billed=${this.goodsJrnBilled}&period=${this.goodsJrnPeriod}`;
                const rows = await api(`/api/goods/journal?${qs}&limit=100&offset=${this.goodsJrnOff}`) || [];
                this.goodsJournal = reset ? rows : this.goodsJournal.concat(rows);
                this.goodsJrnMore = rows.length === 100;
                if (reset) {
                    try { this.goodsJrnSum = await api(`/api/goods/journal/summary?${qs}`) || { count: 0, sum: 0 }; }
                    catch (e) { this.goodsJrnSum = { count: 0, sum: 0 }; }
                }
            } catch (e) { this.toast(e.message, 'error'); }
        },
        moreGoodsJournal() { this.goodsJrnOff += 100; this.loadGoodsJournal(false); },

        // ═══════════════ FAB (плавающий + → выбор) ═══════════════
        fabOrder() { this.resetOrderForm(); this.goTo('orders'); this.showOrderForm = true; this.$nextTick(() => window.scrollTo({ top: 0, behavior: 'smooth' })); },
        fabRefill() { this.cartCard = null; this.goTo('cartridges'); },
        fabWork() { this.workCard = null; this.goTo('works'); },
        fabGoods() { this.goodsCard = null; this.goTo('goods'); },

        // наличная выписка (Документ не нужен → доход в CRM)
        async createCashRefills() {
            if (!this.selectedRefills.length) { this.toast('Не выбрано ни одной заправки', 'error'); return; }
            const total = (this.cartCard?.refills || []).filter(r => this.selectedRefills.includes(r.id)).reduce((s, r) => s + (Number(r.price) || 0), 0);
            const tr = this.cartTransfer;
            const msg = tr ? ('Перевод Коле на карту ' + total + ' ₽ — записать в его зарплату?')
                           : ('Внести в кассу (CRM) ' + total + ' ₽ без документа?');
            if (!confirm(msg)) return;
            try {
                const ids = this.selectedRefills.slice();
                const res2 = await api('/api/documents/cash', { method: 'POST', body: JSON.stringify({ client_id: this.cartCard.client_id, refill_ids: ids, date: this.todayStr(), transfer: tr }),
                    offline: { kind: 'cash', client: 'cart', clientId: this.cartCard.client_id, ids } });
                const chek = res2 && res2.doc_number ? ' · товарный чек №' + res2.doc_number : '';
                this.toast((tr ? ('Перевод записан, в зарплату Коле: ' + total + ' ₽') : ('Внесено в кассу (CRM): ' + total + ' ₽')) + chek, 'success');
                this.selectedRefills = []; this.cartTransfer = false;
                await this.reloadCard();
            } catch (e) { this.toast(e.message, 'error'); }
        },
        async createCashWorks() {
            if (!this.selectedWorks.length) { this.toast('Не выбрано ни одной работы', 'error'); return; }
            const total = (this.workCard?.jobs || []).filter(w => this.selectedWorks.includes(w.id)).reduce((s, w) => s + (Number(w.price) || 0), 0);
            const tr = this.workTransfer;
            const msg = tr ? ('Перевод Коле на карту ' + total + ' ₽ — записать в его зарплату?')
                           : ('Внести в кассу (CRM) ' + total + ' ₽ без документа?');
            if (!confirm(msg)) return;
            try {
                const ids = this.selectedWorks.slice();
                await api('/api/documents/cash-works', { method: 'POST', body: JSON.stringify({ client_id: this.workCard.client_id, work_ids: ids, date: this.todayStr(), transfer: tr }),
                    offline: { kind: 'cash', client: 'work', clientId: this.workCard.client_id, ids } });
                this.toast(tr ? ('Перевод записан, в зарплату Коле: ' + total + ' ₽') : ('Внесено в кассу (CRM): ' + total + ' ₽'), 'success');
                this.selectedWorks = []; this.workTransfer = false;
                await this.openWorkCard(this.workCard.client_id);
            } catch (e) { this.toast(e.message, 'error'); }
        },

        // ═══════════════ SEARCH ═══════════════
        async doSearch() {
            if (!this.searchQuery || this.searchQuery.length < 1) { this.searchResults = []; return; }
            try {
                this.searchResults = await api(`/api/search?q=${encodeURIComponent(this.searchQuery)}`) || [];
            } catch { this.searchResults = []; }
        },

        goToResult(r) {
            this.searchOpen = false;
            this.searchQuery = '';
            this.searchResults = [];
            if (r.type === 'client') {
                this.goTo('clients');
            } else if (r.type === 'order') {
                this.goTo('orders');
            }
        },

        // ═══════════════ EXPORT ═══════════════
        async downloadExport(type) {
            const token = localStorage.getItem(TOKEN_KEY);
            const month = new Date().getMonth() + 1;
            let url;
            if (type === 'yearly') {
                url = `${API}/api/export/yearly?year=${this.year}`;
            } else {
                url = `${API}/api/export/monthly?year=${this.year}&month=${month}`;
            }
            // Use fetch to get blob with auth header
            try {
                const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
                if (!res.ok) throw new Error('Export failed');
                const blob = await res.blob();
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = type === 'yearly' ? `Техно-Принт_${this.year}.xlsx` : `Техно-Принт_${this.year}-${month}.xlsx`;
                a.click();
                URL.revokeObjectURL(a.href);
                this.toast('Файл скачан', 'success');
            } catch (e) {
                this.toast('Ошибка экспорта', 'error');
            }
        },

        // ═══════════════ YEAR CHANGE ═══════════════
        async onYearChange() {
            await this.loadPage(this.page);
        },

        // ═══════════════ WEBSOCKET ═══════════════
        connectWS() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const token = localStorage.getItem(TOKEN_KEY);
            if (!token || !navigator.onLine) return;
            try {
                this.ws = new WebSocket(`${proto}//${location.host}/api/ws?token=${encodeURIComponent(token)}`);
                this.ws.onmessage = (e) => {
                    try {
                        const msg = JSON.parse(e.data);
                        this.handleWSMessage(msg);
                    } catch {}
                };
                this.ws.onclose = (ev) => {
                    if (ev.code === 1008) {  // auth rejected — token gone/expired
                        localStorage.removeItem(TOKEN_KEY);
                        location.href = '/login.html';
                        return;
                    }
                    setTimeout(() => this.connectWS(), 3000);
                };
                this.ws.onerror = () => {};
            } catch {}
        },

        handleWSMessage(msg) {
            if (msg.event === 'order_created') {
                this.toast('Новый заказ: ' + (msg.data?.service_name || ''), 'info');
                if (this.page === 'orders') this.loadOrders();
                if (this.page === 'dashboard') this.loadDashboard();
                this.loadDebtCount();
            } else if (msg.event === 'order_updated' || msg.event === 'debt_paid') {
                if (this.page === 'orders') this.loadOrders();
                if (this.page === 'dashboard') this.loadDashboard();
                if (this.page === 'debts') { this.loadDebts(); this.loadDebtsByClient(); }
                this.loadDebtCount();
            } else if (msg.event === 'order_deleted') {
                if (this.page === 'orders') this.loadOrders();
                if (this.page === 'dashboard') this.loadDashboard();
                this.loadDebtCount();
            }
        },

        // ═══════════════ UI HELPERS ═══════════════
        toggleDark() {
            this.darkMode = !this.darkMode;
            localStorage.setItem('darkMode', this.darkMode);
            document.documentElement.classList.toggle('dark', this.darkMode);
            // Re-render charts if on relevant pages
            if (this.page === 'dashboard') this.$nextTick(() => this.renderRevenueChart());
            if (this.page === 'reports') this.$nextTick(() => { this.renderReportChart(); this.renderPieChart(); });
        },

        logout() {
            localStorage.removeItem(TOKEN_KEY);
            location.href = '/login.html';
        },

        handleKey(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.searchOpen = true;
                this.$nextTick(() => this.$refs.searchInput?.focus());
            }
            if (e.key === 'F2') {
                e.preventDefault();
                if (this.page === 'orders') {
                    this.showOrderForm = true;
                }
            }
        },

        fmt(num) {
            const n = Number(num) || 0;
            return n.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' ₽';
        },
        payLabel(o) {
            if ((o.notes || '').toLowerCase().includes('перевод')) return 'Перевод';
            if (Number(o.amount_cash) > 0) return 'Нал';
            if (Number(o.amount_bank) > 0) return 'Безнал';
            if (Number(o.amount_card) > 0) return 'Перевод';
            return '—';
        },

        formatDate(dateStr) {
            if (!dateStr) return '';
            const d = new Date(dateStr + (dateStr.includes('T') ? '' : 'T00:00:00'));
            return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' });
        },

        todayStr() {
            return new Date().toISOString().split('T')[0];
        },

        toast(message, type = 'info') {
            const id = ++this.toastId;
            this.toasts.push({ id, message, type });
            setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
            }, 3000);
        },
    };
}
