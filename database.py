import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "mycom.db"
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def now_str():
    '''현재 시각을 초 단위 문자열로 반환'''
    return datetime.now().strftime(TIME_FMT)


def init_db():
    '''초기 테이블 생성 함수'''
    conn = get_db_connection()
    c = conn.cursor()
    # 사용자 테이블 생성
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_table (
        id_num INTEGER PRIMARY KEY AUTOINCREMENT,
        userid TEXT NOT NULL UNIQUE COLLATE NOCASE,
        username TEXT NOT NULL, 
        password TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # 설문 테이블 생성
    c.execute('''
    CREATE TABLE IF NOT EXISTS survey_table (
        id_num INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER,
        q6 INTEGER, q7 INTEGER, q8 INTEGER, q9 INTEGER, q10 INTEGER,
        created_at TEXT
    )
    ''')
    # 학습 이력 테이블 생성 (메뉴 클릭/체류 시간 기록)
    #  - std_time     : 메뉴에 들어간 시각
    #  - end_time     : 다른 메뉴로 이동(또는 로그아웃)한 시각
    #  - waiting_time : 해당 메뉴에 머문 시간(초 단위)
    c.execute('''
    CREATE TABLE IF NOT EXISTS learninghistory (
        id_num INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        userid TEXT NOT NULL,
        menu_id TEXT NOT NULL,
        std_time TEXT NOT NULL,
        end_time TEXT,
        waiting_time INTEGER,
        created_at TEXT NOT NULL
    )
    ''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_learninghistory_user ON learninghistory (userid, menu_id)")
    conn.commit()
    conn.close()


def create_user(userid, username, password, email):
    '''사용자 생성 함수'''
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO user_table (userid, username, password, email) VALUES (?, ?, ?, ?)",
                  (userid, username, password, email))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def login_user(userid, password):
    '''사용자 로그인 함수'''
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM user_table WHERE userid=? AND password=?", (userid, password))
    data = c.fetchall()
    conn.close()
    return data


def insert_survey_data(user_id, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10):
    '''설문 응답을 DB에 저장하는 함수'''
    conn = get_db_connection()
    c = conn.cursor()
    created_at = now_str()
    
    query = """
    INSERT INTO survey_table (user_id, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    c.execute(query, (user_id, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, created_at))
    conn.commit()
    conn.close()


def fetch_survey_data():
    '''설문 결과를 Pandas DataFrame으로 불러오는 함수'''
    conn = get_db_connection()
    query = "SELECT * FROM survey_table"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# =========================================================
# 학습 이력(learninghistory) 관련 함수
# =========================================================
def start_learning(userid, menu_id):
    '''메뉴가 클릭되었을 때 학습 이력 1건을 시작(INSERT)하고 그 id_num을 반환'''
    conn = get_db_connection()
    c = conn.cursor()
    t = now_str()
    c.execute(
        "INSERT INTO learninghistory (userid, menu_id, std_time, end_time, waiting_time, created_at) "
        "VALUES (?, ?, ?, NULL, NULL, ?)",
        (userid, menu_id, t, t),
    )
    conn.commit()
    history_id = c.lastrowid
    conn.close()
    return history_id


def end_learning(history_id):
    '''다른 메뉴로 이동할 때 진행 중이던 학습 이력을 마감(end_time, waiting_time[초])'''
    if not history_id:
        return None
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT std_time FROM learninghistory WHERE id_num=? AND end_time IS NULL", (history_id,))
    row = c.fetchone()
    if row is None:          # 이미 마감되었거나 없는 기록
        conn.close()
        return None
    end_dt = datetime.now().replace(microsecond=0)
    std_dt = datetime.strptime(row[0], TIME_FMT)
    waiting = max(0, int((end_dt - std_dt).total_seconds()))
    c.execute(
        "UPDATE learninghistory SET end_time=?, waiting_time=? WHERE id_num=?",
        (end_dt.strftime(TIME_FMT), waiting, history_id),
    )
    conn.commit()
    conn.close()
    return waiting


def get_menu_usage(userid):
    '''사용자의 메뉴별 누적 체류시간(초)과 클릭 수를 {menu_id: (총초, 횟수)} 형태로 반환'''
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT menu_id, COALESCE(SUM(waiting_time), 0) AS total_sec, COUNT(*) AS cnt
        FROM learninghistory
        WHERE userid = ? COLLATE NOCASE AND waiting_time IS NOT NULL
        GROUP BY menu_id
        """,
        (userid,),
    )
    rows = c.fetchall()
    conn.close()
    return {menu_id: (int(total), int(cnt)) for menu_id, total, cnt in rows}


def fetch_learning_history(userid, limit=30):
    '''사용자의 최근 학습 이력을 DataFrame으로 반환'''
    conn = get_db_connection()
    df = pd.read_sql_query(
        """
        SELECT id_num, userid, menu_id, std_time, end_time, waiting_time, created_at
        FROM learninghistory
        WHERE userid = ? COLLATE NOCASE
        ORDER BY id_num DESC
        LIMIT ?
        """,
        conn,
        params=(userid, limit),
    )
    conn.close()
    return df
