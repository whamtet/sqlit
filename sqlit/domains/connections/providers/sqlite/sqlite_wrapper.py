import re
import sqlite3
import subprocess

## for dev use
def spit(text):
    with open("dump", "w") as f:
        f.write(text)

def process_rows(sql, cursor):

    sql_regex = r"updateclj\s+(\w+)\s+set\s+(\w+)\s+=(.*?)(where.*?)use primary key(.*)" # admittedly slightly hacky

    table_name, col_name, updater, where, primary_key = re.search(sql_regex, sql).groups()

    process = subprocess.Popen(
        ["bb", "-I", "-O", "--stream", "-e", updater],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # Handles stdin/stdout as strings instead of bytes
        bufsize=1,  # Line-buffered for real-time streaming
    )

    try:

        select = f'select {primary_key}, {col_name} from {table_name} {where}'
        results = cursor.execute(select).fetchall()

        for k, edn1 in results:
            process.stdin.write(edn1 + '\n')
            process.stdin.flush()
            edn2 = process.stdout.readline().strip()

            cursor.execute(
                f'update {table_name} set {col_name} = ? where {primary_key} = ?',
                (edn2, k)
            )

#updateclj company set details = (assoc *input* :hi :there) where company_id = 9 use primary key company_id

    finally:

        process.stdin.close()
        process.stdout.close()
        process.terminate()

class Cursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=()):
        sql2 = sql.lstrip().lower()
        if sql2.startswith("updateclj"):
            return process_rows(sql2, self._cursor)

        return self._cursor.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class Connection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return Cursor(self._conn.cursor())

    def __getattr__(self, name):
        return getattr(self._conn, name)


def konnect(*args, **kwargs):
    return Connection(sqlite3.connect(*args, **kwargs))


