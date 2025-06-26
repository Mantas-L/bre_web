from flask import Flask, Blueprint, render_template, jsonify, make_response, request
import cv2
import numpy as np
import re
import duckdb
import uuid

app = Blueprint("app", __name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/browse")
def browse():
    con = duckdb.connect("website/data/bre_cards.duckdb")
    limit = 100
    offset = 0
    results = con.execute(
        """
        SELECT id, title, author, drawer, tags, status, ocr_text
        FROM index_cards
        ORDER BY pos ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()

    total = con.execute(""" SELECT COUNT(*) FROM index_cards """).fetchall()

    p = {}
    p["total"] = total[0][0]
    p["start"] = offset + 1
    p["end"] = offset + limit
    p["current_page"] = p["start"] // limit + 1
    p["total_pages"] = (p["total"] // limit + 1) + (
        0 if (p["total"] % limit == 0) else 1
    )

    con.close()

    return render_template("browse.html", results=results, p=p)


@app.route("/search", methods=["GET"])
def change_page():
    page = int(request.args.get("page", 1))
    con = duckdb.connect("website/data/bre_cards.duckdb")
    limit = 100
    offset = limit * (page - 1)

    total = con.execute(""" SELECT COUNT(*) FROM index_cards """).fetchall()[0][0]

    if offset < 0 or offset >= total:
        offset = 0

    p = {}
    p["total"] = total
    p["start"] = offset + 1
    p["end"] = offset + limit if (offset + limit < total) else total
    p["current_page"] = p["start"] // limit + 1
    p["total_pages"] = (p["total"] // limit + 1) + (
        0 if (p["total"] % limit == 0) else 1
    )

    results = con.execute(
        """
        SELECT id, title, author, drawer, tags, status, ocr_text
        FROM index_cards
        ORDER BY pos ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()

    con.close()

    return render_template("partials/table.html", results=results, p=p)


def parse_range(to_parse):
    start = 1
    end = 100
    return start, end


@app.route("/data")
@app.route("/data/<records>")
def get_data(records="1-100"):
    con = duckdb.connect("website/data/bre_cards.duckdb")
    limit = 100
    offset = 0
    results = con.execute(
        """
        SELECT id, title, author, drawer, tags, status, ocr_text
        FROM index_cards
        ORDER BY pos ASC
        LIMIT ? OFFSET ?
    """,
        (limit, offset),
    ).fetchall()

    data = []
    for row in results:
        r = {}
        r["image_id"] = row[0]
        r["title"] = row[1]
        r["author"] = row[2]
        r["drawer"] = row[3]
        r["tags"] = row[4]
        r["status"] = row[5]
        r["ocr_text"] = row[6]

        data.append(r)

    con.close()
    return jsonify(data)


# A placeholder function to get an image path from an ID
def get_image_path(image_id):
    con = duckdb.connect("website/data/bre_cards.duckdb")
    results = con.execute(
        """
        SELECT image_path
        FROM index_cards
        WHERE id=?
    """,
        (image_id,),
    ).fetchall()
    con.close()

    return f"website/{results[0][0]}.png"


@app.route("/image/<image_id>")
def serve_image(image_id):
    image_path = get_image_path(image_id)

    # Read the original image using OpenCV
    img = cv2.imread(image_path)

    # Encode the resized image to PNG format in memory
    _, img_encoded = cv2.imencode(".png", img)

    # Convert the encoded image to a byte string
    image_bytes = img_encoded.tobytes()

    # Create a Flask response with the image bytes
    response = make_response(image_bytes)
    response.headers.set("Content-Type", "image/png")

    return response
