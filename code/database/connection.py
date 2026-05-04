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

        # 创建表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT NOT NULL,
                description TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                category_id INTEGER,
                price REAL NOT NULL,
                stock_quantity INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)

        # 插入示例数据
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            categories = [
                ("电子产品", "各类电子设备和配件"),
                ("图书", "各类书籍和出版物"),
                ("服装", "男女服装和配饰"),
                ("食品", "食品和饮料")
            ]
            cursor.executemany("INSERT INTO categories (category_name, description) VALUES (?, ?)", categories)

            products = [
                ("iPhone 15", 1, 7999.00, 50),
                ("MacBook Pro", 1, 12999.00, 30),
                ("Python编程", 2, 89.00, 100),
                ("数据结构与算法", 2, 79.00, 80),
                ("T恤", 3, 99.00, 200),
                ("牛仔裤", 3, 299.00, 150),
                ("咖啡豆", 4, 68.00, 300),
                ("巧克力", 4, 25.00, 500)
            ]
            cursor.executemany("INSERT INTO products (product_name, category_id, price, stock_quantity) VALUES (?, ?, ?, ?)", products)

            customers = [
                ("张三", "zhangsan@example.com", "13800138000"),
                ("李四", "lisi@example.com", "13900139000"),
                ("王五", "wangwu@example.com", "13700137000")
            ]
            cursor.executemany("INSERT INTO customers (customer_name, email, phone) VALUES (?, ?, ?)", customers)

            orders = [
                (1, "2024-01-15 10:30:00", 8088.00, "completed"),
                (2, "2024-01-16 14:20:00", 168.00, "completed"),
                (1, "2024-01-17 09:15:00", 398.00, "pending"),
                (3, "2024-01-18 16:45:00", 7999.00, "completed")
            ]
            cursor.executemany("INSERT INTO orders (customer_id, order_date, total_amount, status) VALUES (?, ?, ?, ?)", orders)

            order_items = [
                (1, 1, 1, 7999.00),
                (1, 3, 1, 89.00),
                (2, 3, 1, 89.00),
                (2, 4, 1, 79.00),
                (3, 5, 2, 99.00),
                (3, 6, 1, 299.00),
                (4, 1, 1, 7999.00)
            ]
            cursor.executemany("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)", order_items)

        conn.commit()
        print("Demo database initialized successfully!")

