import sqlite3
import pymysql
import psycopg2
from typing import Any, Optional
from contextlib import contextmanager
from config import config


class DatabaseConnection:
    """数据库连接管理器"""

    def __init__(self):
        self.db_type = config.db_type
        self._connection = None

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = None
        try:
            if self.db_type == "sqlite":
                conn = sqlite3.connect(config.db_path)
                conn.row_factory = sqlite3.Row
            elif self.db_type == "mysql":
                conn = pymysql.connect(
                    host=config.db_host,
                    port=config.db_port,
                    user=config.db_user,
                    password=config.db_password,
                    database=config.db_name,
                    cursorclass=pymysql.cursors.DictCursor
                )
            elif self.db_type == "postgresql":
                conn = psycopg2.connect(
                    host=config.db_host,
                    port=config.db_port,
                    user=config.db_user,
                    password=config.db_password,
                    database=config.db_name
                )
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")

            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()


db_manager = DatabaseConnection()


def execute_query_sync(sql: str, params: Optional[tuple] = None) -> list[dict]:
    """同步执行SQL查询"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())

        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    results.append(row)
                else:
                    results.append(dict(zip(columns, row)))
            return results
        return []


def get_table_schema_sync(table_name: str) -> dict[str, Any]:
    """获取表结构信息"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        if config.db_type == "sqlite":
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            schema = {
                "table_name": table_name,
                "columns": []
            }
            for col in columns:
                if isinstance(col, dict):
                    schema["columns"].append({
                        "name": col["name"],
                        "type": col["type"],
                        "nullable": not col["notnull"],
                        "primary_key": bool(col["pk"])
                    })
                else:
                    schema["columns"].append({
                        "name": col[1],
                        "type": col[2],
                        "nullable": not col[3],
                        "primary_key": bool(col[5])
                    })
            return schema

        elif config.db_type == "mysql":
            cursor.execute(f"DESCRIBE {table_name}")
            columns = cursor.fetchall()
            schema = {
                "table_name": table_name,
                "columns": []
            }
            for col in columns:
                schema["columns"].append({
                    "name": col["Field"],
                    "type": col["Type"],
                    "nullable": col["Null"] == "YES",
                    "primary_key": col["Key"] == "PRI"
                })
            return schema

        elif config.db_type == "postgresql":
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable,
                       (SELECT COUNT(*) FROM information_schema.key_column_usage
                        WHERE table_name = '{table_name}' AND column_name = c.column_name) as is_pk
                FROM information_schema.columns c
                WHERE table_name = '{table_name}'
            """)
            columns = cursor.fetchall()
            schema = {
                "table_name": table_name,
                "columns": []
            }
            for col in columns:
                schema["columns"].append({
                    "name": col[0],
                    "type": col[1],
                    "nullable": col[2] == "YES",
                    "primary_key": bool(col[3])
                })
            return schema


def list_tables_sync() -> list[str]:
    """列出所有表名"""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        if config.db_type == "sqlite":
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] if isinstance(row, tuple) else row["name"] for row in cursor.fetchall()]
        elif config.db_type == "mysql":
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
        elif config.db_type == "postgresql":
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            tables = [row[0] for row in cursor.fetchall()]
        else:
            raise ValueError(f"Unsupported database type: {config.db_type}")

        return tables


def get_db():
    """获取数据库管理器实例"""
    return db_manager


def initialize_demo_db():
    """初始化演示数据库"""
    if config.db_type != "sqlite":
        print("Demo database initialization only supports SQLite")
        return

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        # 删除旧表（重新初始化）
        tables_to_drop = ['order_items', 'orders', 'products', 'categories', 'customers',
                          'suppliers', 'inventory_logs', 'reviews', 'coupons', 'customer_coupons',
                          'shopping_cart', 'payments', 'shipments', 'addresses']
        for table in tables_to_drop:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")

        # 创建类别表
        cursor.execute("""
            CREATE TABLE categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT NOT NULL,
                parent_category_id INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建供应商表
        cursor.execute("""
            CREATE TABLE suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT NOT NULL,
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建产品表
        cursor.execute("""
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                category_id INTEGER,
                supplier_id INTEGER,
                price REAL NOT NULL,
                cost_price REAL,
                stock_quantity INTEGER DEFAULT 0,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(category_id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
            )
        """)

        # 创建客户表
        cursor.execute("""
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vip_level INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0
            )
        """)

        # 创建地址表
        cursor.execute("""
            CREATE TABLE addresses (
                address_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                receiver_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                province TEXT,
                city TEXT,
                district TEXT,
                detail_address TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # 创建订单表
        cursor.execute("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                discount_amount REAL DEFAULT 0,
                final_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                address_id INTEGER,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                FOREIGN KEY (address_id) REFERENCES addresses(address_id)
            )
        """)

        # 创建订单明细表
        cursor.execute("""
            CREATE TABLE order_items (
                order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)

        # 创建库存记录表
        cursor.execute("""
            CREATE TABLE inventory_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                change_type TEXT NOT NULL,
                quantity_change INTEGER NOT NULL,
                before_quantity INTEGER,
                after_quantity INTEGER,
                reason TEXT,
                operator TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)

        # 创建评论表
        cursor.execute("""
            CREATE TABLE reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                order_id INTEGER,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(product_id),
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)

        # 创建优惠券表
        cursor.execute("""
            CREATE TABLE coupons (
                coupon_id INTEGER PRIMARY KEY AUTOINCREMENT,
                coupon_code TEXT UNIQUE NOT NULL,
                coupon_name TEXT NOT NULL,
                discount_type TEXT NOT NULL,
                discount_value REAL NOT NULL,
                min_purchase_amount REAL DEFAULT 0,
                max_discount_amount REAL,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                total_quantity INTEGER,
                used_quantity INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        """)

        # 创建客户优惠券关联表
        cursor.execute("""
            CREATE TABLE customer_coupons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                coupon_id INTEGER NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP,
                order_id INTEGER,
                status TEXT DEFAULT 'unused',
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                FOREIGN KEY (coupon_id) REFERENCES coupons(coupon_id),
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)

        # 创建购物车表
        cursor.execute("""
            CREATE TABLE shopping_cart (
                cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)

        # 创建支付记录表
        cursor.execute("""
            CREATE TABLE payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                payment_amount REAL NOT NULL,
                payment_status TEXT DEFAULT 'pending',
                transaction_id TEXT,
                paid_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)

        # 创建物流信息表
        cursor.execute("""
            CREATE TABLE shipments (
                shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                tracking_number TEXT,
                carrier TEXT,
                shipping_status TEXT DEFAULT 'preparing',
                shipped_at TIMESTAMP,
                delivered_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)

        # 插入示例数据
        # 1. 类别数据
        categories = [
            ("电子产品", None, "各类电子设备和配件"),
            ("手机", 1, "智能手机和配件"),
            ("电脑", 1, "笔记本电脑和台式机"),
            ("图书", None, "各类书籍和出版物"),
            ("编程", 4, "编程相关书籍"),
            ("文学", 4, "文学作品"),
            ("服装", None, "男女服装和配饰"),
            ("食品", None, "食品和饮料")
        ]
        cursor.executemany("INSERT INTO categories (category_name, parent_category_id, description) VALUES (?, ?, ?)", categories)

        # 2. 供应商数据
        suppliers = [
            ("苹果供应商", "张经理", "13800001111", "apple@supplier.com", "深圳市南山区"),
            ("联想供应商", "李经理", "13800002222", "lenovo@supplier.com", "北京市海淀区"),
            ("出版社A", "王编辑", "13800003333", "publisher@book.com", "上海市浦东新区"),
            ("服装厂B", "赵厂长", "13800004444", "factory@cloth.com", "广州市天河区"),
            ("食品公司C", "刘总", "13800005555", "food@company.com", "杭州市西湖区")
        ]
        cursor.executemany("INSERT INTO suppliers (supplier_name, contact_person, phone, email, address) VALUES (?, ?, ?, ?, ?)", suppliers)

        # 3. 产品数据
        products = [
            ("iPhone 15 Pro", 2, 1, 7999.00, 6500.00, 50, "最新款苹果手机"),
            ("iPhone 14", 2, 1, 5999.00, 4800.00, 80, "上一代苹果手机"),
            ("MacBook Pro M3", 3, 1, 12999.00, 10500.00, 30, "专业笔记本电脑"),
            ("ThinkPad X1", 3, 2, 8999.00, 7200.00, 40, "商务笔记本"),
            ("Python编程从入门到精通", 5, 3, 89.00, 45.00, 100, "Python学习书籍"),
            ("数据结构与算法", 5, 3, 79.00, 40.00, 80, "算法基础书籍"),
            ("三体", 6, 3, 59.00, 30.00, 200, "科幻小说"),
            ("活着", 6, 3, 39.00, 20.00, 150, "文学作品"),
            ("男士T恤", 7, 4, 99.00, 50.00, 200, "纯棉T恤"),
            ("牛仔裤", 7, 4, 299.00, 150.00, 150, "经典牛仔裤"),
            ("咖啡豆500g", 8, 5, 68.00, 35.00, 300, "精品咖啡豆"),
            ("巧克力礼盒", 8, 5, 128.00, 65.00, 500, "进口巧克力")
        ]
        cursor.executemany("""INSERT INTO products
            (product_name, category_id, supplier_id, price, cost_price, stock_quantity, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", products)

        # 4. 客户数据
        customers = [
            ("张三", "zhangsan@example.com", "13800138000", "2024-01-01 10:00:00", 2, 15000.00),
            ("李四", "lisi@example.com", "13900139000", "2024-01-05 14:30:00", 1, 5000.00),
            ("王五", "wangwu@example.com", "13700137000", "2024-01-10 09:20:00", 0, 1000.00),
            ("赵六", "zhaoliu@example.com", "13600136000", "2024-01-15 16:45:00", 3, 30000.00),
            ("孙七", "sunqi@example.com", "13500135000", "2024-02-01 11:10:00", 0, 500.00)
        ]
        cursor.executemany("""INSERT INTO customers
            (customer_name, email, phone, registration_date, vip_level, total_spent)
            VALUES (?, ?, ?, ?, ?, ?)""", customers)

        # 5. 地址数据
        addresses = [
            (1, "张三", "13800138000", "广东省", "深圳市", "南山区", "科技园南路10号", 1),
            (1, "张三", "13800138000", "广东省", "广州市", "天河区", "天河路100号", 0),
            (2, "李四", "13900139000", "北京市", "北京市", "海淀区", "中关村大街1号", 1),
            (3, "王五", "13700137000", "上海市", "上海市", "浦东新区", "陆家嘴环路500号", 1),
            (4, "赵六", "13600136000", "浙江省", "杭州市", "西湖区", "文一路200号", 1)
        ]
        cursor.executemany("""INSERT INTO addresses
            (customer_id, receiver_name, phone, province, city, district, detail_address, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", addresses)

        # 6. 订单数据
        orders = [
            (1, "2024-01-15 10:30:00", 8088.00, 89.00, 7999.00, "completed", 1),
            (2, "2024-01-16 14:20:00", 168.00, 0.00, 168.00, "completed", 3),
            (1, "2024-01-17 09:15:00", 398.00, 0.00, 398.00, "shipped", 1),
            (3, "2024-01-18 16:45:00", 7999.00, 0.00, 7999.00, "completed", 4),
            (4, "2024-02-01 11:20:00", 13298.00, 299.00, 12999.00, "completed", 5),
            (2, "2024-02-05 15:30:00", 8999.00, 0.00, 8999.00, "pending", 3)
        ]
        cursor.executemany("""INSERT INTO orders
            (customer_id, order_date, total_amount, discount_amount, final_amount, status, address_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", orders)

        # 7. 订单明细数据
        order_items = [
            (1, 1, 1, 7999.00, 7999.00),
            (1, 5, 1, 89.00, 89.00),
            (2, 5, 1, 89.00, 89.00),
            (2, 6, 1, 79.00, 79.00),
            (3, 9, 2, 99.00, 198.00),
            (3, 10, 1, 299.00, 299.00),
            (4, 1, 1, 7999.00, 7999.00),
            (5, 3, 1, 12999.00, 12999.00),
            (6, 4, 1, 8999.00, 8999.00)
        ]
        cursor.executemany("""INSERT INTO order_items
            (order_id, product_id, quantity, unit_price, subtotal)
            VALUES (?, ?, ?, ?, ?)""", order_items)

        # 8. 库存记录数据
        inventory_logs = [
            (1, "purchase", 50, 0, 50, "初始入库", "系统", "2024-01-01 08:00:00"),
            (1, "sale", -1, 50, 49, "订单销售", "系统", "2024-01-15 10:30:00"),
            (3, "purchase", 30, 0, 30, "初始入库", "系统", "2024-01-01 08:00:00"),
            (3, "sale", -1, 30, 29, "订单销售", "系统", "2024-02-01 11:20:00"),
            (5, "purchase", 100, 0, 100, "初始入库", "系统", "2024-01-01 08:00:00"),
            (5, "sale", -2, 100, 98, "订单销售", "系统", "2024-01-16 14:20:00")
        ]
        cursor.executemany("""INSERT INTO inventory_logs
            (product_id, change_type, quantity_change, before_quantity, after_quantity, reason, operator, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", inventory_logs)

        # 9. 评论数据
        reviews = [
            (1, 1, 1, 5, "非常好用，性能强劲！", "2024-01-20 10:00:00"),
            (1, 4, 4, 5, "物流很快，手机很棒", "2024-01-25 14:30:00"),
            (3, 4, 5, 5, "MacBook性能无敌", "2024-02-10 09:15:00"),
            (5, 2, 2, 4, "内容详细，适合入门", "2024-01-22 16:20:00"),
            (9, 1, 3, 4, "质量不错，穿着舒适", "2024-01-25 11:30:00")
        ]
        cursor.executemany("""INSERT INTO reviews
            (product_id, customer_id, order_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""", reviews)

        # 10. 优惠券数据
        coupons = [
            ("NEW2024", "新用户优惠券", "fixed", 50.00, 100.00, None, "2024-01-01", "2024-12-31", 1000, 5, "active"),
            ("VIP100", "VIP专享100元", "fixed", 100.00, 500.00, None, "2024-01-01", "2024-12-31", 500, 2, "active"),
            ("DISCOUNT10", "全场9折", "percentage", 0.1, 0.00, 200.00, "2024-01-01", "2024-12-31", 10000, 50, "active"),
            ("BOOK20", "图书满100减20", "fixed", 20.00, 100.00, None, "2024-01-01", "2024-06-30", 2000, 10, "active")
        ]
        cursor.executemany("""INSERT INTO coupons
            (coupon_code, coupon_name, discount_type, discount_value, min_purchase_amount, max_discount_amount, start_date, end_date, total_quantity, used_quantity, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", coupons)

        # 11. 客户优惠券关联数据
        customer_coupons = [
            (1, 2, "2024-01-10 10:00:00", "2024-01-15 10:30:00", 1, "used"),
            (2, 1, "2024-01-05 14:30:00", None, None, "unused"),
            (3, 1, "2024-01-10 09:20:00", None, None, "unused"),
            (4, 2, "2024-01-15 16:45:00", "2024-02-01 11:20:00", 5, "used"),
            (1, 3, "2024-01-20 10:00:00", None, None, "unused")
        ]
        cursor.executemany("""INSERT INTO customer_coupons
            (customer_id, coupon_id, received_at, used_at, order_id, status)
            VALUES (?, ?, ?, ?, ?, ?)""", customer_coupons)

        # 12. 购物车数据
        shopping_cart = [
            (2, 4, 1, "2024-02-10 10:00:00"),
            (3, 7, 2, "2024-02-11 14:30:00"),
            (3, 11, 3, "2024-02-11 14:35:00"),
            (5, 9, 1, "2024-02-12 09:20:00")
        ]
        cursor.executemany("""INSERT INTO shopping_cart
            (customer_id, product_id, quantity, added_at)
            VALUES (?, ?, ?, ?)""", shopping_cart)

        # 13. 支付记录数据
        payments = [
            (1, "alipay", 7999.00, "completed", "ALI20240115103000", "2024-01-15 10:31:00", "2024-01-15 10:30:00"),
            (2, "wechat", 168.00, "completed", "WX20240116142000", "2024-01-16 14:21:00", "2024-01-16 14:20:00"),
            (3, "alipay", 398.00, "completed", "ALI20240117091500", "2024-01-17 09:16:00", "2024-01-17 09:15:00"),
            (4, "wechat", 7999.00, "completed", "WX20240118164500", "2024-01-18 16:46:00", "2024-01-18 16:45:00"),
            (5, "alipay", 12999.00, "completed", "ALI20240201112000", "2024-02-01 11:21:00", "2024-02-01 11:20:00"),
            (6, "wechat", 8999.00, "pending", None, None, "2024-02-05 15:30:00")
        ]
        cursor.executemany("""INSERT INTO payments
            (order_id, payment_method, payment_amount, payment_status, transaction_id, paid_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", payments)

        # 14. 物流信息数据
        shipments = [
            (1, "SF1234567890", "顺丰速运", "delivered", "2024-01-16 08:00:00", "2024-01-17 14:30:00", "2024-01-15 11:00:00"),
            (2, "YTO9876543210", "圆通速递", "delivered", "2024-01-17 09:00:00", "2024-01-19 10:20:00", "2024-01-16 15:00:00"),
            (3, "SF2345678901", "顺丰速运", "in_transit", "2024-01-18 08:00:00", None, "2024-01-17 10:00:00"),
            (4, "JD3456789012", "京东物流", "delivered", "2024-01-19 10:00:00", "2024-01-20 16:45:00", "2024-01-18 17:00:00"),
            (5, "SF4567890123", "顺丰速运", "delivered", "2024-02-02 08:00:00", "2024-02-03 11:20:00", "2024-02-01 12:00:00"),
            (6, None, None, "preparing", None, None, "2024-02-05 15:30:00")
        ]
        cursor.executemany("""INSERT INTO shipments
            (order_id, tracking_number, carrier, shipping_status, shipped_at, delivered_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", shipments)

        conn.commit()
        print("Demo database initialized successfully!")

