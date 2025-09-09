#!/usr/bin/env python3
"""
创建示例表和数据的脚本
用于测试 NL2SQL 系统
"""

import pymysql
from config import DB_CONFIG
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_sample_tables():
    """创建示例表和数据"""
    connection = None
    try:
        # 建立连接
        connection = pymysql.connect(
            cursorclass=pymysql.cursors.DictCursor,
            **DB_CONFIG
        )
        
        with connection.cursor() as cursor:
            # 创建客户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_name VARCHAR(200) NOT NULL COMMENT '公司名称',
                    contact_person VARCHAR(100) COMMENT '联系人',
                    id_card VARCHAR(18) COMMENT '身份证号',
                    phone VARCHAR(20) COMMENT '联系电话',
                    city VARCHAR(100) COMMENT '所在城市',
                    industry VARCHAR(100) COMMENT '行业',
                    risk_level ENUM('低', '中', '高') DEFAULT '低' COMMENT '风险等级',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户信息表'
            """)
            logger.info("创建 customers 表成功")
            
            # 创建产品表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    product_name VARCHAR(200) NOT NULL COMMENT '产品名称',
                    category VARCHAR(100) COMMENT '产品类别',
                    price DECIMAL(12,2) NOT NULL COMMENT '价格',
                    stock_quantity INT DEFAULT 0 COMMENT '库存数量',
                    supplier VARCHAR(200) COMMENT '供应商',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品信息表'
            """)
            logger.info("创建 products 表成功")
            
            # 创建订单表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_no VARCHAR(50) UNIQUE NOT NULL COMMENT '订单号',
                    customer_id INT NOT NULL COMMENT '客户ID',
                    product_id INT NOT NULL COMMENT '产品ID',
                    quantity INT NOT NULL COMMENT '数量',
                    unit_price DECIMAL(12,2) NOT NULL COMMENT '单价',
                    total_amount DECIMAL(12,2) NOT NULL COMMENT '总金额',
                    order_date DATE NOT NULL COMMENT '订单日期',
                    status ENUM('待处理', '已确认', '已发货', '已完成', '已取消') DEFAULT '待处理' COMMENT '订单状态',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单信息表'
            """)
            logger.info("创建 orders 表成功")
            
            # 创建高管信息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS executives (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT NOT NULL COMMENT '客户ID',
                    name VARCHAR(100) NOT NULL COMMENT '姓名',
                    position VARCHAR(100) COMMENT '职位',
                    id_card VARCHAR(18) COMMENT '身份证号',
                    phone VARCHAR(20) COMMENT '联系电话',
                    email VARCHAR(200) COMMENT '邮箱',
                    is_legal_person BOOLEAN DEFAULT FALSE COMMENT '是否法人',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='高管信息表'
            """)
            logger.info("创建 executives 表成功")
            
            # 插入示例客户数据
            cursor.execute("""
                INSERT INTO customers (company_name, contact_person, id_card, phone, city, industry, risk_level) VALUES
                ('大理矿业公司', '张明华', '532901198501234567', '13888888888', '大理', '矿业', '中'),
                ('昆明科技有限公司', '李小红', '530102199203156789', '13999999999', '昆明', '科技', '低'),
                ('丽江旅游集团', '王大强', '532701197812345678', '13777777777', '丽江', '旅游', '低'),
                ('曲靖钢铁厂', '赵建国', '530321196505234567', '13666666666', '曲靖', '钢铁', '高'),
                ('保山农业合作社', '陈美丽', '530521198909876543', '13555555555', '保山', '农业', '低')
                ON DUPLICATE KEY UPDATE 
                contact_person=VALUES(contact_person), 
                phone=VALUES(phone)
            """)
            logger.info("插入客户数据成功")
            
            # 插入示例产品数据
            cursor.execute("""
                INSERT INTO products (product_name, category, price, stock_quantity, supplier) VALUES
                ('铁矿石', '原材料', 850.00, 5000, '山西铁矿集团'),
                ('煤炭', '原材料', 650.00, 8000, '陕西煤业公司'),
                ('钢材', '金属制品', 4200.00, 2000, '宝钢集团'),
                ('水泥', '建材', 320.00, 10000, '海螺水泥'),
                ('化肥', '化工产品', 2800.00, 3000, '中化集团')
                ON DUPLICATE KEY UPDATE 
                price=VALUES(price), 
                stock_quantity=VALUES(stock_quantity)
            """)
            logger.info("插入产品数据成功")
            
            # 插入示例订单数据
            cursor.execute("""
                INSERT INTO orders (order_no, customer_id, product_id, quantity, unit_price, total_amount, order_date, status) VALUES
                ('ORD20250101001', 1, 1, 100, 850.00, 85000.00, '2025-01-01', '已完成'),
                ('ORD20250102001', 2, 3, 50, 4200.00, 210000.00, '2025-01-02', '已发货'),
                ('ORD20250103001', 3, 4, 200, 320.00, 64000.00, '2025-01-03', '已确认'),
                ('ORD20250104001', 4, 2, 150, 650.00, 97500.00, '2025-01-04', '待处理'),
                ('ORD20250105001', 5, 5, 80, 2800.00, 224000.00, '2025-01-05', '已完成')
                ON DUPLICATE KEY UPDATE 
                status=VALUES(status)
            """)
            logger.info("插入订单数据成功")
            
            # 插入示例高管数据
            cursor.execute("""
                INSERT INTO executives (customer_id, name, position, id_card, phone, email, is_legal_person) VALUES
                (1, '张明华', '董事长', '532901198501234567', '13888888888', 'zhang@dali-mining.com', TRUE),
                (1, '李建军', '总经理', '532901197203456789', '13888888889', 'li@dali-mining.com', FALSE),
                (2, '李小红', '法人代表', '530102199203156789', '13999999999', 'li@kunming-tech.com', TRUE),
                (3, '王大强', '总裁', '532701197812345678', '13777777777', 'wang@lijiang-tour.com', TRUE),
                (4, '赵建国', '厂长', '530321196505234567', '13666666666', 'zhao@qujing-steel.com', TRUE),
                (5, '陈美丽', '理事长', '530521198909876543', '13555555555', 'chen@baoshan-agri.com', TRUE)
                ON DUPLICATE KEY UPDATE 
                position=VALUES(position), 
                phone=VALUES(phone)
            """)
            logger.info("插入高管数据成功")
            
            # 提交事务
            connection.commit()
            logger.info("所有数据创建完成！")
            
            # 显示表统计信息
            cursor.execute("SELECT COUNT(*) as count FROM customers")
            customer_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM products")
            product_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM orders")
            order_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM executives")
            executive_count = cursor.fetchone()['count']
            
            print(f"\n=== 数据统计 ===")
            print(f"客户表 (customers): {customer_count} 条记录")
            print(f"产品表 (products): {product_count} 条记录")
            print(f"订单表 (orders): {order_count} 条记录")
            print(f"高管表 (executives): {executive_count} 条记录")
            print(f"\n现在可以测试查询：'查询客户风险模块大理矿业公司负责人身份证号'")
            
    except Exception as e:
        logger.error(f"创建表失败: {str(e)}")
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    create_sample_tables()
