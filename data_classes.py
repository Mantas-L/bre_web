from dataclasses import dataclass, field
from typing import List
from datetime import datetime
import duckdb
from sentence_transformers import SentenceTransformer


@dataclass
class BRECard:
    card_id: str = field(default=None)
    text: str = field(default=None)
    title: str = field(default=None)
    author: str = field(default=None)
    yr: str = field(default=None)
    shelf_mark: str = field(default=None)
    drawer: str = field(default=None)
    drawer_id: str = field(default=None)
    tags: List[str] = field(default_factory=list)
    status: str = field(default=None)
    notes: str = field(default=None)
    created: datetime = field(default=None)
    updated: datetime = field(default=None)


@dataclass
class Segment:
    card_id: str = field(default=None)
    segment_id: str = field(default=None)
    text: str = field(default=None)
    # tags: List[str] = field(default_factory=list)
    status: str = field(default=None)



@dataclass
class RequestHeaders:
    page: int = field(default=1)
    query: str = field(default=None)


@dataclass
class SearchTable:
    total: int = field(default=None)
    start: int = field(default=None)
    end: int = field(default=None)
    current_page: int = field(default=1)
    total_pages: int = field(default=None)
    columns: str = field(default="id, title, author, drawer, tags, status, text")
    cards: List[BRECard] = field(default_factory=list)
    all_cards: List[BRECard] = field(default_factory=list)
    cards_per_page: int = field(default=100)
    model: SentenceTransformer = field(default=None)
    headers: RequestHeaders = field(default=None)

    def get_cards(self, con, headers):
        self.total = con.execute(""" SELECT COUNT(*) FROM cards """).fetchall()[0][0]

        self.total_pages = (self.total // self.cards_per_page + 1) + (
            0 if self.total % self.cards_per_page == 0 else 1
        )

        self.current_page = (
            headers.page if headers.page > 0 and headers.page <= self.total_pages else 1
        )

        self.end = self.cards_per_page * self.current_page
        self.start = self.end - self.cards_per_page

        if self.end > self.total:
            self.end = self.total

        self.cards = []
        results = con.execute(
            """
                    SELECT id, title, author, drawer, tags, status, text
                    FROM cards
                    ORDER BY last_update DESC
                    LIMIT ? OFFSET ?
                    """,
            (self.cards_per_page, self.start),
        ).fetchall()

        for r in results:
            card = BRECard(
                card_id=r[0],
                title=r[1],
                author=r[2],
                drawer=r[3],
                status=r[5],
                text=r[6],
            )
            self.cards.append(card)

    def get_next_page(self, full=False):
        p = self.current_page + 1
        if p >= self.total_pages:
            p = 1
        return f"/search?page={p}{'&full_send=False' if not full else ''}"

    def get_prev_page(self, full=False):
        p = self.current_page - 1
        if p < 1:
            p = self.total_pages - 1
        return f"/search?page={p}{'&full_send=False' if not full else ''}"

    def get_page(self, page_num, full=False):
        return f"/search?page={page_num}{'&full_send=False' if not full else ''}"

    def key_phrase_search(self, con, query):
        query = f"%{query}%"
        r = con.execute(
            """
        SELECT id, title, author, drawer, tags, status, text
        FROM cards
        WHERE text ILIKE ?
        LIMIT 200
        """,
            (query,),
        ).fetchall()

        return r

    # Full text search index for better querying the database using regular keywords
    def create_fts_index(self, con):
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
    def fts_search(self, con, query):
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

    def get_text_embedding_list(self, list_text: list[str]):
        """
        Return the list of normalized vector embeddings for list_text.
        """
        return model.encode(self, list_text, normalize_embeddings=True)

    def semantic_search_db_setup(self, con):
        con.create_function(
            "get_text_embedding_list",
            get_text_embedding_list,
            return_type="FLOAT[384][]",
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

    def semantic_search(self, con, query):
        con.create_function(
            "get_text_embedding_list",
            get_text_embedding_list,
            return_type="FLOAT[384][]",
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

    def search(self, con, headers):
        # if self.model == None:
        #     self.model = SentenceTransformer("all-MiniLM-L6-v2")

        if (
            self.headers != None
            and not headers.query == self.headers.query
            or self.headers == None
        ):
            self.all_cards = []
            kps = self.key_phrase_search(con, headers.query)

            for r in kps:
                card = BRECard(
                    card_id=r[0],
                    title=r[1],
                    author=r[2],
                    drawer=r[3],
                    status=r[5],
                    text=r[6],
                )
                self.all_cards.append(card)

            self.total = len(self.all_cards)

            self.total_pages = (self.total // self.cards_per_page + 1) + (
                0 if self.total % self.cards_per_page == 0 else 1
            )

        self.current_page = (
            headers.page if headers.page > 0 and headers.page <= self.total_pages else 1
        )

        self.end = self.cards_per_page * self.current_page
        self.start = self.end - self.cards_per_page

        if self.end > self.total:
            self.end = self.total

        self.cards = self.all_cards[self.start : self.end]


class SegmentTable:
    total: int = field(default=0)
    start: int = field(default=None)
    end: int = field(default=None)
    current_page: int = field(default=1)
    total_pages: int = field(default=None)
    columns: str = field(default="card_id, id, text, status")
    segments: List[Segment] = field(default_factory=list)
    segments_per_page: int = 100
    model: SentenceTransformer = field(default=None)
    headers: RequestHeaders = field(default=None)

    def get_segments(self, con, headers):
        if headers.query != None:
            self.total = con.execute(f" SELECT COUNT(*) FROM segments WHERE text ILIKE ?", (f"%{headers.query}%",)).fetchall()[0][0]
        else:
            self.total = con.execute(f" SELECT COUNT(*) FROM segments").fetchall()[0][0]

        self.headers = headers

        self.total_pages = (self.total // self.segments_per_page + 1) + (
            0 if self.total % self.segments_per_page == 0 else 1
        )

        self.current_page = (
            headers.page if headers.page > 0 and headers.page <= self.total_pages else 1
        )

        self.end = self.segments_per_page * self.current_page
        self.start = self.end - self.segments_per_page

        if self.end > self.total:
            self.end = self.total

        self.segments = []
        if headers.query != None:
            query = f"%{headers.query}%"
            results = con.execute(
            """
                    SELECT card_id, id, text, status
                    FROM segments
                    WHERE text ILIKE ?
                    LIMIT ? OFFSET ?
                    """,
            (query, self.segments_per_page, self.start),
        ).fetchall()
        else:
            results = con.execute(
                """
                        SELECT card_id, id, text, status
                        FROM segments
                        LIMIT ? OFFSET ?
                        """,
                (self.segments_per_page, self.start),
            ).fetchall()

        for r in results:
            segment = Segment(
                card_id=r[0],
                segment_id=r[1],
                text=r[2],
                status=r[3]
            )
            self.segments.append(segment)

    def get_next_page(self, full=False):
        query = f"query={self.headers.query}&" if self.headers.query != None else ''
        p = self.current_page + 1
        if p >= self.total_pages:
            p = 1
        return f"/segments?{query}page={p}{'&full_send=False' if not full else ''}"

    def get_prev_page(self, full=False):
        query = f"query={self.headers.query}&" if self.headers.query != None else ''
        p = self.current_page - 1
        if p < 1:
            p = self.total_pages - 1
        return f"/segments?{query}page={p}{'&full_send=False' if not full else ''}"

    def get_page(self, page_num, full=False):
        query = f"query={self.headers.query}&" if self.headers.query != None else ''
        return f"/segments?{query}page={page_num}{'&full_send=False' if not full else ''}"