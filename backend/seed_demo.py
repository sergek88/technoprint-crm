"""Наполняет базу ВЫМЫШЛЕННЫМИ данными — чтобы посмотреть систему вживую.

    docker compose exec tp-backend python seed_demo.py

Создаёт клиентов, картриджи с историей заправок, работы, товары, заказы, документы,
расходы и зарплату за полгода. Все названия и суммы придуманы.
Запускать ТОЛЬКО на пустой или демонстрационной базе — на боевую данные не лить.
Логины после наполнения: demo/demo12345 (владелец), master/master12345 (работник).
"""
import asyncio, random
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from app.database import async_session
from app.auth import hash_password
from app.models import (User, Client, Service, Order, Expense, Manufacturer, CartridgeModel,
                        Cartridge, CartridgeWorker, CartridgeSpecType, CartridgePrice,
                        WorkType, WorkJob, Good, GoodSale, Organization, MonthlyCost,
                        SalaryWork, SalaryPayment, Document, DocumentItem)

random.seed(20260827)
TODAY = date(2026, 8, 27)

CLIENTS = [
    ("МБОУ «Средняя школа №1»", "org", "5001001001"),
    ("МБДОУ детский сад «Ромашка»", "org", "5001001002"),
    ("Администрация Приозёрного поселения", "org", "5001001003"),
    ("АУ «Центр социального обслуживания»", "org", "5001001004"),
    ("ООО «Мебельщик»", "org", "5001001005"),
    ("ИП Соколов А. В.", "org", "500100100600"),
    ("МБУ «Дом культуры»", "org", "5001001007"),
    ("ч.л.", "person", None),
]
MODELS = [("HP", "CE285A", 850), ("HP", "CF217A", 900), ("Canon", "725", 850), ("Canon", "737", 950),
          ("Samsung", "MLT-D111S", 1000), ("Kyocera", "TK-1170", 1600), ("Brother", "TN-2375", 1100),
          ("Pantum", "PC-211", 900), ("Xerox", "106R02773", 950), ("HP", "CF259A", 1900)]
WORKS = [("Чистка системного блока", 1200), ("Установка Windows и ПО", 2500), ("Замена термопасты", 800),
         ("Диагностика", 500), ("Ремонт блока питания", 1800), ("Замена жёсткого диска на SSD", 3500),
         ("Настройка сети", 1500), ("Ремонт принтера", 2200), ("Прошивка МФУ", 2500),
         ("Восстановление данных", 3000), ("Замена ролика захвата", 900), ("Копия документа", 20)]
GOODS = [("Бумага А4 «Снегурочка», 500 л", 420), ("Кабель USB A-B 1.8 м", 350), ("Мышь проводная", 590),
         ("Клавиатура USB", 890), ("Тонер HP универсальный, 1 кг", 1450), ("Флешка 32 ГБ", 690),
         ("Сетевой фильтр 5 розеток", 750), ("Патч-корд 3 м", 260), ("HDMI кабель 2 м", 540),
         ("Термопаста, шприц", 320), ("Чип для картриджа", 280), ("SSD 240 ГБ", 2400)]


async def main():
    async with async_session() as db:
        db.add(User(username="demo", password_hash=hash_password("demo12345"), full_name="Демо-владелец", role="admin"))
        db.add(User(username="master", password_hash=hash_password("master12345"), full_name="Мастер", role="worker"))

        org = (await db.execute(select(Organization))).scalars().first()
        if not org:
            org = Organization(id=1)
            db.add(org)
        org.name = 'ООО «Ромашка»'
        org.address = "628000, Приозёрный край, с. Приозёрное, ул. Центральная, д. 12"
        org.phones = "8(00000)0-00-00, моб. 8-900-000-00-00"
        org.inn, org.kpp, org.ogrnip = "5001001000", "500101001", "1200000000000"
        org.bank_name, org.bank_bik = "АО «Демо-Банк»", "040000000"
        org.bank_account, org.bank_corr = "40702810000000000001", "30101810000000000001"
        org.director = "Демидов Д. Д."
        await db.flush()

        clients = []
        for name, ctype, inn in CLIENTS:
            c = Client(name=name, client_type=ctype, inn=inn,
                       kpp=("500101001" if inn and len(inn) == 10 else None),
                       address=("с. Приозёрное, ул. Школьная, д. 1" if ctype == "org" else None),
                       bank=("АО «Демо-Банк»" if ctype == "org" else None),
                       bik=("040000000" if ctype == "org" else None),
                       account=("40204810000000000002" if ctype == "org" else None))
            db.add(c); clients.append(c)

        services = {}
        for sname in ("Заправка картриджа", "Ремонт/работа", "Товар", "Печать/копия"):
            s = Service(name=sname, is_active=True); db.add(s); services[sname] = s

        worker = CartridgeWorker(name="И. И. Мастеров"); db.add(worker)
        spec = (await db.execute(select(CartridgeSpecType).where(CartridgeSpecType.is_refill == True))).scalars().first()
        if not spec:
            spec = CartridgeSpecType(name="Заправка", is_refill=True, is_active=True, sort=1); db.add(spec)
        for wt, _ in [(w, p) for w, p in WORKS]:
            db.add(WorkType(name=wt, is_active=True, sort=0))
        await db.flush()

        manufs, models = {}, []
        for mf, model, price in MODELS:
            if mf not in manufs:
                manufs[mf] = Manufacturer(name=mf); db.add(manufs[mf]); await db.flush()
            cm = CartridgeModel(name=f"Картридж {mf} {model}", manufacturer_id=manufs[mf].id, norm=random.choice([60, 85, 100]))
            db.add(cm); await db.flush()
            db.add(CartridgePrice(model_id=cm.id, spec_type_id=spec.id, price=Decimal(price)))
            models.append((cm, price))

        goods = []
        for i, (gname, gprice) in enumerate(GOODS, 1):
            g = Good(code=f"D-{1000+i}", name=gname, category="Расходники", unit="шт",
                     last_price=Decimal(gprice), is_active=True)
            db.add(g); goods.append(g)
        await db.flush()

        # картриджи по клиентам + история заправок за 5 месяцев
        carts = []
        for i in range(48):
            cm, price = random.choice(models)
            cl = random.choice(clients[:7])
            c = Cartridge(barcode=f"DEMO{4000+i:06d}", model_id=cm.id, client_id=cl.id,
                          count_do=0, total_sum=Decimal(0), is_eternal=False, is_china=False)
            db.add(c); carts.append((c, cl, price))
        await db.flush()

        for month_back in range(5, -1, -1):
            first = (TODAY.replace(day=1) - timedelta(days=31 * month_back)).replace(day=1)
            n = random.randint(45, 80) if month_back != 1 else 22
            for _ in range(n):
                c, cl, price = random.choice(carts)
                d = first + timedelta(days=random.randint(0, 26))
                if d > TODAY: continue
                p = Decimal(price + random.choice([-50, 0, 0, 50, 100]))
                from app.models import CartridgeRefill
                db.add(CartridgeRefill(cartridge_id=c.id, work_date=d, last_date=d, price=p,
                                       spec_type_id=spec.id, worker_id=worker.id, is_billed=True))
                # деньги: бюджет — безнал (счёт), частник — наличные
                if cl.name == "ч.л.":
                    db.add(Order(date=d, service_id=services["Заправка картриджа"].id, client_id=cl.id,
                                 amount_cash=p, amount_bank=Decimal(0), amount_card=Decimal(0),
                                 is_paid=True, paid_at=datetime.combine(d, datetime.min.time()),
                                 notes="Заправка картриджа (наличные)"))
                else:
                    paid = random.random() > 0.25
                    db.add(Order(date=d, service_id=services["Заправка картриджа"].id, client_id=cl.id,
                                 amount_cash=Decimal(0), amount_bank=p, amount_card=Decimal(0),
                                 is_paid=paid, paid_at=(datetime.combine(d, datetime.min.time()) if paid else None),
                                 invoice_number=str(random.randint(1, 60)), notes="Счёт на заправку"))

        # работы и товар
        for month_back in range(4, -1, -1):
            first = (TODAY.replace(day=1) - timedelta(days=31 * month_back)).replace(day=1)
            for _ in range(random.randint(8, 18)):
                title, price = random.choice(WORKS)
                cl = random.choice(clients)
                d = first + timedelta(days=random.randint(0, 26))
                if d > TODAY: continue
                p = Decimal(price)
                db.add(WorkJob(client_id=cl.id, title=title, date=d, worker_id=worker.id,
                               price=p, is_billed=True, device_label=random.choice(["Системный блок", "Ноутбук", "МФУ", "Принтер", None])))
                db.add(Order(date=d, service_id=services["Ремонт/работа"].id, client_id=cl.id,
                             amount_cash=(p if cl.name == "ч.л." else Decimal(0)),
                             amount_bank=(Decimal(0) if cl.name == "ч.л." else p),
                             amount_card=Decimal(0), is_paid=(cl.name == "ч.л." or random.random() > 0.3),
                             notes=title))
            for _ in range(random.randint(4, 10)):
                g = random.choice(goods)
                cl = random.choice(clients)
                d = first + timedelta(days=random.randint(0, 26))
                if d > TODAY: continue
                qty = Decimal(random.choice([1, 1, 2, 3]))
                total = qty * (g.last_price or Decimal(0))
                db.add(GoodSale(client_id=cl.id, good_id=g.id, name=g.name, qty=qty,
                                price=g.last_price, date=d, is_billed=True))
                db.add(Order(date=d, service_id=services["Товар"].id, client_id=cl.id,
                             amount_cash=(total if cl.name == "ч.л." else Decimal(0)),
                             amount_bank=(Decimal(0) if cl.name == "ч.л." else total),
                             amount_card=Decimal(0), is_paid=(cl.name == "ч.л."), notes=f"Товар: {g.name}"))

        # расходы и постоянные затраты
        for month_back in range(5, -1, -1):
            first = (TODAY.replace(day=1) - timedelta(days=31 * month_back)).replace(day=1)
            for descr, amount in (("Тонер оптом", 18000), ("Чипы и ролики", 6500), ("Хозтовары", 1800)):
                d = first + timedelta(days=random.randint(1, 20))
                if d > TODAY: continue
                db.add(Expense(date=d, category="Расходники", description=descr,
                               amount=Decimal(amount + random.randint(-1500, 1500)), from_cash_register=True))
            db.add(MonthlyCost(year=first.year, month=first.month, salary_admin=Decimal(28000),
                               salary_master=Decimal(0), rent=Decimal(15000), taxes=Decimal(6000),
                               other=Decimal(2000)))

        # зарплата: ручные работы и выплаты
        for month_back in range(2, -1, -1):
            first = (TODAY.replace(day=1) - timedelta(days=31 * month_back)).replace(day=1)
            for _ in range(random.randint(1, 3)):
                title, price = random.choice(WORKS[:6])
                db.add(SalaryWork(year=first.year, month=first.month,
                                  date=first + timedelta(days=random.randint(1, 25)),
                                  description=title, client="ч.л.", amount=Decimal(price)))
            for _ in range(random.randint(2, 4)):
                db.add(SalaryPayment(year=first.year, month=first.month,
                                     date=first + timedelta(days=random.randint(1, 26)),
                                     amount=Decimal(random.choice([3000, 5000, 7000, 10000])),
                                     payment_type=random.choice(["cash", "card", "bank"]),
                                     notes=random.choice(["", "аванс", "перевод от клиента"])))

        # документ-счёт с позициями
        doc = Document(client_id=clients[0].id, doc_type="invoice", number="42",
                       date=TODAY - timedelta(days=3), total=Decimal(0))
        db.add(doc); await db.flush()
        total = Decimal(0)
        for cm, price in models[:4]:
            line = Decimal(price)
            db.add(DocumentItem(document_id=doc.id, kind="work", name=f"Заправка {cm.name}",
                                unit="шт", qty=Decimal(1), price=line, total=line))
            total += line
        doc.total = total

        await db.commit()

        cnt = lambda q: db.execute(text(q))
        for label, q in (("клиентов", "select count(*) from clients"), ("заказов", "select count(*) from orders"),
                         ("заправок", "select count(*) from cartridge_refills"), ("работ", "select count(*) from work_jobs"),
                         ("товаров", "select count(*) from goods"), ("продаж", "select count(*) from good_sales")):
            print(f"  {label}: {(await cnt(q)).scalar()}")

asyncio.run(main())
