import os
import subprocess
import urllib.parse
import pyodbc


def get_available_odbc_driver():
    """Detect available SQL Server ODBC drivers in priority order."""
    installed = pyodbc.drivers()
    preferred = [
        'ODBC Driver 18 for SQL Server',
        'ODBC Driver 17 for SQL Server',
        'ODBC Driver 13 for SQL Server',
        'SQL Server Native Client 11.0',
        'SQL Server'
    ]
    for driver in preferred:
        if driver in installed:
            return driver
    return 'SQL Server'


def resolve_localdb_server(server_name, driver):
    """
    Ensure LocalDB instance is started and resolve the pipe name
    if using the legacy 'SQL Server' driver which does not resolve
    (localdb)\\... syntax directly.
    """
    if server_name and server_name.lower().startswith('(localdb)'):
        instance = server_name.split('\\')[-1] if '\\' in server_name else 'MSSQLLocalDB'
        try:
            subprocess.run(['sqllocaldb', 'start', instance], capture_output=True, text=True)
            if driver == 'SQL Server':
                output = subprocess.check_output(['sqllocaldb', 'info', instance], text=True)
                for line in output.splitlines():
                    if 'Instance pipe name:' in line:
                        pipe = line.split('Instance pipe name:')[1].strip()
                        if pipe:
                            return pipe
        except Exception as e:
            print(f"[LocalDB Warning] Could not query sqllocaldb: {e}")
    return server_name


def ensure_database_exists(driver, resolved_server, db_name):
    """Ensure the target database exists on SQL Server LocalDB."""
    try:
        master_conn = f"DRIVER={{{driver}}};SERVER={resolved_server};DATABASE=master;Trusted_Connection=yes;"
        conn = pyodbc.connect(master_conn, autocommit=True, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sys.databases WHERE name = ?", (db_name,))
        if not cursor.fetchone():
            cursor.execute(f"CREATE DATABASE [{db_name}]")
            print(f"[LocalDB] Database '{db_name}' created successfully.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[LocalDB Info] Database existence check: {e}")


def build_sqlalchemy_uri():
    """Construct a SQLAlchemy connection URI for SQL Server LocalDB."""
    server = os.environ.get('DB_SERVER', r'(localdb)\MSSQLLocalDB')
    db_name = os.environ.get('DB_NAME', 'AcxiomCrmDb')
    driver = get_available_odbc_driver()
    resolved_server = resolve_localdb_server(server, driver)
    
    # Auto-ensure database exists
    ensure_database_exists(driver, resolved_server, db_name)

    conn_params = [
        f"DRIVER={{{driver}}}",
        f"SERVER={resolved_server}",
        f"DATABASE={db_name}",
        "Trusted_Connection=yes"
    ]
    if 'ODBC Driver 18' in driver:
        conn_params.append("TrustServerCertificate=yes")

    odbc_str = ";".join(conn_params) + ";"
    encoded_params = urllib.parse.quote_plus(odbc_str)
    return f"mssql+pyodbc:///?odbc_connect={encoded_params}"


class Config:
    """Base configuration settings for Acxiom CRM."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'acxiom-crm-dev-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = build_sqlalchemy_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'use_setinputsizes': False
    }
    WTF_CSRF_ENABLED = True
