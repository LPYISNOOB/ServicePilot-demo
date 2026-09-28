"""Create deterministic synthetic enterprise data. No private data is required."""

from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from servicepilot.database import connect, initialize_schema, resolve_db_path, table_counts
from servicepilot.business_rules import load_business_rules


PRODUCTS = [
    ("P-001", "星云降噪耳机 Pro", "audio", 899.0, 80),
    ("P-002", "轻羽无线鼠标", "accessory", 129.0, 160),
    ("P-003", "极光机械键盘", "accessory", 499.0, 75),
    ("P-004", "远航 14 英寸轻薄本", "laptop", 5299.0, 30),
    ("P-005", "拓界 27 英寸显示器", "monitor", 1599.0, 45),
    ("P-006", "灵犀智能手表", "wearable", 1199.0, 60),
    ("P-007", "100W 氮化镓充电器", "power", 299.0, 200),
    ("P-008", "双头 USB-C 数据线", "power", 69.0, 400),
    ("P-009", "云台高清摄像头", "office", 399.0, 90),
    ("P-010", "清语会议麦克风", "office", 599.0, 55),
    ("P-011", "极速移动固态硬盘 1TB", "storage", 699.0, 100),
    ("P-012", "便携扩展坞 8 合 1", "accessory", 359.0, 95),
    ("P-013", "悦读电子墨水屏", "reader", 1799.0, 35),
    ("P-014", "灵动画笔套装", "creative", 259.0, 110),
    ("P-015", "幻彩桌面音箱", "audio", 329.0, 85),
    ("P-016", "全景 Wi-Fi 7 路由器", "network", 999.0, 45),
    ("P-017", "随行移动电源 20000mAh", "power", 249.0, 140),
    ("P-018", "人体工学支架", "office", 189.0, 125),
    ("P-019", "智能寻物标签四件套", "smart", 399.0, 90),
    ("P-020", "家庭云存储 4TB", "storage", 2299.0, 25),
]

SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜"
GIVEN_NAMES = ["伟", "芳", "娜", "敏", "静", "强", "磊", "洋", "艳", "勇", "杰", "娟", "涛", "明", "超"]
REGIONS = ["华东", "华南", "华北", "西南", "华中"]
STATUSES = ["paid", "processing", "shipped", "delivered", "completed", "cancelled"]


def _iso_date(day_offset: int) -> str:
    return (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day_offset)).isoformat(timespec="seconds")


def seed_database(db_path: str | Path | None = None, *, force: bool = False) -> dict[str, int]:
    rules = load_business_rules().demo_data
    path = resolve_db_path(db_path)
    initialize_schema(path)
    existing = table_counts(path)
    if existing["customers"] and not force:
        return existing

    rng = random.Random(rules.random_seed)
    with connect(path) as connection:
        if force:
            for table in ["action_audits", "refund_requests", "tickets", "order_items", "orders", "products", "customers"]:
                connection.execute(f"DELETE FROM {table}")

        customers = []
        for index in range(1, rules.customer_count + 1):
            name = "张伟" if index == 1 else rng.choice(SURNAMES) + rng.choice(GIVEN_NAMES)
            email = "zhangwei@example.com" if index == 1 else f"customer{index:03d}@example.com"
            tier = "gold" if index % 20 == 0 or index == 1 else "silver" if index % 5 == 0 else "normal"
            customers.append((f"CUST-{index:04d}", name, email, tier, rng.choice(REGIONS), _iso_date(-rng.randint(30, 700))))
        connection.executemany(
            "INSERT INTO customers(customer_id, name, email, tier, region, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            customers,
        )
        connection.executemany(
            "INSERT INTO products(product_id, name, category, price, stock) VALUES (?, ?, ?, ?, ?)",
            PRODUCTS,
        )

        orders = []
        order_items = []
        for index in range(1, rules.order_count + 1):
            customer_index = 1 if index == 1 else rng.randint(1, rules.customer_count)
            order_id = f"SP-2026-{index:04d}"
            chosen = [("P-007", "100W 氮化镓充电器", "power", 299.0, 200)] if index == 1 else rng.sample(PRODUCTS, rng.randint(1, 3))
            items = []
            total = 0.0
            for product in chosen:
                quantity = 1 if index == 1 else rng.randint(1, 2)
                unit_price = round(product[3] * rng.choice([0.9, 0.95, 1.0]), 2)
                items.append((order_id, product[0], quantity, unit_price))
                total += quantity * unit_price
            day = 30 if index == 1 else rng.randint(0, 210)
            status = "delivered" if index == 1 else rng.choices(STATUSES, weights=[4, 8, 15, 25, 35, 3], k=1)[0]
            tracking = f"SF{202600000000 + index}" if status in {"shipped", "delivered", "completed"} else None
            orders.append((order_id, f"CUST-{customer_index:04d}", _iso_date(day), status, round(total, 2), tracking))
            order_items.extend(items)

        connection.executemany(
            "INSERT INTO orders(order_id, customer_id, created_at, status, total_amount, tracking_no) VALUES (?, ?, ?, ?, ?, ?)",
            orders,
        )
        connection.executemany(
            "INSERT INTO order_items(order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
            order_items,
        )
    return table_counts(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化 ServicePilot 合成数据库")
    parser.add_argument("--force", action="store_true", help="清空并按固定随机种子重新生成")
    parser.add_argument("--db-path", default=None, help="覆盖数据库路径")
    args = parser.parse_args()
    counts = seed_database(args.db_path, force=args.force)
    print("ServicePilot 数据已就绪：")
    for table, count in counts.items():
        print(f"  {table}: {count}")
    print("演示账号：zhangwei@example.com / SP-2026-0001")


if __name__ == "__main__":
    main()
