from flask import Flask, Blueprint, render_template, jsonify, make_response, request
import cv2
import numpy as np
import re
import duckdb
import uuid
from dataclasses import dataclass
from data_classes import BRECard, SearchTable, RequestHeaders, Segment, SegmentTable


app = Blueprint("app", __name__)

state = {}


@app.route("/")
def home():
    global state
    return render_template("index.html")


@app.route("/search", methods=["GET"])
def browse():
    send_full = True if request.args.get("full_send", "True") == "True" else False
    if "SearchTable" not in state:
        state["SearchTable"] = SearchTable()

    page = int(request.args.get("page", 1))
    q = request.args.get("query", None)
    headers = RequestHeaders(page, q)
    con = duckdb.connect("data/bre_cards.duckdb")
    if q == None or q == "":
        state["SearchTable"].get_cards(con, headers)
    else:
        state["SearchTable"].search(con, headers)

    con.close()

    if send_full:
        return render_template("search.html", table=state["SearchTable"])
    else:
        return render_template("partials/search_table.html", table=state["SearchTable"])


@app.route("/segments", methods=["GET"])
def segments():
    send_full = True if request.args.get("full_send", "True") == "True" else False
    if "SegmentTable" not in state:
        state["SegmentTable"] = SegmentTable()

    page = int(request.args.get("page", 1))
    q = request.args.get("query", None)
    headers = RequestHeaders(page, q)
    con = duckdb.connect("data/bre_cards.duckdb")
    if q == None or q == "":
        state["SegmentTable"].get_segments(con, headers)
    # else:
    #     state["SegmentTable"].search(con, headers)

    con.close()

    if send_full:
        return render_template("segments.html", table=state["SegmentTable"])
    else:
        return render_template("partials/segment_table.html", table=state["SegmentTable"])


@app.route("/image/<image_id>")
def serve_image(image_id):
    image_path = f"data/img/{image_id}.png"

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

@app.route("/segimg/<image_id>")
def serve_seg_image(image_id):
    image_path = f"data/segments/{image_id}.png"

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