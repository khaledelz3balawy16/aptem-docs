"""Read the learner cohort from the existing LMS.Aptem_users table in Neon.

That table is not managed by Django, so we read it with raw SQL. Column names
have spaces / mixed case, so they must stay double-quoted.
"""

from django.db import connection

ACTIVE_STATUS = "Active"


def get_active_learners(program_contains=None):
    """Return active learners as dicts: {id, full_name, program_name}.

    If `program_contains` is given, only learners whose Program Name contains
    that substring (case-insensitive) are returned.
    """
    sql = '''
        SELECT "ID", "FullName", "Program Name"
        FROM "LMS"."Aptem_users"
        WHERE "Program-Status" = %s
          AND "ID" IS NOT NULL
    '''
    params = [ACTIVE_STATUS]

    if program_contains:
        sql += ' AND "Program Name" ILIKE %s'
        params.append(f"%{program_contains}%")

    sql += ' ORDER BY "Program Name", "ID"'

    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        {"id": r[0], "full_name": r[1] or "", "program_name": r[2]}
        for r in rows
    ]
