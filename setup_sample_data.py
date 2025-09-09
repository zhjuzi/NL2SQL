#!/usr/bin/env python3
"""
Sample database setup script for NL2SQL testing
Creates sample tables and data for demonstration
"""

import pymysql
from database import DB_CONFIG
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_sample_tables():
    """Create sample tables for testing"""
    
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            
            # Create customers table
            logger.info("Creating customers table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL COMMENT 'Customer full name',
                    email VARCHAR(100) UNIQUE NOT NULL COMMENT 'Customer email address',
                    phone VARCHAR(20) COMMENT 'Customer phone number',
                    city VARCHAR(50) COMMENT 'Customer city',
                    country VARCHAR(50) COMMENT 'Customer country',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Customer creation date',
                    INDEX idx_city (city),
                    INDEX idx_country (country)
                ) COMMENT='Customer information table'
            """)
            
            # Create products table
            logger.info("Creating products table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL COMMENT 'Product name',
                    description TEXT COMMENT 'Product description',
                    price DECIMAL(10,2) NOT NULL COMMENT 'Product price',
                    category VARCHAR(50) COMMENT 'Product category',
                    stock_quantity INT DEFAULT 0 COMMENT 'Available stock quantity',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Product creation date',
                    INDEX idx_category (category),
                    INDEX idx_price (price)
                ) COMMENT='Product catalog table'
            """)
            
            # Create orders table
            logger.info("Creating orders table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT NOT NULL COMMENT 'Customer ID',
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Order date',
                    total_amount DECIMAL(10,2) NOT NULL COMMENT 'Total order amount',
                    status VARCHAR(20) DEFAULT 'pending' COMMENT 'Order status',
                    shipping_address TEXT COMMENT 'Shipping address',
                    INDEX idx_customer_id (customer_id),
                    INDEX idx_order_date (order_date),
                    INDEX idx_status (status),
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                ) COMMENT='Customer orders table'
            """)
            
            # Create order_items table
            logger.info("Creating order_items table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_id INT NOT NULL COMMENT 'Order ID',
                    product_id INT NOT NULL COMMENT 'Product ID',
                    quantity INT NOT NULL COMMENT 'Quantity ordered',
                    unit_price DECIMAL(10,2) NOT NULL COMMENT 'Price per unit',
                    subtotal DECIMAL(10,2) NOT NULL COMMENT 'Line item subtotal',
                    INDEX idx_order_id (order_id),
                    INDEX idx_product_id (product_id),
                    FOREIGN KEY (order_id) REFERENCES orders(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                ) COMMENT='Order line items table'
            """)
            
            # Create employees table
            logger.info("Creating employees table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL COMMENT 'Employee full name',
                    email VARCHAR(100) UNIQUE NOT NULL COMMENT 'Employee email',
                    department VARCHAR(50) COMMENT 'Employee department',
                    position VARCHAR(50) COMMENT 'Job position',
                    salary DECIMAL(10,2) COMMENT 'Employee salary',
                    hire_date DATE COMMENT 'Hire date',
                    manager_id INT COMMENT 'Manager ID (self-referencing)',
                    INDEX idx_department (department),
                    INDEX idx_manager_id (manager_id),
                    FOREIGN KEY (manager_id) REFERENCES employees(id)
                ) COMMENT='Employee information table'
            """)
            
            connection.commit()
            logger.info("Sample tables created successfully!")
            
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()

def insert_sample_data():
    """Insert sample data for testing"""
    
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            
            # Insert sample customers
            logger.info("Inserting sample customers...")
            customers_data = [
                ('John Doe', 'john@example.com', '555-0101', 'New York', 'USA'),
                ('Jane Smith', 'jane@example.com', '555-0102', 'Los Angeles', 'USA'),
                ('Bob Johnson', 'bob@example.com', '555-0103', 'Chicago', 'USA'),
                ('Alice Brown', 'alice@example.com', '555-0104', 'Houston', 'USA'),
                ('Charlie Wilson', 'charlie@example.com', '555-0105', 'Phoenix', 'USA'),
                ('Diana Davis', 'diana@example.com', '555-0106', 'Beijing', 'China'),
                ('Eva Martinez', 'eva@example.com', '555-0107', 'Shanghai', 'China'),
                ('Frank Lee', 'frank@example.com', '555-0108', 'Tokyo', 'Japan'),
            ]
            
            cursor.executemany("""
                INSERT INTO customers (name, email, phone, city, country) 
                VALUES (%s, %s, %s, %s, %s)
            """, customers_data)
            
            # Insert sample products
            logger.info("Inserting sample products...")
            products_data = [
                ('Laptop', 'High-performance laptop computer', 999.99, 'Electronics', 50),
                ('Smartphone', 'Latest model smartphone', 699.99, 'Electronics', 100),
                ('Headphones', 'Wireless noise-canceling headphones', 199.99, 'Electronics', 75),
                ('Coffee Maker', 'Automatic coffee maker', 89.99, 'Home Appliances', 30),
                ('Desk Chair', 'Ergonomic office chair', 249.99, 'Furniture', 25),
                ('Notebook', 'Premium quality notebook', 12.99, 'Stationery', 200),
                ('Pen Set', 'Professional pen set', 24.99, 'Stationery', 150),
                ('Monitor', '27-inch LED monitor', 299.99, 'Electronics', 40),
            ]
            
            cursor.executemany("""
                INSERT INTO products (name, description, price, category, stock_quantity) 
                VALUES (%s, %s, %s, %s, %s)
            """, products_data)
            
            # Insert sample orders
            logger.info("Inserting sample orders...")
            orders_data = [
                (1, 1299.98, 'completed', '123 Main St, New York, NY'),
                (2, 699.99, 'completed', '456 Oak Ave, Los Angeles, CA'),
                (3, 339.98, 'shipped', '789 Pine Rd, Chicago, IL'),
                (4, 24.99, 'pending', '321 Elm St, Houston, TX'),
                (5, 249.99, 'completed', '654 Maple Dr, Phoenix, AZ'),
                (6, 999.99, 'processing', '987 Cedar Ln, Beijing, China'),
                (7, 199.99, 'completed', '147 Birch Way, Shanghai, China'),
                (8, 312.98, 'shipped', '258 Spruce Ct, Tokyo, Japan'),
            ]
            
            cursor.executemany("""
                INSERT INTO orders (customer_id, total_amount, status, shipping_address) 
                VALUES (%s, %s, %s, %s)
            """, orders_data)
            
            # Insert sample order items
            logger.info("Inserting sample order items...")
            order_items_data = [
                (1, 1, 1, 999.99, 999.99),  # Order 1: 1 Laptop
                (1, 2, 1, 299.99, 299.99),  # Order 1: 1 Monitor
                (2, 2, 1, 699.99, 699.99),  # Order 2: 1 Smartphone
                (3, 3, 1, 199.99, 199.99),  # Order 3: 1 Headphones
                (3, 7, 2, 12.99, 25.98),    # Order 3: 2 Notebooks
                (3, 8, 2, 24.99, 49.99),    # Order 3: 2 Pen Sets
                (4, 8, 1, 24.99, 24.99),    # Order 4: 1 Pen Set
                (5, 5, 1, 249.99, 249.99),  # Order 5: 1 Desk Chair
                (6, 1, 1, 999.99, 999.99),  # Order 6: 1 Laptop
                (7, 3, 1, 199.99, 199.99),  # Order 7: 1 Headphones
                (8, 2, 1, 699.99, 699.99),  # Order 8: 1 Smartphone
                (8, 8, 1, 24.99, 24.99),    # Order 8: 1 Pen Set
                (8, 7, 2, 12.99, 25.98),    # Order 8: 2 Notebooks
            ]
            
            cursor.executemany("""
                INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal) 
                VALUES (%s, %s, %s, %s, %s)
            """, order_items_data)
            
            # Insert sample employees
            logger.info("Inserting sample employees...")
            employees_data = [
                ('Manager One', 'manager1@company.com', 'Management', 'General Manager', 80000.00, '2020-01-15', None),
                ('John Manager', 'john.m@company.com', 'Sales', 'Sales Manager', 65000.00, '2020-03-01', 1),
                ('Jane Leader', 'jane.l@company.com', 'IT', 'IT Manager', 70000.00, '2020-02-15', 1),
                ('Bob Developer', 'bob.d@company.com', 'IT', 'Senior Developer', 55000.00, '2021-01-10', 3),
                ('Alice Designer', 'alice.de@company.com', 'Design', 'UI/UX Designer', 45000.00, '2021-06-01', 1),
                ('Charlie Sales', 'charlie.s@company.com', 'Sales', 'Sales Representative', 40000.00, '2021-09-15', 2),
            ]
            
            cursor.executemany("""
                INSERT INTO employees (name, email, department, position, salary, hire_date, manager_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, employees_data)
            
            connection.commit()
            logger.info("Sample data inserted successfully!")
            
    except Exception as e:
        logger.error(f"Failed to insert sample data: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()

def show_sample_queries():
    """Show some example queries that users can try"""
    
    sample_queries = [
        "Show me all customers",
        "Find customers from China",
        "Show me all products in Electronics category",
        "What are the top 3 most expensive products?",
        "Show me all orders with status completed",
        "Find orders with total amount greater than 500",
        "Show me all employees in IT department",
        "Find employees with salary greater than 50000",
        "显示所有客户信息",
        "查询电子产品类别的商品",
        "显示工资大于60000的员工",
        "查询已完成的订单",
    ]
    
    print("\n" + "="*60)
    print("SAMPLE QUERIES YOU CAN TRY")
    print("="*60)
    
    for i, query in enumerate(sample_queries, 1):
        print(f"{i:2d}. {query}")
    
    print("\nYou can test these queries using:")
    print("curl -X POST http://localhost:8000/query \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"question\": \"YOUR_QUERY_HERE\"}'")

def main():
    """Main setup function"""
    
    print("="*60)
    print("NL2SQL Sample Database Setup")
    print("="*60)
    
    print("\nThis script will create sample tables and data for testing the NL2SQL system.")
    print("Make sure your MySQL database is running and configured properly.")
    
    response = input("\nDo you want to proceed? (yes/no): ")
    if response.lower() != 'yes':
        print("Setup cancelled.")
        return
    
    try:
        # Create tables
        create_sample_tables()
        
        # Insert sample data
        insert_sample_data()
        
        # Show sample queries
        show_sample_queries()
        
        print("\n" + "="*60)
        print("SETUP COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nNext steps:")
        print("1. Start the NL2SQL server: python main.py")
        print("2. Test the system with the sample queries above")
        print("3. Use the test script: python test_system.py")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        print("Please check your database configuration and try again.")

if __name__ == "__main__":
    main()