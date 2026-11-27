import json
import math
import uuid

from django.db import connection

from .program_status_services import list_program_statuses, normalize_program_status


PAGE_SIZE = 10

DOCUMENT_COLUMNS = [
    {"key": "apprenticeship-agreement", "label": "Apprenticeship Agreement"},
    {"key": "training-plan", "label": "Training Plan"},
    {"key": "written-agreement", "label": "Written Agreement"},
    {"key": "individual-learning-record", "label": "Individual Learning Record"},
    {"key": "contract-for-service", "label": "Contract for Service"},
    {"key": "cv", "label": "CV"},
    {"key": "cv-job-description", "label": "CV / Job Description"},
]

DOCUMENT_KEY_BY_NAME = {
    "Apprenticeship Agreement": "apprenticeship-agreement",
    "Training Plan": "training-plan",
    "Training Plan 25/26": "training-plan",
    "Written Agreement": "written-agreement",
    "Written Agreement 25/26": "written-agreement",
    "Individual Learning Record": "individual-learning-record",
    "Contract for Service": "contract-for-service",
}

MISSING_ILR_LEARNERS_SQL = """
    SELECT
        -missing_ilr.id AS learner_id,
        CONCAT_WS(' ', missing_ilr.given_names, missing_ilr.family_name) AS full_name,
        missing_ilr.email,
        NULL::text AS program_name,
        NULL::text AS program_status,
        missing_ilr.learn_start_date AS aptem_start_date,
        missing_ilr.learn_plan_end_date AS aptem_end_date,
        missing_ilr.planned_hours::numeric AS aptem_planned_hours
    FROM (
        SELECT DISTINCT ON (LOWER(TRIM(delivery.email)))
            delivery.id,
            delivery.given_names,
            delivery.family_name,
            delivery.email,
            delivery.learn_start_date,
            delivery.learn_plan_end_date,
            delivery.planned_hours
        FROM "Audit".ilr_learning_deliveries delivery
        WHERE NULLIF(TRIM(delivery.email), '') IS NOT NULL
        ORDER BY LOWER(TRIM(delivery.email)),
                 (delivery.aim_type = 1) DESC,
                 (delivery.planned_hours IS NOT NULL) DESC,
                 delivery.updated_at DESC NULLS LAST,
                 delivery.id DESC
    ) missing_ilr
    WHERE NOT EXISTS (
        SELECT 1
        FROM fetching_evidence.aptem_cv_contracts_probe document_learner
        WHERE LOWER(TRIM(document_learner.email)) = LOWER(TRIM(missing_ilr.email))
           OR LOWER(REGEXP_REPLACE(TRIM(document_learner.full_name), '\\s+', ' ', 'g'))
              = LOWER(REGEXP_REPLACE(
                    TRIM(CONCAT_WS(' ', missing_ilr.given_names, missing_ilr.family_name)),
                    '\\s+', ' ', 'g'
                ))
    )
"""


def dict_fetchall(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def dict_fetchone(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def document_column_key(document):
    if document["document_category"] == "CV":
        return "cv"
    if document["document_category"] == "CV_TEXT":
        return "cv-job-description"
    return DOCUMENT_KEY_BY_NAME.get(document["document_name"], "other")


def list_documents(
    page=1,
    search="",
    learner_scope="ilr",
    program_status="all",
):
    safe_page = max(int(page or 1), 1)
    normalized_scope = str(learner_scope or "ilr").strip().lower()
    if normalized_scope not in {"ilr", "all"}:
        raise ValueError("Invalid learner scope.")

    missing_ilr_union = ""
    if normalized_scope == "ilr":
        missing_ilr_union = f"UNION ALL {MISSING_ILR_LEARNERS_SQL}"

    filter_conditions = []
    params = []
    normalized_program_status = normalize_program_status(program_status)

    if normalized_scope == "ilr":
        filter_conditions.append(
            """
            EXISTS (
                SELECT 1
                FROM "Audit".ilr_learning_deliveries scope_delivery
                WHERE LOWER(TRIM(scope_delivery.email)) = LOWER(TRIM(learner.email))
                   OR LOWER(REGEXP_REPLACE(
                        TRIM(CONCAT_WS(' ', scope_delivery.given_names, scope_delivery.family_name)),
                        '\\s+', ' ', 'g'
                    )) = LOWER(REGEXP_REPLACE(TRIM(learner.full_name), '\\s+', ' ', 'g'))
            )
            """
        )

    if search.strip():
        pattern = f"%{search.strip()}%"
        filter_conditions.append(
            """
            (
                learner.full_name ILIKE %s
                OR COALESCE(learner.email, '') ILIKE %s
                OR COALESCE(learner.program_name, '') ILIKE %s
                OR EXISTS (
                    SELECT 1
                    FROM fetching_evidence.aptem_cv_contracts_probe search_doc
                    WHERE search_doc.learner_id = learner.learner_id
                      AND search_doc.document_name ILIKE %s
                )
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern])

    if normalized_program_status != "all":
        filter_conditions.append(
            "LOWER(TRIM(COALESCE(learner.program_status, ''))) = %s"
        )
        params.append(normalized_program_status)

    search_condition = ""
    if filter_conditions:
        search_condition = "WHERE " + " AND ".join(filter_conditions)

    offset = (safe_page - 1) * PAGE_SIZE

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH learner AS (
                SELECT
                    p.learner_id,
                    MAX(
                        COALESCE(
                            NULLIF(p.full_name, ''),
                            NULLIF(u."FullName", ''),
                            INITCAP(REPLACE(
                                SPLIT_PART(COALESCE(p.email, u."Email", ''), '@', 1),
                                '.',
                                ' '
                            ))
                        )
                    ) AS full_name,
                    MAX(COALESCE(NULLIF(p.email, ''), u."Email")) AS email,
                    COALESCE(
                        MAX(NULLIF(p.current_programme, '')),
                        (
                            ARRAY_AGG(
                                NULLIF(p.program_name, '')
                                ORDER BY (p.document_name IN (
                                    'Training Plan', 'Training Plan 25/26',
                                    'Apprenticeship Agreement'
                                )) DESC,
                                p.date DESC NULLS LAST,
                                p.id DESC
                            ) FILTER (WHERE NULLIF(p.program_name, '') IS NOT NULL)
                        )[1],
                        MAX(u."Program Name")
                    ) AS program_name,
                    MAX(COALESCE(
                        NULLIF(p.program_status, ''),
                        NULLIF(u."Program-Status", '')
                    )) AS program_status,
                    MAX(COALESCE(
                        p.program_start_date::date,
                        u."Start-Date"
                    )) AS aptem_start_date,
                    MAX(COALESCE(
                        p.planned_end_date::date,
                        u."End-Date"
                    )) AS aptem_end_date,
                    MAX(COALESCE(
                        p.planned,
                        u."Planned"
                    )) AS aptem_planned_hours
                FROM fetching_evidence.aptem_cv_contracts_probe p
                LEFT JOIN "LMS"."Aptem_users" u ON u."ID" = p.learner_id
                GROUP BY p.learner_id
                HAVING NOT BOOL_OR(
                    LOWER(TRIM(COALESCE(
                        NULLIF(p.current_programme, ''),
                        NULLIF(p.program_name, ''),
                        u."Program Name",
                        ''
                    ))) = 'project control professional level 6 - al fanar'
                )
                {missing_ilr_union}
            )
            SELECT
                learner.learner_id::text,
                learner.full_name,
                learner.email,
                learner.program_name,
                learner.program_status,
                COALESCE(ilr.learn_start_date, learner.aptem_start_date) AS learn_start_date,
                COALESCE(ilr.learn_plan_end_date, learner.aptem_end_date) AS learn_plan_end_date,
                COALESCE(ilr.planned_hours, learner.aptem_planned_hours) AS planned_hours,
                (
                    SELECT otj.training_plan_planned_hours
                    FROM fetching_evidence.aptem_cv_contracts_probe otj
                    WHERE otj.learner_id = learner.learner_id
                      AND otj.document_name IN ('Training Plan', 'Training Plan 25/26')
                      AND LOWER(TRIM(otj.program_name)) = LOWER(TRIM(learner.program_name))
                    ORDER BY COALESCE(
                        otj.fully_signed_date,
                        otj.learner_signed_date,
                        otj.date
                    ) DESC NULLS LAST,
                    otj.id DESC
                    LIMIT 1
                ) AS training_plan_planned_hours,
                (
                    SELECT otj.apprenticeship_agreement_planned_hours
                    FROM fetching_evidence.aptem_cv_contracts_probe otj
                    WHERE otj.learner_id = learner.learner_id
                      AND otj.document_name = 'Apprenticeship Agreement'
                      AND LOWER(TRIM(otj.program_name)) = LOWER(TRIM(learner.program_name))
                    ORDER BY COALESCE(
                        otj.fully_signed_date,
                        otj.learner_signed_date,
                        otj.date
                    ) DESC NULLS LAST,
                    otj.id DESC
                    LIMIT 1
                ) AS apprenticeship_agreement_planned_hours
            FROM learner
            LEFT JOIN LATERAL (
                SELECT learner_email
                FROM "Audit".learner_match
                WHERE aptem_id = learner.learner_id
                ORDER BY (NULLIF(TRIM(learner_email), '') IS NOT NULL) DESC,
                         lms_id DESC NULLS LAST
                LIMIT 1
            ) learner_match ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    delivery.learn_start_date,
                    delivery.learn_plan_end_date,
                    delivery.planned_hours
                FROM "Audit".ilr_learning_deliveries delivery
                WHERE LOWER(TRIM(delivery.email)) = LOWER(TRIM(COALESCE(
                        NULLIF(learner_match.learner_email, ''),
                        learner.email
                    )))
                   OR LOWER(REGEXP_REPLACE(
                        TRIM(CONCAT_WS(' ', delivery.given_names, delivery.family_name)),
                        '\\s+', ' ', 'g'
                    )) = LOWER(REGEXP_REPLACE(TRIM(learner.full_name), '\\s+', ' ', 'g'))
                ORDER BY (delivery.aim_type = 1) DESC,
                         (delivery.planned_hours IS NOT NULL) DESC,
                         delivery.updated_at DESC NULLS LAST,
                         delivery.source_datetime DESC NULLS LAST,
                         delivery.id DESC
                LIMIT 1
            ) ilr ON TRUE
            {search_condition}
            ORDER BY learner.full_name ASC, learner.learner_id ASC
            LIMIT %s OFFSET %s
            """,
            [*params, PAGE_SIZE, offset],
        )
        learners = dict_fetchall(cursor)

        cursor.execute(
            f"""
            WITH learner AS (
                SELECT
                    p.learner_id,
                    MAX(
                        COALESCE(
                            NULLIF(p.full_name, ''),
                            NULLIF(u."FullName", ''),
                            INITCAP(REPLACE(
                                SPLIT_PART(COALESCE(p.email, u."Email", ''), '@', 1),
                                '.',
                                ' '
                            ))
                        )
                    ) AS full_name,
                    MAX(COALESCE(NULLIF(p.email, ''), u."Email")) AS email,
                    COALESCE(
                        MAX(NULLIF(p.current_programme, '')),
                        (
                            ARRAY_AGG(
                                NULLIF(p.program_name, '')
                                ORDER BY (p.document_name IN (
                                    'Training Plan', 'Training Plan 25/26',
                                    'Apprenticeship Agreement'
                                )) DESC,
                                p.date DESC NULLS LAST,
                                p.id DESC
                            ) FILTER (WHERE NULLIF(p.program_name, '') IS NOT NULL)
                        )[1],
                        MAX(u."Program Name")
                    ) AS program_name,
                    MAX(COALESCE(
                        NULLIF(p.program_status, ''),
                        NULLIF(u."Program-Status", '')
                    )) AS program_status,
                    NULL::date AS aptem_start_date,
                    NULL::date AS aptem_end_date,
                    NULL::numeric AS aptem_planned_hours
                FROM fetching_evidence.aptem_cv_contracts_probe p
                LEFT JOIN "LMS"."Aptem_users" u ON u."ID" = p.learner_id
                GROUP BY p.learner_id
                HAVING NOT BOOL_OR(
                    LOWER(TRIM(COALESCE(
                        NULLIF(p.current_programme, ''),
                        NULLIF(p.program_name, ''),
                        u."Program Name",
                        ''
                    ))) = 'project control professional level 6 - al fanar'
                )
                {missing_ilr_union}
            )
            SELECT COUNT(*)::int AS count
            FROM learner
            {search_condition}
            """,
            params,
        )
        total = cursor.fetchone()[0]

        learner_ids = [
            int(learner["learner_id"])
            for learner in learners
            if int(learner["learner_id"]) > 0
        ]
        documents = []
        if learner_ids:
            cursor.execute(
                """
                SELECT
                    id::text,
                    learner_id::text,
                    document_category,
                    document_name,
                    file,
                    status,
                    date,
                    updated_to,
                    fetched_at
                FROM fetching_evidence.aptem_cv_contracts_probe
                WHERE learner_id = ANY(%s)
                ORDER BY date DESC NULLS LAST, id DESC
                """,
                [learner_ids],
            )
            documents = dict_fetchall(cursor)

        cursor.execute(
            f"""
            WITH learner AS (
                SELECT
                    p.learner_id,
                    MAX(
                        COALESCE(
                            NULLIF(p.full_name, ''),
                            NULLIF(u."FullName", ''),
                            INITCAP(REPLACE(
                                SPLIT_PART(COALESCE(p.email, u."Email", ''), '@', 1),
                                '.',
                                ' '
                            ))
                        )
                    ) AS full_name,
                    MAX(COALESCE(NULLIF(p.email, ''), u."Email")) AS email,
                    COALESCE(
                        MAX(NULLIF(p.current_programme, '')),
                        (
                            ARRAY_AGG(
                                NULLIF(p.program_name, '')
                                ORDER BY (p.document_name IN (
                                    'Training Plan', 'Training Plan 25/26',
                                    'Apprenticeship Agreement'
                                )) DESC,
                                p.date DESC NULLS LAST,
                                p.id DESC
                            ) FILTER (WHERE NULLIF(p.program_name, '') IS NOT NULL)
                        )[1],
                        MAX(u."Program Name")
                    ) AS program_name,
                    MAX(COALESCE(
                        NULLIF(p.program_status, ''),
                        NULLIF(u."Program-Status", '')
                    )) AS program_status,
                    NULL::date AS aptem_start_date,
                    NULL::date AS aptem_end_date,
                    NULL::numeric AS aptem_planned_hours
                FROM fetching_evidence.aptem_cv_contracts_probe p
                LEFT JOIN "LMS"."Aptem_users" u ON u."ID" = p.learner_id
                GROUP BY p.learner_id
                HAVING NOT BOOL_OR(
                    LOWER(TRIM(COALESCE(
                        NULLIF(p.current_programme, ''),
                        NULLIF(p.program_name, ''),
                        u."Program Name",
                        ''
                    ))) = 'project control professional level 6 - al fanar'
                )
                {missing_ilr_union}
            ),
            filtered_learner AS (
                SELECT learner.learner_id
                FROM learner
                {search_condition}
            )
            SELECT
                COUNT(document.id)::int AS documents,
                COUNT(DISTINCT filtered_learner.learner_id)::int AS learners,
                COUNT(*) FILTER (WHERE COALESCE(document.file, '') <> '')::int AS linked,
                COUNT(*) FILTER (
                    WHERE COALESCE(document.status, '') ILIKE '%%verified%%'
                       OR COALESCE(document.status, '') ILIKE '%%signed%%'
                )::int AS completed
            FROM fetching_evidence.aptem_cv_contracts_probe document
            RIGHT JOIN filtered_learner
                ON filtered_learner.learner_id = document.learner_id
            """,
            params,
        )
        summary = dict_fetchone(cursor)

    learners_by_id = {learner["learner_id"]: learner for learner in learners}
    for learner in learners:
        learner["documents"] = {column["key"]: [] for column in DOCUMENT_COLUMNS}

    for document in documents:
        learner = learners_by_id.get(document["learner_id"])
        key = document_column_key(document)
        if learner and key in learner["documents"]:
            learner["documents"][key].append(document)

    return {
        "rows": learners,
        "documentColumns": DOCUMENT_COLUMNS,
        "summary": summary,
        "pagination": {
            "page": safe_page,
            "pageSize": PAGE_SIZE,
            "total": total,
            "pages": max(math.ceil(total / PAGE_SIZE), 1),
        },
        "activeProgramStatus": normalized_program_status,
        "programStatuses": list_program_statuses(),
    }


def create_document(data):
    natural_key = f"MANUAL|{uuid.uuid4()}"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO fetching_evidence.aptem_cv_contracts_probe (
                document_category,
                source,
                learner_id,
                full_name,
                program_name,
                document_name,
                status,
                answer_text,
                file,
                raw,
                fetched_at,
                natural_key,
                email,
                current_programme,
                file_manually_edited,
                updated_to,
                updated_to_manually_edited
            )
            VALUES (
                %s, 'Manual', %s, %s, %s, %s, %s, '', %s, %s::jsonb,
                NOW(), %s, %s, %s, TRUE, %s, TRUE
            )
            RETURNING id::text
            """,
            [
                data["category"],
                data["learnerId"],
                data["fullName"],
                data["programName"],
                data["documentName"],
                data.get("status") or "Added manually",
                data["file"],
                json.dumps({"source": "documents-dashboard"}),
                natural_key,
                data.get("email") or None,
                data["programName"],
                data.get("updatedTo") or None,
            ],
        )
        return cursor.fetchone()[0]


def update_document(document_id, data):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE fetching_evidence.aptem_cv_contracts_probe
            SET file = %s,
                document_name = %s,
                document_category = %s,
                file_manually_edited = TRUE,
                updated_to = %s,
                updated_to_manually_edited = TRUE
            WHERE id = %s
            RETURNING id::text
            """,
            [
                data["file"],
                data["documentName"],
                data["category"],
                data.get("updatedTo") or None,
                document_id,
            ],
        )
        row = cursor.fetchone()
        return row[0] if row else None


def delete_document(document_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM fetching_evidence.aptem_cv_contracts_probe
            WHERE id = %s
            RETURNING id::text
            """,
            [document_id],
        )
        row = cursor.fetchone()
        return row[0] if row else None


def database_is_ready():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone()[0] == 1
