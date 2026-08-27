from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)   # создаёт недостающие ТАБЛИЦЫ
    await _ensure_columns()                             # добавляет недостающие КОЛОНКИ (аддитивно)
    await _seed_defaults()


async def _ensure_columns():
    """Безопасная авто-миграция: добавляет в существующие таблицы недостающие колонки моделей
    (ALTER TABLE ... ADD COLUMN IF NOT EXISTS, как nullable). Только аддитивно — данные не трогает.
    Закрывает разрыв create_all (он создаёт новые таблицы, но НЕ новые колонки существующих)."""
    from sqlalchemy import inspect, text

    def _introspect(sync_conn):
        insp = inspect(sync_conn)
        tables = set(insp.get_table_names())
        cols = {t: {c["name"] for c in insp.get_columns(t)} for t in tables}
        return tables, cols

    try:
        dialect = engine.dialect
        async with engine.begin() as conn:
            tables, cols = await conn.run_sync(_introspect)
            for table in Base.metadata.sorted_tables:
                if table.name not in tables:
                    continue  # целиком создаст create_all
                have = cols.get(table.name, set())
                for column in table.columns:
                    if column.name in have:
                        continue
                    try:
                        coltype = column.type.compile(dialect=dialect)
                        await conn.execute(text(
                            f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS "{column.name}" {coltype}'
                        ))
                    except Exception:
                        pass  # одна колонка не критична — не валим старт
    except Exception:
        pass  # авто-миграция не должна ронять запуск приложения


# Базовые справочники — нужны для работы на чистой/восстановленной БД (FK на cartridge_spec_types).
_SPEC_TYPES = [
    (1, "Заправка", True, 1), (11, "Заправка/восстановление (ф) картриджа", True, 11),
    (12, "Заправка/восстановление (м)", True, 12), (13, "Заправка/восстановление", True, 13),
    (14, "Заправка/восстановление (мф)", True, 14), (15, "Заправка/восстановление (р)", True, 15),
    (16, "Заправка/восстановление (мр)", True, 16), (17, "Заправка/восстановление (фр)", True, 17),
    (18, "Заправка/восстановление (мфр)", True, 18), (19, "Заправка/замена ЧИПа", True, 19),
    (2, "Рециклинг", True, 1002), (3, "Производство", True, 1003), (6, "Замена фотобарабана", True, 1006),
    (7, "Замена резинового вала", True, 1007), (8, "Замена магнитного вала", True, 1008),
    (9, "Замена бушингов", True, 1009), (10, "Полное восстановление", True, 1010),
    (20, "Чистка, замена фотобарабана", True, 1020),
]


async def _seed_defaults():
    from sqlalchemy import text
    async with async_session() as db:
        try:
            n = (await db.execute(text("SELECT count(*) FROM cartridge_spec_types"))).scalar()
            if not n:
                for sid, name, is_refill, sort in _SPEC_TYPES:
                    await db.execute(text(
                        "INSERT INTO cartridge_spec_types (id,name,is_refill,is_active,sort) "
                        "VALUES (:i,:n,:r,true,:s) ON CONFLICT (id) DO NOTHING"),
                        {"i": sid, "n": name, "r": is_refill, "s": sort})
                await db.execute(text(
                    "SELECT setval(pg_get_serial_sequence('cartridge_spec_types','id'), "
                    "GREATEST((SELECT COALESCE(MAX(id),1) FROM cartridge_spec_types),1))"))
                await db.commit()
        except Exception:
            await db.rollback()
