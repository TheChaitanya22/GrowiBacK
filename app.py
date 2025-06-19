import os
import aiomysql
from quart import Quart, request, jsonify
from quart_cors import cors
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

app = Quart(__name__)
app = cors(app, allow_origin="http://localhost:3000")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'db': os.getenv('DB_NAME', 'contact_db'),
    'charset': 'utf8mb4',
    'autocommit': True
}

# Global connection pool
pool = None

async def init_db_pool():
    """Initialize the database connection pool"""
    global pool
    try:
        pool = await aiomysql.create_pool(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            db=DB_CONFIG['db'],
            charset=DB_CONFIG['charset'],
            autocommit=DB_CONFIG['autocommit'],
            minsize=1,
            maxsize=20
        )
        logger.info("Database connection pool created successfully")
        
        # Create table if it doesn't exist
        await create_table()
        
    except Exception as e:
        logger.error(f"Failed to create database pool: {e}")
        raise

async def create_table():
    """Create the contacts table if it doesn't exist"""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS contacts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(100) NOT NULL,
        phone VARCHAR(20),
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(create_table_query)
            logger.info("Contacts table created/verified successfully")

@app.before_serving
async def startup():
    """Initialize database pool before serving requests"""
    await init_db_pool()

@app.after_serving
async def cleanup():
    """Clean up database pool after serving"""
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        logger.info("Database connection pool closed")

@app.route('/api/contact', methods=['POST'])
async def create_contact():
    """Handle contact form submission"""
    try:
        data = await request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
                
        # Validate email format (basic validation)
        email = data.get('email')
        if '@' not in email or '.' not in email:
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Insert data into database
        insert_query = """
        INSERT INTO contacts (name, email, phone, message)
        VALUES (%s, %s, %s, %s)
        """
        
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(insert_query, (
                    data.get('name').strip(),
                    email.strip().lower(),
                    data.get('phone', '').strip(),
                    data.get('message').strip()
                ))
                
                contact_id = cursor.lastrowid
                logger.info(f"Contact created with ID: {contact_id}")
                
        return jsonify({
            'message': 'Contact created successfully',
            'id': contact_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    

@app.route('/api/contacts', methods=['GET'])
async def get_contacts():
    """Get all contacts (for testing purposes)"""
    try:
        select_query = """
        SELECT id, name, email, phone, message, created_at
        FROM contacts
        ORDER BY created_at DESC
        """
        
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(select_query)
                contacts = await cursor.fetchall()
                
        return jsonify({
            'contacts': contacts,
            'count': len(contacts)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching contacts: {e}")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)