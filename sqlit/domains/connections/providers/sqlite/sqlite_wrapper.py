import re
import sqlite3
import subprocess

## for dev use
def dump(text):
    with open("dump", "w") as f:
        f.write(text)

def popen(updater):
    return subprocess.Popen(
        ["bb", "-I", "-O", "--stream", "-e", updater],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # Handles stdin/stdout as strings instead of bytes
        bufsize=1,  # Line-buffered for real-time streaming
    )

def run_update(sql, cursor):

    sql_regex = r"updateclj\s+(\w+)\s+set\s+(\w+)\s+=(.*?)(where.*?)use primary key(.*)" # admittedly slightly hacky

    table_name, col_name, updater, where, primary_key = re.search(sql_regex, sql).groups()

    process = popen(updater)

    try:

        select = f'select {primary_key}, {col_name} from {table_name} {where}'
        update = f'update {table_name} set {col_name} = ? where {primary_key} = ?'

        results = cursor.execute(select).fetchall()

        for k, edn1 in results:
            process.stdin.write(edn1 + '\n')
            process.stdin.flush()
            edn2 = process.stdout.readline().strip()
            cursor.execute(update, (edn2, k))

        return len(results)

        # updateclj company set details = (assoc *input* :hi 3) where company_id > 7 use primary key company_id

    finally:

        process.stdin.close()
        process.stdout.close()
        process.terminate()

def run_select(sql, cursor):

    sql_regex = r"selectclj(.*?)(\[.*?\])(.*)"
    prior, get_in, rest = re.search(sql_regex, sql).groups()

    updater = '(keys *input*)' if get_in == '[:keys]' else f'(get-in *input* {get_in} -1)'
    process = popen(updater)

    try:

        select = f'select {prior} {rest}'
        results = cursor.execute(select).fetchall()
        out = []

        for row in results:
            process.stdin.write(row[0] + '\n')
            process.stdin.flush()

            v = process.stdout.readline().strip()
            out.append([v])

        return out

    finally:

        process.stdin.close()
        process.stdout.close()
        process.terminate()

class Cursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._rowcount = None
        self._results = None

    def execute(self, sql, params=()):
        sql2 = sql.lstrip().lower()
        if sql2.startswith("updateclj"):
            self._rowcount = run_update(sql2, self._cursor)
            return

        if sql2.startswith("selectclj"):
            self._results = run_select(sql2, self._cursor)
            return

        self._cursor.execute(sql, params)

    @property
    def rowcount(self):
        if self._rowcount is not None:
            return self._rowcount
        return self._cursor.rowcount

    def fetchall(self):
        if self._results is not None:
            return self._results
        return self._cursor.fetchall()

    def fetchmany(self, n):
        if self._results is not None:
            return self._results
        return self._cursor.fetchmany(n)

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


