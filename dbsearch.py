import duckdb
import os
import json
from datetime import datetime
from typing import Optional, List
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")


def get_text_embedding_list(list_text: list[str]):
    """
    Return the list of normalized vector embeddings for list_text.
    """
    return model.encode(list_text, normalize_embeddings=True)


def key_phrase_search(con, query):
    query = f"%{query}%"
    r = con.execute(
        """
    SELECT id, title, author, drawer, tags, status, text
    FROM cards
    WHERE text ILIKE ?
    """,
        (query,),
    ).fetchall()

    return r


# Full text search index for better querying the database using regular keywords
def create_fts_index(con):
    english_stopwords_rel = con.read_csv(
        "https://raw.githubusercontent.com/stopwords-iso/stopwords-en/refs/heads/master/stopwords-en.txt",
        header=False,
    ).select("column0 as token")

    english_stopwords_rel.to_table("english_stopwords")

    con.execute(
        """
        PRAGMA create_fts_index(
            "cards",
            id,
            "text",
            stemmer = 'english',
            stopwords = 'english_stopwords',
            ignore = '(\\.|[^a-z])+',
            strip_accents = 1,
            lower = 1,
            overwrite = 1
        )
    """
    )


# Do a full text search on the database.
def fts_search(con, query):
    r = con.execute(
        """
        SELECT
            text,
            fts_main_cards.match_bm25(id, ?)::DECIMAL(3, 2) AS bm25_score
        FROM cards
        ORDER BY bm25_score DESC
        LIMIT 10
    """,
        (query,),
    ).fetchall()

    return r


def semantic_search_db_setup(con):
    con.create_function(
        "get_text_embedding_list", get_text_embedding_list, return_type="FLOAT[384][]"
    )

    # con.sql(
    #     """
    #     create table text_embeddings (
    #         id integer,
    #         text_embedding FLOAT[384]
    #     )
    # """
    # )

    num_batches = 400
    batch_size = 2101 // num_batches

    for i in range(num_batches):
        print(f"Processing Batch {i} of {num_batches}")
        selection_query = (
            con.table("cards")
            .order("id")
            .limit(batch_size, offset=batch_size * i)
            .select("*")
        )

    (
        selection_query.aggregate(
            """
            array_agg(text) as text_list,
            array_agg(id) as id_list,
            get_text_embedding_list(text_list) as text_emb_list
        """
        ).select(
            """
            unnest(id_list) as id,
            unnest(text_emb_list) as text_embedding
        """
        )
    ).insert_into("text_embeddings")


def semantic_search(con, query):
    con.create_function(
        "get_text_embedding_list", get_text_embedding_list, return_type="FLOAT[384][]"
    )

    r = con.execute(
        """
    WITH input_text_embedding AS (
        SELECT get_text_embedding_list([?])[1] AS input_text_embedding
    )
    SELECT ic.ocr_text, array_cosine_distance(te.text_embedding, ite.input_text_embedding)::DECIMAL(3,2) AS cosine_distance_score
    FROM cards ic
    JOIN text_embeddings te ON ic.id = te.id
    CROSS JOIN input_text_embedding ite
    ORDER BY cosine_distance_score ASC
    LIMIT 10
    """,
        (query,),
    ).fetchall()

    return r


def print_table(r):
    print("-" * tl)
    print(f"| {'Search Result ':<{l}} | Score |")
    print("-" * tl)
    for row in r:
        if len(row) < 2:
            s = "n/a"
        else:
            s = row[1]

        cleaned = "".join(c for c in row[0] if c.isprintable())
        cleaned = cleaned.replace("\n", "").replace("\t", "")
        print(f"| {cleaned:<{l}.{l-5}} | {s} |")

    print("-" * tl)
    print("\n")


if __name__ == "__main__":
    con = duckdb.connect("bre_cards.duckdb")
    # create_fts_index(con)
    # semantic_search_db_setup(con)

    q = "fire protection"

    kps = key_phrase_search(con, q)
    ftss = fts_search(con, q)
    ss = semantic_search(con, q)

    l = 180
    tl = l + len("| Score |") + 3

    # Key Phrase Search Example
    print(f"\nKey Phrase Search example, term: '{q}'\n")
    print_table(kps)

    print("=" * tl)

    # Full Text Search Example
    print(f"\nFull Text Search example, term: '{q}'\n")
    print_table(ftss)

    print("=" * tl)

    # Semantic Search Example
    print(f"\nSemantic Search example, term: '{q}'\n")
    print_table(ss)

    con.close()
